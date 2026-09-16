## LaTeX-only exemplar alignment — 16 September 2026

The edited `TrafficTwin_Dissertation.tex` is the current manuscript source for this pass. **Do not run `convert_source.py`**: the Markdown and its source map are preserved historical inputs, and that converter would overwrite the authorised LaTeX changes. The tracked dissertation PDF remains the ded54bd build; it does not reflect this pass. The delivery contains LaTeX plus build inputs. See [CHANGES.md](CHANGES.md), [operation ledger](evidence/EXEMPLAR_OPERATIONS_2026-09-16.json) and [command receipt](evidence/EXEMPLAR_COMMANDS_2026-09-16.json).

Appendix H uses these read-only inspection commands from an authorised repository copy with dependencies available. The compact helper extends the existing `joint_confirmation_2026-09-08/document/verify_results.py` route to Tables 6, 7, 7a and 7b. The platform and TOS commands are copied from the repository README (launch command and adapter examples); `EXTERNAL_PACKAGE` is an explicitly supplied package path. Launching the platform does not execute a research cell.

```sh
python docs/dissertation/examiner_revision_2026-09-11/document/verify_compact_tables.py
streamlit run src/traffictwin/ui/app.py
traffictwin integration tos validate "$EXTERNAL_PACKAGE"
```

Build with XeLaTeX/latexmk; no bibliography backend or custom class is required. Keep the Liberation Serif, Liberation Sans and DejaVu Sans Mono fonts available. Run `document/count_exemplar_words.py`, `document/validate_final_pass.py` and `document/validate_revision.py` for this overlay. When preserving the tracked PDF, set `TRAFFICTWIN_REVIEW_PDF` to the separately compiled current PDF for the validators; they must inspect that build, not the historical tracked PDF. The previous manuscript-only word-count waiver remains in force. PR remains draft, unmerged.

---

# Dynamic Resource Management for Intelligent Transportation System Applications

## Current final-pass overlay — 16 September 2026

[PDF](TrafficTwin_Dissertation.pdf) · [Markdown](TrafficTwin_Dissertation.md) · [acceptance receipt](evidence/FINAL_PASS_ACCEPTANCE_2026-09-16.json) · [combined validator](document/REVISION_VALIDATION.json)

The **68-page draft** includes studies 7–12 in Section 3.4 (Tables 7a and 7b), the five-scenario interpretation, reference 47, authentic three-panel Figure 7, the supplied title-page identity and standard declaration. The 58-operation ledger preserves the published manuscript baseline `a8cffe7` and the earlier protection layers. Integration base is current main `fe8c8d9`; the draft changes only this revision package.

**9,555 strict / 8,136 prose-only words.** All G.1–G.9 fallbacks were used. The owner explicitly waived the word-count stop and will trim the manuscript: the 8,950 ceiling is exceeded by 605 and the 9,000 rubric ceiling by 555. Both failed diagnostics remain in the validator; only those two are nonblocking under the recorded waiver. No further content cuts were made.

The Abstract reports **seven policies, 274 distinct full evaluator runs and five Manchester scenarios**. Receipt counts are 82 + 72 + 120; the expected 275 counted the E0 reference reused by E1 twice. Of the historical records, 26 establish full-run identity through accepted campaign receipts/manifests instead of retained per-summary horizons. C5 and the ownership paragraph retain initial-programme scoping. The confirmation and follow-up protocols were sealed before outcomes; the initial incident development remains adaptive. Claude proposed the later conditions; the owner authorised them.

**PR 144 is open/draft and unmerged by owner instruction.** S19 cites the original study source `c95e4f86d6dd83207ed3c810826ca48768af8471` on `research/dissertation-traces-2026-09-16`. The pending integration/archive-registration commit `885cc86` remains on that branch for post-submission work. Main remains `fe8c8d9`. S18 links the already merged studies 7–9 at `fe8c8d9`.

Acceptance is restricted to the owner-requested manuscript checks: **223/223 extended preservation checks**, **70/70 final-pass checks**, **2/2 mutation probes**, and **285/287 combined checks**, with only the two waived word-limit diagnostics false. Clean latexmk succeeds with zero overfull boxes, oversized floats, missing glyphs or undefined references. All 68 pages were rendered; changed pages, new table layouts, source links, title/contents and Figure 7 were visually inspected. The full list and artifact hashes are recorded in the acceptance receipt. Application tests were stopped; incomplete logs are retained in the [stop receipt](evidence/APPLICATION_TEST_STOP_2026-09-16.json). No application-suite pass or new scientific execution is claimed. The push uses `[skip ci]` to honour the instruction not to launch that suite.

Figure 7 includes panel **(c)** from the actual bridge at `17d6b21`, plus real external-package inspection/matrix panels. Capture and adapter receipts preserve the 300/60/6/5/66 inventory and distinguish the external engine's results from dissertation evidence. The source PNG/PDF retain 300 dpi; small interface detail can be inspected at zoom in the standalone asset.

The award, faculty/school/department, student ID and author are filled. Signature/date remain for the owner. The prescribed copyright statement was not found in the specified handbook, so the existing page is kept under F.2's fallback. AI-use permission, copyright wording, backup/examiner access, final reading and the assessed video remain open in [SUBMISSION_GATES](SUBMISSION_GATES.md). This is a draft hand-off, not submission certification; no merge or tag is authorised before the owner's PDF review.

### Rebuild and manuscript-only validation

Use the existing document environment (MarkdownIt, PyMuPDF and XeLaTeX/latexmk), retaining the pinned historical Git objects. The original frozen research code and results are unchanged.

```sh
pkg_dir=docs/dissertation/examiner_revision_2026-09-11
python "$pkg_dir/document/convert_source.py"
latexmk -cd -C "$pkg_dir/TrafficTwin_Dissertation.tex"
latexmk -cd -xelatex -interaction=nonstopmode -halt-on-error "$pkg_dir/TrafficTwin_Dissertation.tex"
python "$pkg_dir/document/validate_option_b.py"
python "$pkg_dir/document/validate_final_pass.py"
python "$pkg_dir/document/probe_final_pass_mutations.py"
python "$pkg_dir/document/validate_revision.py"
```

### Final artifact SHA-256

- Markdown: `517256406a2bd81320b1da75e0b01aabca99285ec2bc2360a5732e1c5a17aedc`
- TeX: `988f14d42e3c01cb6c23817ce8bed2b2a20503a890c51547a5d021d4531f54db`
- PDF: `2730a690075f6c29586e9fe16c20f4ed367d1318692d91ae8fe847ebd50de2e8`

## Earlier overlays — historical records

The dates, counts, hashes and completion claims below describe their original candidates. The 16 September overlay above governs the current draft.

## Experimental results and abstract scale - 15 September 2026

[Current PDF](TrafficTwin_Dissertation.pdf) · [Markdown](TrafficTwin_Dissertation.md) · [current acceptance record](evidence/PLATFORM_CONNECTION_ACCEPTANCE_2026-09-15.json)

Figure 7 (page 37) now shows TrafficTwin inspecting the completed joint-randomness study: 32 cells, eight paired blocks, four policies and the three declared contrasts. The caption calls it a workflow demonstration and distinguishes compact arithmetic/receipt checks from historical task-level validation and original experiment execution. The first abstract paragraph adds the authorised scale sentence: six evaluated policies, more than eighty full runs, and three replication stages culminating in a sealed confirmation.

The report is **8,984 strict / 7,784 prose-only words**, with 63 pages. The rubric's 7,000-9,000 range passes. The earlier 8,950 owner gate remains **failed by 34 words**; it was already failed by ten words before these changes. The user subsequently requested the current version be pushed and merged. No text was trimmed and the earlier gate was not silently waived.

The pinned four-operation ledger recovers `b3b8dbc` byte-for-byte before every earlier contribution/editorial preservation layer runs. All **168/168 preservation checks** pass; combined validation is **215/216**, with only `word_count_in_range` failing. Five negative probes reject an extra abstract claim, a removed validation boundary, a changed result, altered ledger bytes and a modified screenshot. Ruff passes all seven document scripts.

The canonical PDF was rebuilt here with package-relative links: all 99 local links resolve and all 63 pages render pixel-identically to the verified Desktop delivery. Pages 3, 4, 6, 36, 37, 38 and 48 were inspected with no defects. The page break before Table 8 preserves its complete layout. The copied [abstract receipt](evidence/ABSTRACT_SCALE_UPDATE.json) retains the **Desktop PDF hash**; the [canonical receipt](evidence/PLATFORM_CONNECTION_ACCEPTANCE_2026-09-15.json) records this repository PDF's different identity.

The [capture receipt](evidence/PLATFORM_RESULTS_CAPTURE.json) binds the unedited screenshot to source `5e18707`; [browser checks](evidence/BROWSER_CHECK.json) bind the unchanged results page to final product source `17d6b21`. [Import checks](evidence/TRAFFICTWIN_IMPORT_CHECK.json), the [product workflow](../../integration/dissertation_results.md) and the [portable packet](../../../src/traffictwin/resources/research/joint_confirmation_results.zip) are available. The historical inventory and prior receipts retain their original source identities. No scientific workload was launched.

Rebuild with the existing MarkdownIt/XeLaTeX environment and the commands below. `validate_revision.py` deliberately exits nonzero while the disclosed earlier word ceiling is unmet. Independent exact-SHA review and merge are coordinated separately; document-builder checks are not self-approval or submission certification.

```sh
pkg_dir=docs/dissertation/examiner_revision_2026-09-11
python "$pkg_dir/document/convert_source.py"
latexmk -cd -g -xelatex -interaction=nonstopmode -halt-on-error "$pkg_dir/TrafficTwin_Dissertation.tex"
python "$pkg_dir/document/validate_option_b.py"
python "$pkg_dir/document/validate_revision.py"
```

## Earlier contributions revision - preserved historical record

The notes below describe their original candidate and counts. The current overlay above governs the later Figure 7 and abstract changes.

**Contributions revision stopped at the requested word-count gate: 8,960 strict/package words / 7,760 prose-only words.** Strict is **10 above 8,950**; prose meets the 7,600 floor. The **63-page PDF** is a reviewable draft. Further manuscript editing stopped after the prescribed F1 fallback. The title stays unchanged.

[PDF](TrafficTwin_Dissertation.pdf) · [Markdown](TrafficTwin_Dissertation.md) · [generated TeX](TrafficTwin_Dissertation.tex) · [contributions stop report](CONTRIBUTIONS_REVIEW_2026-09-15.md) · [revision history](REVISION_REPORT.md) · [validation](document/REVISION_VALIDATION.json)

## Current change

Section 1.3 ends with the owner's Contributions lead and C1–C6, verbatim except C5's prescribed “more than eighty” fallback. Only B.1–B.5's named spans were trimmed. The 3.7 timing-limit sentence moves verbatim to Appendix D under F1, which was triggered by the A+B count of 8,975. AUTHOR_ACTIONS records the owner's contribution statement supplied on 15 September 2026. C3 retains the supplied wording; the Declaration and Section 3.7 retain assistance and supplied-component attribution.

## Counts and checks

| Stage | Strict/package headline | Prose-only |
|---|---:|---:|
| Reviewed `da49954` | 8,938 | 7,738 |
| Contributions A+B | 8,975 | 7,775 |
| Current A+B+F1 | **8,960** | **7,760** |
| Required | ≤ 8,950 | ≥ 7,600 |

The count rose by 22 words; the requested zero-net-cost goal was not achieved. The count method and bounds are unchanged. The contents prints strict first; [WORD_COUNT.json](document/WORD_COUNT.json) includes tables, equations and pseudocode in the headline, excluding captions, references, appendices and front matter. Prose-only additionally excludes table bodies and pseudocode.

- Preservation validator: **157/157 pass**. Combined validator: **203/204 pass; `word_count_in_range` fails**.
- Sections 1.2 and 3.2–3.6 byte-identical to `da49954`; all twenty table bodies, six equations, two algorithms, proposition and references 1–46 unchanged.
- The pinned [ledger](evidence/CONTRIBUTIONS_OPERATIONS_2026-09-15.json) recovers `da49954` exactly before every prior protection layer runs. Earlier appendix moves remain verbatim.
- A [mutation probe](evidence/CONTRIBUTIONS_MUTATION_CHECK_2026-09-15.json) rejects reinsertion of a deleted sentence.
- Clean XeLaTeX/latexmk build, 63 pages rendered, contents and all changed-text locations inspected. Zero overfull boxes, missing glyphs, undefined references or duplicate captions. PDF title/author metadata retained. Ruff lint/format pass for six document scripts.

## Evaluator-run derivation

The supplied components total 83, but E1 reuses E0's reference, proven by the same raw locator and summary hash. Counting it once gives **82 distinct completed-campaign records**: 1+14+3+1+8+4+5+2+12+32. Smokes, probes, reused controls and duplicate archives are excluded.

**The manuscript prints “more than eighty”.** Only 56 unique full-horizon summary fields are directly available. E1/E2c/E2d retain completed campaign receipts and manifest horizons for the other 26, but not the per-run summary fields required for printing an exact number. [Derivation](evidence/CONTRIBUTIONS_RUN_COUNT_2026-09-15.json) records all paths, hashes, horizon evidence and deduplication. No new scientific run was launched.

## SHA256

- TrafficTwin_Dissertation.md: `5fe0b6dc38c3fde1282affb502ea72d650ef0ea59f59c741086a333a962258cc`
- TrafficTwin_Dissertation.tex: `739fb2f99119afe068a8fb309084fb2acd97d790858b20dc8ea3daa8aec22411`
- TrafficTwin_Dissertation.pdf: `f85bf697f62beb68b850e042f55cde316ea4c8a4c5c15a58aaea6951b44486e9`

## Build and check

Use the existing document environment with MarkdownIt, NumPy, SciPy, Matplotlib, PyMuPDF, XeLaTeX and latexmk. Preserve Git baselines `9b49efc`, `2c29392`, `7075b25` and `da49954`. Current combined validation intentionally reports the unmet word-count gate; do not relax its bound.

```sh
pkg_dir=docs/dissertation/examiner_revision_2026-09-11
python "$pkg_dir/document/convert_source.py"
latexmk -cd -xelatex -interaction=nonstopmode -halt-on-error "$pkg_dir/TrafficTwin_Dissertation.tex"
python "$pkg_dir/document/validate_option_b.py"
python "$pkg_dir/document/validate_revision.py"
ruff check "$pkg_dir/document"
ruff format --check "$pkg_dir/document"
```

[Build log](evidence/latexmk-contributions-2026-09-15.log) · [grep receipt](evidence/CONTRIBUTIONS_GREP_2026-09-15.json) · [stop receipt](evidence/CONTRIBUTIONS_ACCEPTANCE_2026-09-15.json). The original `revision_recipe.json` and earlier acceptance receipts remain historical. [Earlier six-point review](EDITORIAL_FIX_REVIEW_2026-09-15.md) records the prior passing candidate; [Option B closing review](OPTION_B_CLOSE_REVIEW.md) retains the full earlier move map.

## Existing boundaries

Main remains `1e01b755b8b633f43c9c7bb6fdd0d75beb6469e8`; frozen packages and scientific results are unchanged. The hosted 56 test failures remain disclosed; no fresh global suite, usability result or E3 execution is claimed. The owner-confirmed ethics-tool outcome and primary references remain unchanged. [AI permission, institutional front matter/copyright, examiner access and video gates](SUBMISSION_GATES.md) remain open. Keep the PR draft; no passing count acceptance or formal integration approval is implied.
