"""Validate the LaTeX-only exemplar overlay while retaining historical Markdown guards."""

import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

from count_exemplar_words import calculate, count

BASE = "ded54bd2a043ec4ff7dbef6eb92e6176bc4963b9"
PACKAGE = "docs/dissertation/examiner_revision_2026-09-11"
LEDGER_SHA256 = "a103cd528b1c4750b81da081053d98ccbef09dfd3aaee8598926f243590a475c"
TEX_SHA256 = "817b8dddf4140e86ef10c7691c2b8093fd8baa6983c6b945e70879126ae874d6"
PRESERVED_PDF_SHA256 = "2730a690075f6c29586e9fe16c20f4ed367d1318692d91ae8fe847ebd50de2e8"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def baseline_bytes(here, path):
    return subprocess.check_output(["git", "show", f"{BASE}:{PACKAGE}/{path}"], cwd=here.parents[2])


def review_pdf_path(here):
    return Path(
        os.environ.get("TRAFFICTWIN_REVIEW_PDF", str(here / "TrafficTwin_Dissertation.pdf"))
    )


def block(text, number):
    match = re.search(
        r"% BEGIN SOURCE BLOCK "
        + f"{number:03}"
        + r" [^\n]+\n(.*?)\n% END SOURCE BLOCK "
        + f"{number:03}",
        text,
        re.S,
    )
    return match[1] if match else None


def historical_exemplar_checks(here, tex_override=None):
    tex = (
        tex_override
        if tex_override is not None
        else (here / "TrafficTwin_Dissertation.tex").read_text()
    )
    original = baseline_bytes(here, "TrafficTwin_Dissertation.tex").decode()
    raw = (here / "evidence/EXEMPLAR_OPERATIONS_2026-09-16.json").read_bytes()
    ledger = json.loads(raw)
    results = {
        "exemplar_ledger_hash": digest(raw) == LEDGER_SHA256,
        "exemplar_tex_hash": digest(tex.encode()) == TEX_SHA256,
        "exemplar_exact_baseline": digest(original.encode()) == ledger["baseline_tex_sha256"],
        "exemplar_markdown_preserved": (here / "TrafficTwin_Dissertation.md").read_bytes()
        == baseline_bytes(here, "TrafficTwin_Dissertation.md"),
    }
    results.update(
        {
            "exemplar_artifact_" + name: digest((here / name).read_bytes()) == value
            for name, value in ledger["artifact_sha256"].items()
        }
    )
    restored = tex
    valid = True
    for op in reversed(ledger["operations"]):
        if not op["new"] or restored.count(op["new"]) != 1:
            valid = False
            break
        restored = restored.replace(op["new"], op["old"], 1)
    results["exemplar_only_recorded_tex_operations"] = valid and restored == original
    results["exemplar_glossary_present"] = (
        r"\section*{Glossary}" in tex and r"\addcontentsline{toc}{section}{Glossary}" in tex
    )
    glossary = tex.split(r"\section*{Glossary}", 1)[-1].split(r"\clearpage", 1)[0]
    results["exemplar_glossary_nineteen_sourced_sentences"] = (
        len(re.findall(r"\\item\[", glossary)) == 19
        and len(re.findall(r"\[Section~\\ref\{sec:[^}]+\}\]", glossary)) == 19
    )
    source = json.loads((here / "evidence/EXEMPLAR_SOURCES_2026-09-16.json").read_text())
    copyright_section = tex.split(r"\section*{Copyright statement}", 1)[-1].split(
        r"\end{enumerate}", 1
    )[0]
    copyright_section = re.sub(r"\\url\{([^}]+)\}", r"\1", copyright_section)
    actual = re.findall(r"\\item\[\((i|ii|iii|iv)\)\]\s+(.*?)(?=\n\n|$)", copyright_section, re.S)
    results["exemplar_copyright_i_to_iv_verbatim"] = actual == [
        (label, body) for label, body in source["copyright_clauses"]
    ]
    def declaration(text):
        return text.split(r"\section*{Declaration}", 1)[1].split(r"\clearpage", 1)[
            0
        ]
    results["exemplar_declaration_unchanged"] = declaration(tex) == declaration(original)
    results["exemplar_abstract_only_authorised_provenance_change"] = all(
        block(tex, n) == block(original, n) for n in (3, 4, 5)
    ) and block(tex, 6) == block(original, 6).replace(
        "one calibrated Manchester network", "one demand-scaled Manchester network"
    )
    results["exemplar_environment_table_present"] = (
        r"\label{tab:environment}" in tex and r"\caption[Execution environment]" in tex
    )
    results["exemplar_environment_values_bound"] = all(
        value in tex for value in source["environment_tex_values"]
    )
    results["exemplar_access_appendix_present"] = (
        r"\appendixsection{app:H}{Artefact access and verification}" in tex
        and r"AUTHOR\_ACTION: access mechanism" in tex
    )
    results["exemplar_no_path_with_spaces"] = not re.search(r"\\path\{[^}]*\s[^}]*\}", tex)
    refs = tex.split(r"\begin{thebibliography}", 1)[1].split(r"\end{thebibliography}", 1)[0]
    oldrefs = original.split(r"\begin{thebibliography}", 1)[1].split(r"\end{thebibliography}", 1)[0]
    results["exemplar_no_bibliography_access_tags"] = not re.search(
        r"\}(?:\{(?:Source|Author manuscript[^}]*|Proceedings paper|Publisher record|Proceedings record|Author technical manuscript|DLR author repository|Primary document|Benchmarking guidance)\})|(?:^|[. ])(?:Source|Author manuscript|Proceedings paper|Publisher record|Proceedings record|Author technical manuscript|DLR author repository|Primary document|Benchmarking guidance)\.",
        refs,
        re.M,
    )
    def urls(value):
        return Counter(re.findall(r"\\href\{\\detokenize\{([^}]+)\}\}", value))
    results["exemplar_bibliography_all_links_preserved"] = urls(refs) == urls(oldrefs)
    results["exemplar_web_access_dates_preserved"] = all(
        re.search(r"\\bibitem\{ref" + str(n) + r"\}[^\n]*Accessed \d+ September 2026", refs)
        for n in (35, 42, 43, 44)
    )
    results["exemplar_no_calibrated_network_or_simulation"] = not re.search(
        r"calibrated(?:\s+\w+){0,3}\s+(?:network|simulation)", tex, re.I
    )
    results["exemplar_jax_citation_version_year"] = (
        "Software, version 0.4.30, 2024 (first released 2018)" in refs
    )
    results["exemplar_setting_precedes_results_verbatim"] = block(tex, 142) == block(
        original, 143
    ) and block(tex, 143) == block(original, 142)
    results["exemplar_table2_sumo_row"] = (
        r"SUMO version (source study) & 1.27.0 \cite{ref47} & 1.27.0 \cite{ref47}" in tex
    )
    before, after = calculate()
    counts = json.loads((here / "document/WORD_COUNT.json").read_text())
    results["exemplar_both_counts_match_tooling"] = after == {
        "strict": counts["words"],
        "prose_only": counts["prose_only_words"],
    }
    blocks = json.loads((here / "document/SOURCE_MAP.json").read_text())["blocks"]
    # Isolate F.6/F.7 from the other requested changes in the shared Table 8 block.
    provenance = {
        k: v
        for k, v in ledger["count_source_overrides"].items()
        if k in ("6", "13", "61", "64", "152", "180")
    }
    provenance["180"] = re.sub(
        r"Appendix [A-Z] checks", "Portable compact checks", provenance["180"]
    )
    results["exemplar_F6_F7_at_most_45_strict_words"] = (
        count(blocks, provenance)["strict"] - before["strict"] <= 45
    )
    opener = ledger["count_source_overrides"]["183"]
    results["exemplar_conclusion_opener_bounded"] = (
        len(re.findall(r"[\w]+(?:[’'-][\w]+)*", opener)) <= 110
        and ledger["count_source_overrides"]["184"] == ""
    )
    results["exemplar_frontmatter_appendices_excluded_from_count"] = "Glossary" not in "\n".join(
        ledger["count_source_overrides"].values()
    )
    commands = json.loads((here / "evidence/EXEMPLAR_COMMANDS_2026-09-16.json").read_text())
    results["exemplar_three_commands_once_read_only"] = (
        len(commands["commands"]) == 3
        and all(x["exit_status"] == 0 for x in commands["commands"])
        and commands["scratch_source_files_unchanged"]
        and commands["external_package_files_unchanged"]
        and commands["research_workloads_launched"] == 0
    )
    results["exemplar_platform_health"] = commands["commands"][1]["health"] == {
        "status": 200,
        "body": "ok",
    }
    capture = json.loads((here / "evidence/FINAL_PLATFORM_CAPTURE_2026-09-16.json").read_text())
    oldcapture = json.loads(baseline_bytes(here, "evidence/FINAL_PLATFORM_CAPTURE_2026-09-16.json"))
    results["exemplar_screenshots_not_recaptured"] = all(
        digest((here / name).read_bytes()) == value
        for name, value in oldcapture["files"].items()
        if "/shots/" in name and name.endswith(".png")
    )
    results["exemplar_figure_split_and_caption"] = capture["figure_split"] and all(
        x in tex
        for x in [
            r"\label{fig:7b}",
            "onehot17 versus capscalar13",
            "original interface captures, no simulated UI",
        ]
    )
    results["exemplar_gate_three_remains_open"] = (
        "AUTHOR_ACTION: access mechanism" in (here / "SUBMISSION_GATES.md").read_text()
    )
    return results


def checks(here, tex_override=None):
    """Keep the historical exemplar receipt and validate the live prose overlay.

    The old whole-source hash belongs to cf8b514; it must not be treated as a
    live-source check after an authorised LaTeX-only pass. Live checks require
    the explicitly selected local review PDF and its build source/log.
    """
    from validate_prose_pass import baseline, pdf_checks
    from validate_prose_pass import checks as prose_checks

    results = {
        "historical_" + key: value
        for key, value in historical_exemplar_checks(here, tex_override=baseline()).items()
    }
    results.update(prose_checks(here, tex_override=tex_override))
    results.update(pdf_checks(review_pdf_path(here), tex=tex_override))
    return results
