# Codex coding brief — the GPU training track (start now)

Owner decision, 27 July 2026 (recorded verbatim intent): **the full research-directions-v2
programme is in scope for delivery by 4 September** — Tier A local experiments AND the
Tier B GPU track — using owner Colab compute units now and CSF when access lands. Codex
is the lead for the GPU-track build-out. This brief is the coding mandate; the primary
integration session continues the local experiment/confirmatory line in parallel.

## Mission

Build everything needed so that, the moment permissions/access land, these two training
experiments RUN with zero further engineering:

1. **B-CAP: capacity-aware retraining** — fine-tune/retrain the MAPPO actor with the
   producer's capacity-scalar observation variant, capacity randomised across the pilot's
   grid {2.5, 1.5, 1.0, 0.75}, trace-replay training.
2. **B-BUS: bus-native training** — trace-replay training on the derived real-bus-fleet
   trace (B1 chain output) once the peak session and G-signing land.

Plus the evaluation homecoming: trained checkpoints return to this machine and are
compared against the two audited actors through the EXISTING instrument (campaigns,
admission, STA-02 per-algorithm ranking, slope comparison).

## Hard gates (these make the results count — never route around them)

- **Producer assets on third-party cloud need his recorded written permission.** Until
  the owner forwards Randy's written OK: build and dry-run everything with synthetic
  stand-ins on Colab; the real `vec_env`/`tos-data` content runs only locally or on CSF.
  Track the permission state in the run-readiness checklist below, never assume it.
- **Our bus artifacts**: derived/pseudonymised only ever leave the machine; raw
  quarantine snapshots never do; note the open BODS retention question (BETA-B-01).
- **A returned checkpoint is not evidence.** New actors enter evaluation only through a
  reviewed extension of the pinned-actor set (the ADR-062/065 pattern: record identity
  hashes + provenance, extend `PINNED_ACTORS` with tests pinning the count) and their
  runs only become scientific through fresh-run admission. Training metrics (reward
  curves) are diagnostics, never results.
- **Every experiment gets its own predeclaration** before results are looked at —
  training hyperparameters, seeds, the evaluation design, and the publishable null.
- Standing repo rules unchanged: never fetch the pinned external clones (clone fresh
  copies for cloud packaging from the university remote instead); never touch
  main/tags/byte-frozen files; AGENTS.md claims before editing; full gates per slice.

## What to build (suggested order; Codex owns the decomposition)

1. **Training job harness** — `gpu/` (new top-level dir or `scripts/gpu-track/`):
   parameterised launchers for the producer's `jaxmarl/scripts/train_mappo_vec.py` with
   the 2B_2 variant knobs (capacity-scalar obs, trace-replay source, fleet distribution),
   the `--init-actor` warm-start path, seed discipline, and deterministic run manifests
   (config fingerprint, env commit, dataset hashes) — as BOTH a Colab notebook/driver and
   a CSF SLURM script (his `slurm/` dir is the template). Dry-runnable with a tiny
   synthetic trace so the harness is proven before any permission lands.
2. **Checkpoint homecoming** — import tooling: verify a returned actor npz (hash,
   manifest, training-run identity), store under a provenance record, and generate the
   pinned-actor extension proposal (docs + code + tests) for review. The CSF job-pack
   contract (`vec_campaign/job_pack.py` + `scripts/vec_job_pack.py`) is the transport for
   evaluation campaigns; extend only via new files.
3. **Derived-trace packaging for B-BUS** — bundle the B1 chain output (bus_trajectory →
   bus_vec_bridge) into a training-ready replay input with the same manifest discipline;
   blocked on the peak session data, so build against synthetic session fixtures.
4. **Predeclaration drafts** — B-CAP and B-BUS training+evaluation predeclarations in
   the house structural-draft style (FILL-AT-SIGNING, empty sign-off), plus the A1
   three-trace-grid predeclaration so the local track can launch the moment the
   confirmatory is analysed.
5. **Run-readiness checklist** — one committed page tracking the real-world gates:
   Randy permission (Colab), CSF account, compute-unit budget, peak session done,
   G1–G5 signed, ev timing probe measured.

## Coordination

- Record Codex lead-ownership sections in AGENTS.md for each slice; the primary session
  is at Phase 80+; parallel feature batches own 40–71. File claims stay disjoint —
  everything above is NEW files except the reviewed `PINNED_ACTORS` extension, which goes
  through the proposal-then-extend pattern with its own record.
- The detached confirmatory campaign finishes ~00:35 tonight; until the receipt exists,
  no heavy local compute. Cloud-side work is unaffected.
- The primary session will handle: tonight's confirmatory analysis + results record, the
  branch-merge handoff (separate document), and the Tier A predeclaration signings relay.

Deadline framing: training jobs are GPU-days — B-CAP should be ON compute by the first
week of August to leave evaluation + writing headroom before 4 September. The rubric
deliverables (report, video, user evaluation) remain owner-track and untouched by this
brief.
