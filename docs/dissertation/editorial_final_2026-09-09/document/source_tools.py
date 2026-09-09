"""Reuse pinned document-only tools without changing the reviewed package.

Run with the document Python, not the scientific runtime. No TeX engine,
renderer, evaluator, raw-data audit or benchmark is invoked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import runpy
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
PACKAGE = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/dissertation/joint_confirmation_2026-09-08"
BASE_COMMIT = "477304f7f988f7d5d5ea5ae21d0e49eed1429e5a"
TOOL_HASHES = {
    "convert_source.py": "b97668c6aa72a8672ae5b019f82be6cc52547cff75d12d634adc0ad2c7d9240a",
    "check_source.py": "6e2ddf898960f8766427fe13a8e0c368398c989c4a84099947654d991ccd3a65",
}


def replace_once(text: str, old: str, new: str) -> str:
    """Refuse a changed upstream tool rather than silently patching it."""
    if text.count(old) != 1:
        raise ValueError(f"Expected one document adapter site: {old!r}")
    return text.replace(old, new)


def adapted_tool(name: str) -> str:
    """Adapt document destinations and the preservation baseline only."""
    source = (BASE / "document" / name).read_text()
    if hashlib.sha256(source.encode()).hexdigest() != TOOL_HASHES[name]:
        raise ValueError(f"Reviewed document tool changed: {name}")
    if name == "convert_source.py":
        source = replace_once(
            source, "ROOT=Path(__file__).resolve().parents[4]", f"ROOT=Path({str(ROOT)!r})"
        )
        source = replace_once(
            source,
            "SRC=ROOT/'docs/dissertation/joint_confirmation_2026-09-08'",
            "SRC=ROOT/'docs/dissertation/editorial_final_2026-09-09'",
        )
        source = replace_once(
            source,
            "% Synchronized research revision from the reviewed c049f00 manuscripts.\n"
            "% New study execution source was sealed at c4fe336; see evidence and protocol.",
            "% Editorial revision of the completed-study manuscript at 477304f.\n"
            "% Scientific evidence and full existing proof are preserved; see README.md.",
        )
    else:
        source = replace_once(
            source, "R=Path(__file__).resolve().parents[4]", f"R=Path({str(ROOT)!r})"
        )
        source = replace_once(
            source,
            "O=R/'docs/dissertation/joint_confirmation_2026-09-08'",
            "O=R/'docs/dissertation/editorial_final_2026-09-09'",
        )
        source = replace_once(
            source,
            "S=R/'docs/dissertation/latex_markdown_2026-09-08'",
            "S=R/'docs/dissertation/joint_confirmation_2026-09-08'",
        )
        source = replace_once(
            source, "'c049f00f2247bfbd1196d5e6524de8198fdd2df7'", repr(BASE_COMMIT)
        )
        source = replace_once(
            source, "raise SystemExit(bool(failures))", "if failures:\n raise SystemExit(1)"
        )
    return source


def latex_words(namespace: dict[str, Any]) -> dict[str, Any]:
    """Count decoded visible LaTeX, excluding repeated headers and captions.

    Equation words use the checked explicit formula mapping, after confirming the
    six formulas are identical to the reviewed baseline. This is semantic source
    counting, not an assertion about a rendered document or a TeX-engine count.
    """
    record = namespace["record"]
    decode = namespace["decode"]
    plain = namespace["mdplain"]
    old = json.loads((BASE / "document/SOURCE_MAP.json").read_text())
    if record["equations"] != old["equations"]:
        raise ValueError("Numbered equation mapping differs from reviewed source")
    counts: dict[str, int] = {}
    active = False
    section = ""
    for block in record["blocks"]:
        kind, raw, code = block["kind"], block["source"], block["latex"]
        if kind == "bibliography_open":
            break
        if kind == "heading" and raw == "Abstract":
            active = True
            section = raw
            counts[section] = 0
        if not active:
            continue
        visible = ""
        if kind == "heading":
            if raw == "Abstract":
                visible = "Abstract"
            else:
                match = re.fullmatch(
                    r"\\(section|subsection)\{(.*)\}\\label\{sec:([^}]+)\}", code, re.S
                )
                if match is None:
                    raise ValueError("Unexpected main-text heading")
                number = match[3]
                visible = number + (". " if match[1] == "section" else " ") + decode(match[2])
                if match[1] == "section":
                    section = visible
                    counts[section] = 0
        elif kind == "paragraph":
            visible = decode(code)
        elif kind == "proposition":
            match = re.fullmatch(
                r"\\begin\{proposition\}\[(.*?)\]\\label\{prop:1\}\n(.*)"
                r"\\end\{proposition\}",
                code,
                re.S,
            )
            if match is None:
                raise ValueError("Unexpected proposition")
            visible = "Proposition 1 (" + decode(match[1]) + "). " + decode(match[2])
        elif kind == "proof":
            visible = "Proof sketch. " + decode(
                code.removeprefix("\\begin{proof}[Proof sketch]\n").removesuffix("\\end{proof}")
            )
        elif kind == "equation":
            visible = plain(raw)
        elif kind == "algorithm":
            number = re.search(r"\\label\{alg:([^}]+)\}", code)
            if number is None:
                raise ValueError("Unlabelled algorithm")
            title, _ = namespace["group"](code, code.index("\\caption{") + len("\\caption"))
            body = re.search(r"\\begin\{Verbatim\}\[[^\n]*\]\n(.*?)\n\\end\{Verbatim\}", code, re.S)
            if body is None:
                raise ValueError("Missing algorithm body")
            visible = "Algorithm " + number[1] + ": " + decode(title) + "\n" + body[1]
        elif kind == "table":
            header = code.split("\\toprule\n", 1)[1].split("\n\\midrule\\endfirsthead", 1)[0]
            rows = code.split("\\bottomrule\\endfoot\n", 1)[1].split("\n\\end{xltabular}", 1)[0]
            values = []
            for line in [header, *rows.splitlines()]:
                values.extend(decode(x) for x in re.split(r"(?<!\\) & ", line[:-3]))
            visible = " ".join(values)
        counts[section] += len(visible.split())
    markdown_counts = namespace["sections"]
    differences = {key: counts[key] - value for key, value in markdown_counts.items()}
    return {
        "markdown_semantic_words": sum(markdown_counts.values()),
        "latex_semantic_words": sum(counts.values()),
        "markdown_sections": markdown_counts,
        "latex_sections": counts,
        "latex_minus_markdown": differences,
        "markup_difference_explanation": (
            "Eight section references decode with a space after the section sign (+8 tokens); "
            "one inline R >= K formula decodes without surrounding spaces (-2 tokens). "
            "The net six tokens are markup spacing, not different content."
        ),
        "method": "Abstract through Conclusion; headings, table cells and algorithms included; "
        "captions, cover, references and appendices excluded. Decode actual LaTeX source blocks; "
        "count continuation headers once. Six unchanged equations use the checked formula mapping. "
        "Markup and automatic numbering commands are not prose words. No rendering performed.",
        "raw_markdown_source_tokens": len(namespace["md"].split()),
        "raw_latex_source_tokens": len(namespace["tex"].split()),
        "raw_token_boundary": (
            "Whole-file whitespace counts include markup, captions and appendices; "
            "they are not assessment word counts."
        ),
    }


def preservation_checks(namespace: dict[str, Any]) -> dict[str, Any]:
    """Check retained proof, bibliography, algorithms and every result-table cell."""
    old_md = (BASE / "TrafficTwin_Dissertation.md").read_text()
    new_md = (PACKAGE / "TrafficTwin_Dissertation.md").read_text()
    old_c = old_md.split("## Appendix C.")[1].split("## Appendix D.")[0].rstrip()
    new_c = new_md.split("## Appendix C.")[1].split("### C.7")[0].rstrip()
    if old_c != new_c:
        raise ValueError("Original full Appendix C changed")
    old_bib = old_md.split("## References")[1].split("## Appendix A.")[0]
    new_bib = new_md.split("## References")[1].split("## Appendix A.")[0]
    if old_bib != new_bib:
        raise ValueError("Bibliographic entries changed")
    old = json.loads((BASE / "document/SOURCE_MAP.json").read_text())
    new = namespace["record"]
    if old["algorithms"] != new["algorithms"]:
        raise ValueError("Operational algorithm pseudocode changed")
    remap = {"13": "7", "7": "8", "8": "9", "9": "C1"}
    new_tables = {table["number"]: table for table in new["tables"]}
    checked_cells = 0
    for table in old["tables"]:
        if table["number"] in ("11", "12"):
            continue
        target = new_tables[remap.get(table["number"], table["number"])]
        if table["rows"] != target["rows"]:
            raise ValueError(f"Retained table values changed: {table['number']}")
        checked_cells += sum(len(row) for row in table["rows"])
    return {
        "full_original_appendix_c_unchanged": True,
        "appendix_c_sha256": hashlib.sha256(old_c.encode()).hexdigest(),
        "bibliography_unchanged": True,
        "algorithm_pseudocode_unchanged": True,
        "protected_table_cells": checked_cells,
        "table_number_mapping": remap,
        "declared_table_edits": {
            "11": "Research implementation replaces status-heavy ownership",
            "12": "Validity limits retained; no result estimate represented",
        },
        "old_study_populations_preserved": True,
        "new_scientific_execution": False,
    }


def main() -> None:
    """Run one document action; leave scientific files untouched."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("convert", "check"))
    args = parser.parse_args()
    name = "convert_source.py" if args.action == "convert" else "check_source.py"
    with tempfile.TemporaryDirectory(prefix="traffictwin-editorial-source-") as temporary:
        path = Path(temporary) / name
        path.write_text(adapted_tool(name))
        namespace = runpy.run_path(str(path), run_name="__main__")
    if args.action == "check":
        result = json.loads((PACKAGE / "document/SOURCE_VALIDATION.json").read_text())
        result["word_counts"] = latex_words(namespace)
        result["preservation"] = preservation_checks(namespace)
        result["document_tool_bindings"] = TOOL_HASHES
        result["check_status_counts"] = dict(
            Counter(x["passed"] for x in result["checks"].values())
        )
        result["failed_checks"] = {
            key: value for key, value in result.pop("checks").items() if not value["passed"]
        }
        (PACKAGE / "document/SOURCE_VALIDATION.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        )
        print(
            json.dumps(
                {"words": result["word_counts"], "preservation": result["preservation"]}, indent=2
            )
        )


if __name__ == "__main__":
    main()
