# Parallel-agent master prompt — batch 3 (27 July 2026)

Successor to batches 1 (Phases 40–45) and 2 (Phases 46–50), both shipped and independently
verified. Paste into a fresh agent session started from `~/AntigravityTest/diss-integration`:

```text
You are a parallel feature-building agent for TrafficTwin v0.7, batch 3. The canonical copy
of this brief is committed at repo root as PARALLEL_FEATURES_MASTER_PROMPT_3.md — read it
first; it governs over this paste. Same branch (`claude/complete-v0.7`) as an active
primary session: build ONLY the features below, ONLY in the exact files each names,
re-verify `git status` + `git log -1` before EVERY edit and commit, `git pull --ff-only`
when HEAD moved.

FIRST ACTIONS — VERIFY
1. Read AGENTS.md §"v0.7 Work Coordination": Phases 14–39 (primary) and 40–50 (batches 1–2)
   are FORBIDDEN files unless a feature below grants a named touchpoint. Your claims start
   at Phase 51.
2. Read PARALLEL_FEATURES_MASTER_PROMPT.md — its boundaries, gotchas, gates, and stop
   conditions apply verbatim, including: no multi-core/long compute while the held-out
   campaign runs (until ~23:30 local 27 Jul; single-process pytest fine); never edit
   docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md (byte-frozen by a
   live approval digest); external clones are never fetched; main/tags/changelog/cli.py/
   manifests untouched.
3. ONE CARVE-OUT changes from earlier batches: you MAY READ (never write, never delete)
   the completed pilot's local analysis artifacts at
   data/vec-fresh/capacity-pilot/campaign_analysis.json — Features 12 and 15 consume it.
   Everything else under data/vec-fresh/** stays completely untouched, ESPECIALLY
   data/vec-fresh/capacity-confirmatory/** (live campaign) and every .demo/registry-*.
4. Expected start state: clean tree at `d65dae5` or later, in sync with origin.

GATES per feature (unchanged): focused tests, all tests/unit, tests/ui when UI changed,
uv run ruff check src tests scripts, format check on touched files, uv run mypy src tests,
git diff --check. One feature = one AGENTS.md Phase claim = one commit series, pushed
immediately.

THE FEATURES — in order, each independently shippable

FEATURE 12 (Phase 51) — Capacity-study research figures through the ACCEPTED export machinery
  Goal: dissertation-ready static figures for the capacity study, generated ONLY through
  the accepted LaTeX/research-figure machinery in src/traffictwin/reporting/latex.py
  (read its public models first; do not modify it): (a) per-seed mean-latency versus
  capacity curves (one line per fleet seed, four capacity points), (b) deadline-success
  flatness chart (same axes structure, y-range chosen to show the ~0.79 band honestly —
  include a zero-anchored companion or state the zoom in the caption data), (c) a tex/SVG
  table of the offload-rate invariance (per-seed values identical across arms).
  Input: an analysis-JSON path argument — no default; the committed pilot values come from
  the carve-out path above. Every figure carries "exploratory, owner_approved_candidate,
  descriptive non-causal" in its rendered text. Outputs committed under
  docs/dissertation_appendices/figures/ with a provenance note (design fingerprint,
  source-JSON identity) beside them.
  New files ONLY: scripts/generate_capacity_figures.py,
  tests/unit/test_capacity_figures_script.py (tmp_path fixtures, structure assertions),
  docs/dissertation_appendices/figures/* (generated), one docs/index.md row.

FEATURE 13 (Phase 52) — User-evaluation instrument draft (docs only, PROPOSED)
  Goal: the survey instrument the ethics application references, drafted so submission is
  attach-and-send: participant information sheet skeleton (aligned to the ethics draft's
  PROPOSED values: survey not interview, no recording, anonymised, degree+12mo retention,
  14-day withdrawal), consent checklist, the task walkthrough (guided demo → RSU Monitor →
  provenance trace → match review decide/seal), and the questionnaire: 8–12 Likert items +
  3 free-text, with at least two explainability items ("did the provenance/diagnostics
  help you understand WHY the policy behaved as it did?" and an RSU-overwhelm insight
  item), plus standard usability items. Status header: PROPOSED, unsigned, values confirmed
  by a person at ethics submission; an agent never fabricates responses or approval.
  New files ONLY: docs/evaluation/user_evaluation_instrument_draft.md + docs/index.md row.

FEATURE 14 (Phase 53) — Bus-session post-session report script
  Goal: after tomorrow's attended peak session, one command turns the workspace's session
  artifacts into the numbers the B1 draft needs: cadence percentiles, hourly progression
  aggregates, active-vehicle counts, and a clearly-labelled "B1 FILL-FROM-PROBE candidate
  values" block. Composes the ACCEPTED modules read-only —
  traffictwin.integration.manchester.bods_session_identity and bus_profile_comparison,
  imported by FULL module path (the package __init__ is lead-claimed) — over an explicit
  workspace-path argument; aggregates only; raw refs and tokens never printed; no
  acquisition, no API key, no network.
  New files ONLY: scripts/bus_session_report.py,
  tests/unit/test_bus_session_report_script.py (synthetic workspace fixtures — reuse the
  recipes in tests/unit/test_bods_session_identity.py).

FEATURE 15 (Phase 54) — Mechanism-report CLI + the committed pilot exhibit
  Goal: (a) scripts/render_mechanism_report.py — renders batch 1's
  vec_campaign/mechanism_report.py output from an analysis-JSON path to an output path,
  both required arguments, no defaults; (b) run it once against the pilot carve-out JSON
  and COMMIT the rendered exhibit as
  docs/evaluation/capacity_pilot_mechanism_report_20260727.md with a header stating source
  identity (design fingerprint de474e03…), exploratory status, and the corrected
  range-overlap wording (within-seed ordering strict, pooled ranges overlap — see the
  corrected results record; do not reintroduce the old sentence).
  New files ONLY: the script, tests/unit/test_render_mechanism_report_script.py, the
  committed exhibit document, one docs/index.md row.

FEATURE 16 (Phase 55) — Dissertation appendices: objectives traceability + abbreviations
  Goal: (a) docs/dissertation_appendices/objectives_traceability.md — the O1–O7 spine
  table (objective → status today → evidence artifacts with repo paths → dissertation
  section that will cite it), honest statuses only (e.g. O7 user-evaluation = pending
  ethics; confirmatory = in execution); (b)
  docs/dissertation_appendices/abbreviations.md — the abbreviation list seeded from the
  skeleton (VEC, RSU, DRL, MARL, MAPPO, IPPO, DQN, DDQN, SUMO, FCD, TOS, V2I, V2V, V2X,
  ITS, ADR, CSF) extended with house terms actually used in the docs (BODS, DfT, STA-01…05,
  VEC-01…12, GEH, OSM, AppTest) — each with a one-line expansion.
  New files ONLY: those two documents + their docs/index.md rows.

STOP CONDITIONS and end-report format: batch 1's, unchanged. Leave the changelog, week-4
checklist, and every capacity_* evaluation document alone (the mechanism exhibit in
Feature 15 is a NEW file and is the one exception by name).
```

Batch-3 claims run Phase 51–55; the primary session owns numbers below 40 and the
reconciliation passes.
