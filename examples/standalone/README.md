# Standalone TrafficTwin Example

This example uses only repository-contained synthetic generation.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
traffictwin demo initialise .demo
traffictwin demo status .demo
traffictwin compare .demo/bundles/baseline .demo/bundles/stressed_demand
traffictwin diagnose bundle .demo/bundles/under_offloading
traffictwin provenance metric .demo/bundles/baseline task.completion.rate
traffictwin report full .demo/bundles/stressed_demand \
  --comparison-baseline .demo/bundles/baseline \
  --output .demo/reports/stressed_full.html
traffictwin demo launch .demo
```

All generated outputs are synthetic software demonstration artifacts.
