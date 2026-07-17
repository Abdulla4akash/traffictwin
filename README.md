# TrafficTwin

TrafficTwin is a modular, import-first research software platform for reproducible urban traffic and vehicular edge-computing what-if experiments.

Current scope: Phase 1 core library only. No SUMO adapter, Randy VEC adapter, Streamlit UI, metrics engine, diagnostic rules, live data, or external launch integration is implemented yet.

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

## Data-Mode Disclaimer

Any examples in this repository are synthetic or structural unless explicitly documented otherwise. The project does not currently include Randy's environment, SUMO networks, Manchester sensor data, or live feeds.

## Current Limitations

- No metrics engine yet.
- No dashboard or Streamlit UI yet.
- No SUMO/VEC adapter or external launcher.
- No live, near-live, or simulated-stream ingestion.
