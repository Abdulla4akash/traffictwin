# Trace provenance appendix

The five source trace/occupancy pairs the dissertation's VEC work stands on, with the
identity, shape, and reconciliation evidence recorded for each. Every number below is copied
from a committed machine record; nothing here is retyped from memory or recomputed by hand.

**Appendix letter.** The write-up assigns the letter. The generated
[`appendix_b_software_versions.md`](appendix_b_software_versions.md) in this directory
currently carries `B`, so this table is referenced by name until the write-up fixes the
ordering.

**Sources.**

- Shapes, seeds, windows, hashes, and occupancy reconciliation:
  [`docs/reference/generated/vec_source_snapshot_audit.json`](../reference/generated/vec_source_snapshot_audit.json)
  — the Gate-A machine record.
- Identity-snapshot measurements for the admitted traces: the admission-probe evidence JSONs
  ([`inc`](../integration/evidence/vec_inc_trace_admission_probe_20260726.json),
  [`ev`](../integration/evidence/vec_ev_trace_admission_probe_20260727.json)).
- Scenario day, local window, and rationale: the producer's sidecar
  `traces/PROVENANCE.md` at upstream commit `6e56393` (read via blob-less peek; the pinned
  clones remain unfetched pending the R1 re-pin decision).

**Audited commits.** `tos-data` at `f6c67acbed3360dba3a0d5c8d1fd557caa99ecff`; `vec_env` at
`068b4ea33e640f206ce6a7d04f3d6fae2ac831f4`. Both were the origin `main` at audit time, and
the audit outcome is `accepted_with_scoped_blockers`.

**Rights boundary, carried from the audit record.** Permitted: sanitized samples, aggregates,
and dissertation use with both repositories cited. Not inferred: an open-source licence, raw
data redistribution, checkpoint redistribution, or blanket publication permission. Required
labels when those rows are used: engine `v2_post_nrsus_fix`, and `_s102` best-of-seeds.

## B.1 Trace inventory

| Trace file | Scenario day | Local window | SUMO seed | Trace steps (T) | Slots (maxN) | Gate-A sha256 (first 16) | Occupancy rows | Admission status |
|---|---|---|---:|---:|---:|---|---:|---|
| `traces/trace_we_fullrsu.npz` | weekend | 12:00–21:00 | 42 | 32,400 | 139 | `a2612865f5e1ef6d` | 13,249 | admitted (originally pinned) |
| `traces/trace_wd_am_fullrsu.npz` | weekday morning | 08:00–11:00 | 42 | 10,800 | 215 | `5e36a7cb8b49afa9` | 5,381 | **not admitted** |
| `traces/trace_wd_pm_fullrsu.npz` | weekday afternoon–evening | 14:00–21:00 | 42 | 25,200 | 163 | `848ba3cf278515f6` | 12,232 | **not admitted** |
| `traces/trace_inc_fullrsu.npz` | incident hour | 20:00–21:00 | 43 | 3,600 | 2,488 | `e188ce076b0d0001` | 5,307 | admitted (ADR-062) |
| `traces/trace_ev_fullrsu.npz` | event night | 17:30–24:00 | 42 | 23,400 | 175 | `70d6d12f3004b08c` | 9,130 | admitted (ADR-065) |

**How the window column was derived.** Each row's clock window is the trace's own recorded
first and last simulation seconds (seconds since local midnight) from the Gate-A record, and
each agrees exactly with the producer's window filename stored inside the `.npz` — for
example `fcd_ev_1730_2400.xml` against 63,000–86,399 s. The *local* basis is the producer's
declaration; this repository has not independently verified the timezone.

**Rationale column, and why it is not in the table.** Only two of the five rationales are
recorded anywhere in this repository, and inventing the other three for a dissertation
appendix would be fabricating provenance:

- `inc` — the modelled traffic-collapse hour; the densest resource-pressure window at 2,488
  concurrent slots (recorded in ADR-062 and the capacity-squeeze predeclaration).
- `ev` — the Champions League event night on the Manchester Etihad/Co-op Live event-district
  network (recorded in ADR-065 and the stadium event-study draft, both citing the sidecar).
- `we`, `wd_am`, `wd_pm` — **not restated here.** Read them from the cited sidecar at
  `6e56393` before the write-up quotes them; the pinned clones stay unfetched until the R1
  re-pin decision, so no agent has read those three rationales.

## B.2 Occupancy identity files

| Occupancy file | Gate-A sha256 (first 16) | Rows | Distinct vehicle ids | Inclusive visit-seconds | Ids ending at trace boundary |
|---|---|---:|---:|---:|---:|
| `occupancy/occupancy_we.csv` | `258cc3f39e3d8789` | 13,249 | 13,249 | 2,776,283 | 39 |
| `occupancy/occupancy_wd_am.csv` | `203172baab0785a5` | 5,381 | 5,377 | 1,166,439 | 95 |
| `occupancy/occupancy_wd_pm.csv` | `7f45a3e924a5f149` | 12,232 | 12,232 | 2,621,666 | 52 |
| `occupancy/occupancy_inc.csv` | `c4e59a7e43e51075` | 5,307 | 3,780 | 8,747,692 | 2,405 |
| `occupancy/occupancy_ev.csv` | `88a2ff15dd0612fe` | 9,130 | 9,129 | 1,898,428 | 35 |

All five pairs reconcile exactly in the Gate-A record: the occupancy spans reproduce the
trace mask (`exact_mask_match`), the inclusive visit-seconds equal the mask's true count
(`visit_seconds_match_mask`), and every pair records zero invalid spans, zero slot overlaps,
zero same-vehicle overlaps, and zero out-of-range slots or times.

The high boundary count for `inc` (2,405 of 3,780 vehicles still present at the trace
boundary) is a property of a one-hour window over a congested network, not a defect; the
Gate-A audit records the tripinfo join as `confirmed_with_incomplete_coverage` for exactly
this reason, and `inc` additionally has unmatched earlier exits.

## B.3 Identity-snapshot measurements for the admitted traces

The three admitted traces each had their vehicle identity snapshot rebuilt with the
production code path before use. These are joinability measurements, not execution timings,
reproduction grades, or scientific results.

| Trace | Measured on | T | maxN | Masked vehicle-seconds | Occupancy spans | Identity-snapshot fingerprint (first 16) | Build time (s) | Evidence |
|---|---|---:|---:|---:|---:|---|---:|---|
| `we` | Gate-A audit (19–24 Jul 2026) | 32,400 | 139 | 2,776,283 | 13,249 | not separately recorded | not recorded | Gate-A record |
| `inc` | 26 Jul 2026 | 3,600 | 2,488 | 8,747,692 | 5,307 | `fe60739ce99138de` | 1.14 | probe JSON |
| `ev` | 27 Jul 2026 | 23,400 | 175 | 1,898,428 | 9,130 | `2221bfac986aef04` | 1.51 | probe JSON |

**Why the `we` row differs, recorded rather than smoothed over.** The feature brief expected
three admission-probe evidence files. Only two exist. `we` was the originally pinned reviewed
trace, so admitting it required no allowlist extension and therefore produced no probe
document; its shape and reconciliation numbers come from the Gate-A record itself, and it has
no separately recorded identity-snapshot fingerprint or build time. Those two cells say so
rather than borrowing a number from a different trace.

`ev` additionally recorded 9,129 distinct vehicles with **zero** missing identity cells and
**zero** inactive identity cells. Both probes read their blobs at the audited `tos-data`
commit through the local pinned clone and confirmed the Gate-A hashes byte for byte; no fetch
touched the pinned clones.

## B.4 The two refused traces

`wd_am` and `wd_pm` carry **audit-table values only** in §B.1 and §B.2. They are Gate-A
audited, so their shapes and hashes are known, but they are outside VEC-07's reviewed-trace
allowlist: no admission probe has been run for either, no identity snapshot has been built,
and neither can pass preflight today. A test pins the allowlist to exactly the three admitted
identities so any growth is deliberate and carries its own decision record.

## B.5 Limitations this appendix carries

- Reconciliation proves the trace/occupancy identity is joinable. It is not an execution
  timing, a reproduction grade, or a scientific result.
- The scenario labels are the producer's, taken from window filenames and the cited sidecar.
  The informal "calm"/"stressed" classifications that appear elsewhere in the source material
  are untracked and are not used here.
- No `ev` execution has ever been timed. The 7,200-second VEC-07 request ceiling against the
  15,305.9-second historical source maximum remains an open measured risk and an escalation
  trigger, never a bound to raise.
- Admission enables no experiment by itself: any study on any of these traces still requires
  its own predeclaration and an approval-gated campaign.
- Label ceiling throughout: `owner_approved_candidate`. Nothing here is supervisor-approved
  or scientifically validated.
