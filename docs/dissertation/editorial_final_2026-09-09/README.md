# Editorial finalisation — 9 September 2026

Complete editable [Markdown](TrafficTwin_Dissertation.md) and [LaTeX](TrafficTwin_Dissertation.tex), based on reviewed `477304f7f988f7d5d5ea5ae21d0e49eed1429e5a`. Local branch: `docs/research-editorial-final-2026-09-09`. This package is for author review, not certified submission-ready. The completed scientific study and all earlier packages remain unchanged.

The revision moves the eight-block confirmation immediately after the four-draw morning replication, strengthens motivation and synthesis, and condenses secondary diagnostics. [Revision report](REVISION_REPORT.md), [claim/source map](CLAIM_SOURCE_MAP.md), [source validation](VALIDATION.json) and [specific author questions](AUTHOR_INPUTS.md) explain the changes and remaining decisions. This was an editorial task: no evaluator, qualification, benchmark, task-level reanalysis, numerical suite or new proof was run.

## Assessment and assistance

The actual supplied **MSc_Report_and_Video_Rubric.pdf** was read by text extraction on 9 September. Its SHA-256 is `c88175e344c8aa0cfd5eba6164a8b5941670c7cc5bb69e89213c6c019bcd8c0f`. The owner's copy is in `/Users/akashx/Downloads/diss_mat/`; it is not redistributed here. The [repository transcription](../comp66060_rubric_readiness_2026-08-19.md) supplies the accessible reference. The rubric specifies approximately 8,000 words, range 7,000–9,000 excluding references, appendices and captions; the recorded report/video weighting is 85/15. No separate Background chapter is introduced.

[Sandra's recorded guidance](../../correspondence/sandra_randy_vec_progress_email_thread_2026-08-18.md) encourages the research emphasis, clear operational explanation, worked examples and bounded follow-up. It is not approval of this September manuscript, its substantive AI assistance or subsequent extensions. The manuscript preserves credit for supplied code, documented intellectual contributions and AI-assisted implementation, proof, analysis and writing. Personal verification and assessment-specific disclosure remain for the author to confirm.

## Source-only verification and assets

From the repository root, use a document environment with MarkdownIt and SciPy:

```sh
python docs/dissertation/editorial_final_2026-09-09/document/source_tools.py convert
python docs/dissertation/joint_confirmation_2026-09-08/document/verify_results.py --output docs/dissertation/editorial_final_2026-09-09/document/COMPACT_CHECKS.json
python docs/dissertation/editorial_final_2026-09-09/document/source_tools.py check
```

The wrapper reuses hash-pinned reviewed conversion/checking tools through temporary destination adapters. It never modifies those tools or scientific files. The compact verifier recomputes the existing eight paired block effects and intervals from bound summaries/receipts, not raw tasks. Source checks compare all text blocks, equations, tables, citations, links and assets between formats and preserve the original full Appendix C. They do not establish rendered appearance.

The complete bibliography is embedded in both manuscripts. All five original SVG figures are byte-identical copies. Earlier PNG plots exist for two topics, but their companion SVGs differ from the reviewed figures; suitable matching PNGs were not verified. The retained LaTeX therefore requires standard `svg`/Inkscape support for a future authorised build, potentially with shell escape. No TeX compilation, PDF generation/rendering, page inspection, pagination or DOCX work was performed. Historical PDFs and validation receipts are unchanged.

## Evidence access and preservation

The central results and all eight blocks remain in the [reviewed evidence package](../joint_confirmation_2026-09-08/evidence/ANALYSIS.json), with [cell counts](../joint_confirmation_2026-09-08/evidence/CELL_RESULTS.csv), [paired effects](../joint_confirmation_2026-09-08/evidence/PAIRED_EFFECTS.csv) and [block controls](../joint_confirmation_2026-09-08/evidence/BLOCK_CONTROLS.json). A marker with this repository can inspect those records and regenerate compact tables without the actor, JAX or raw arrays. Repository and raw-input access are separate arrangements; private links alone do not establish examiner access.

The unchanged [campaign inventory](../joint_confirmation_2026-09-08/evidence/RAW_INVENTORY.json) records **267 files, 8,380,562,432 bytes (7.805 GiB)**. The recorded local raw root is:

```text
/Users/akashx/Downloads/diss_mat/traffictwin-joint-confirmation-raw-2026-09-08/campaign/
```

No raw files were moved, rewritten, uploaded or reanalysed in this task. The inventory and prior validation are reused evidence, not a new raw-hash pass. Historical E0/E1/E2 original raw outputs remain **unavailable; deletion reported by the author; no known backup**. No search or recovery was attempted, and September evidence cannot quantify their unresolved scoring impact.

**Destination confirmation still required:** does the owner approve a copy-only transfer to a University-managed OneDrive folder `TrafficTwin/research-evidence/joint-confirmation-2026-09-08/campaign`, and what exact account/destination identifies that folder? No such destination-specific approval or transfer is recorded.

After that approval only: use a new destination folder, retain every source file, and copy without deletion or overwrite (for example `rsync -a --ignore-existing -- SOURCE/ DESTINATION/`). Stop if existing destination files disagree. Verify the destination against all 267 paths, sizes and SHA-256 values using the existing verifier's explicit `--raw-root DESTINATION` option. If the destination is a local sync folder, additionally establish remote synchronisation and retrieve/verify the remote copy before calling it an off-machine backup. Record the verified destination and date; leave the original raw root intact. A second local folder or checksum is not a backup.

## Separate CI maintenance

The narrow repair is on `maintenance/immutable-research-ci-2026-09-09`, commit `d32519c58820ff4fe1e9ef7bcc1562bc38cfb4cc`, not merged here. Its report is `docs/quality/immutable_research_ci_2026-09-09.md` on that branch. Eight explicit frozen packages receive an integrity gate rather than destructive formatting; maintained code and this new package stay checked. Bounded local checks passed, including 31 selected tests (0 failed, 0 skipped); the full suite was not run. The latest inspected hosted run remains failed at Ruff, with downstream checks skipped. Local success does not make that hosted run green. The new editorial Python source also passed format/lint under that maintenance configuration, without merging branches. Local untracked or gitignored extra files inside the eight archive roots intentionally fail the integrity gate; Python caches and `.DS_Store` are the documented exceptions.

No push, merge, submission, human approval or off-machine backup is claimed for this task.
