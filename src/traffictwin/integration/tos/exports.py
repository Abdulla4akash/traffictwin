"""Deterministic reports and a permission-conscious static TOS results atlas."""

# ruff: noqa: E501 - readable embedded HTML, CSS, and JavaScript source

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from pathlib import Path

from traffictwin.integration.tos.analysis import (
    build_evaluation_matrix,
    build_generalisation_matrix,
    compare_campaigns,
    tos_analysis_catalogue,
)
from traffictwin.integration.tos.audit import audit_tos_package
from traffictwin.integration.tos.readers import read_evaluation_runs
from traffictwin.integration.tos.training import list_training_runs
from traffictwin.reporting.html import report_to_html
from traffictwin.reporting.markdown import report_to_markdown
from traffictwin.reporting.models import ResearchReport

Clock = Callable[[], datetime]


@dataclass(frozen=True)
class TosResultsPack:
    """Paths written by the dissertation-safe results-pack exporter."""

    directory: Path
    markdown_report: Path
    html_report: Path
    matrix_json: Path
    comparison_json: Path
    audit_json: Path
    atlas_html: Path


def build_tos_research_report(
    root: str | Path,
    *,
    variation_campaign: str = "ukfleettrain_mappo",
    clock: Clock | None = None,
) -> ResearchReport:
    """Build deterministic prose from inspected source summaries only."""

    now = (clock or _utc_now)()
    rows = read_evaluation_runs(root)
    matrix = build_evaluation_matrix(rows, root, clock=lambda: now)
    comparison = compare_campaigns(
        rows,
        root,
        "baseline",
        variation_campaign,
        clock=lambda: now,
    )
    generalisation = build_generalisation_matrix(rows, root)
    audit = audit_tos_package(root, clock=lambda: now)
    training = list_training_runs(root)
    matrix_lines = [
        (
            f"{entry.campaign} / {entry.cell}: n={entry.statistics.n}, "
            f"mean={_format(entry.statistics.mean)}, "
            f"sample SD={_format(entry.statistics.sample_sd)}"
        )
        for entry in matrix.entries
    ]
    comparison_lines = [
        (
            f"{item.cell}: paired n={item.paired_difference_statistics.n}, "
            f"mean delta={_format(item.paired_difference_statistics.mean)}"
        )
        for item in comparison.comparisons
    ]
    domain_counts = Counter(entry.evaluation_domain.value for entry in generalisation.entries)
    audit_lines = [
        f"{check.code}: {check.status.value} - {check.message}" for check in audit.checks
    ]
    return ResearchReport(
        report_id=f"tos-results-{audit.package_fingerprint[:12]}",
        title="TrafficTwin TOS Imported Simulation Results Pack",
        generated_at=now,
        source_reference="TOS Data package (read-only imported simulation)",
        synthetic=False,
        sections=[
            (
                "Scope and provenance",
                [
                    f"Package fingerprint: {audit.package_fingerprint}",
                    f"Package commit: {audit.package_commit or 'unavailable'}",
                    f"Semantics evidence commit: {audit.semantics_source_commit}",
                    f"Evaluation rows: {audit.evaluation_run_count}",
                    f"Training histories: {len(training)}",
                    "All calculations are deterministic summaries of supplied artifacts.",
                ],
            ),
            ("Deadline-success matrix", matrix_lines),
            (
                f"Paired comparison: baseline vs {variation_campaign}",
                comparison_lines,
            ),
            (
                "Generalisation labels",
                [
                    f"{status}: {count} campaign/cell entries"
                    for status, count in sorted(domain_counts.items())
                ]
                + [
                    "Labels are copied from or conservatively derived from package records; "
                    "unknown relationships remain unknown."
                ],
            ),
            ("Reproducibility audit", audit_lines),
            (
                "Limitations",
                [
                    "Results are imported simulation outputs, not live Manchester observations.",
                    "Deadline success is not evidence of eventual completion for late tasks.",
                    "Processed FCD contains mobility states but no trip-duration output.",
                    "RSU pressure is not CPU utilisation.",
                    "Checkpoint payloads and the instrumented-array writer are unavailable.",
                    "Publication or public deployment of Randy-provided outputs requires permission.",
                ],
            ),
            (
                "Reproduction",
                [
                    "traffictwin integration tos validate TOS_DATA_PATH",
                    (
                        "traffictwin integration tos results-pack TOS_DATA_PATH "
                        "--output results-pack"
                    ),
                ],
            ),
        ],
        warnings=[
            "This report does not establish real-world causality or external validity.",
            "Review source-data permissions before sharing this report outside the research team.",
        ],
    )


def write_tos_results_pack(
    root: str | Path,
    output: str | Path,
    *,
    variation_campaign: str = "ukfleettrain_mappo",
    clock: Clock | None = None,
) -> TosResultsPack:
    """Write a deterministic, aggregate-only dissertation results pack."""

    target = Path(output)
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"results-pack directory is not empty: {target}")
    target.mkdir(parents=True, exist_ok=True)
    now = (clock or _utc_now)()
    rows = read_evaluation_runs(root)
    matrix = build_evaluation_matrix(rows, root, clock=lambda: now)
    comparison = compare_campaigns(
        rows,
        root,
        "baseline",
        variation_campaign,
        evaluation_fleet="uk2030",
        measure_keys=[definition.key for definition in tos_analysis_catalogue()],
        clock=lambda: now,
    )
    audit = audit_tos_package(root, clock=lambda: now)
    report = build_tos_research_report(
        root, variation_campaign=variation_campaign, clock=lambda: now
    )
    paths = TosResultsPack(
        directory=target,
        markdown_report=target / "research-report.md",
        html_report=target / "research-report.html",
        matrix_json=target / "evaluation-matrix.json",
        comparison_json=target / "paired-comparison.json",
        audit_json=target / "reproducibility-audit.json",
        atlas_html=target / "results-atlas.html",
    )
    paths.markdown_report.write_text(report_to_markdown(report), encoding="utf-8")
    paths.html_report.write_text(report_to_html(report), encoding="utf-8")
    paths.matrix_json.write_text(matrix.to_json() + "\n", encoding="utf-8")
    paths.comparison_json.write_text(comparison.to_json() + "\n", encoding="utf-8")
    paths.audit_json.write_text(audit.to_json() + "\n", encoding="utf-8")
    paths.atlas_html.write_text(
        build_static_results_atlas(root, clock=lambda: now), encoding="utf-8"
    )
    return paths


def build_static_results_atlas(
    root: str | Path,
    *,
    clock: Clock | None = None,
) -> str:
    """Render a self-contained atlas using precomputed aggregate values only."""

    now = (clock or _utc_now)()
    rows = read_evaluation_runs(root)
    fingerprint = build_evaluation_matrix(rows, root, clock=lambda: now).package_fingerprint
    matrix_rows: list[dict[str, object]] = []
    for fleet in sorted({row.eval_fleet for row in rows}):
        for definition in tos_analysis_catalogue():
            matrix = build_evaluation_matrix(
                rows,
                root,
                measure_key=definition.key,
                evaluation_fleet=fleet,
                clock=lambda: now,
            )
            matrix_rows.extend(
                {
                    "fleet": fleet,
                    "measure": definition.key,
                    "measure_name": definition.human_name,
                    "unit": definition.unit,
                    "campaign": entry.campaign,
                    "cell": entry.cell,
                    "n": entry.statistics.n,
                    "mean": entry.statistics.mean,
                    "sample_sd": entry.statistics.sample_sd,
                    "minimum": entry.statistics.minimum,
                    "maximum": entry.statistics.maximum,
                }
                for entry in matrix.entries
            )
    generalisation = build_generalisation_matrix(rows, root)
    payload = {
        "fingerprint": fingerprint,
        "generated_at": now.isoformat(),
        "matrix": matrix_rows,
        "generalisation": [entry.model_dump(mode="json") for entry in generalisation.entries],
    }
    encoded = _safe_embedded_json(payload)
    return _atlas_document(encoded, fingerprint, now)


def _atlas_document(payload: str, fingerprint: str, generated_at: datetime) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TrafficTwin TOS Results Atlas</title>
  <style>
    :root {{ color-scheme: light; --ink:#18211d; --muted:#5d6863; --line:#d8ddda;
      --paper:#f7f8f7; --panel:#fff; --accent:#176b55; --warn:#7b4d00; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; font:15px/1.5 system-ui,sans-serif;
      color:var(--ink); background:var(--paper); }}
    header {{ padding:24px max(24px,calc((100% - 1180px)/2)); background:#153c32; color:white; }}
    header h1 {{ margin:0 0 4px; font-size:28px; letter-spacing:0; }}
    main {{ max-width:1180px; margin:auto; padding:24px; }}
    .notice {{ border-left:4px solid #e0a129; background:#fff8e8; padding:12px 16px; }}
    .controls {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px;
      margin:20px 0; }} label {{ font-weight:650; }} select {{ width:100%; margin-top:5px;
      padding:9px; border:1px solid var(--line); background:white; }}
    .meta {{ color:var(--muted); overflow-wrap:anywhere; }} .table-wrap {{ overflow:auto;
      border:1px solid var(--line); background:var(--panel); }} table {{ width:100%;
      border-collapse:collapse; min-width:760px; }} th,td {{ padding:10px 12px;
      border-bottom:1px solid var(--line); text-align:left; }} th {{ position:sticky; top:0;
      background:#edf2ef; }} td.num {{ font-variant-numeric:tabular-nums; text-align:right; }}
    .tag {{ display:inline-block; padding:2px 7px; border:1px solid currentColor; font-size:12px; }}
    section {{ margin:28px 0; }} h2 {{ font-size:20px; letter-spacing:0; }}
  </style>
</head>
<body>
<header><h1>TrafficTwin TOS Results Atlas</h1><div>Read-only imported simulation summaries</div></header>
<main>
  <p class="notice"><strong>Research-use notice.</strong> These are imported simulation outputs,
  not live Manchester data or external validation. Public sharing requires confirmation of source-data
  permission. The atlas shows descriptive associations and does not establish causality.</p>
  <p class="meta">Package fingerprint: <code>{escape(fingerprint)}</code><br>
  Generated: <code>{escape(generated_at.isoformat())}</code></p>
  <section><h2>Evaluation matrix</h2>
    <div class="controls"><label>Evaluation fleet<select id="fleet"></select></label>
    <label>Measure<select id="measure"></select></label></div>
    <div class="table-wrap"><table><thead><tr><th>Campaign</th><th>Cell</th><th>n</th>
    <th>Mean</th><th>Sample SD</th><th>Minimum</th><th>Maximum</th></tr></thead>
    <tbody id="matrix-body"></tbody></table></div>
  </section>
  <section><h2>Training/evaluation domain labels</h2>
    <p class="meta">Unknown relationships remain unknown. These labels describe provenance, not quality.</p>
    <div class="table-wrap"><table><thead><tr><th>Campaign</th><th>Cell</th><th>Domain</th>
    <th>Evidence statement</th></tr></thead><tbody id="domain-body"></tbody></table></div>
  </section>
</main>
<script id="atlas-data" type="application/json">{payload}</script>
<script>
  const data = JSON.parse(document.getElementById('atlas-data').textContent);
  const fleet = document.getElementById('fleet'); const measure = document.getElementById('measure');
  const unique = (xs) => [...new Set(xs)].sort();
  unique(data.matrix.map(x=>x.fleet)).forEach(x=>fleet.add(new Option(x,x)));
  const measures = [...new Map(data.matrix.map(x=>[x.measure,x.measure_name])).entries()];
  measures.forEach(([key,name])=>measure.add(new Option(`${{name}} (${{key}})`,key)));
  const fmt = x => x === null ? 'Unavailable' : Number(x).toLocaleString(undefined,{{maximumFractionDigits:6}});
  function render() {{
    const body=document.getElementById('matrix-body'); body.replaceChildren();
    data.matrix.filter(x=>x.fleet===fleet.value && x.measure===measure.value).forEach(x=>{{
      const tr=document.createElement('tr'); [x.campaign,x.cell,x.n,fmt(x.mean),fmt(x.sample_sd),
        fmt(x.minimum),fmt(x.maximum)].forEach((value,index)=>{{const td=document.createElement('td');
        td.textContent=value; if(index>1)td.className='num'; tr.appendChild(td);}}); body.appendChild(tr);
    }});
  }}
  fleet.addEventListener('change',render); measure.addEventListener('change',render); render();
  const domainBody=document.getElementById('domain-body'); data.generalisation.forEach(x=>{{
    const tr=document.createElement('tr'); [x.campaign,x.cell,x.evaluation_domain,x.evidence_statement]
      .forEach((value,index)=>{{const td=document.createElement('td'); td.textContent=value;
      if(index===2)td.className='tag'; tr.appendChild(td);}}); domainBody.appendChild(tr);
  }});
</script>
</body>
</html>
"""


def _safe_embedded_json(payload: Mapping[str, object]) -> str:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _format(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.6f}"


def _utc_now() -> datetime:
    return datetime.now(UTC)
