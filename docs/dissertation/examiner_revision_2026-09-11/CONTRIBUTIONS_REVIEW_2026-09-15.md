# Contributions revision — stopped at the requested word-count gate

Input: `da499546207afe33d878eca2ba709f5efbb1e673`. Applied the owner-supplied A paragraphs, only the designated B trims, and conditional F1. **Strict count is 8,960, ten above the 8,950 ceiling.** Prose-only is **7,760**, above 7,600. Further manuscript edits stopped as instructed; this revision is not claimed to pass acceptance.

## Changes

The seven new paragraphs appear once, in order, at the end of Section 1.3. C1–C6 use the supplied wording, with C5's prescribed **“more than eighty”** fallback. C3 remains “Specifying and implementing”; the lead points to the Declaration, and Section 3.7 retains its AI-assistance and supplied-code attribution. AUTHOR_ACTIONS records that the six C-items were the owner's own statement supplied on 15 September 2026.

B.1 replaces the specified research-path/component-size span with its Table A1 pointer and removes the named closing sentence. The span contains three existing sentences despite the prompt calling it two. B.2 removes the named RQ2 repetition in 4.3; the equivalent 84.8%/15.2% statement in protected 3.4 is unchanged, although it was not byte-identical. B.3 removes only its two named sentences; the experiment-design, assistance, Putra-attribution and verification statements remain. B.4 shortens only the hosted-run parenthetical. B.5 applies the exact scope-sentence replacement. No other deletion was made.

**F1 was used.** After A+B the count was 8,975. “Fixed order and uncontrolled frequency/thermal state limit timing comparisons; durations and IQRs remain available.” moves verbatim from 3.7 to the end of Appendix D's first paragraph, with no new pointer, as specified. It removes 15 main-text words, leaving 8,960. The existing Appendix D pointer remains elsewhere in 3.7.

## Count derivation for C5

The supplied component counts sum to 83, but E1's seed-0/cap-2p5 cell is the E0 reference reused. The E1 manifest explicitly locates it under `e0_outputs/e0-full-corrected-reference-v1/run_1`; its summary SHA256 matches E0: `1ed26e6c8a4411b9a4e27dacf4d9381c8f8430a37c434f93b36f1150d8c661e1`. Counting that cell once gives a completed-campaign inventory of **82 distinct summary hashes**.

| Component | Distinct runs added | Horizon evidence |
|---|---:|---|
| E0 | 1 | Per-run summary horizon |
| E1 | 14 | Campaign receipt; per-run horizon not retained |
| E2 | 3 | Per-run summary horizon |
| E2b | 1 | Per-run summary horizon |
| E2c | 8 | Campaign receipt; per-run horizon not retained |
| E2d | 4 | Campaign receipt; per-run horizon not retained |
| state-delay pilot | 5 | Per-run summary horizon |
| morning pilot | 2 | Per-run summary horizon |
| morning replication | 12 | Per-run summary horizon |
| joint confirmation | 32 | Per-run summary horizon |
| **Total** | **82** | **56 direct per-run horizons; 26 supported by campaign receipts and manifests** |

E2b's reused E2 cells are excluded; E2c's reused seed-0 records and E2d's reused controls are also excluded. Smokes, probes, forwarding recomputation, scheduler fixtures and duplicate archive copies do not add runs. All counted original summary hashes are distinct.

The compact E1/E2c/E2d records do not preserve the individual summary horizon fields for 26 non-reused cells. Their accepted campaign records and manifest horizons support the broad inventory, but the task's stronger per-summary rule cannot establish an exact printed total. **The manuscript therefore says “more than eighty”, not 82 or 83.** The original raw locations searched are unavailable. Every component, receipt path, JSON pointer, hash, observed/planned horizon distinction and deduplication is recorded in [the derivation](evidence/CONTRIBUTIONS_RUN_COUNT_2026-09-15.json), whose hash is pinned in [the operation ledger](evidence/CONTRIBUTIONS_OPERATIONS_2026-09-15.json).

## Counts and verification

| Stage | Strict/package | Prose-only |
|---|---:|---:|
| Input `da49954` | 8,938 | 7,738 |
| A+B | 8,975 | 7,775 |
| A+B+F1 | **8,960** | **7,760** |
| Required | ≤ 8,950 | ≥ 7,600 |

Net change: **+22 words** under each method. This does not meet the requested zero-net-cost target or the 8,950 acceptance ceiling. Counting rules and bounds are unchanged; the contents page prints strict first.

- `validate_option_b.py`: **157/157 preservation checks pass**.
- `validate_revision.py`: **203/204 checks pass**; **`word_count_in_range` fails**. The failure is preserved in the validation receipt.
- New pinned-ledger layer exactly recovers `da49954` before all earlier preservation guards run. Sections 1.2 and 3.2–3.6, all twenty table bodies, six equations, two algorithms, Proposition 1 and references 1–46 are unchanged.
- [Mutation probe](evidence/CONTRIBUTIONS_MUTATION_CHECK_2026-09-15.json) reinserts the deleted B.2 sentence and is rejected.
- Clean XeLaTeX/latexmk build; zero overfull boxes, missing glyphs, undefined references or duplicate caption readings. Title and author metadata remain set. Ruff lint/format pass for all six document scripts.
- **63 pages** rendered; all contact sheets inspected, plus full pages 2, 3, 16, 35, 36, 40, 41 and 58, covering contents and every requested changed-text location.

## Artifact identity

- Markdown SHA256: `5fe0b6dc38c3fde1282affb502ea72d650ef0ea59f59c741086a333a962258cc`.
- TeX SHA256: `739fb2f99119afe068a8fb309084fb2acd97d790858b20dc8ea3daa8aec22411`.
- PDF SHA256: `f85bf697f62beb68b850e042f55cde316ea4c8a4c5c15a58aaea6951b44486e9`.

[Build log](evidence/latexmk-contributions-2026-09-15.log) · [validation](document/REVISION_VALIDATION.json) · [acceptance/stop receipt](evidence/CONTRIBUTIONS_ACCEPTANCE_2026-09-15.json).

The title, scientific results, frozen packages and main remain unchanged. No scientific runs were launched. Existing institutional submission gates remain open. Push this reviewable stop state to the same draft PR; exact pushed-SHA review is recorded in its body. No passing word-count acceptance or formal integration approval is claimed.
