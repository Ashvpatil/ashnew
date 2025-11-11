# Running Experiments

The `twgbg.experiments.run` module allows you to collect reproducible statistics
for different engine settings. Example command:

```
python -m twgbg.experiments.run --games 50 --mode hybrid --depth 4 --iter_ms 900 \
    --rollouts 1200 --playout 32 --c_puct 1.414 --csv results.csv --seed 1
```

The script prints mean, standard deviation, minimum and maximum of the collected
metric and writes per-game results into the specified CSV file. You can combine
this data with the templates in `docs/REPORT_TEMPLATE.md` for write-ups.
