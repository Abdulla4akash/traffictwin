# Complete revised TrafficTwin dissertation

Prepared 7 September 2026 from evidence baseline `04f3b6a95c7bc06c80ed95b54762f12861bba183`.

- [Complete editable manuscript](TrafficTwin_Dissertation.md)
- [Complete review PDF](TrafficTwin_Dissertation.pdf)
- [Concise claim-to-source map](CLAIM_SOURCE_MAP.md)
- [Word count and deterministic checks](VALIDATION.json)
- [Reference/access-scope check](REFERENCE_CHECK.md)
- [Remaining author inputs](AUTHOR_INPUTS.md)
- [Validation and adversarial review scope](REVIEW.md)

**Report word count: 7,424.** The count includes Abstract through Conclusion, body headings, table cells and the algorithm; it excludes cover/contents, captions, references and appendix. The recorded COMP66060 requirement is 7,000–9,000 words. Related work is inside the Introduction; Abstract and Conclusion remain separate.

This is one complete report centred on corrected task accounting, admission capacity versus compute service, frozen-policy infrastructure placement, the incident reversal, morning replication and post-hoc five-RSU audit. The August manuscript and September source material remain intact. This draft replaces the obsolete central framing; it does not append a new results chapter to the historical draft.

No simulations were launched and no evaluator source was changed. The inspected morning pilot remains outside primary inference; scenario analyses remain separate. Sensitivities are single-draw, intermediate audit workloads are reconstructed, and the rotating-tie-break test remains proposed and unrun.

The Markdown is the editable source. The PDF is generated from that source with embedded fonts, linked citations and a linked contents page. It is a review layout, not a signed or officially templated submission. The author-input record lists the few remaining administrative/authorship decisions. Word export is not provided because the installed documents skill's required managed dependency runtime is unavailable in this session.

## Rebuilding the document

The PDF builder and draft checker do not import or execute the evaluator. They require Python 3.12, `reportlab`, `pypdf`, `pillow`, `markdown-it-py`, and `svglib`. The recorded build used an isolated document-only environment outside the scientific runtime. Times New Roman and Arial fonts are read from the macOS system font directory; adjust `FONT_ROOT` for a different host with those fonts available.

```sh
python validate_draft.py
python build_pdf.py
```

PDF rendering must be rechecked after edits. The preserved research figures are embedded from their archived files; the three new SVG diagrams are explanatory illustrations. No new measurements or regenerated experimental figures are introduced by the builder.
