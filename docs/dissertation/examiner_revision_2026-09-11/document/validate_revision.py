"""Check an additive editorial revision against preserved source and receipts."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import fitz
from markdown_it import MarkdownIt

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
OLD = ROOT / "docs/dissertation/editorial_final_2026-09-09"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(text: str) -> dict[str, list[str]]:
    """Preserve exact table rows while allowing captions and numbering to change."""
    output = {}
    parts = re.split(r"(?m)^\*Table ([A-E]?\d+)\.", text)
    for index in range(1, len(parts), 2):
        number, following = parts[index : index + 2]
        lines = following.splitlines()
        start = next((i for i, line in enumerate(lines) if line.startswith("|")), None)
        if start is None:
            continue
        rows = []
        for line in lines[start:]:
            if not line.startswith("|"):
                break
            rows.append(line)
        output[number] = rows
    return output


def main() -> None:
    original = (OLD / "TrafficTwin_Dissertation.md").read_text()
    revised = (HERE / "TrafficTwin_Dissertation.md").read_text()
    oldmap = json.loads((OLD / "document/SOURCE_MAP.json").read_text())
    newmap = json.loads((HERE / "document/SOURCE_MAP.json").read_text())
    before, after = tables(original), tables(revised)
    mapping = {
        "1": "1",
        "2": "2",
        "3": "3",
        "4": "4",
        "5": "5",
        "6": "6",
        "7": "7",
        "8": "C2",
        "9": "C3",
        "10": "8",
        "B2": "B2",
        "C1": "C1",
        "D1": "D1",
        "E1": "E1",
        "E2": "E2",
    }
    checks = {f"table_{a}_to_{b}_rows_unchanged": before[a] == after[b] for a, b in mapping.items()}
    checks["abstract_unchanged"] = (
        original.split("## Abstract\n", 1)[1].split("## 1.", 1)[0].strip()
        == revised.split("## Abstract\n", 1)[1].split("## 1.", 1)[0].strip()
    )
    proposition = re.search(r"(?m)^\*\*Proposition 1 .*", original)
    checks["proposition_statement_unchanged"] = (
        proposition is not None and proposition[0] in revised
    )
    checks["algorithms_unchanged"] = oldmap["algorithms"] == newmap["algorithms"]
    checks["equations_unchanged"] = oldmap["equations"] == newmap["equations"]
    for asset in sorted((OLD / "assets").glob("*.svg")):
        checks[f"preserved_svg_{asset.stem}"] = sha(asset) == sha(HERE / "assets" / asset.name)
    checks["three_research_questions"] = len(re.findall(r"\*\*RQ[123]:", revised)) == 3
    checks["no_rq4"] = "RQ4" not in revised
    checks["twenty_five_references"] = len(newmap["bibkeys"]) == 25
    captions = re.findall(r"(?m)^\*(?:Figure|Table) .*", revised)
    checks["every_caption_has_reading"] = all("Reading:" in c for c in captions)
    checks["no_editorial_ownership_placeholders_in_body"] = all(
        phrase not in revised for phrase in ["for author review", "still require the candidate's"]
    )
    count = json.loads((HERE / "document/WORD_COUNT.json").read_text())["words"]
    checks["word_count_in_range"] = 7000 <= count <= 9000
    parser = MarkdownIt("commonmark").enable("table")
    missing = []
    anchors = set(re.findall(r'<a id="([^"]+)"', revised))
    for token in parser.parse(revised):
        for child in token.children or []:
            if child.type not in ("link_open", "image"):
                continue
            target = child.attrGet("href") or child.attrGet("src") or ""
            if target.startswith(("http://", "https://")):
                continue
            if target.startswith("#"):
                if target[1:] not in anchors:
                    missing.append(target)
            elif not (HERE / target.partition("#")[0]).exists():
                missing.append(target)
    checks["manuscript_links_resolve"] = not missing
    pdf = fitz.open(HERE / "TrafficTwin_Dissertation.pdf")
    pdftext = "\n".join(page.get_text() for page in pdf)
    log = (HERE / "TrafficTwin_Dissertation.log").read_text(errors="replace")
    checks["no_overfull_boxes"] = "Overfull \\" not in log
    checks["no_missing_glyphs"] = "Missing character:" not in log
    checks["no_undefined_references"] = "undefined references" not in log.lower()
    checks["pdf_has_disclosure"] = "Assistance and attribution" in pdftext
    checks["pdf_has_expected_figures"] = all(f"Figure {n}:" in pdftext for n in range(1, 9))
    # Reproducible lexical diagnostic only, not a semantic quality score.
    sentences = []
    for block in newmap["blocks"]:
        if block["kind"] == "bibliography_open":
            break
        if block["kind"] != "paragraph":
            continue
        text = re.sub(r"\[\[.*?\]\]\(.*?\)", "", block["source"])
        ending = re.split(r"(?<=[.!?])\s+", text.strip())[-1]
        flagged = bool(
            re.search(
                r"\b(not|neither|cannot|without|limit\w*|restrict\w*|unresolved|uncertain\w*|"
                r"conditional|unavailable|ambigu\w*|unrun)\b",
                ending,
                re.I,
            )
        )
        sentences.append({"source_block": block["id"], "ending": ending, "flagged": flagged})
    flag_count = sum(item["flagged"] for item in sentences)
    record = {
        "base_commit": "1e01b755b8b633f43c9c7bb6fdd0d75beb6469e8",
        "checks": checks,
        "passed": all(checks.values()),
        "missing_links": missing,
        "words": count,
        "pages": len(pdf),
        "captions": len(captions),
        "hashes": {
            name: sha(HERE / name)
            for name in [
                "TrafficTwin_Dissertation.md",
                "TrafficTwin_Dissertation.tex",
                "TrafficTwin_Dissertation.pdf",
            ]
        },
        "ending_audit": {
            "method": "Lexical screen of final prose sentence; not semantic grading",
            "paragraphs": len(sentences),
            "flagged": flag_count,
            "flagged_percent": 100 * flag_count / max(len(sentences), 1),
        },
        "not_certified": [
            "author independent verification",
            "assessment AI permission",
            "signed institutional declarations",
            "incident geographic layout",
            "off-machine raw backup",
            "recorded assessed video",
            "full-text review of both newly cited Fan papers",
            "independent exact-SHA review",
            "full regression-suite pass",
        ],
    }
    (HERE / "document/ENDING_AUDIT.json").write_text(json.dumps(sentences, indent=2) + "\n")
    (HERE / "document/REVISION_VALIDATION.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
