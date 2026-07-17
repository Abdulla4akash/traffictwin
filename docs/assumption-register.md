# TrafficTwin Assumption Register

Statuses:

- `confirmed`: directly evidenced in the current repository or user brief.
- `inferred`: reasonable working interpretation, but not directly proven.
- `unknown`: not evidenced.
- `contradicted`: existing evidence conflicts with another instruction or assumption.

| Assumption | Evidence | Status | Affected feature | Fallback behaviour |
|---|---|---|---|---|
| `diss/` is the TrafficTwin project root. | Abdulla explicitly confirmed `diss/` as the permanent TrafficTwin project root before Phase 1. | confirmed | File layout, docs, Phase 1 scaffold | Keep all new TrafficTwin files inside `diss/`. |
| The complete v0.4 design has been supplied locally. | The original `diss/AGENTS.md` contained `TrafficTwin - Design Proposal (v0.4)` and was read completely before relocation. | confirmed | Phase 0 planning | Use `docs/traffictwin-design-v0_4.md` as the canonical design source. |
| The canonical design path exists. | The design was copied exactly to `diss/docs/traffictwin-design-v0_4.md`. | confirmed | Agent discovery, documentation traceability | Require agents to read the canonical spec before architectural work. |
| No existing TrafficTwin implementation exists. | Repository file inventory contains no `traffictwin/`, package config, tests, or app files. | confirmed | Phase 1 scaffold | Start with a new package scaffold. |
| No real data is available in the workspace. | No CSV, YAML bundle, SUMO, Parquet, SQLite, or notebook files were found. | confirmed | Adapters, metrics, validation | Build synthetic fixtures and import-first architecture first. |
| Randy's environment is available locally. | No VEC/SUMO environment files, scripts, configs, or checkpoints were found. | contradicted | Launcher, adapters, capability manifest | Mark direct launch unavailable and capabilities unknown. |
| Direct launch is supported. | No CLI/API/script contract is present. | unknown | Scenario Studio run button, launcher | Export seed only; hide or disable direct run. |
| Randy's CSV schema is known. | No sample Randy files or schema documentation are present. | unknown | Generic CSV adapter, validation, canonicalisation | Implement only documented generic CSV contract and synthetic fixture schema. |
| SUMO trip records will be available. | Design mentions SUMO trip output as assumed; repo has no SUMO files. | unknown | Journey-Time Lens | Mark trip metrics unavailable unless `trips.csv` is present and valid. |
| Per-RSU queue and utilisation are exported over time. | Design notes queue state may exist but export is unconfirmed. | unknown | Infrastructure metrics, R2 | Compute infrastructure metrics only from valid `infra_state.csv`; otherwise return unavailable. |
| Energy per completed task is available. | Design marks energy logging as assumed/unconfirmed. | unknown | Energy metrics | Do not compute energy metrics unless the column and unit are declared. |
| Task decisions include local, V2I, and V2V. | User brief defines these allowed decisions; Randy's concrete labels are not evidenced. | inferred | Seed schema, validation, metrics | Use these labels in synthetic and generic contracts; adapter maps real labels later. |
| Unknown fields should remain absent or null. | User brief explicitly requires absent fields not be fabricated. | confirmed | Canonical models, validation, metrics | Preserve nulls; mark dependent metrics unavailable. |
| Deterministic code must compute all metrics. | User brief states numbers come from deterministic code. | confirmed | Metrics engine, rules, UI | Keep LLM out of metric and diagnosis computation. |
| Diagnostic outputs are hypotheses, not proven causes. | User brief and design both require softened causal claims. | confirmed | Rules engine and UI copy | Use `hypothesis` language and include alternatives/missing evidence. |
| Earlier XITS instruction says not to lock design before `MATERIALS COMPLETE`. | `XITS/README.md` and `XITS/research_context.md` contain that gate, but Abdulla explicitly superseded it for implementation purposes with the approved TrafficTwin v0.4 specification. | contradicted | Planning authority | Preserve XITS as historical research material, not an active implementation blocker. |
| The first vertical slice should be synthetic. | No real data or simulator exists locally; user permits synthetic fixtures if no real data exists. | confirmed | Phase 1-4 planning | Build synthetic baseline/variation demonstration and label it synthetic. |
| SQLite is sufficient for Phase 1 registries. | User says SQLite is acceptable if simpler; no data volume evidence exists. | inferred | Metadata registry | Use SQLite for metadata first; defer DuckDB/Parquet until run volume justifies it. |
| Streamlit is the first UI. | User explicitly lists Streamlit as preferred. | confirmed | Phase 4 UI | Keep UI thin over tested library services. |
| FastAPI, React, queues, and cloud infrastructure are out of scope. | User explicitly excludes them unless demonstrated requirement exists. | confirmed | Architecture | Do not add these in the protected vertical slice. |
| The package should target Python 3.11+. | User explicitly specifies Python 3.11+. | confirmed | Packaging and typing | Configure package metadata for Python 3.11 or newer. |
| The local quality-gate interpreter is Python 3.12. | `/opt/homebrew/bin/python3.12` is available; system `python3` is 3.9.6. | confirmed | Tooling, tests | Use Python 3.12 for local validation and declare Python 3.11+ support in packaging. |
