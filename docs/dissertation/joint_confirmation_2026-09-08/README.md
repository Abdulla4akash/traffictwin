# Joint-randomness confirmation and manuscript sources

This package starts from reviewed commit
`c049f00f2247bfbd1196d5e6524de8198fdd2df7`. The authorised scientific execution
was frozen in local commit `c4fe33681bd11e5af429d9f2c8c7f70f2bb745f1`, with seal
SHA256 `65028659439a8808fe825e0142e8276c9c293e09085b2db036131434085beca3`.
The original disabled protocol/seal and all historical scientific files remain
unchanged. [The dated amendment](confirmation/EXECUTION_AMENDMENT.md) and
[execution protocol](confirmation/PROTOCOL_EXECUTION.md) record the new authority,
qualification, controls, tolerances, attempt ceiling and analysis.

The editable report is [Markdown](TrafficTwin_Dissertation.md) and
[LaTeX](TrafficTwin_Dissertation.tex), with the original five SVG figures.
Appendix C includes the full existing exact-model proof. The LaTeX includes
its complete bibliography and portable preamble; a separate bibliography file
is unnecessary. Future SVG compilation requires the standard `svg` package
and Inkscape, potentially with authorised shell escape. No compilation,
PDF generation, rendering, visual inspection or DOCX work is performed here.


## Completed result and scientific change

All **32 full attempts, 32 cells and eight four-arm block-control receipts passed**;
no attempt failed, no cell was retried, and no seed or block was excluded. The
first block is included. The three predeclared paired effects use equal block
weighting and two-sided Bonferroni simultaneous 95% Student-t intervals, df=7.

| Contrast | Mean, percentage points | Simultaneous 95% interval |
|---|---:|---|
| Per-task − ingress | +4.137 | [+3.556, +4.717] |
| Common-target − ingress | −3.504 | [−3.980, −3.028] |
| Per-task − round-robin | +0.631 | [+0.511, +0.750] |

The declared reversal criterion holds. Workload-aware targeting also improves
attainment over cyclic spreading in this sample, by about 63.1 successes per
10,000 offered tasks. Its higher scheduler-only cost relative to round-robin
comes from the retained, separately constructed CPU fixtures. This is a measured
trade-off in the studied model, not a universal scheduler or deployment result.

All required exogenous inputs matched within each block. In block 1, all three
non-reference arms had tiny observation/SoC and logit differences from ingress
(maxima 1.4901161193847656e-8 and 3.5762786865234375e-7 respectively). **Actions
matched exactly in every comparison.** Feedback was allowed, not suppressed;
this finite matching result does not follow from frozen weights alone.

| Previous gap | Action and result | Remaining boundary |
|---|---|---|
| Fresh joint randomness untested | Executed the sealed eight-block morning matrix; reversal supported under the declared interval family | Same trace, actor and model; approximate-normality assumption and finite blocks |
| Workload awareness versus spreading open | Same-causal-admission round-robin comparison: per-task +0.631 pp with simultaneous interval above zero | No universal optimality, physical timing or distributed-information validation |
| Protocol/qualification only | Eight short attempts, source/field/control checks, then 32 full cells with independent final-admission and work accounting | Finite path coverage; qualification had no unavailable-radio/RSU-capacity/local-capacity events |
| Full proof only externally linked | Included the complete existing exact-model proof in Appendix C of both formats | Exact sums versus executable float32; proof is AI-assisted retrospective work |
| New evidence inaccessible through compact records | Supplied counts, effects, receipts, inventory and a verifier tested from a clean temporary copy | Raw outputs remain local; private access and off-machine preservation need arrangements |

The study elapsed **6,440.25 s (107.34 min)**. Evaluator processes accounted for
6,375.54 s, cell validation 49.59 s, block validation 10.83 s and other campaign
overhead 4.28 s. The subsequent sealed analysis/completion checks took 3.44 s.
Short qualification processes separately took 68.09 s. Process time includes
startup, compilation, evaluation and compressed output writing; these figures
are not scheduler benchmark durations or simulated task latencies.

Results and evidence:

- [Primary estimates and all block effects](evidence/ANALYSIS.json).
- [All cell counts, categories and elapsed times](evidence/CELL_RESULTS.csv).
- [Paired block effects](evidence/PAIRED_EFFECTS.csv) and [eight block controls](evidence/BLOCK_CONTROLS.json).
- [Timing boundaries](evidence/TIMING.json), [completion receipt](evidence/COMPLETE.json), and [raw inventory](evidence/RAW_INVENTORY.json).
- [Clean-copy arithmetic verification](evidence/CLEAN_VERIFICATION.json), [source-only document checks](document/SOURCE_VALIDATION.json), and [separate AI critique](REVIEW.md).

Raw full-study records occupy 7.805 GiB across 267 inventoried files. They are
preserved at the local location below; no off-machine backup is claimed. The
original type analysis, timing measurements, four-draw inference and historical
scoring limitations are unchanged. No new programme follows this study.

## Verification route

From any working directory, with Python and SciPy available:

```sh
python /path/to/package/document/verify_results.py
```

This verifies the compact 32-cell/eight-block structure, bound summaries and
receipts, shared-input hashes and category totals, and independently regenerates
the three equal-weight paired contrasts and predeclared Student-t intervals.
It requires neither JAX nor the actor. It does **not** repeat task-level checks
or establish raw-data availability. Missing or mismatched evidence is an error.

To additionally authenticate an explicitly supplied copy of this study's raw
directory, use `--raw-root /approved/path/to/campaign`. This performs file-hash
checks only. It neither searches for inputs nor reruns any evaluator. Source
and manuscript checks are in [document/check_source.py](document/check_source.py);
the source converter uses MarkdownIt and never invokes a TeX engine.

The primary analysis is the pre-outcome sealed
[confirmation/analyse.py](confirmation/analyse.py). Its completion gate requires
all eight four-arm block receipts, exact source/configuration identities and
current output hashes. Compact arithmetic is a separate, narrower check.

## Qualification and preservation

Eight short evaluator attempts used the previously inspected fleet/evaluator
pair (1,0): seven 300-step attempts and one 150-step restart. Three unchanged-arm
comparisons matched 83 shared scientific fields exactly. Four-arm inputs,
pointer progression, fresh-process prefix restart, and count/input/receipt/hash
negative checks passed. Short records contain gate rejections, but no unavailable
radio, RSU-capacity or local-capacity failures; those branches retain the prior
kernel coverage only. [Qualification](evidence/QUALIFICATION.json) and the
[prelaunch safeguard follow-up](evidence/QUALIFICATION_FOLLOWUP.json) preserve
that finite scope. No extra evaluator run was added for the safeguard fixes.

Raw outputs are retained locally at:

```text
/Users/akashx/Downloads/diss_mat/traffictwin-joint-confirmation-raw-2026-09-08/
  qualification/
  campaign/
```

The original qualification source bytes are preserved in its `source_snapshot`
subdirectory because launch/validation safeguards were strengthened before
full execution. The original and final seals identify these versions explicitly.
Compact results belong in this repository package; large arrays remain in the
raw directory. No off-machine destination has been approved and no transfer
occurred. A local directory and checksums are not an off-machine backup.
Marker access to the private repository, actor/trace and raw outputs requires
the author's arrangements. [AUTHOR_INPUTS.md](AUTHOR_INPUTS.md) records precise
personal-verification, attribution, AI-use and access questions.

Historical E0/E1/E2 original raw outputs remain unavailable: deletion reported
by the author, no known backup. No recovery search or historical rerun was
performed. The new records cannot quantify that historical scoring uncertainty.
The completed September audit, task joins, type analysis, scheduler benchmark
and numerical suite were reused without repetition.

No push, merge, public upload, paid service, cluster job, retraining, full-evaluator
tie-break prefix or dissertation submission is part of this delivery.
