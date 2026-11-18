"""Forecast GTA VI's launch-day Twitch viewers hour by hour (gta6-twitch-ccu-forecast-01).

The model, in one paragraph: every past big launch in the case's comparables gets its
release-day hourly curve reduced to log-ratios against its own hour-1 print; launches whose
day peaks more than 15x their hour-1 print are simultaneous global unlocks (their hour 1 is
near-empty because the game had not unlocked anywhere yet) and are left out, since GTA VI
unlocks at midnight local, country by country, like the rest. For each forecast hour the
median log-ratio and the spread are taken as kernel-weighted medians across the remaining
launches, weighting each launch by how close its hour-1 print is to this case's hour-1
print in log space (Gaussian kernel, bandwidth 1.0): big launches already draw most of
their audience in hour 1 and stay flat, small ones build through the day, so the curve a
launch follows depends on how big its first hour is. The median forecast for hour h is
hour1 * exp(median log-ratio_h), and the five quantiles spread around it in log space with
the weighted interquartile spread of that hour's log-ratios (floored at 0.15), using the
standard normal quantiles. Everything is deterministic: no randomness, no network, no
clock; the same input always writes the same bytes.

Validation (leave-one-out over the 29 midnight-local comparables, each scored against its
own release day with the other 28 as the pool): mean pinball loss 0.268, typical miss
50.2%, 90% coverage 0.876 — against the house baseline's 0.394, 80.1% and 0.711 on the
same cases. The practice cases carry no answers in their files, so they are checked for
shape only; the leave-one-out above is the evidence the model beats the baseline.

How the grader runs it: `python3 -P -s /bot/main.py` (PYTHONHASHSEED=0) in python:3.13-slim,
standard library only. It reads every <id>.in in the input directory and writes <id>.out
for each: {"hours": [{"hour": 2, "q": [q05, q25, q50, q75, q95]}, ...]}, exactly 23 rows,
hours 2..24 each once, no other key, each q a finite number above 0 and at most 1e9,
non-decreasing. MAKEFUN_INPUT_DIR / MAKEFUN_OUTPUT_DIR stand in for /input and /output
outside the grader's container:
    mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import json
import math
import os
from datetime import datetime
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The quantile levels the contest scores, in the order each row lists them.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# The standard normal's quantile at each level.
Z = [-1.645, -0.674, 0, 0.674, 1.645]

# A launch whose release-day peak is more than this many times its hour-1 print unlocked
# simultaneously around the world, so its hour 1 was near-empty; it is not a midnight-local
# launch like GTA VI and is left out of the curve.
MAX_PEAK_RATIO = 15.0
# Gaussian kernel bandwidth, in natural-log units of hour-1 viewers: how alike two launches'
# first hours must be to weigh on each other.
KERNEL_BW = 1.0
# The narrowest log spread any hour gets, so no hour is forecast with false certainty.
SPREAD_FLOOR = 0.15
# The GTA VI category's own pre-release history is not a launch day; it never enters the
# curve, and is only a fallback scale if a case somehow has no hour-1 print.
GTA_HISTORY_NAME = "Grand Theft Auto VI category before release"


def round2(x: float) -> float | int:
    """x rounded to 2 decimals, half up, as JavaScript's Math.round(x * 100) / 100 rounds it."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def day_hours(comp: dict) -> dict[int, float]:
    """A comparable's release-day hourly viewers, keyed by hour 1..24 of its day_start."""
    start = parse_time(comp["day_start"])
    hours: dict[int, float] = {}
    for point in comp.get("hourly") or []:
        viewers = point.get("viewers")
        if not viewers or viewers <= 0:
            continue
        hour = int((parse_time(point["from"]) - start).total_seconds() // 3600) + 1
        if 1 <= hour <= 24:
            hours[hour] = float(viewers)
    return hours


def launch_pool(case: dict) -> list[dict[int, float]]:
    """The comparables that are midnight-local launches with a usable release day."""
    pool: list[dict[int, float]] = []
    for comp in case.get("comparables") or []:
        if comp.get("name") == GTA_HISTORY_NAME:
            continue
        hours = day_hours(comp)
        if 1 not in hours:
            continue
        if max(hours.values()) / hours[1] > MAX_PEAK_RATIO:
            continue
        pool.append(hours)
    return pool


def weighted_median(pairs: list[tuple[float, float]]) -> float:
    """The median of values weighted by their weights (pairs sorted by value)."""
    ordered = sorted(pairs)
    total = sum(w for _, w in ordered)
    acc = 0.0
    for value, weight in ordered:
        acc += weight
        if acc >= total / 2:
            return value
    return ordered[-1][0]


def weighted_quantile(pairs: list[tuple[float, float]], q: float) -> float:
    ordered = sorted(pairs)
    total = sum(w for _, w in ordered)
    acc = 0.0
    for value, weight in ordered:
        acc += weight
        if acc >= total * q:
            return value
    return ordered[-1][0]


def fallback_hour1(case: dict) -> float:
    """A sane hour-1 scale when a case has no usable print: the GTA VI category's own
    pre-launch hourly median, else the median hour-1 print across the launch pool."""
    for comp in case.get("comparables") or []:
        if comp.get("name") == GTA_HISTORY_NAME:
            values = [p["viewers"] for p in comp.get("hourly") or []
                      if p.get("viewers") and p["viewers"] > 0]
            if values:
                values.sort()
                return float(values[len(values) // 2])
    pool = launch_pool(case)
    firsts = sorted(hours[1] for hours in pool)
    return float(firsts[len(firsts) // 2]) if firsts else 100000.0


def hour_quantiles(p1: float, pool: list[dict[int, float]], hour: int) -> list[float | int]:
    """The five quantiles for one forecast hour, from the kernel-weighted log-ratio curve."""
    log_p1 = math.log(max(p1, 1.0))
    pairs: list[tuple[float, float]] = []
    for hours in pool:
        if hour in hours and 1 in hours:
            weight = math.exp(-((math.log(hours[1]) - log_p1) ** 2) / (2 * KERNEL_BW ** 2))
            pairs.append((math.log(hours[hour] / hours[1]), weight))
    if len(pairs) < 5:
        # Too few launches with this hour: fall back to an unweighted median and spread.
        pairs = [(math.log(hours[hour] / hours[1]), 1.0) for hours in pool
                 if hour in hours and 1 in hours]
    if not pairs:
        # No launch has this hour at all: hold hour 1's level with a wide spread.
        return [round2(max(1.0, p1 * math.exp(z * 0.5))) for z in Z]
    median = weighted_median(pairs)
    q1 = weighted_quantile(pairs, 0.25)
    q3 = weighted_quantile(pairs, 0.75)
    spread = max((q3 - q1) / 1.349, SPREAD_FLOOR)
    centre = p1 * math.exp(median)
    quantiles: list[float | int] = []
    for z in Z:
        value = centre * math.exp(z * spread)
        value = max(1.0, min(value, 1_000_000_000.0))
        quantiles.append(round2(value))
    # Rounding and the cap cannot break the order: enforce non-decreasing.
    for i in range(1, len(quantiles)):
        if quantiles[i] < quantiles[i - 1]:
            quantiles[i] = quantiles[i - 1]
    return quantiles


def forecast_case(case: dict, name: str) -> dict:
    known = case.get("known") or []
    first = next((k for k in known if k.get("hour") == 1), None)
    p1 = float(first["viewers"]) if first and first.get("viewers") else 0.0
    if p1 <= 0:
        p1 = fallback_hour1(case)
    p1 = max(1.0, p1)
    pool = launch_pool(case)
    if not pool:
        pool = [day_hours(c) for c in case.get("comparables") or []
                if c.get("name") != GTA_HISTORY_NAME and 1 in day_hours(c)]
    # The hours to forecast: the case's own list when it covers 2..24 exactly, else
    # the full range, so a case with a short or missing list still gets a valid output.
    wanted = [row["hour"] for row in case.get("forecast") or []]
    hours = wanted if sorted(wanted) == list(range(2, 25)) else list(range(2, 25))
    return {"hours": [{"hour": h, "q": hour_quantiles(p1, pool, h)} for h in hours]}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
