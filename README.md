[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Yahous/gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Yahous/gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

# GTA VI launch-day Twitch forecast

`main.py` (Python 3.13, standard library only) forecasts how many people watch
Grand Theft Auto VI live on Twitch in each hour of its release day, 19 November
2026 (UTC), hours 2–24, as five quantiles each — after seeing only hour 1.

## The model

Every past big launch in the case's comparables is reduced to its release-day
hourly curve as log-ratios against its own hour-1 print. Launches whose day peaks
more than 15× their hour-1 print unlocked simultaneously around the world, so
their hour 1 was near-empty; they are left out, since GTA VI unlocks at midnight
local, country by country. For each forecast hour the median log-ratio and the
spread are kernel-weighted medians across the remaining launches, weighting each
launch by how close its hour-1 print is to this case's hour-1 print in log space
(Gaussian kernel, bandwidth 1.0): big launches already draw most of their audience
in hour 1 and stay flat, small ones build through the day. The median forecast for
hour h is hour1 × exp(median log-ratio_h); the five quantiles spread around it in
log space with the weighted interquartile spread of that hour's log-ratios
(floored at 0.15). The key insight the baseline misses: hour 1 covers 00:00–01:00
UTC, when only New Zealand, Australia, Asia and the UK have unlocked, so hour 1
is low relative to the peak — the forecast rises through the morning as the US
unlocks and peaks in the US evening, it does not sit at hour 1's level all day.

## Validation

Leave-one-out over the 29 midnight-local comparables, each scored against its own
release day with the other 28 as the pool: mean pinball loss **0.268**, typical
miss **50.2%**, 90% coverage **0.876** — against the house baseline's 0.394, 80.1%
and 0.711 on the same cases. The practice cases carry no answers in their files,
so they are checked for shape only. Two runs on the same input write byte-identical
outputs; a run takes about 0.06 s per case, far inside the 8 s limit.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Reads every `*.in` in the input directory and writes one `<id>.out` per case to
the output directory. Deterministic, no network, no randomness.
