"""Private supervisor/viva pack and permission-gated TOS publication staging."""

from __future__ import annotations

import hashlib
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.integration.tos.analysis_models import TosReproducibilityAudit
from traffictwin.integration.tos.audit import audit_tos_package
from traffictwin.integration.tos.exports import build_static_results_atlas, write_tos_results_pack
from traffictwin.integration.tos.readiness import (
    ReadinessStatus,
    build_tos_integration_readiness,
)

Clock = Callable[[], datetime]


class SupervisorPackArtifact(BaseModel):
    """One checksummed artifact in a private research pack."""

    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str
    media_type: str
    purpose: str


class TosSupervisorPackManifest(BaseModel):
    """Manifest for a private, non-public TOS supervisor pack."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    pack_id: str
    generated_at: datetime
    classification: str = "private_research_material"
    synthetic: bool = False
    publication_permission_required: bool = True
    licence_status: str = "Licence not yet specified."
    package_fingerprint: str
    package_commit: str | None
    semantics_source_commit: str
    artifacts: list[SupervisorPackArtifact]
    blocked_capabilities: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return finite, deterministic JSON."""

        return self.model_dump_json(indent=2)


@dataclass(frozen=True)
class TosSupervisorPack:
    """Paths written for private supervisor and viva review."""

    directory: Path
    manifest: Path
    checksums: Path
    readme: Path
    viva_notes: Path
    evaluation_plan: Path
    screenshot_checklist: Path
    results_directory: Path


def write_tos_supervisor_pack(
    root: str | Path,
    output: str | Path,
    *,
    variation_campaign: str = "ukfleettrain_mappo",
    clock: Clock | None = None,
) -> TosSupervisorPack:
    """Write a private pack without granting publication permission."""

    target = Path(output)
    _require_empty_output(target)
    target.mkdir(parents=True, exist_ok=True)
    now = (clock or _utc_now)()
    results = write_tos_results_pack(
        root,
        target / "results",
        variation_campaign=variation_campaign,
        clock=lambda: now,
    )
    audit = audit_tos_package(root, clock=lambda: now)
    readiness = build_tos_integration_readiness(root, clock=lambda: now)
    readiness_path = target / "integration-readiness.json"
    readiness_path.write_text(readiness.to_json() + "\n", encoding="utf-8")
    readme = target / "README.md"
    readme.write_text(_pack_readme(variation_campaign), encoding="utf-8")
    viva_notes = target / "viva-notes.md"
    viva_notes.write_text(_viva_notes(audit), encoding="utf-8")
    evaluation_plan = target / "dissertation-evaluation.md"
    evaluation_plan.write_text(_evaluation_plan(variation_campaign), encoding="utf-8")
    screenshot_checklist = target / "screenshot-checklist.md"
    screenshot_checklist.write_text(_screenshot_checklist(), encoding="utf-8")

    artifact_specs = {
        readme: ("text/markdown", "Pack entry point and handling constraints."),
        viva_notes: ("text/markdown", "Candid viva talking points grounded in inspected evidence."),
        evaluation_plan: (
            "text/markdown",
            "Descriptive evaluation plan without causal or external-validity claims.",
        ),
        screenshot_checklist: ("text/markdown", "Repeatable private screenshot capture sequence."),
        readiness_path: (
            "application/json",
            "Machine-readable external-integration and permission gates.",
        ),
        results.markdown_report: ("text/markdown", "Deterministic aggregate research report."),
        results.html_report: ("text/html", "Self-contained aggregate research report."),
        results.matrix_json: ("application/json", "Evaluation matrix with descriptive statistics."),
        results.comparison_json: ("application/json", "Common-seed paired campaign comparison."),
        results.audit_json: ("application/json", "Reproducibility and artifact-coverage audit."),
        results.atlas_html: ("text/html", "Private interactive aggregate results atlas."),
    }
    artifacts = [
        SupervisorPackArtifact(
            path=path.relative_to(target).as_posix(),
            sha256=_sha256(path),
            media_type=media_type,
            purpose=purpose,
        )
        for path, (media_type, purpose) in sorted(
            artifact_specs.items(), key=lambda item: item[0].relative_to(target).as_posix()
        )
    ]
    blocked = sorted(
        capability
        for capability, status in readiness.capabilities.items()
        if status is not ReadinessStatus.READY
    )
    manifest_model = TosSupervisorPackManifest(
        pack_id=f"tos-supervisor-{audit.package_fingerprint[:12]}",
        generated_at=now,
        package_fingerprint=audit.package_fingerprint,
        package_commit=audit.package_commit,
        semantics_source_commit=audit.semantics_source_commit,
        artifacts=artifacts,
        blocked_capabilities=blocked,
        warnings=[
            "Keep this pack private until source-data publication permission is recorded.",
            "Imported simulation evidence does not establish real-world causality or validity.",
            "The repository licence has not yet been specified.",
        ],
    )
    manifest = target / "manifest.json"
    manifest.write_text(manifest_model.to_json() + "\n", encoding="utf-8")
    checksums = target / "checksums.sha256"
    checksummed = [*artifact_specs, manifest]
    checksums.write_text(
        "".join(
            f"{_sha256(path)}  {path.relative_to(target).as_posix()}\n"
            for path in sorted(checksummed, key=lambda item: item.relative_to(target).as_posix())
        ),
        encoding="utf-8",
    )
    return TosSupervisorPack(
        directory=target,
        manifest=manifest,
        checksums=checksums,
        readme=readme,
        viva_notes=viva_notes,
        evaluation_plan=evaluation_plan,
        screenshot_checklist=screenshot_checklist,
        results_directory=results.directory,
    )


def build_tos_supervisor_pack_zip(
    root: str | Path,
    *,
    variation_campaign: str = "ukfleettrain_mappo",
    clock: Clock | None = None,
) -> bytes:
    """Build a bounded in-memory ZIP for deliberate UI download."""

    with tempfile.TemporaryDirectory() as temp:
        pack = write_tos_supervisor_pack(
            root,
            Path(temp) / "supervisor-pack",
            variation_campaign=variation_campaign,
            clock=clock,
        )
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(pack.directory.rglob("*")):
                if not path.is_file():
                    continue
                info = zipfile.ZipInfo(
                    f"traffictwin-tos-supervisor-pack/{path.relative_to(pack.directory).as_posix()}",
                    date_time=(2026, 7, 18, 0, 0, 0),
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes())
        return buffer.getvalue()


def stage_public_tos_atlas(
    root: str | Path,
    output: str | Path,
    *,
    publication_permission_confirmed: bool = False,
    clock: Clock | None = None,
) -> Path:
    """Stage a public atlas only after an explicit permission attestation."""

    if not publication_permission_confirmed:
        raise PermissionError("public TOS atlas staging requires --confirm-publication-permission")
    target = Path(output)
    _require_empty_output(target)
    target.mkdir(parents=True, exist_ok=True)
    index = target / "index.html"
    index.write_text(build_static_results_atlas(root, clock=clock), encoding="utf-8")
    return index


def _require_empty_output(path: Path) -> None:
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise FileExistsError(f"output directory is not empty: {path}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pack_readme(variation_campaign: str) -> str:
    return f"""# TrafficTwin Private Supervisor Pack

Classification: **private research material**.

This pack contains aggregate imported-simulation evidence from Randy's supplied TOS package.
It is not live Manchester data, a real-world validation result, or permission to publish the
underlying outputs. The configured comparison is `baseline` versus `{variation_campaign}`.

Start with `results/research-report.html`, then inspect `results/results-atlas.html`,
`integration-readiness.json`, and `viva-notes.md`. Verify file integrity with
`checksums.sha256` before review.

Public sharing remains blocked until source-data permission is explicitly recorded. The
TrafficTwin repository licence is also not yet specified.
"""


def _viva_notes(audit: TosReproducibilityAudit) -> str:
    evaluation_count = audit.evaluation_run_count
    training_count = audit.training_history_count
    instrumented_count = audit.instrumented_run_count
    return f"""# Viva Notes: TOS Evidence

- TrafficTwin inspected {evaluation_count} evaluation summary rows and {training_count} training
  histories without modifying the source package.
- {instrumented_count} showcase runs contain per-step instrumentation; this does not cover every
  evaluation row.
- `task_met` is presented as deadline success, not eventual physical completion.
- `rsu_load` is in-flight task count and `rsu_busy_ms` is remaining compute backlog. Their ratio
  to the concurrency ceiling is pressure, not CPU utilisation.
- Processed FCD supports mobility replay but not persistent vehicle identity or trip duration.
- Comparisons are descriptive and paired by common fleet seed where possible. They do not prove
  causality or generalisation.
- Canonical conversion and direct launch remain blocked by missing producer, writer, checkpoint,
  outcome, identity, and runtime evidence.
"""


def _evaluation_plan(variation_campaign: str) -> str:
    return f"""# Dissertation Evaluation Plan

## Current Evidence

1. Describe the validated campaign/cell/fleet matrix using the source-analysis catalogue.
2. Compare `baseline` with `{variation_campaign}` using exact common fleet seeds.
3. Report sample size, mean, sample standard deviation, minimum, maximum, and paired differences.
4. Show training/evaluation domain labels as provenance context, retaining `unknown` values.
5. Use the reproducibility audit and package fingerprint to support repeatability claims.

## Interpretation Boundary

- Report associations and observed differences, not causes.
- Treat deadline success separately from eventual completion.
- Do not call RSU pressure CPU utilisation.
- Do not claim trip or journey-time results from processed FCD.
- Do not promote R1-R3 from insufficient evidence without their required canonical evidence.
- Do not describe these imported simulations as live or externally validated Manchester results.

## Blocked Evaluation

Real R1/R2 evaluation, canonical journey time, and executable-environment reproduction remain
blocked in `integration-readiness.json`.
"""


def _screenshot_checklist() -> str:
    return """# Private Screenshot Checklist

1. Home: show imported-simulation and not-live notices.
2. TOS Results: capture the selected fleet, measure, and sample-size columns.
3. TOS Results: capture one compatible common-seed paired comparison.
4. TOS Mobility & RSU Replay: capture the historical-replay badge and source caveats.
5. TOS Training & Audit: capture the training-distribution warning and audit table.
6. TOS Training & Audit: capture the publication-permission warning.
7. Record the package fingerprint and selected campaign in the screenshot caption.

Do not publish screenshots until Randy-derived aggregate publication permission is recorded.
"""


def _utc_now() -> datetime:
    return datetime.now(UTC)
