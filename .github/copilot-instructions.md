# TrafficTwin repository instructions for coding agents

Current authoritative release: `main` at `337f1624e5ffe188393554b1110a35ababcce8e1`.

For ordinary code tasks, obey the repository's existing source/test conventions and start from current `main` unless the task explicitly specifies another reviewed base.

For architectural, multi-agent orchestration, integration, review-coordination, or campaign-resume work, read `AGENTS.md` and `CONTROLLER.md` first, then `docs/traffictwin_product_design_v3.md`, `docs/traffictwin_use_cases_v3.md`, and `docs/architecture_current_release.md`.

The old Dynamic/Expansion lane campaign is closed and merged. Historical lane prompts, v0.7/v0.8 handoffs, and receipts are evidence/history, not instructions to restart completed work.

Preserve exact-SHA trust: source-changing fixes create new SHAs; builders cannot self-approve; promotable source needs fresh independent read-only exact-SHA approval; reviewed histories are not rebased; `main` is never force-pushed.

Never infer scientific authorization from software readiness. E3 remains `E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED` with `evidence_state = NOT_EXECUTED`, `result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE`, and `research_workloads_launched = 0` until the owner explicitly changes the hold.

Keep vehicle mode choice separate from infrastructure RSU placement, waiting-room capacity separate from compute/service capacity, and simulated resource scaling separate from a real Kubernetes deployment. Preserve evidence/provenance/denominator/missingness truth in code, UI, tests, and docs.
