# Experiments

Run automated matches using:

```bash
python -m twgbg.experiments.run twgbg/puzzles/preset_games/sample_pair.json --rounds 5 --depth 3
```

The script outputs a CSV with columns `win_rate`, `avg_rounds`, and `runtime`.
Use the **Experiments** tab to trigger the same routine from the GUI and review
results inline.
