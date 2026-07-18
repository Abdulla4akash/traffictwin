"""Reproducible standalone demo workspace management."""

from __future__ import annotations

import shutil
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.domain.enums import ExperimentStatus
from traffictwin.domain.experiment import Experiment
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.evidence.pack import EvidencePack
from traffictwin.ingestion.bundle import import_bundle, validate_bundle
from traffictwin.metrics.comparison import compare_metric_collections
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.results import MetricCollection
from traffictwin.provenance.query import (
    build_provenance_context,
    get_metric_provenance,
    get_rule_provenance,
)
from traffictwin.provenance.serialization import trace_to_json
from traffictwin.reporting.builder import (
    build_comparison_report,
    build_diagnostics_report,
    build_full_report,
    build_run_report,
)
from traffictwin.reporting.html import report_to_html
from traffictwin.reporting.markdown import report_to_markdown
from traffictwin.rules.engine import evaluate_rules
from traffictwin.storage.registry import DuplicateIdentifierError, Registry, RegistryConflictError
from traffictwin.synthetic.bundles import DETERMINISTIC_CREATED_AT, write_synthetic_bundle
from traffictwin.synthetic.experiments import (
    build_r3_evidence_pack_from_bundles,
    generate_trivial_multi_algorithm_experiment,
)
from traffictwin.synthetic.scenarios import default_workspace_configs

WORKSPACE_SCHEMA_VERSION = "1.0"
WORKSPACE_KIND = "traffictwin_standalone_demo"


@dataclass(frozen=True)
class WorkspaceInitialiseResult:
    """Result from creating a standalone demo workspace."""

    path: Path
    registry_path: Path
    bundle_count: int
    imported_run_count: int
    report_count: int
    manifest_path: Path


@dataclass(frozen=True)
class WorkspaceStatus:
    """Summary of a standalone demo workspace."""

    path: Path
    exists: bool
    valid_workspace: bool
    registry_path: Path
    scenario_count: int
    imported_run_count: int
    report_count: int
    diagnostics_status: str
    comparison_count: int
    messages: list[str]


def initialise_workspace(path: str | Path, *, force: bool = False) -> WorkspaceInitialiseResult:
    """Create a deterministic standalone demo workspace."""

    workspace = Path(path)
    _ensure_safe_workspace_path(workspace)
    if workspace.exists() and any(workspace.iterdir()):
        if not force:
            msg = f"workspace already exists and is not empty: {workspace}"
            raise FileExistsError(msg)
        _reset_existing_workspace(workspace)
    _create_workspace_dirs(workspace)

    registry_path = workspace / "registry.sqlite"
    registry = Registry(registry_path)
    registry.initialize()
    _register_experiments(registry)

    bundle_paths: list[Path] = []
    for config in default_workspace_configs():
        bundle_path = write_synthetic_bundle(
            config,
            workspace / "bundles" / config.scenario_id,
            overwrite=True,
        )
        bundle_paths.append(bundle_path)
        (workspace / "seeds" / f"{config.scenario_id}.yaml").write_text(
            (bundle_path / "seed.yaml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    r3_paths = generate_trivial_multi_algorithm_experiment(
        workspace / "bundles" / "trivial_multi_algorithm",
        overwrite=True,
    )
    bundle_paths.extend(r3_paths)

    imported_count = 0
    report_count = 0
    for bundle_path in bundle_paths:
        result = validate_bundle(bundle_path)
        if result.seed is not None:
            with suppress(DuplicateIdentifierError):
                registry.add_seed(result.seed)
        if result.report.may_import:
            try:
                import_result = import_bundle(bundle_path, registry_path)
            except RegistryConflictError:
                import_result = None
            if import_result is not None and (import_result.created or import_result.idempotent):
                imported_count += 1
            metrics = compute_metrics_for_bundle(result, clock=_fixed_clock)
            evidence = build_evidence_pack(result, metrics, clock=_fixed_clock)
            diagnostics = evaluate_rules(evidence, clock=_fixed_clock)
            _store_pipeline_outputs(
                workspace,
                bundle_path,
                metrics,
                evidence,
                diagnostics,
                registry,
            )
            report_count += 3

    r3_pack = build_r3_evidence_pack_from_bundles(r3_paths, clock=_fixed_clock)
    r3_report = evaluate_rules(r3_pack, clock=_fixed_clock)
    (workspace / "exports" / "trivial_multi_algorithm_evidence.json").write_text(
        r3_pack.to_json(),
        encoding="utf-8",
    )
    (workspace / "exports" / "trivial_multi_algorithm_diagnostics.json").write_text(
        r3_report.to_json(),
        encoding="utf-8",
    )
    report_count += 2

    _write_comparison_outputs(workspace)
    report_count += _write_report_outputs(workspace)
    manifest_path = _write_workspace_manifest(workspace, bundle_paths)
    return WorkspaceInitialiseResult(
        path=workspace,
        registry_path=registry_path,
        bundle_count=len(bundle_paths),
        imported_run_count=imported_count,
        report_count=report_count,
        manifest_path=manifest_path,
    )


def reset_workspace(path: str | Path, *, yes: bool = False) -> WorkspaceInitialiseResult:
    """Reset a marked standalone demo workspace."""

    workspace = Path(path)
    if not yes:
        msg = "reset requires explicit confirmation"
        raise PermissionError(msg)
    _require_workspace_marker(workspace)
    _reset_existing_workspace(workspace)
    return initialise_workspace(workspace, force=True)


def workspace_status(path: str | Path) -> WorkspaceStatus:
    """Inspect a standalone demo workspace."""

    workspace = Path(path)
    registry_path = workspace / "registry.sqlite"
    messages: list[str] = []
    valid = False
    scenario_count = 0
    comparison_count = 0
    report_count = 0
    diagnostics_status = "missing"
    imported_run_count = 0
    if workspace.exists():
        try:
            manifest = _read_workspace_manifest(workspace)
            valid = True
            scenarios = manifest.get("scenarios", [])
            comparisons = manifest.get("comparisons", [])
            scenario_count = len(scenarios) if isinstance(scenarios, list) else 0
            comparison_count = len(comparisons) if isinstance(comparisons, list) else 0
            diagnostics_status = "prepared" if (workspace / "exports").exists() else "missing"
        except (OSError, ValueError) as exc:
            messages.append(str(exc))
        report_count = (
            len(list((workspace / "reports").glob("*"))) if (workspace / "reports").exists() else 0
        )
        if registry_path.exists():
            imported_run_count = Registry(registry_path).inspect().run_count
        else:
            messages.append("registry.sqlite is missing")
    else:
        messages.append("workspace does not exist")
    return WorkspaceStatus(
        path=workspace,
        exists=workspace.exists(),
        valid_workspace=valid,
        registry_path=registry_path,
        scenario_count=scenario_count,
        imported_run_count=imported_run_count,
        report_count=report_count,
        diagnostics_status=diagnostics_status,
        comparison_count=comparison_count,
        messages=messages,
    )


def _create_workspace_dirs(workspace: Path) -> None:
    for name in ("seeds", "bundles", "reports", "exports", "logs"):
        (workspace / name).mkdir(parents=True, exist_ok=True)


def _register_experiments(registry: Registry) -> None:
    for experiment in (
        Experiment(
            experiment_id="exp-standalone-demo",
            research_question="How does the standalone synthetic baseline change under stress?",
            hypothesis=(
                "Synthetic stressed scenarios should expose lower completion or longer trips."
            ),
            baseline_seed_id="seed-baseline",
            variation_seed_ids=[
                "seed-stressed_demand",
                "seed-under_offloading",
                "seed-infrastructure_bottleneck",
                "seed-mixed_fault",
                "seed-partial_evidence",
            ],
            algorithms=[
                "synthetic-balanced",
                "synthetic-low-offload",
                "synthetic-selective",
            ],
            common_random_seed_set=[7],
            planned_replicates=1,
            status=ExperimentStatus.COMPLETED,
            created_at=_fixed_clock(),
            updated_at=_fixed_clock(),
        ),
        Experiment(
            experiment_id="exp-standalone-trivial",
            research_question="Can low-pressure synthetic cases exercise R3 readiness?",
            hypothesis=None,
            baseline_seed_id="seed-trivial_multi_algorithm",
            variation_seed_ids=[],
            algorithms=[
                "synthetic-always-local",
                "synthetic-selective",
                "synthetic-balanced",
            ],
            common_random_seed_set=[1, 2, 3],
            planned_replicates=3,
            status=ExperimentStatus.COMPLETED,
            created_at=_fixed_clock(),
            updated_at=_fixed_clock(),
        ),
    ):
        with suppress(DuplicateIdentifierError):
            registry.add_experiment(experiment)


def _store_pipeline_outputs(
    workspace: Path,
    bundle_path: Path,
    metrics: MetricCollection,
    evidence: EvidencePack,
    diagnostics: DiagnosticReport,
    registry: Registry,
) -> None:
    stem = bundle_path.name
    (workspace / "exports" / f"{stem}_metrics.json").write_text(
        metrics.model_dump_json(indent=2),
        encoding="utf-8",
    )
    evidence_json = evidence.to_json()
    (workspace / "exports" / f"{stem}_evidence.json").write_text(evidence_json, encoding="utf-8")
    (workspace / "exports" / f"{stem}_diagnostics.json").write_text(
        diagnostics.to_json(),
        encoding="utf-8",
    )
    registry.store_metric_collection(
        run_id=metrics.run_id,
        metric_version=metrics.metric_version,
        source_fingerprint=metrics.input_fingerprint,
        payload_json=metrics.model_dump_json(),
    )
    registry.store_evidence_pack(
        pack_id=evidence.pack_id,
        run_id=metrics.run_id,
        source_fingerprint=metrics.input_fingerprint,
        payload_json=evidence_json,
    )
    if stem in {"baseline", "under_offloading", "infrastructure_bottleneck"}:
        context = build_provenance_context(bundle_path)
        metric_trace = get_metric_provenance(context, "task.completion.rate")
        (workspace / "exports" / f"{stem}_completion_provenance.json").write_text(
            trace_to_json(metric_trace),
            encoding="utf-8",
        )
    if stem in {"under_offloading", "infrastructure_bottleneck"}:
        context = build_provenance_context(bundle_path)
        rule_id = "R1" if stem == "under_offloading" else "R2"
        rule_trace = get_rule_provenance(context, rule_id)
        (workspace / "exports" / f"{stem}_{rule_id}_provenance.json").write_text(
            trace_to_json(rule_trace),
            encoding="utf-8",
        )


def _write_comparison_outputs(workspace: Path) -> None:
    pairs = [
        ("baseline", "stressed_demand"),
        ("baseline", "under_offloading"),
        ("baseline", "infrastructure_bottleneck"),
    ]
    comparisons: list[dict[str, str]] = []
    for baseline, variation in pairs:
        base_result = validate_bundle(workspace / "bundles" / baseline)
        variation_result = validate_bundle(workspace / "bundles" / variation)
        if not base_result.report.may_import or not variation_result.report.may_import:
            continue
        report = compare_metric_collections(
            compute_metrics_for_bundle(base_result, clock=_fixed_clock),
            compute_metrics_for_bundle(variation_result, clock=_fixed_clock),
            baseline_seed=base_result.seed,
            variation_seed=variation_result.seed,
            clock=_fixed_clock,
        )
        filename = f"compare_{baseline}_vs_{variation}.json"
        (workspace / "exports" / filename).write_text(report.to_json(), encoding="utf-8")
        comparisons.append({"baseline": baseline, "variation": variation, "file": filename})
    (workspace / "exports" / "comparisons.yaml").write_text(
        yaml.safe_dump({"comparisons": comparisons}, sort_keys=False),
        encoding="utf-8",
    )


def _write_report_outputs(workspace: Path) -> int:
    reports = {
        "baseline_run.md": report_to_markdown(
            build_run_report(workspace / "bundles" / "baseline", clock=_fixed_clock)
        ),
        "baseline_vs_stressed.md": report_to_markdown(
            build_comparison_report(
                workspace / "bundles" / "baseline",
                workspace / "bundles" / "stressed_demand",
                clock=_fixed_clock,
            )
        ),
        "under_offloading_diagnostics.md": report_to_markdown(
            build_diagnostics_report(
                workspace / "bundles" / "under_offloading",
                clock=_fixed_clock,
            )
        ),
        "stressed_full.html": report_to_html(
            build_full_report(
                workspace / "bundles" / "stressed_demand",
                comparison_baseline=workspace / "bundles" / "baseline",
                clock=_fixed_clock,
            )
        ),
    }
    for filename, payload in reports.items():
        (workspace / "reports" / filename).write_text(payload, encoding="utf-8")
    return len(reports)


def _write_workspace_manifest(workspace: Path, bundle_paths: list[Path]) -> Path:
    manifest = {
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "workspace_type": WORKSPACE_KIND,
        "created_at": DETERMINISTIC_CREATED_AT,
        "synthetic": True,
        "generator": "TrafficTwin standalone synthetic generator",
        "registry": "registry.sqlite",
        "scenarios": [
            {
                "name": path.name,
                "bundle": _workspace_relative(workspace, path),
                "expected_behavior": _expected_behavior(path.name),
            }
            for path in bundle_paths
        ],
        "comparisons": [
            "baseline_vs_stressed_demand",
            "baseline_vs_under_offloading",
            "baseline_vs_infrastructure_bottleneck",
        ],
        "disclaimer": (
            "Synthetic data supports software demonstration only; it is not real Manchester, "
            "Randy/VEC, or SUMO output."
        ),
    }
    manifest_path = workspace / "workspace.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return manifest_path


def _read_workspace_manifest(workspace: Path) -> dict[str, object]:
    manifest_path = workspace / "workspace.yaml"
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("workspace_type") != WORKSPACE_KIND:
        msg = f"not a TrafficTwin standalone demo workspace: {workspace}"
        raise ValueError(msg)
    return raw


def _require_workspace_marker(workspace: Path) -> None:
    _read_workspace_manifest(workspace)


def _reset_existing_workspace(workspace: Path) -> None:
    if workspace.exists():
        _ensure_safe_workspace_path(workspace)
        if any(workspace.iterdir()):
            if (workspace / "workspace.yaml").exists():
                _require_workspace_marker(workspace)
            for child in workspace.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
    workspace.mkdir(parents=True, exist_ok=True)


def _ensure_safe_workspace_path(workspace: Path) -> None:
    resolved = workspace.resolve()
    blocked = {Path("/").resolve(), Path.home().resolve(), Path.cwd().resolve()}
    if resolved in blocked or resolved.parent == resolved:
        msg = f"unsafe workspace path: {workspace}"
        raise ValueError(msg)


def _workspace_relative(workspace: Path, path: Path) -> str:
    return path.relative_to(workspace).as_posix()


def _expected_behavior(name: str) -> str:
    if name == "baseline":
        return "high completion, moderate utilisation, no strong hypothesis"
    if name == "stressed_demand":
        return "lower completion, longer queues, longer trips"
    if name == "under_offloading":
        return "R1 under-offloading candidate"
    if name == "infrastructure_bottleneck":
        return "R2 infrastructure-bottleneck candidate"
    if name == "mixed_fault":
        return "R1 and R2 may both be plausible"
    if name == "partial_evidence":
        return "R0 and insufficient-evidence statuses"
    if "trivial_multi_algorithm" in name:
        return "low-pressure policy-profile replicate for R3 evidence"
    return "synthetic standalone run"


def _fixed_clock() -> datetime:
    return datetime(2026, 7, 18, tzinfo=UTC)
