"""Reproduce the cf8b514 prose/layout pass without modifying historical receipts.

Word counts use the existing source-block count and exclusions. Only changed
counted blocks are projected back from TeX; the original formula spelling is
recovered from the converter AST without importing/executing the converter.
"""

import ast
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

from count_exemplar_words import count

BASE = "cf8b514f9cb80ba75de5e15452fa6b8af539834b"
PACKAGE = "docs/dissertation/examiner_revision_2026-09-11"
HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
TOKEN = r"[\w]+(?:[’'-][\w]+)*"
BLOCK = r"% BEGIN SOURCE BLOCK (\d+) (\w+)\n(.*?)\n% END SOURCE BLOCK \d+"
TAG = r"\\hyperref\[source-s(\d+)\]\{\[S\d+\]\}"


def baseline(name="TrafficTwin_Dissertation.tex"):
    return subprocess.check_output(["git", "show", f"{BASE}:{PACKAGE}/{name}"], cwd=ROOT).decode()


def blocks(tex):
    return {int(n): (kind, value) for n, kind, value in re.findall(BLOCK, tex, re.S)}


def body(tex):
    return tex.split(r"\section{Introduction}", 1)[1].split(r"\begin{thebibliography}", 1)[0]


def projection(value):
    tree = ast.parse((HERE / "document/convert_source.py").read_text())
    mathmap = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "mathmap" for t in node.targets
        ):
            mathmap.update(ast.literal_eval(node.value))
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "mathmap"
                and call.func.attr == "update"
            ):
                mathmap.update(ast.literal_eval(call.args[0]))
    for old, new in sorted(mathmap.items(), key=lambda pair: -len(pair[1])):
        value = value.replace("$" + new + "$", old)
    value = re.sub(r"\\href\{\\detokenize\{[^}]*\}\}\{([^}]*)\}", r"\1", value)
    value = re.sub(r"\\hyperref\[[^]]*\]\{([^}]*)\}", r"\1", value)
    value = re.sub(
        r"\\cite\{([^}]+)\}",
        lambda m: ", ".join("[" + x.removeprefix("ref") + "]" for x in m[1].split(",")),
        value,
    )
    value = re.sub(
        r"\\(?:eqref|ref)\{[^}:]+:([^}]+)\}", lambda m: "G" if m[1] == "H" else m[1], value
    )
    value = re.sub(r"\\label\{[^}]+\}", "", value)
    value = value.replace(r"\FloatBarrier", "")
    value = re.sub(r"\\(?:subsection|section)\*?\{([^}]+)\}", r"\1", value)
    value = value.replace(r"\S\,", "§ ")
    value = value.replace(r"\ensuremath{-}", "−").replace(r"\ensuremath{\times}", "×")
    value = value.replace(r"$10^{-5}$", "10⁻⁵")
    for _ in range(3):
        value = re.sub(
            r"\\(?:textbf|texttt|emph|path|text|mathrm|operatorname)\{([^{}]*)\}", r"\1", value
        )
    value = value.replace(r"\%", "%").replace(r"\_", "_").replace("~", " ")
    value = value.replace("---", "—").replace("--", "–").replace("``", "“").replace("''", "”")
    value = value.replace("$", "").replace(r"\,", " ")
    return value.strip()


def word_counts(tex=None):
    tex = tex if tex is not None else (HERE / "TrafficTwin_Dissertation.tex").read_text()
    original = baseline()
    original_blocks, current_blocks = blocks(original), blocks(tex)
    source = json.loads((HERE / "document/SOURCE_MAP.json").read_text())["blocks"]
    overrides = json.loads((HERE / "evidence/EXEMPLAR_OPERATIONS_2026-09-16.json").read_text())[
        "count_source_overrides"
    ].copy()
    before = count(source, overrides)
    assert before == {"strict": 9605, "prose_only": 8174}, before
    deltas = []
    for number, (kind, old) in original_blocks.items():
        if number >= 206 or kind not in {
            "paragraph",
            "heading",
            "proposition",
            "proof",
            "equation",
            "algorithm",
            "table",
        }:
            continue
        new = current_blocks[number][1]
        if old == new or kind == "table":
            continue  # Only captions changed in the existing tables; those are excluded.
        # An inserted paragraph in block 41 is deliberately counted as prose.
        previous = overrides.get(
            str(number), next(b["source"] for b in source if b["id"] == number)
        )
        projected_old, projected_new = projection(old), projection(new)
        old_count = count([{"id": number, "kind": kind, "source": projected_old}])
        previous_count = count([{"id": number, "kind": kind, "source": previous}])
        # Preserve the original equation/notation spelling through a checked delta.
        # Baseline projection differences are reported, never silently rebased.
        new_count = count([{"id": number, "kind": kind, "source": projected_new}])
        deltas.append(
            {
                "block": number,
                "kind": kind,
                "baseline_projection_difference": old_count["strict"] - previous_count["strict"],
                "strict_delta": new_count["strict"] - old_count["strict"],
                "prose_delta": new_count["prose_only"] - old_count["prose_only"],
            }
        )
    study = tex.split("% BEGIN PROSE STUDY MAP", 1)[1].split("% END PROSE STUDY MAP", 1)[0]
    study = study.split(r"\toprule", 1)[1].split(r"\bottomrule", 1)[0]
    study = study.replace(r"\midrule", "").replace(r"\\", "\n").replace("&", " ")
    study_words = len(re.findall(TOKEN, projection(study)))
    after = {
        "strict": before["strict"] + sum(x["strict_delta"] for x in deltas) + study_words,
        "prose_only": before["prose_only"] + sum(x["prose_delta"] for x in deltas),
    }
    return {
        "before": before,
        "after": after,
        "deltas": deltas,
        "study_map_words": study_words,
        "method": "Existing count_exemplar_words tokenisation/exclusions; cf8b514 source-block baseline plus checked TeX-projection word deltas, with the new Study map counted only in strict.",
    }


def hedge_counts(text):
    return {
        name: len(re.findall(pattern, text, re.I))
        for name, pattern in {
            "negative": r"\b(?:does not|do not|did not|cannot|neither)\b",
            "not_word": r"\bnot\s+\w+",
            "rather_than": r"\brather than\b",
            "remains": r"\bremains?\b",
            "remain_family": r"\bremain(?:s|ed|ing)?\b",
        }.items()
    }


def prose_metrics(tex):
    paragraphs = {
        n: projection(v) for n, (k, v) in blocks(tex).items() if 7 <= n <= 205 and k == "paragraph"
    }
    captions = {}
    for n, (kind, value) in blocks(tex).items():
        if 7 <= n <= 205 and kind in ("figure", "table"):
            matches = re.findall(r"\\caption\[[^\n]+?\]\{(.*)\}\\label", value)
            for index, text in enumerate(matches):
                captions[f"{n}-caption-{index + 1}"] = projection(text)
    sentences = []
    for n, text in (paragraphs | captions).items():
        text = re.sub(r"\[(?:S)?\d+\]", "", text).replace("et al.", "et al·")
        text = re.sub(r"\b([A-Z])\.(?=\s)", r"\1·", text)
        # Bold run-in labels do not add a separate sentence or inflate its length.
        text = re.sub(r"^(?:Setting|Results|Remark|C[1-6])\.\s*", "", text)
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9]|\([a-z]\))", text):
            words = len(re.findall(TOKEN, sentence))
            if words > 35:
                clauses = re.sub(r"\([^()]*\)", "", sentence)
                sentences.append(
                    {
                        "block": n,
                        "words": words,
                        "joined": bool(re.search(r";|\b(?:while|whereas|which)\b", clauses)),
                        "text": sentence,
                    }
                )
    # Count code mentions only in visible prose; labels such as tab:E1 are excluded.
    codes = Counter(re.findall(r"\bE(?:0|1|2[bcd]?|3)\b", " ".join(paragraphs.values())))
    return {
        "hedges": hedge_counts(projection(body(tex))),
        "codes": dict(codes),
        "code_total": sum(codes.values()),
        "sentences_over_35": len(sentences),
        "joined_over_35": [x for x in sentences if x["joined"]],
        "long_sentences": sentences,
    }


def table_environments(tex):
    return re.findall(r"\\begin\{(tabular\*?|tabularx|xltabular)\}(.*?)\\end\{\1\}", tex, re.S)


def checks(here=HERE, tex_override=None):
    tex = (
        tex_override
        if tex_override is not None
        else (here / "TrafficTwin_Dissertation.tex").read_text()
    )
    old = baseline()
    result = {}
    old_blocks, current = blocks(old), blocks(tex)

    # Literal table payloads, including all numeric precision, must survive unchanged.
    def table_payload(s):
        return s.split(r"\toprule", 1)[1] if r"\toprule" in s else s

    new_without_map = re.sub(
        r"% BEGIN PROSE STUDY MAP.*?% END PROSE STUDY MAP", "", tex, flags=re.S
    )
    old_tables, new_tables = table_environments(old), table_environments(new_without_map)
    result["prose_existing_table_payloads_byte_identical"] = len(old_tables) == len(
        new_tables
    ) and all(
        a == c and table_payload(b) == table_payload(d)
        for (a, b), (c, d) in zip(old_tables, new_tables)
    )

    # Extract numeric tokens from every old environment (caption included); ignore TeX labels and source links.
    def numeric(s):
        return re.findall(
            r"(?<![\w.])[-+]?\d+(?:[,.]\d+)*(?![\w.])",
            re.sub(r"\\(?:label|ref|hyperref)(?:\[[^]]*\])?\{[^}]*\}", "", s),
        )

    result["prose_existing_table_numeric_tokens_byte_identical"] = len(old_tables) == len(
        new_tables
    ) and all(numeric(b) == numeric(d) for (_, b), (_, d) in zip(old_tables, new_tables))
    result["prose_all_fifty_source_tags_preserved"] = (
        Counter(re.findall(TAG, body(tex))) == Counter(re.findall(TAG, body(old)))
        and len(re.findall(TAG, body(tex))) == 50
    )
    tags_at_end = True
    for n, (kind, value) in current.items():
        if not 7 <= n <= 205 or kind not in ("paragraph", "figure", "table"):
            continue
        if kind != "paragraph":
            match = re.search(r"\\caption\[[^\n]+?\]\{(.*)\}\\label", value)
            value = match[1] if match else ""
        hits = list(re.finditer(TAG, value))
        if hits:
            suffix = re.sub(TAG, "", value[hits[0].start() :])
            tags_at_end &= not re.sub(r"[\s.,–-]", "", suffix) and [
                int(m[1]) for m in hits
            ] == sorted(int(m[1]) for m in hits)
    result["prose_source_tags_at_paragraph_ends_in_order"] = bool(tags_at_end)
    citations = {
        key for group in re.findall(r"\\cite\{([^}]+)\}", body(tex)) for key in group.split(",")
    }
    result["prose_all_bibliography_keys_cited_in_body"] = (
        set(re.findall(r"\\bibitem\{([^}]+)\}", tex)) <= citations
    )
    seen = set()
    named_once = True
    for number, (kind, value) in current.items():
        if not 7 <= number <= 205:
            continue
        if kind == "heading":
            seen = set()
        if kind != "paragraph":
            continue
        visible = re.sub(r"\\(?:ref|eqref|label)\{[^}]*\}", "", value)
        for match in re.finditer(r"\bE(?:0|1|2[bcd]?|3)\b", visible):
            named_once &= (
                visible[match.start() - 1 : match.start()] == "("
                and visible[match.end() : match.end() + 1] == ")"
                and match[0] not in seen
            )
            seen.add(match[0])
    result["prose_codes_only_parenthesised_first_section_mentions"] = bool(named_once)
    preview = current[41][1].split(r"\textbf{Contributions.}", 1)[0].strip()
    result["prose_result_preview_three_sentences_under_60"] = (
        len(re.findall(TOKEN, projection(preview))) <= 60
        and len(re.findall(r"\.\s+(?=[A-Z])|\.$", preview)) == 3
        and all(number in preview for number in ("3.5", "4.1", "0.6"))
    )
    offered, successes = [], {}
    for line in current[388][1].splitlines():
        cells = [cell.strip().replace("$", "") for cell in line.split("&")]
        if len(cells) == 7 and re.fullmatch(r"\d/[IDPR]", cells[0]):
            block, arm = cells[0].split("/")
            successes[(block, arm)] = int(cells[3].replace(",", ""))
            if arm == "I":
                offered.append(int(cells[1].replace(",", "")))
    low, high = [round(value * 0.04137 / 3 / 100) * 100 for value in (min(offered), max(offered))]
    result["prose_hourly_range_matches_table_e1"] = (
        f"about {low:,} to {high:,} additional tasks per hour" in current[145][1]
    )
    result["prose_each_block_workload_increment_positive"] = all(
        successes[(str(n), "P")] > successes[(str(n), "R")] for n in range(8)
    )
    result["prose_declaration_unchanged"] = (
        tex.split(r"\section*{Declaration}")[1].split(r"\clearpage")[0]
        == old.split(r"\section*{Declaration}")[1].split(r"\clearpage")[0]
    )
    result["prose_final_reflection_unchanged"] = current[205] == old_blocks[205]
    result["prose_four_retained_related_work_paragraphs_unchanged"] = all(
        current[n] == old_blocks[n] for n in (28, 29, 30, 31)
    )
    result["prose_markdown_historical"] = (
        here / "TrafficTwin_Dissertation.md"
    ).read_text() == baseline("TrafficTwin_Dissertation.md")
    metrics = prose_metrics(tex)
    result["prose_no_long_joined_sentences"] = not metrics["joined_over_35"]
    for key, target in {
        "negative": 30,
        "not_word": 50,
        "rather_than": 8,
        "remains": 18,
        "remain_family": 18,
    }.items():
        result["prose_source_hedge_" + key] = metrics["hedges"][key] <= target
    result["prose_related_work_paragraph_limits"] = all(
        len(re.findall(TOKEN, re.sub(r"\[\d+\]", "", projection(current[n][1])))) <= 70
        for n in (21, 22, 24, 25)
    )
    result["prose_research_design_length"] = (
        len(re.findall(TOKEN, re.sub(r"\[S\d+\]", "", projection(current[54][1])))) <= 130
        and current[55][1] == ""
    )
    # P.5's explicit tolerance edits override A's generic decimal ban.
    decimals = re.findall(r"\b\d+\.\d{4,}\b", body(tex).replace(current[66][1], ""))
    result["prose_only_explicit_precision_exceptions"] = sorted(decimals) == ["0.00012", "0.0017"]
    result["prose_appendix_g_macro"] = (
        r"\appendixsectionsamepage{app:H}{Artefact access and verification}" in tex
        and r"\setcounter{section}{7}" not in tex
    )
    result["prose_count_projection_matches_historical_tokenisation"] = all(
        x["baseline_projection_difference"] == 0 for x in word_counts(tex)["deltas"]
    )
    return result


def pdf_audit(path):
    import pymupdf as fitz

    doc = fitz.open(path)
    raw = subprocess.check_output(["pdftotext", "-layout", str(path), "-"], text=True).split("\f")
    rows, texts = [], []
    for i, page in enumerate(doc):
        bboxes = [
            fitz.Rect(b[:4])
            for b in page.get_text("blocks")
            if b[1] < page.rect.height - 55 and b[3] > 55
        ]
        for im in page.get_images():
            bboxes += page.get_image_rects(im[0])
        bboxes += [
            d["rect"]
            for d in page.get_drawings()
            if d["rect"].y0 < page.rect.height - 55 and d["rect"].y1 > 55
        ]
        top = 25 * 72 / 25.4
        bottom = page.rect.height - top
        fill = (
            min(bottom, max((b.y1 for b in bboxes), default=top))
            - max(top, min((b.y0 for b in bboxes), default=top))
        ) / (bottom - top)
        tokens = raw[i].split()
        rows.append(
            {
                "page": i + 1,
                "words": len(tokens) - int(bool(tokens) and tokens[-1] == str(i + 1)),
                "fill": round(fill * 100, 2),
            }
        )
        lines = page.get_text().splitlines()
        if lines and lines[-1].strip() == str(i + 1):
            lines.pop()
        texts.append("\n".join(lines))
    # Use the rendered headings, not fixed physical page numbers or bookmark destinations.
    intro_page = next(i for i, t in enumerate(texts) if re.search(r"^1\s+Introduction\s*\n", t))
    joined = "\n".join(texts[intro_page:])
    manuscript_body = joined.split("\nReferences\n", 1)[0]
    reference_page = next(
        i for i, t in enumerate(texts) if i >= intro_page and re.search(r"(?:^|\n)References\n", t)
    )
    # Keep genuine hyphenated terms but remove line-wrap hyphens before known hedge fragments.
    normal = re.sub(r"(?<=\w)-\n(?=\w)", "", manuscript_body)
    normal = re.sub(r"\s+", " ", normal)
    fulltext = "\n".join(texts)
    conclusion_page = next(
        i
        for i, t in enumerate(texts)
        if i >= intro_page and re.search(r"(?:^|\n)4\s+Conclusion\s*\n", t)
    )
    verdict_page = next(
        i
        for i, t in enumerate(texts)
        if i >= intro_page and re.search(r"(?:^|\n)4\.1\s+Verdict against", t)
    )
    figure_pages = [i for i, t in enumerate(texts) if re.search(r"Figure 7[ab]:", t)]
    toc = "\n".join(texts[1:intro_page])
    toc_appendices = re.findall(r"Appendix ([A-Z])\.", toc)
    return {
        "pages": len(doc),
        "page_table": rows,
        "body_pages": [intro_page + 1, reference_page + 1],
        "hedges": hedge_counts(normal),
        "body_code_counts": dict(Counter(re.findall(r"\bE(?:0|1|2[bcd]?|3)\b", normal))),
        "toc_appendices": toc_appendices,
        "conclusion_page": conclusion_page + 1,
        "verdict_page": verdict_page + 1,
        "figure_7_pages": [i + 1 for i in figure_pages],
        "body_text": normal,
        "full_text": fulltext,
        "method": "pdftotext -layout whitespace tokens minus final physical page-number token; vertical extent of text/image/vector bboxes clipped to 25 mm margins, footer excluded, identical to preceding CHANGES.md method.",
    }


def pdf_checks(path, tex=None):
    tex = tex if tex is not None else (HERE / "TrafficTwin_Dissertation.tex").read_text()
    audit = pdf_audit(path)
    result = {}
    text = audit["full_text"]
    # Whole words: the mandatory copyright text contains "The ownership".
    result["prose_pdf_no_process_language"] = not re.search(
        r"AUTHOR_ACTION|\bThe owner\b|\b[Ss]ubmission gate\b", text
    )
    result["prose_pdf_owner_only_copyright"] = not re.search(r"\bowner\b(?!\(s\))", text, re.I)
    result["prose_pdf_contiguous_appendices"] = audit["toc_appendices"] == list("ABCDEFG")
    result["prose_pdf_figures_precede_conclusion"] = (
        len(audit["figure_7_pages"]) == 2
        and max(audit["figure_7_pages"]) < audit["conclusion_page"]
    )
    result["prose_pdf_no_figure_between_conclusion_and_verdict"] = not any(
        audit["conclusion_page"] <= p <= audit["verdict_page"] for p in audit["figure_7_pages"]
    )
    result["prose_pdf_body_fill_at_least_60"] = all(
        row["fill"] >= 60
        for row in audit["page_table"]
        if audit["body_pages"][0] <= row["page"] <= audit["body_pages"][1]
    )
    result["prose_pdf_no_nonfinal_page_below_30"] = all(
        row["fill"] >= 30 for row in audit["page_table"][:-1]
    )
    for key, target in {
        "negative": 30,
        "not_word": 50,
        "rather_than": 8,
        "remains": 18,
        "remain_family": 18,
    }.items():
        result["prose_pdf_hedge_" + key] = audit["hedges"][key] <= target
    words = word_counts(tex)["after"]
    normalized = " ".join(text.split())
    result["prose_pdf_displayed_word_counts"] = (
        f"Word count: {words['strict']:,}" in normalized
        and f"{words['prose_only']:,} excluding tables and pseudocode." in normalized
    )
    # The built source alongside the PDF binds the validation to this exact TeX.
    built_source = Path(path).with_suffix(".tex")
    result["prose_pdf_built_source_matches"] = (
        built_source.exists() and built_source.read_text() == tex
    )
    log_path = Path(os.environ.get("TRAFFICTWIN_REVIEW_LOG", str(Path(path).with_suffix(".log"))))
    log = log_path.read_text() if log_path.exists() else "MISSING BUILD LOG"
    result["prose_compile_clean"] = log_path.exists() and not any(
        x in log
        for x in [
            "\n!",
            "Overfull \\",
            "undefined references",
            "Missing character:",
            "Float too large",
        ]
    )
    return result


if __name__ == "__main__":
    record = {
        "baseline_commit": BASE,
        "word_counts": word_counts(),
        "before": prose_metrics(baseline()),
        "after": prose_metrics((HERE / "TrafficTwin_Dissertation.tex").read_text()),
        "checks": checks(),
    }
    if os.environ.get("TRAFFICTWIN_REVIEW_PDF"):
        record["checks"].update(pdf_checks(Path(os.environ["TRAFFICTWIN_REVIEW_PDF"])))
        record["pdf"] = {
            k: v
            for k, v in pdf_audit(Path(os.environ["TRAFFICTWIN_REVIEW_PDF"])).items()
            if k not in ("body_text", "full_text")
        }
    print(json.dumps(record, indent=2))
    raise SystemExit(0 if all(record["checks"].values()) else 1)
