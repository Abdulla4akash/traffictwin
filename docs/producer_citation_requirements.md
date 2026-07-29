# Producer citation requirements — what every published artifact must carry

**Why this exists.** The producer's permission covers code, data and publication **with
citation**. Citation is therefore not a courtesy here, it is the condition the permission is
granted under, and it now binds *more* output than before: every capacity number in the
dissertation is producer-derived. See
[the permission record](integration/randy_data_and_publication_permission_20260729.md).

**Verify every bibliographic detail against the source before submission.** The supervisor's
stated standard is explicit that citation failures put the degree at risk, and the entries below
are assembled from the repository and local files rather than from a bibliographic database.
Treat them as a checklist of *what must be cited*, not as pre-verified reference strings.

## 1. The mandatory set

Every artifact that uses producer code, producer data, or numbers derived from either:

| Item | Value |
|---|---|
| Environment repository | `gitlab.cs.man.ac.uk/e62992rp/vec_env` |
| Environment pinned commit | `068b4ea33e640f206ce6a7d04f3d6fae2ac831f4` |
| Trace/data repository | `gitlab.cs.man.ac.uk/e62992rp/tos-data` |
| Trace/data audited commit | `f6c67acbed3360dba3a0d5c8d1fd557caa99ecff` |
| Engine / environment version | `v2_post_nrsus_fix` |
| Author | Randy Prasetia Putra, University of Manchester |

Both commits were verified read-only against the pinned clones when this document was written;
the clones are never fetched.

## 2. The Year-1 report

Cited wherever its findings are discussed — in particular the distribution-shift and
reward-misalignment results, which this project's capacity-invariance finding directly echoes.

> Putra, R. P. *Intelligent Task Offloading: Current State Limitations and Proposed Potential
> Solutions.* Year-1 PhD report, University of Manchester. Supervisor: Dr Sandra Sampaio;
> co-supervisor: Prof. Rizos Sakellariou.

**The PDF itself is private.** It sits untracked at `~/AntigravityTest/diss/` and must never be
committed to this repository or redistributed. Cite it; do not reproduce it.

## 3. SUMO

The supervisor named SUMO explicitly as a required citation. Traces were generated with **SUMO
1.27.0**; the Manchester network build in this project used **SUMO 1.27.1** (`netconvert`).
The standard reference is Lopez et al., *Microscopic Traffic Simulation using SUMO*, IEEE ITSC
2018 — **verify authors, venue and year against the paper before use.**

## 4. Per-trace provenance — get the scope right

From the producer's own `traces/PROVENANCE.md`. The single most important correction: the
network is the Manchester **Etihad / Co-op Live event district**, **not** city-wide. Any wording
implying a city-scale digital twin of Manchester traffic in the VEC experiments is wrong.

| Trace | Scenario | sha256 (prefix) |
|---|---|---|
| `we` | Sun 2024-09-15, zero-event weekend, 12:00–21:00, SUMO seed 42 | `a2612865…` |
| `ev` | Champions League night, Inter @ Man City, kickoff 20:00 BST | `70d6d12f…` |
| `inc` | Fri 2024-03-15 20:00–21:00, reactive-rule VSL collapse hour, **SUMO seed 43** | `e188ce07…` |
| `wd_am` | Tue 2024-10-15 morning peak | `5e36a7cb…` |
| `wd_pm` | Tue 2024-10-15 evening peak | `848ba3cf…` |

Demand is Lourenço-calibrated (per the producer's provenance note — **confirm the correct
citation for that calibration with the producer**, it is referenced but not fully specified in
the material held here).

Note for the write-up: **every confirmed capacity result is on `inc` alone**, the modelled
collapse hour, and it is the only regime of the five where capacity moves outcomes at all.

## 5. Which outputs carry this

- The dissertation reference list, as first-class entries.
- Any figure, table or appendix reporting capacity-study numbers.
- The video, where it shows results.
- GPU-track manifests already embed a `citation` field; keep it.
- The appendix quick-start already names the repositories — keep that consistent with §1.

## 6. What is still not permitted

- **Rehosting or republishing producer repository content.** Cite and link; do not copy the
  repositories into this one or into any public output. The permission covers use, and
  republication was recorded conservatively.
- Committing the Year-1 report PDF, or any producer data blob, into this repository.
- Presenting producer-derived results without the citation set in §1 — that is the condition the
  permission rests on.
