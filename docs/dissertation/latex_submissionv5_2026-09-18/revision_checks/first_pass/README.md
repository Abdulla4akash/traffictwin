# TrafficTwin dissertation — objections revision

The entry point is `TrafficTwin_Dissertation.tex`; its matching compiled output is `TrafficTwin_Dissertation.pdf`. This is a separate revised package. The original `latex_prose_2026-09-17` folder is preserved.

## Changes

Applied the supported corrections and editorial recommendations from `TrafficTwin_Objections_Review.md`. Correct material challenged in the objections was retained. The revision shortens the abstract, introduces the platform and control boundaries, clarifies task generation, service and queue units, distinguishes admission from deadline success, defines the latency symbols and binary-mask domain, and explains the fixed-target proof's limits. The worked illustration and diagram labels were updated without changing their numerical example.

Main-text tables now run consecutively from 1 to 13; appendix tables follow their order of appearance. Figures run from 1 to 9. The study map is numbered and lists completed work. The outcomes table uses evidence and limitations rather than self-awarded verdicts. Follow-up study attribution reflects the author's account of literature review, deliberation, selection and implementation direction. AI assistance is consolidated in the Declaration. Implemented what-if workflows are credited separately from user evaluation and the unexecuted E3 campaign. Unsupported personal regrets and current backup/access obligations were removed.

The numerical data rows in 16 retained scenario/results tables and all 48 bibliography entries are unchanged. No scientific simulations or software test campaigns were rerun. `revision_checks/manuscript.patch` gives the complete TeX difference; `EDITS.json` records the final changed source blocks. Original figure files not used by the TeX are retained as supporting assets, not additional results.

## Word count

**8,444 automated words**, compared with the independently reviewed original count of 9,860; the abstract has **217** words using the same tokenisation. The count includes the abstract, main headings and text, table bodies, equations and pseudocode. It excludes captions, references, appendices, other front matter and repeated continuation headers. This is an automated source-projection estimate, not a manual or institutionally certified count. It is below the rubric's upper guidance of 9,000 and the author's approximate 9,200 maximum.

Reproduce it from this directory using Python 3 with `markdown-it-py` installed:

```sh
python3 revision_checks/recount.py
```

All historical inputs needed by that counter are included in `revision_checks/counting/`. They are counting provenance, not an alternative manuscript to compile. The wrapper extends the original project convention to account for changed table bodies. `word-count.json` records block deltas, method and limitations.

## Build

The build was checked with Tectonic 0.17.0:

```sh
tectonic -X compile TrafficTwin_Dissertation.tex --keep-logs
```

Tectonic may download missing TeX packages on its first run. XeLaTeX is also suitable; repeat until cross-references stabilise or use `latexmk -xelatex`. Fonts and images use relative paths. The font files are supplied in `build_inputs/fonts/`; auxiliary TeX files are in `build_inputs/texmf/`. References are inline, so no bibliography processor is required. Do not run a historical Markdown-to-TeX converter over this edited source.

The bundle contains manuscript build inputs, not the full research-data archive. Existing repository-relative evidence links require the original evidence repository; supplying this source package does not certify examiner access to raw data.

## Evidence and author checks still open

- Historical gate-off scoring impact cannot be quantified without the missing original task-level records. Later results do not resolve that gap.
- The saved 56 software-test failures remain disclosed. Their full causal relationship to every scientific evidence path has not been audited; this edit does not classify all failures as harmless or repair the software.
- The current institutional AI form and complete submission requirements were not supplied. The existing conventional declaration is retained; the consolidated assistance statement must agree with the form. Recorded author-check exercises are attributed to the record rather than newly asserted as personally completed in this edit.
- The author's first-pass appendix review was unfinished. Fixing the specified appendix concerns does not mark the remaining appendices as author-reviewed or approved.

## Validation

The PDF was compiled, all pages rendered, and changed figures, equations, tables and pagination visually checked. Source references and citation labels were checked, and preserved numerical table rows were compared directly with the original. Build and page-check records are in `revision_checks/`. These document manuscript validation; they are not new experimental evidence.
