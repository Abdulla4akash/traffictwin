# TrafficTwin

TrafficTwin is a modular, import-first research software platform for reproducible urban traffic and vehicular edge-computing what-if experiments.

Current scope: Phase 4 import-first library plus Streamlit UI slice. The project can validate synthetic run bundles, canonicalise them in memory, compute deterministic metrics, build evidence packs, compare baseline-versus-variation runs, and present the workflow in a restrained research UI. No SUMO adapter, Randy VEC adapter, diagnostic rules, live data, or external launch integration is implemented yet.

## Quick Start

Use Python 3.11 or newer.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Validate the example seed:

```bash
traffictwin validate-seed examples/seeds/arena_gridlock.yaml
```

Normalise a seed to deterministic YAML:

```bash
traffictwin normalise-seed examples/seeds/arena_gridlock.yaml /tmp/arena_gridlock.normalised.yaml
```

Show the default export/import capability manifest:

```bash
traffictwin capabilities
```

Create and inspect a registry:

```bash
traffictwin registry init data/registry/traffictwin.sqlite
traffictwin registry inspect data/registry/traffictwin.sqlite
```

Validate a run bundle:

```bash
traffictwin bundle validate tests/fixtures/bundles/baseline_valid
```

Inspect a bundle without registry mutation:

```bash
traffictwin bundle inspect tests/fixtures/bundles/partial_valid
```

Import an accepted bundle into the registry:

```bash
traffictwin bundle import tests/fixtures/bundles/baseline_valid --registry data/registry/traffictwin.sqlite
```

Export a machine-readable validation report:

```bash
traffictwin bundle report tests/fixtures/bundles/partial_valid --format json
```

Compute deterministic metrics:

```bash
traffictwin metrics compute tests/fixtures/bundles/baseline_valid
traffictwin metrics report tests/fixtures/bundles/variation_valid --format json
```

Compare baseline and variation bundles:

```bash
traffictwin compare tests/fixtures/bundles/baseline_valid tests/fixtures/bundles/variation_valid
```

Build an evidence pack for future deterministic rules:

```bash
traffictwin evidence build tests/fixtures/bundles/baseline_valid --output /tmp/baseline-evidence.json
```

Launch the Streamlit UI:

```bash
streamlit run src/traffictwin/ui/app.py
```

Demo fixture paths:

```text
tests/fixtures/bundles/baseline_valid
tests/fixtures/bundles/variation_valid
tests/fixtures/bundles/partial_valid
```

## Screenshots

Screenshot placeholders are reserved for the dissertation write-up after Phase 4 visual review:

- Home / Project Status
- Bundle Import & Validation
- Run Overview
- What-if Compare
- Evidence & Diagnostic Readiness

## Data-Mode Disclaimer

Any examples in this repository are synthetic or structural unless explicitly documented otherwise. The project does not currently include Randy's environment, SUMO networks, Manchester sensor data, or live feeds.

## Current Limitations

- No SUMO/VEC adapter or external launcher.
- No live, near-live, or simulated-stream ingestion.
- No deterministic diagnostic rules R1-R3 yet.
- Energy, drop-cause, vehicle-tier, and capacity-normalised load metrics are unavailable unless source fields are declared and valid.
