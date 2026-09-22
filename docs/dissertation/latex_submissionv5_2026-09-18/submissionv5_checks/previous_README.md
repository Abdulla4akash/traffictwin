# TrafficTwin dissertation: browser citation correction, 18 September 2026

`TrafficTwin_Dissertation.pdf` is the revised output; `TrafficTwin_Dissertation.tex` is its matching source. Build with `./build.sh` (Tectonic 0.17.0).

The page 34 correction attaches references [45] and [46] to a separate statement about scientific-software practices and reproducibility. The browser result is stated separately and linked to the retained `evidence/product_capture/ui/accessibility-audit.json`. Its five snapshots report no Streamlit exceptions or horizontal overflow, in light theme at a 1440 by 1000 desktop viewport. The text retains the limitation that this inspection did not assess usability.

The original inspection JSON and five accompanying screenshots are included unchanged. This is a retained historical check; no new browser inspection or scientific workload was run. The linked JSON is relative to the PDF, so keep the extracted package together when following it. Other inherited evidence links may still require the original research repository, as described in Appendix G.

The automated word count is 8,386, including the 217-word abstract under the inherited counting method. Run `python3 revision_checks/recount.py` with `markdown-it-py` installed to reproduce it.

`browser_citation_checks/` records this correction, input identities, manuscript diff, count and current validation. `citation_checks/`, `revision_checks/` and `SECOND_PASS_CHANGES.md` retain historical records for earlier revisions; their counts, hashes and validation statements describe those earlier versions. The previous package `../latex_second_pass_citations_fixed_2026-09-18/` is preserved.

`SHA256SUMS` binds this delivery's files.
