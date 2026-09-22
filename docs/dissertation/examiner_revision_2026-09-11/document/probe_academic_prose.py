"""In-memory scientific mutations; no manuscript or research inputs are changed."""

import json
import re

from validate_academic_prose import HERE, scientific_checks
from validate_prose_pass import checks as prose_checks


def main() -> int:
    tex = (HERE / "TrafficTwin_Dissertation.tex").read_text()
    assert all(scientific_checks(tex).values())
    probes = [
        ("result sign", "+4.137", "-4.137"),
        ("interval endpoint", "+0.750", "+0.751"),
        (
            "interval endpoint order",
            "+0.649 points [+0.517, +0.781]",
            "+0.649 points [+0.781, +0.517]",
        ),
        ("table count", "1,744,761 & 1,655,779", "1,744,762 & 1,655,779"),
        ("table unit", "Contrast & Mean difference, pp", "Contrast & Mean difference, percent"),
        (
            "algorithm restart",
            "working_W = W; working_Q = Q",
            "working_W = working_W; working_Q = Q",
        ),
        ("proof assumption", "All sums here are exact.", "All sums here use float32."),
        ("proof bound", "2d_r-1", "2d_r+1"),
        ("pilot exclusion", "The pilot is excluded", "The pilot is included"),
        ("reused blocks", "reused its eight joint blocks", "used eight new joint blocks"),
        (
            "followup protocol",
            "protocol sealed before the new outcomes",
            "protocol sealed after the new outcomes",
        ),
        (
            "shared training seed",
            "sharing training seed 100",
            "using independent training seed 100",
        ),
        (
            "causal shares",
            "neither identify causal mechanism shares",
            "identify causal mechanism shares",
        ),
        (
            "scenario scope",
            "same demand-scaled Manchester network",
            "independent Manchester networks",
        ),
        (
            "historical uncertainty",
            "historical numerical impact remains unquantified",
            "historical numerical impact is zero",
        ),
        (
            "E3 unexecuted",
            "Dynamic Resource V2 (E3) remained unexecuted",
            "Dynamic Resource V2 (E3) was executed",
        ),
        (
            "AI attribution",
            "Codex and ChatGPT helped generate implementation and text",
            "I generated all implementation and text unaided",
        ),
        ("citation lost", r"\cite{ref4}", ""),
        ("evidence link lost", r"\hyperref[source-s4]{[S4]}", ""),
        ("duplicate removal from results", "+0.193 [+0.034, +0.352]", "+0.193"),
        ("numerical boundary", "sub-0.001 ms", "sub-0.01 ms"),
    ]
    results = []
    for name, old, new in probes:
        assert old in tex, name
        mutated = tex.replace(old, new, 1)
        failed = [key for key, passed in scientific_checks(mutated).items() if not passed]
        results.append({"probe": name, "rejected": bool(failed), "guards": failed})
    changed_count = re.sub(r"Word count: [\d,]+", "Word count: 1", tex)
    result = prose_checks(tex_override=changed_count)
    results.append(
        {
            "probe": "displayed count",
            "rejected": not result["citation_displayed_counts_match_count_exemplar_words"],
        }
    )
    record = {
        "passed": all(row["rejected"] for row in results),
        "probes": results,
        "research_workloads_launched": 0,
    }
    print(json.dumps(record, indent=2))
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
