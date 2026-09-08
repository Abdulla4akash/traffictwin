# Production-mechanism revision — 8 September 2026

This isolated revision starts from `1b6a8555c27901ec95ad8b123c413453ecdb5620` on branch `docs/dissertation-production-mechanism-2026-09-08`. Its predecessor and all historical scientific records are unchanged. It is for author review; no push, publication, submission or author approval occurred in this task.

- [Complete editable dissertation](TrafficTwin_Dissertation.md) and [new PDF](TrafficTwin_Dissertation.pdf).
- [Substantive changes and boundaries](REVISION_REPORT.md), [specific author confirmations](AUTHOR_INPUTS.md) and [separate AI critique with response](REVIEW.md).
- [Claim-source map](CLAIM_SOURCE_MAP.md) and [retained reference-access record](REFERENCE_CHECK.md).
- [Mathematical appendix](analysis/MATHEMATICS.md), [executable analysis guide](analysis/README.md) and [final 719-input coverage](analysis/results/EVIDENCE_SUMMARY.json).
- [Morning outcome accounting](analysis/results/OUTCOME_ACCOUNTING.csv), displayed by draw in manuscript Table 7; [worked adverse example](analysis/results/ADVERSE_PRODUCTION.csv), displayed in Table 8.
- [Current validation](VALIDATION.json), [every-page visual record](VISUAL_REVIEW.json) and [checksums](SHA256SUMS).

The proof establishes exact-model fixed-target equivalence in at most min(n,2d−1) replacements from eligibility. Two production deadline thresholds therefore suffice for three passes. Numerical fixtures restrict implementation equivalence; they do not establish observed frequency or explain the empirical performance gap. The small adverse example retains production task/service/capacity coupling but uses reduced infrastructure; its checked RSU/substep transfers do not retain the loss.

Verification requires this repository checkout and its compact source/evidence files, not deleted historical arrays. In a document-only Python environment with [these dependencies](requirements-pdf.txt), run `python validate_document.py` from this directory to check saved evidence, table arithmetic, links, source identities and the existing visual-review binding. This command does not conduct a new visual inspection. `python build_pdf.py` rebuilds the PDF; a different output hash requires a new every-page inspection before validation can pass. Follow the PDF authoring environment's requirements when rebuilding.

The [previous relocatable verification package](../gap_closure_2026-09-08/verification/README.md) remains the route to compact historical tables and optional September raw checks. This task reused its authenticated results without repeating its 19-run audit or 23 joins. Original E0/E1/E2 raw outputs remain unavailable: deletion reported by the author; no known backup. Historical checks requiring them remain not assessable. No recovery activity was attempted or is required here. A local checkout and checksum are not an off-machine backup; markers still need authorised access to the repository and any requested private September inputs. No private data was transferred.
