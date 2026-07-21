"""Build reproducible, explicitly synthetic comparison case-study packs."""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.reporting.builder import build_comparison_report, build_run_report
from traffictwin.reporting.markdown import report_to_markdown
from traffictwin.rules.engine import evaluate_rules
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.config import IncidentSpec
from traffictwin.synthetic.scenarios import incident_variant_config, preset_config


class CaseStudyArtifact(BaseModel):
    """One checksummed file in a generated case-study pack."""

    model_config = ConfigDict(extra="forbid")

    relative_path: str
    kind: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CaseStudyPackManifest(BaseModel):
    """Manifest for one deterministic synthetic case-study pack."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    pack_id: str
    generated_at: datetime
    synthetic: bool = True
    scenario_ids: list[str]
    artifacts: list[CaseStudyArtifact]
    limitations: list[str]

    def to_json(self) -> str:
        """Return readable JSON."""

        return self.model_dump_json(indent=2)


def build_synthetic_case_study_pack(
    destination: str | Path,
    *,
    overwrite: bool = False,
    clock: Callable[[], datetime] | None = None,
) -> CaseStudyPackManifest:
    """Build baseline, incident, and infrastructure comparison artifacts."""

    output = Path(destination)
    _prepare_destination(output, overwrite=overwrite)
    now = clock() if clock is not None else datetime.now(UTC)
    experiment_id = "exp-synthetic-case-study"
    baseline = preset_config("baseline", random_seed=11).model_copy(
        update={
            "scenario_id": "case-baseline",
            "experiment_id": experiment_id,
            "name": "Synthetic case-study baseline",
        }
    )
    incident_source = baseline.model_copy(
        update={
            "incident_schedule": [
                IncidentSpec(
                    timestamp_s=90.0,
                    incident_type="synthetic_corridor_incident",
                    location="synthetic-corridor-a",
                    severity="high",
                    duration_s=150.0,
                    lanes_closed=1,
                    demand_multiplier=2.0,
                    vehicles_involved=["vehicle-case-001", "vehicle-case-002"],
                )
            ]
        }
    )
    incident = incident_variant_config(
        incident_source,
        scenario_id="case-incident-demand",
    )
    infrastructure = preset_config("infrastructure_bottleneck", random_seed=11).model_copy(
        update={
            "scenario_id": "case-infrastructure-reduced",
            "experiment_id": experiment_id,
            "baseline_seed_id": "seed-case-baseline",
            "name": "Synthetic reduced-infrastructure case",
        }
    )
    configs = [baseline, incident, infrastructure]
    bundles = output / "bundles"
    reports = output / "reports"
    exports = output / "exports"
    bundles.mkdir(parents=True)
    reports.mkdir(parents=True)
    exports.mkdir(parents=True)
    paths: dict[str, Path] = {}
    for config in configs:
        bundle_path = write_synthetic_bundle(config, bundles / config.scenario_id)
        paths[config.scenario_id] = bundle_path
        validation = validate_bundle(bundle_path)
        if validation.manifest is None or not validation.report.may_import:
            raise ValueError(f"generated case-study bundle was rejected: {config.scenario_id}")
        metrics = compute_metrics_for_bundle(validation, clock=lambda: now)
        evidence = build_evidence_pack(validation, metrics, clock=lambda: now)
        diagnostics = evaluate_rules(evidence, clock=lambda: now)
        (exports / f"{config.scenario_id}-metrics.json").write_text(
            metrics.model_dump_json(indent=2), encoding="utf-8"
        )
        (exports / f"{config.scenario_id}-diagnostics.json").write_text(
            diagnostics.to_json(), encoding="utf-8"
        )
        (reports / f"{config.scenario_id}.md").write_text(
            report_to_markdown(build_run_report(bundle_path, clock=lambda: now)),
            encoding="utf-8",
        )
    for variation_id in ("case-incident-demand", "case-infrastructure-reduced"):
        comparison = build_comparison_report(
            paths["case-baseline"],
            paths[variation_id],
            clock=lambda: now,
        )
        (reports / f"case-baseline-vs-{variation_id}.md").write_text(
            report_to_markdown(comparison),
            encoding="utf-8",
        )
    artifacts = _artifacts(output)
    manifest = CaseStudyPackManifest(
        pack_id="synthetic-baseline-incident-infrastructure-v1",
        generated_at=now,
        scenario_ids=[config.scenario_id for config in configs],
        artifacts=artifacts,
        limitations=[
            "Every scenario and output is a deterministic synthetic software fixture.",
            "Comparisons are descriptive and do not establish traffic or VEC causality.",
            "The pack launches no Randy/VEC, SUMO, or live-data process.",
        ],
    )
    (output / "manifest.json").write_text(manifest.to_json(), encoding="utf-8")
    return manifest


def _prepare_destination(destination: Path, *, overwrite: bool) -> None:
    resolved = destination.resolve()
    if resolved == Path(resolved.anchor):
        raise ValueError("case-study destination must not be a filesystem root")
    if destination.exists():
        if any(destination.iterdir()) and not overwrite:
            raise FileExistsError(f"case-study destination is not empty: {destination}")
        if overwrite:
            shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)


def _artifacts(root: Path) -> list[CaseStudyArtifact]:
    artifacts: list[CaseStudyArtifact] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        artifacts.append(
            CaseStudyArtifact(
                relative_path=relative,
                kind=_artifact_kind(relative),
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
            )
        )
    return artifacts


def _artifact_kind(relative_path: str) -> str:
    if relative_path.startswith("bundles/"):
        return "run_bundle_file"
    if relative_path.endswith("-metrics.json"):
        return "metric_collection"
    if relative_path.endswith("-diagnostics.json"):
        return "diagnostic_report"
    if relative_path.endswith(".md"):
        return "research_report"
    if relative_path.endswith(".json"):
        return "json"
    return "artifact"
