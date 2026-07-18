"""Deployment-safe artifacts for the standalone synthetic TrafficTwin product."""

# ruff: noqa: E501, S608 - readable embedded HTML, CSS, and JavaScript source

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.demo.workspace import workspace_status
from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.results import MetricCollection, MetricStatus
from traffictwin.release.metadata import current_release_metadata
from traffictwin.reporting.builder import (
    build_comparison_report,
    build_diagnostics_report,
    build_full_report,
    build_run_report,
)
from traffictwin.reporting.html import report_to_html
from traffictwin.synthetic.bundles import DETERMINISTIC_CREATED_AT

Clock = Callable[[], datetime]
SITE_MARKER = "traffictwin_synthetic_static_site"


class StaticSiteArtifact(BaseModel):
    """One checksummed public synthetic-site artifact."""

    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str


class SyntheticStaticSiteManifest(BaseModel):
    """Manifest proving that a staged site contains synthetic outputs only."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    site_type: str = SITE_MARKER
    generated_at: datetime
    package_version: str
    synthetic: bool = True
    live_data: bool = False
    external_integration: bool = False
    licence_status: str
    scenarios: list[str]
    artifacts: list[StaticSiteArtifact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return finite, deterministic JSON."""

        return self.model_dump_json(indent=2)


def stage_synthetic_demo_site(
    workspace: str | Path,
    output: str | Path,
    *,
    overwrite: bool = False,
    clock: Clock | None = None,
) -> SyntheticStaticSiteManifest:
    """Stage an offline static site from existing standalone pipeline outputs."""

    workspace_path = Path(workspace)
    status = workspace_status(workspace_path)
    if not status.valid_workspace:
        raise ValueError(f"not a valid TrafficTwin demo workspace: {workspace_path}")
    target = Path(output)
    _prepare_target(target, overwrite=overwrite)
    now = (clock or _fixed_clock)()
    scenario_ids = [
        "baseline",
        "stressed_demand",
        "under_offloading",
        "infrastructure_bottleneck",
        "mixed_fault",
        "partial_evidence",
    ]
    scenario_payload = [
        _scenario_payload(workspace_path, scenario_id) for scenario_id in scenario_ids
    ]
    report_specs = {
        "baseline-report.html": report_to_html(
            build_run_report(workspace_path / "bundles" / "baseline", clock=lambda: now)
        ),
        "stressed-report.html": report_to_html(
            build_full_report(
                workspace_path / "bundles" / "stressed_demand",
                comparison_baseline=workspace_path / "bundles" / "baseline",
                clock=lambda: now,
            )
        ),
        "comparison.html": report_to_html(
            build_comparison_report(
                workspace_path / "bundles" / "baseline",
                workspace_path / "bundles" / "stressed_demand",
                clock=lambda: now,
            )
        ),
        "under-offloading-diagnostics.html": report_to_html(
            build_diagnostics_report(
                workspace_path / "bundles" / "under_offloading", clock=lambda: now
            )
        ),
        "infrastructure-bottleneck-diagnostics.html": report_to_html(
            build_diagnostics_report(
                workspace_path / "bundles" / "infrastructure_bottleneck",
                clock=lambda: now,
            )
        ),
    }
    index = target / "index.html"
    index.write_text(_site_document(scenario_payload), encoding="utf-8")
    for filename, content in report_specs.items():
        (target / filename).write_text(content, encoding="utf-8")
    metadata = current_release_metadata()
    artifact_paths = [index, *(target / filename for filename in sorted(report_specs))]
    manifest = SyntheticStaticSiteManifest(
        generated_at=now,
        package_version=metadata.version,
        licence_status=metadata.licence_status,
        scenarios=scenario_ids,
        artifacts=[
            StaticSiteArtifact(path=path.name, sha256=_sha256(path)) for path in artifact_paths
        ],
        warnings=[
            "This site contains deterministic synthetic fixtures only.",
            "It is not live Manchester data or external VEC/SUMO validation.",
            "The repository licence has not yet been specified.",
        ],
    )
    (target / "site-manifest.json").write_text(manifest.to_json() + "\n", encoding="utf-8")
    return manifest


def _scenario_payload(workspace: Path, scenario_id: str) -> dict[str, object]:
    bundle = validate_bundle(workspace / "bundles" / scenario_id)
    if bundle.manifest is None or not bundle.report.may_import:
        raise ValueError(f"standalone scenario is not accepted: {scenario_id}")
    if bundle.manifest.environment.name != "synthetic":
        raise ValueError(f"public demo site accepts synthetic bundles only: {scenario_id}")
    metrics_path = workspace / "exports" / f"{scenario_id}_metrics.json"
    diagnostics_path = workspace / "exports" / f"{scenario_id}_diagnostics.json"
    metrics = MetricCollection.model_validate_json(metrics_path.read_text(encoding="utf-8"))
    diagnostics = DiagnosticReport.model_validate_json(diagnostics_path.read_text(encoding="utf-8"))
    selected_keys = [
        "task.generated.count",
        "task.completion.rate",
        "task.incomplete.rate",
        "task.offload.rate",
        "infra.utilisation.p95",
        "infra.queue_length.max",
        "trip.duration.p95_s",
        "traffic.speed.mean_mps",
    ]
    by_key = metrics.by_key()
    selected: list[dict[str, object]] = []
    for key in selected_keys:
        metric = by_key.get(key)
        if metric is None:
            continue
        value = metric.value if metric.status is MetricStatus.AVAILABLE else None
        if not isinstance(value, (int, float, str, bool, type(None))):
            value = None
        selected.append(
            {
                "key": key,
                "status": metric.status.value,
                "value": value,
                "unit": metric.unit,
                "reasons": [reason.value for reason in metric.reason_codes],
            }
        )
    return {
        "scenario_id": scenario_id,
        "name": bundle.seed.name if bundle.seed is not None else scenario_id,
        "run_id": bundle.manifest.run.run_id,
        "algorithm": bundle.manifest.run.algorithm,
        "random_seed": bundle.manifest.run.random_seed,
        "fingerprint": bundle.fingerprint,
        "validation": bundle.report.status.value,
        "metrics": selected,
        "triggered_rules": diagnostics.triggered_rule_ids,
        "insufficient_rules": diagnostics.insufficient_rule_ids,
    }


def _site_document(scenarios: list[dict[str, object]]) -> str:
    payload = (
        json.dumps({"scenarios": scenarios}, sort_keys=True, separators=(",", ":"), allow_nan=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>TrafficTwin Standalone Research Demo</title>
  <style>
    :root {{ color-scheme:light; --ink:#18211d; --muted:#57635e; --line:#d7ddda;
      --paper:#f6f8f7; --panel:#fff; --accent:#176b55; --warning:#fff7df; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; color:var(--ink); background:var(--paper);
      font:15px/1.5 system-ui,sans-serif; }} header {{ background:#153c32; color:#fff;
      padding:24px max(20px,calc((100% - 1120px)/2)); }} header h1 {{ margin:0; font-size:28px; }}
    main {{ max-width:1120px; margin:auto; padding:24px; }} .notice {{ border-left:4px solid #d09a1c;
      background:var(--warning); padding:12px 16px; }} .toolbar {{ display:grid;
      grid-template-columns:minmax(240px,420px) 1fr; gap:16px; align-items:end; margin:24px 0; }}
    label {{ font-weight:650; }} select {{ display:block; width:100%; margin-top:6px; padding:10px;
      border:1px solid var(--line); background:#fff; }} .metadata {{ color:var(--muted);
      overflow-wrap:anywhere; }} .metrics {{ display:grid; grid-template-columns:repeat(auto-fit,
      minmax(210px,1fr)); gap:1px; border:1px solid var(--line); background:var(--line); }}
    .metric {{ min-height:118px; padding:14px; background:var(--panel); }} .metric .key {{ color:var(--muted);
      overflow-wrap:anywhere; }} .metric .value {{ margin-top:8px; font-size:24px; font-weight:700; }}
    .tag {{ display:inline-block; border:1px solid currentColor; padding:2px 7px; font-size:12px; }}
    .links {{ display:flex; flex-wrap:wrap; gap:10px; }} .links a {{ color:var(--accent); }}
    h2 {{ margin-top:30px; font-size:20px; }} @media(max-width:700px) {{ .toolbar {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
<header><h1>TrafficTwin</h1><div>Standalone synthetic research demonstration</div></header>
<main>
  <p class="notice"><strong>Synthetic-only demonstration.</strong> Values come from deterministic
  repository fixtures. This is not live Manchester data, Randy/VEC output, SUMO validation, or a
  calibrated traffic model.</p>
  <div class="toolbar"><label>Scenario<select id="scenario"></select></label>
    <div class="metadata" id="context"></div></div>
  <h2>Existing deterministic metrics</h2><div class="metrics" id="metrics"></div>
  <h2>Existing diagnostic-rule status</h2><div id="diagnostics"></div>
  <h2>Research reports</h2><div class="links">
    <a href="baseline-report.html">Baseline report</a>
    <a href="stressed-report.html">Stressed full report</a>
    <a href="comparison.html">Baseline comparison</a>
    <a href="under-offloading-diagnostics.html">R1 demonstration</a>
    <a href="infrastructure-bottleneck-diagnostics.html">R2 demonstration</a>
  </div>
  <p class="metadata">The interactive Streamlit application requires a Python host and cannot run
  as a Netlify static site. Licence not yet specified.</p>
</main>
<script id="site-data" type="application/json">{payload}</script>
<script>
  const data=JSON.parse(document.getElementById('site-data').textContent);
  const select=document.getElementById('scenario');
  data.scenarios.forEach((item,index)=>select.add(new Option(item.name,item.scenario_id,index===0,index===0)));
  const fmt=(value,unit)=>value===null?'Unavailable':
    `${{typeof value==='number'?value.toLocaleString(undefined,{{maximumFractionDigits:6}}):value}} ${{unit==='ratio'||unit==='count'?'':unit}}`;
  function render() {{ const item=data.scenarios.find(x=>x.scenario_id===select.value);
    document.getElementById('context').textContent=`Run ${{item.run_id}} · ${{item.algorithm}} · seed ${{item.random_seed}} · fingerprint ${{item.fingerprint}}`;
    const metrics=document.getElementById('metrics'); metrics.replaceChildren(); item.metrics.forEach(metric=>{{
      const node=document.createElement('div'); node.className='metric';
      const key=document.createElement('div'); key.className='key'; key.textContent=metric.key;
      const value=document.createElement('div'); value.className='value'; value.textContent=fmt(metric.value,metric.unit);
      const status=document.createElement('span'); status.className='tag'; status.textContent=metric.status.toUpperCase();
      node.append(key,value,status); if(metric.reasons.length){{const reason=document.createElement('div');
      reason.className='metadata'; reason.textContent=metric.reasons.join(', '); node.append(reason);}} metrics.append(node); }});
    document.getElementById('diagnostics').textContent=`Triggered: ${{item.triggered_rules.join(', ')||'none'}} · Insufficient: ${{item.insufficient_rules.join(', ')||'none'}}`;
  }} select.addEventListener('change',render); render();
</script>
</body>
</html>
"""


def _prepare_target(path: Path, *, overwrite: bool) -> None:
    if path.exists() and any(path.iterdir()):
        if not overwrite:
            raise FileExistsError(f"static-site directory is not empty: {path}")
        marker = path / "site-manifest.json"
        if not marker.exists():
            raise PermissionError("refusing to replace an unmarked directory")
        raw = json.loads(marker.read_text(encoding="utf-8"))
        if raw.get("site_type") != SITE_MARKER:
            raise PermissionError("refusing to replace a non-TrafficTwin static site")
        for child in path.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    path.mkdir(parents=True, exist_ok=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixed_clock() -> datetime:
    return datetime.fromisoformat(DETERMINISTIC_CREATED_AT.replace("Z", "+00:00")).astimezone(UTC)
