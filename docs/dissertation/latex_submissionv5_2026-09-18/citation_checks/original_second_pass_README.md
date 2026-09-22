# TrafficTwin dissertation - second pass, 17 September 2026

Compile `TrafficTwin_Dissertation.tex`; the matching output is `TrafficTwin_Dissertation.pdf`. All four requests in `TrafficTwin_Revision_2nd_Pass.md` were implemented. `SECOND_PASS_CHANGES.md` maps them to the final pages and source locations.

The original `latex_objections_fixed_2026-09-17` directory and Desktop second-pass notes are preserved. Scientific numerical content, equations, research results, figure assets and bibliography entries are unchanged. Task deadlines remain **(100, 500, 100) ms**. The suggested positive RSU report ages remain **100, 500 and 1,000 ms**. No experiments, benchmarks, research simulations or repository test campaigns were run. Implementation code and retained research/test evidence were not modified.

## Build

Checked with **Tectonic 0.17.0**. From this directory:

```sh
tectonic -X compile TrafficTwin_Dissertation.tex --keep-logs --keep-intermediates
```

Or run `./build.sh`. If Tectonic is outside PATH, set its executable explicitly:

```sh
TECTONIC=/path/to/tectonic ./build.sh
```

Tectonic resolves references automatically and may download missing TeX packages on its first build. XeLaTeX is also suitable; use `latexmk -xelatex TrafficTwin_Dissertation.tex` or repeat XeLaTeX until references stabilise. Supplied fonts use relative paths in `build_inputs/fonts/`; supporting TeX files are retained in `build_inputs/texmf/`. Figures are in `assets/`. References are inline, so no bibliography processor is needed. Do not run a historical Markdown-to-TeX converter over the edited manuscript.

## Word count

**8,355 automated words** (first pass: 8,444; change: -89). The unchanged abstract has **217 words** under the same tokenisation. The displayed count includes the abstract, main-text headings and prose, table bodies with column headings once, equations and pseudocode. It excludes captions, scholarly references, appendices, other front matter, repeated continuation headers, and layout/figure-label text. This remains an automated source-projection estimate, not a manual or institutionally certified count.

Reproduce the documented method using Python 3 and `markdown-it-py`:

```sh
python3 revision_checks/recount.py
```

The wrapper retains the pinned source-map baseline and TeX-projection delta method from the first pass. It now accepts an empty removed table as zero words. Empty source-block markers 185 and 186 are retained only for counting provenance; their heading, table, labels and layout commands are removed. Historical counting inputs in `revision_checks/counting/` are unchanged. `revision_checks/word-count.json` records the result, block deltas, inclusions and limitations.

## Verification and package contents

`revision_checks/validation-summary.json`, `source-checks.json`, `pdf-checks.json`, `manuscript.patch` and `build-console.txt` record this pass. `revision_checks/build_logs/` contains the final TeX log, contents/list files and reference data. Current source checks can be repeated with `python3 revision_checks/verify_source.py`. `SHA256SUMS` binds the delivered files.

`revision_checks/first_pass/` preserves prior revision records and the immediately preceding TeX for comparison. These historical records are not the current manuscript, current word count or current build report. The included second-pass notes are an unchanged copy of the user's instructions. The source bundle includes the complete manuscript package, fonts, assets, build instructions and word-count provenance; it is not the full research-data repository. Existing repository-relative evidence links still require the original evidence repository. Internal document references and contents/list links were checked separately from external evidence availability.

The final PDF has 62 pages. Contents and List of Tables were rebuilt: main-text tables run 1-12, Conclusion subsections run 4.1-4.4, and the former 4.5 reflection is now 4.4. No compilation errors, undefined citations/references, overfull boxes or missing rendered glyphs remain. The engine retains harmless underfull-box notices in bibliography/evidence entries and legacy package-comment encoding warnings also present in the first-pass build; inspected output is readable. No material unresolved build or document-verification issue was identified.
