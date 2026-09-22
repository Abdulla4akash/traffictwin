"""Use the existing WORD_COUNT tokenisation on a TeX-bound source-block projection.

The Markdown remains the ded54bd historical draft. The operation ledger records
only the changed counted blocks; front matter, captions, references and appendices
retain the original exclusions. Never run convert_source.py over the edited TeX.
"""

from pathlib import Path
import hashlib
import json
import re
from markdown_it import MarkdownIt

HERE = Path(__file__).resolve().parents[1]
PARSER = MarkdownIt("commonmark").enable("table")
KINDS = {"paragraph", "heading", "proposition", "proof", "equation", "algorithm", "table"}


def count(blocks, overrides=None):
    strict = []
    prose = []
    overrides = overrides or {}
    for block in blocks:
        if block["kind"] == "bibliography_open" or (
            block["kind"] == "heading" and block["source"] == "References"
        ):
            break
        if block["kind"] not in KINDS:
            continue
        source = overrides.get(str(block["id"]), block["source"])
        if block["kind"] == "table":
            source = source.split("\n", 1)[1]
        for token in PARSER.parse(source):
            if token.type == "inline":
                visible = "".join(
                    c.content
                    if c.type in ("text", "code_inline")
                    else "\n"
                    if c.type in ("softbreak", "hardbreak")
                    else ""
                    for c in token.children or []
                )
                strict.append(visible)
                if block["kind"] not in ("table", "algorithm"):
                    prose.append(visible)
            elif token.type == "fence":
                strict.append(token.content)
    words = lambda rows: len(re.findall(r"[\w]+(?:[’'-][\w]+)*", " ".join(rows)))
    return {"strict": words(strict), "prose_only": words(prose)}


def calculate():
    ledger = json.loads((HERE / "evidence/EXEMPLAR_OPERATIONS_2026-09-16.json").read_text())
    blocks = json.loads((HERE / "document/SOURCE_MAP.json").read_text())["blocks"]
    before = count(blocks)
    assert before == {"strict": 9555, "prose_only": 8136}, before
    after = count(blocks, ledger["count_source_overrides"])
    return before, after


if __name__ == "__main__":
    before, after = calculate()
    path = HERE / "document/WORD_COUNT.json"
    record = json.loads(path.read_text())
    record.update(
        words=after["strict"], headline_words=after["strict"], prose_only_words=after["prose_only"]
    )
    record["latex_only_overlay"] = {
        "baseline_commit": "ded54bd",
        "before": before,
        "after": after,
        "projection": "evidence/EXEMPLAR_OPERATIONS_2026-09-16.json#count_source_overrides",
        "tool": "document/count_exemplar_words.py",
        "tokenisation": "Unchanged from document/convert_source.py; abstract header is excluded front matter.",
    }
    path.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"before": before, "after": after}))
