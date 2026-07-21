"""Read-only operational diagnostics for TrafficTwin installations and workspaces."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sys
from enum import StrEnum
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as distribution_version
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from traffictwin.config.capabilities import (
    CapabilityManifest,
    default_export_import_manifest,
)
from traffictwin.demo.workspace import WORKSPACE_KIND, WORKSPACE_SCHEMA_VERSION
from traffictwin.ingestion.bundle import inspect_bundle_cache
from traffictwin.ingestion.cache import (
    CanonicalCacheConfigurationError,
    CanonicalCacheState,
    CanonicalCacheStatus,
)
from traffictwin.integration.sumo import sumo_results_capability_manifest
from traffictwin.integration.tos import tos_data_capability_manifest
from traffictwin.release.metadata import current_release_metadata
from traffictwin.storage.migrations import (
    RegistryMigrationError,
    RegistryMigrationState,
    RegistryMigrationStatus,
    inspect_registry_migrations,
)

DOCTOR_SCHEMA_VERSION = "1.0"
DOCTOR_CONTRACT_VERSION = "traffictwin-doctor-v1"
DOCTOR_CAPABILITY_ID = "OPS-03"
MAX_WORKSPACE_MANIFEST_BYTES = 1_000_000
WORKSPACE_DIRECTORIES = ("seeds", "bundles", "reports", "exports", "logs")


class DoctorModel(BaseModel):
    """Strict base for machine-readable doctor artifacts."""

    model_config = ConfigDict(extra="forbid")


class DoctorCheckStatus(StrEnum):
    """Outcome of one read-only operational check."""

    PASS = "pass"  # noqa: S105 - diagnostic state, not a password.
    WARNING = "warning"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"


class DoctorOverallStatus(StrEnum):
    """Aggregate state of all checks required by the requested invocation."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    BLOCKED = "blocked"


class DoctorCategory(StrEnum):
    """Stable category labels for operational checks."""

    RUNTIME = "runtime"
    DEPENDENCY = "dependency"
    INTEGRATION = "integration"
    WORKSPACE = "workspace"
    REGISTRY = "registry"
    PERMISSION = "permission"
    CACHE = "cache"
    CAPABILITY = "capability"
    CONFIGURATION = "configuration"


class DoctorDependencyKind(StrEnum):
    """Relationship between TrafficTwin and an inspected dependency."""

    CORE = "core"
    OPTIONAL = "optional"
    EXTERNAL_COMMAND = "external_command"


class DoctorCheck(DoctorModel):
    """One evidence-backed diagnostic result."""

    check_id: str = Field(pattern=r"^[a-z0-9_.-]+$")
    category: DoctorCategory
    status: DoctorCheckStatus
    required: bool
    title: str
    detail: str
    observed: str | None = None
    remediation: str | None = None


class DoctorDependency(DoctorModel):
    """Installed-state evidence for one Python distribution or command."""

    name: str
    kind: DoctorDependencyKind
    required: bool
    available: bool
    version: str | None = None
    location: str | None = None
    purpose: str


class DoctorCapabilitySummary(DoctorModel):
    """Complete source-adapter capability truth without inferred support."""

    adapter: str
    supported: list[str]
    unsupported: list[str]
    unknown: list[str]


class DoctorWorkspaceDiagnosis(DoctorModel):
    """Bounded structural diagnosis of one standalone workspace."""

    path: str
    status: DoctorCheckStatus
    schema_version: str | None = None
    workspace_type: str | None = None
    synthetic: bool | None = None
    scenario_count: int = Field(default=0, ge=0)
    missing_required_paths: list[str] = Field(default_factory=list)
    unsafe_declared_paths: list[str] = Field(default_factory=list)
    registry_path: str | None = None


class DoctorRegistryDiagnosis(DoctorModel):
    """Read-only schema/integrity result for one distinct registry target."""

    path: str
    sources: list[str]
    status: DoctorCheckStatus
    migration: RegistryMigrationStatus | None = None
    error: str | None = None


class DoctorTargets(DoctorModel):
    """Exact caller-selected paths; absent targets remain explicit."""

    workspace: str | None = None
    registry: str | None = None
    bundle: str | None = None
    cache_root: str | None = None


class DoctorReport(DoctorModel):
    """Complete non-mutating OPS-03 diagnosis."""

    schema_version: str = DOCTOR_SCHEMA_VERSION
    capability_id: str = DOCTOR_CAPABILITY_ID
    contract_version: str = DOCTOR_CONTRACT_VERSION
    implementation_version: str
    overall_status: DoctorOverallStatus
    read_only: bool = True
    mutations_performed: bool = False
    targets: DoctorTargets
    dependencies: list[DoctorDependency]
    checks: list[DoctorCheck]
    capability_summaries: list[DoctorCapabilitySummary]
    workspace: DoctorWorkspaceDiagnosis | None = None
    registries: list[DoctorRegistryDiagnosis] = Field(default_factory=list)
    cache: CanonicalCacheStatus | None = None
    counts_by_status: dict[str, int]
    blocking_check_ids: list[str]

    def canonical_json(self) -> str:
        """Return a stable JSON representation for this observed environment state."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint the complete observed report."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class DoctorContract(DoctorModel):
    """Published operational and non-mutation boundary for OPS-03."""

    schema_version: str = DOCTOR_SCHEMA_VERSION
    capability_id: str = DOCTOR_CAPABILITY_ID
    contract_version: str = DOCTOR_CONTRACT_VERSION
    command: str = "traffictwin doctor"
    check_categories: list[DoctorCategory]
    status_semantics: dict[str, str]
    overall_status_policy: dict[str, str]
    required_python: str
    required_distributions: list[str]
    optional_distributions: list[str]
    optional_commands: list[str]
    target_options: list[str]
    capability_sources: list[str]
    read_only_policy: list[str]
    permission_policy: list[str]
    exit_policy: str
    exclusions: list[str]
    limitations: list[str]

    def canonical_json(self) -> str:
        """Return the byte-stable public contract."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint the public doctor contract."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


_CORE_DISTRIBUTIONS: tuple[tuple[str, str], ...] = (
    ("pydantic", "typed contracts and validation"),
    ("plotly", "interactive charts"),
    ("pyarrow", "Parquet ingestion and canonical caching"),
    ("PyYAML", "manifest, seed, and rule YAML"),
    ("reportlab", "PDF rendering"),
    ("streamlit", "thin local user interface"),
    ("typer", "command-line interface"),
)

_OPTIONAL_DISTRIBUTIONS: tuple[tuple[str, str], ...] = (
    ("numpy", "read-only TOS NPZ analysis"),
    ("playwright", "browser semantic and screenshot audits"),
    ("pypdf", "PDF verification in development and release checks"),
)

_OPTIONAL_COMMANDS: tuple[tuple[str, str], ...] = (
    ("sumo", "external SUMO installation; its presence does not enable direct launch"),
    ("tectonic", "optional real LaTeX compilation verification"),
    ("dot", "optional Graphviz rendering of exported DOT graphs"),
)


def doctor_contract() -> DoctorContract:
    """Return the exact OPS-03 diagnostic boundary."""

    return DoctorContract(
        check_categories=list(DoctorCategory),
        status_semantics={
            DoctorCheckStatus.PASS.value: "The observed evidence satisfies this exact check.",
            DoctorCheckStatus.WARNING.value: (
                "The requested workflow remains inspectable, but operator attention is needed."
            ),
            DoctorCheckStatus.BLOCKED.value: (
                "The requested workflow cannot safely proceed under the observed state."
            ),
            DoctorCheckStatus.UNAVAILABLE.value: (
                "The optional component or evidence was absent; it is never treated as zero or "
                "pass."
            ),
        },
        overall_status_policy={
            DoctorOverallStatus.HEALTHY.value: "Every requested required check passed.",
            DoctorOverallStatus.DEGRADED.value: (
                "No requested required check is blocked, but at least one required warning exists."
            ),
            DoctorOverallStatus.BLOCKED.value: (
                "At least one requested required check is blocked or unavailable."
            ),
        },
        required_python=">=3.11",
        required_distributions=[name for name, _ in _CORE_DISTRIBUTIONS],
        optional_distributions=[name for name, _ in _OPTIONAL_DISTRIBUTIONS],
        optional_commands=[name for name, _ in _OPTIONAL_COMMANDS],
        target_options=["workspace", "registry", "bundle + cache_root"],
        capability_sources=["generic_csv", "sumo_results_v1", "tos_data_read_only"],
        read_only_policy=[
            "No directory, registry, cache entry, manifest, or raw bundle is created or modified.",
            "Registry inspection reuses the immutable read-only OPS-01 connection.",
            "Cache inspection reuses the read-only OPS-02 raw re-fingerprint and entry verifier.",
            "Workspace checks parse only the bounded marker and inspect declared paths.",
        ],
        permission_policy=[
            "Local access is probed with os.access and does not prove future access or ACL policy.",
            "Write access is reported but never exercised.",
            "Unknown TOS fixture/publication permission is never treated as granted.",
        ],
        exit_policy=(
            "Exit zero for healthy or degraded reports; exit one only when a requested required "
            "check is blocked or unavailable."
        ),
        exclusions=[
            "No package installation, registry migration, cache repair, permission change, or "
            "cleanup.",
            "No simulator, evaluator, browser, LaTeX compiler, Graphviz process, or network call.",
            "No scientific validation, metric computation, diagnosis, or external-validity claim.",
        ],
        limitations=[
            "Dependency presence does not prove every platform-specific runtime path works.",
            "Filesystem access checks are point-in-time advisory observations.",
            "Workspace inspection is structural and does not revalidate every contained bundle.",
            "SUMO executable presence never implies TrafficTwin launch support.",
        ],
    )


def run_doctor(
    *,
    workspace: str | Path | None = None,
    registry: str | Path | None = None,
    bundle: str | Path | None = None,
    cache_root: str | Path | None = None,
) -> DoctorReport:
    """Inspect runtime and selected local targets without mutating any observed artifact."""

    targets = DoctorTargets(
        workspace=str(workspace) if workspace is not None else None,
        registry=str(registry) if registry is not None else None,
        bundle=str(bundle) if bundle is not None else None,
        cache_root=str(cache_root) if cache_root is not None else None,
    )
    checks: list[DoctorCheck] = []
    dependencies = _diagnose_dependencies(checks)
    _diagnose_integrations(checks, dependencies)
    capability_summaries = [
        _capability_summary(default_export_import_manifest()),
        _capability_summary(sumo_results_capability_manifest()),
        _capability_summary(tos_data_capability_manifest()),
    ]
    _diagnose_capability_boundaries(checks)

    workspace_diagnosis: DoctorWorkspaceDiagnosis | None = None
    registry_targets: list[tuple[str, Path]] = []
    if workspace is None:
        checks.append(
            _check(
                "workspace.not_requested",
                DoctorCategory.WORKSPACE,
                DoctorCheckStatus.UNAVAILABLE,
                False,
                "Workspace target",
                "No workspace was requested; no workspace files were inspected.",
            )
        )
    else:
        workspace_diagnosis, inferred_registry = _diagnose_workspace(Path(workspace), checks)
        if inferred_registry is not None:
            registry_targets.append(("workspace", inferred_registry))

    if registry is None:
        if not registry_targets:
            checks.append(
                _check(
                    "registry.not_requested",
                    DoctorCategory.REGISTRY,
                    DoctorCheckStatus.UNAVAILABLE,
                    False,
                    "Registry target",
                    "No explicit or workspace registry was requested.",
                )
            )
    else:
        registry_targets.append(("explicit", Path(registry)))
    registries = _diagnose_registries(registry_targets, checks)
    cache = _diagnose_cache(bundle, cache_root, checks)

    blocking = [
        check.check_id
        for check in checks
        if check.required
        and check.status in {DoctorCheckStatus.BLOCKED, DoctorCheckStatus.UNAVAILABLE}
    ]
    if blocking:
        overall = DoctorOverallStatus.BLOCKED
    elif any(check.required and check.status is DoctorCheckStatus.WARNING for check in checks):
        overall = DoctorOverallStatus.DEGRADED
    else:
        overall = DoctorOverallStatus.HEALTHY
    counts = {
        status.value: sum(check.status is status for check in checks)
        for status in DoctorCheckStatus
    }
    return DoctorReport(
        implementation_version=current_release_metadata().version,
        overall_status=overall,
        targets=targets,
        dependencies=dependencies,
        checks=checks,
        capability_summaries=capability_summaries,
        workspace=workspace_diagnosis,
        registries=registries,
        cache=cache,
        counts_by_status=counts,
        blocking_check_ids=blocking,
    )


def doctor_report_to_text(report: DoctorReport) -> str:
    """Render one compact deterministic text diagnosis for the thin CLI."""

    lines = [
        "TrafficTwin doctor",
        f"overall_status: {report.overall_status.value}",
        f"implementation_version: {report.implementation_version}",
        "read_only: true",
        "mutations_performed: false",
        f"report_fingerprint: {report.fingerprint()}",
        "checks:",
    ]
    for check in report.checks:
        required = "required" if check.required else "optional"
        lines.append(f"  [{check.status.value}] {check.check_id} ({required}): {check.detail}")
        if check.remediation is not None:
            lines.append(f"    remediation: {check.remediation}")
    lines.append("capability_summaries:")
    for summary in report.capability_summaries:
        lines.append(
            f"  {summary.adapter}: supported={len(summary.supported)} "
            f"unsupported={len(summary.unsupported)} unknown={len(summary.unknown)}"
        )
        if summary.unsupported:
            lines.append("    unsupported: " + ", ".join(summary.unsupported))
        if summary.unknown:
            lines.append("    unknown: " + ", ".join(summary.unknown))
    return "\n".join(lines) + "\n"


def doctor_contract_to_text(contract: DoctorContract) -> str:
    """Render the public OPS-03 contract without performing any diagnosis."""

    lines = [
        f"schema_version: {contract.schema_version}",
        f"capability_id: {contract.capability_id}",
        f"contract_version: {contract.contract_version}",
        f"command: {contract.command}",
        f"required_python: {contract.required_python}",
        "required_distributions: " + ", ".join(contract.required_distributions),
        "optional_distributions: " + ", ".join(contract.optional_distributions),
        "optional_commands: " + ", ".join(contract.optional_commands),
        f"exit_policy: {contract.exit_policy}",
        f"fingerprint: {contract.fingerprint()}",
    ]
    return "\n".join(lines) + "\n"


def _diagnose_dependencies(checks: list[DoctorCheck]) -> list[DoctorDependency]:
    dependencies: list[DoctorDependency] = []
    python_version = platform.python_version()
    python_supported = sys.version_info >= (3, 11)
    checks.append(
        _check(
            "runtime.python",
            DoctorCategory.RUNTIME,
            DoctorCheckStatus.PASS if python_supported else DoctorCheckStatus.BLOCKED,
            True,
            "Python runtime",
            (
                f"Python {python_version} satisfies >=3.11."
                if python_supported
                else f"Python {python_version} is below the supported >=3.11 boundary."
            ),
            observed=f"{python_version} ({sys.executable})",
            remediation="Install and select Python 3.11 or newer."
            if not python_supported
            else None,
        )
    )
    checks.append(
        _check(
            "runtime.platform",
            DoctorCategory.RUNTIME,
            DoctorCheckStatus.PASS,
            True,
            "Operating-system runtime",
            "The active platform was identified without invoking an external command.",
            observed=platform.platform(),
        )
    )
    release = current_release_metadata()
    dependencies.append(
        DoctorDependency(
            name="traffictwin",
            kind=DoctorDependencyKind.CORE,
            required=True,
            available=True,
            version=release.version,
            purpose="active TrafficTwin implementation",
        )
    )
    checks.append(
        _check(
            "dependency.traffictwin",
            DoctorCategory.DEPENDENCY,
            DoctorCheckStatus.PASS,
            True,
            "TrafficTwin package",
            f"TrafficTwin {release.version} is active.",
            observed=release.version,
        )
    )
    for name, purpose in _CORE_DISTRIBUTIONS:
        dependency = _python_dependency(name, purpose, required=True)
        dependencies.append(dependency)
        checks.append(_dependency_check(dependency, check_id=f"dependency.{name.lower()}"))
    for name, purpose in _OPTIONAL_DISTRIBUTIONS:
        dependency = _python_dependency(name, purpose, required=False)
        dependencies.append(dependency)
        checks.append(_dependency_check(dependency, check_id=f"dependency.optional.{name.lower()}"))
    for name, purpose in _OPTIONAL_COMMANDS:
        location = shutil.which(name)
        dependency = DoctorDependency(
            name=name,
            kind=DoctorDependencyKind.EXTERNAL_COMMAND,
            required=False,
            available=location is not None,
            location=location,
            purpose=purpose,
        )
        dependencies.append(dependency)
        checks.append(_dependency_check(dependency, check_id=f"dependency.command.{name}"))
    return dependencies


def _python_dependency(name: str, purpose: str, *, required: bool) -> DoctorDependency:
    try:
        version = distribution_version(name)
    except PackageNotFoundError:
        version = None
    return DoctorDependency(
        name=name,
        kind=DoctorDependencyKind.CORE if required else DoctorDependencyKind.OPTIONAL,
        required=required,
        available=version is not None,
        version=version,
        purpose=purpose,
    )


def _dependency_check(dependency: DoctorDependency, *, check_id: str) -> DoctorCheck:
    if dependency.available:
        observed = dependency.version or dependency.location or "available"
        return _check(
            check_id,
            DoctorCategory.DEPENDENCY,
            DoctorCheckStatus.PASS,
            dependency.required,
            dependency.name,
            f"{dependency.name} is available for {dependency.purpose}.",
            observed=observed,
        )
    status = DoctorCheckStatus.BLOCKED if dependency.required else DoctorCheckStatus.UNAVAILABLE
    if dependency.kind is DoctorDependencyKind.EXTERNAL_COMMAND:
        detail = f"The optional {dependency.name} command is unavailable; {dependency.purpose}."
    else:
        detail = f"{dependency.name} is unavailable; {dependency.purpose} is not enabled."
    return _check(
        check_id,
        DoctorCategory.DEPENDENCY,
        status,
        dependency.required,
        dependency.name,
        detail,
        remediation=(
            f"Install the required {dependency.name} distribution."
            if dependency.required
            else f"Install {dependency.name} only if this optional workflow is needed."
        ),
    )


def _diagnose_integrations(
    checks: list[DoctorCheck],
    dependencies: list[DoctorDependency],
) -> None:
    dependency_by_name = {item.name: item for item in dependencies}
    checks.extend(
        [
            _check(
                "integration.generic-import",
                DoctorCategory.INTEGRATION,
                DoctorCheckStatus.PASS,
                True,
                "Generic import-first adapter",
                "The guaranteed generic directory/ZIP import path is built in.",
            ),
            _check(
                "integration.sumo-output",
                DoctorCategory.INTEGRATION,
                DoctorCheckStatus.PASS,
                False,
                "SUMO output adapter",
                "The evidenced import-only SUMO results adapter is built in; no SUMO executable "
                "is required.",
            ),
        ]
    )
    numpy_available = dependency_by_name["numpy"].available
    checks.append(
        _check(
            "integration.tos-read-only",
            DoctorCategory.INTEGRATION,
            DoctorCheckStatus.PASS if numpy_available else DoctorCheckStatus.UNAVAILABLE,
            False,
            "TOS read-only array workbench",
            (
                "The optional numpy dependency is available for local NPZ inspection."
                if numpy_available
                else "The TOS NPZ workbench remains unavailable because numpy is not installed."
            ),
            remediation="Install the 'tos' extra only if TOS NPZ inspection is required."
            if not numpy_available
            else None,
        )
    )
    checks.extend(
        [
            _check(
                "permission.tos-fixture",
                DoctorCategory.PERMISSION,
                DoctorCheckStatus.UNAVAILABLE,
                False,
                "TOS sanitised-fixture permission",
                "No permission evidence was supplied; unknown is not treated as granted.",
                remediation="Record written permission before committing a source-derived fixture.",
            ),
            _check(
                "permission.tos-publication",
                DoctorCategory.PERMISSION,
                DoctorCheckStatus.UNAVAILABLE,
                False,
                "TOS aggregate-publication permission",
                "No permission evidence was supplied; public sharing remains permission-gated.",
                remediation="Obtain written permission before public TOS publication.",
            ),
        ]
    )


def _diagnose_capability_boundaries(checks: list[DoctorCheck]) -> None:
    checks.extend(
        [
            _check(
                "capability.direct-launch",
                DoctorCategory.CAPABILITY,
                DoctorCheckStatus.BLOCKED,
                False,
                "Direct simulator launch",
                "Direct Randy/VEC and SUMO launch remains deliberately unsupported.",
            ),
            _check(
                "capability.asynchronous-launch",
                DoctorCategory.CAPABILITY,
                DoctorCheckStatus.BLOCKED,
                False,
                "Asynchronous simulation launch",
                "No evidenced asynchronous simulation queue or launcher exists.",
            ),
            _check(
                "capability.tos-canonical-conversion",
                DoctorCategory.CAPABILITY,
                DoctorCheckStatus.BLOCKED,
                False,
                "TOS canonical conversion",
                "Producer, persistent identity, eventual outcome, and decision-context evidence "
                "remain incomplete.",
            ),
        ]
    )


def _capability_summary(manifest: CapabilityManifest) -> DoctorCapabilitySummary:
    values = manifest.supports.as_manifest_dict()
    return DoctorCapabilitySummary(
        adapter=manifest.adapter,
        supported=[key for key, value in values.items() if value is True],
        unsupported=[key for key, value in values.items() if value is False],
        unknown=[key for key, value in values.items() if value == "unknown"],
    )


def _diagnose_workspace(
    workspace: Path,
    checks: list[DoctorCheck],
) -> tuple[DoctorWorkspaceDiagnosis, Path | None]:
    display = str(workspace)
    if not workspace.exists():
        checks.append(
            _check(
                "workspace.root",
                DoctorCategory.WORKSPACE,
                DoctorCheckStatus.BLOCKED,
                True,
                "Workspace root",
                f"Workspace does not exist: {display}",
                remediation=(
                    "Select an existing TrafficTwin workspace or initialise one explicitly."
                ),
            )
        )
        return DoctorWorkspaceDiagnosis(path=display, status=DoctorCheckStatus.BLOCKED), None
    if not workspace.is_dir():
        checks.append(
            _check(
                "workspace.root",
                DoctorCategory.WORKSPACE,
                DoctorCheckStatus.BLOCKED,
                True,
                "Workspace root",
                f"Workspace target is not a directory: {display}",
            )
        )
        return DoctorWorkspaceDiagnosis(path=display, status=DoctorCheckStatus.BLOCKED), None
    read_ok, _ = _diagnose_path_permissions(
        checks,
        "workspace",
        workspace,
        require_read=True,
        report_write=True,
    )
    if not read_ok:
        return DoctorWorkspaceDiagnosis(path=display, status=DoctorCheckStatus.BLOCKED), None
    checks.append(
        _check(
            "workspace.root",
            DoctorCategory.WORKSPACE,
            DoctorCheckStatus.PASS,
            True,
            "Workspace root",
            f"Workspace directory is present: {display}",
        )
    )
    marker = workspace / "workspace.yaml"
    if not marker.is_file() or marker.is_symlink():
        checks.append(
            _check(
                "workspace.manifest",
                DoctorCategory.WORKSPACE,
                DoctorCheckStatus.BLOCKED,
                True,
                "Workspace manifest",
                "workspace.yaml is missing, not a regular file, or is symlinked.",
            )
        )
        return DoctorWorkspaceDiagnosis(path=display, status=DoctorCheckStatus.BLOCKED), None
    if marker.stat().st_size > MAX_WORKSPACE_MANIFEST_BYTES:
        checks.append(
            _check(
                "workspace.manifest",
                DoctorCategory.WORKSPACE,
                DoctorCheckStatus.BLOCKED,
                True,
                "Workspace manifest",
                "workspace.yaml exceeds the 1,000,000-byte doctor inspection limit.",
            )
        )
        return DoctorWorkspaceDiagnosis(path=display, status=DoctorCheckStatus.BLOCKED), None
    try:
        raw = yaml.safe_load(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        checks.append(
            _check(
                "workspace.manifest",
                DoctorCategory.WORKSPACE,
                DoctorCheckStatus.BLOCKED,
                True,
                "Workspace manifest",
                f"workspace.yaml is unreadable or invalid: {exc}",
            )
        )
        return DoctorWorkspaceDiagnosis(path=display, status=DoctorCheckStatus.BLOCKED), None
    if not isinstance(raw, dict):
        checks.append(
            _check(
                "workspace.manifest",
                DoctorCategory.WORKSPACE,
                DoctorCheckStatus.BLOCKED,
                True,
                "Workspace manifest",
                "workspace.yaml must contain a mapping.",
            )
        )
        return DoctorWorkspaceDiagnosis(path=display, status=DoctorCheckStatus.BLOCKED), None
    schema_version = raw.get("schema_version")
    workspace_type = raw.get("workspace_type")
    if schema_version != WORKSPACE_SCHEMA_VERSION or workspace_type != WORKSPACE_KIND:
        checks.append(
            _check(
                "workspace.manifest",
                DoctorCategory.WORKSPACE,
                DoctorCheckStatus.BLOCKED,
                True,
                "Workspace manifest",
                "Workspace kind or schema version is unsupported.",
                observed=f"schema={schema_version!r}, kind={workspace_type!r}",
            )
        )
        return (
            DoctorWorkspaceDiagnosis(
                path=display,
                status=DoctorCheckStatus.BLOCKED,
                schema_version=str(schema_version) if schema_version is not None else None,
                workspace_type=str(workspace_type) if workspace_type is not None else None,
            ),
            None,
        )
    checks.append(
        _check(
            "workspace.manifest",
            DoctorCategory.WORKSPACE,
            DoctorCheckStatus.PASS,
            True,
            "Workspace manifest",
            "workspace.yaml matches the standalone v1.0 marker contract.",
        )
    )
    missing = [name for name in WORKSPACE_DIRECTORIES if not (workspace / name).is_dir()]
    layout_status = DoctorCheckStatus.WARNING if missing else DoctorCheckStatus.PASS
    checks.append(
        _check(
            "workspace.layout",
            DoctorCategory.WORKSPACE,
            layout_status,
            True,
            "Workspace layout",
            (
                "Missing workspace directories: " + ", ".join(missing)
                if missing
                else "All required workspace directories are present."
            ),
            remediation="Restore missing workspace directories from a trusted workspace copy."
            if missing
            else None,
        )
    )
    scenarios = raw.get("scenarios")
    scenario_entries = scenarios if isinstance(scenarios, list) else []
    unsafe, absent = _inspect_declared_workspace_bundles(workspace, scenario_entries)
    scenario_status = (
        DoctorCheckStatus.BLOCKED
        if unsafe
        else (
            DoctorCheckStatus.WARNING
            if absent or not isinstance(scenarios, list)
            else DoctorCheckStatus.PASS
        )
    )
    scenario_detail = (
        "Unsafe declared bundle paths: " + ", ".join(unsafe)
        if unsafe
        else "Missing declared bundles: " + ", ".join(absent)
        if absent
        else f"All {len(scenario_entries)} declared scenario bundle paths are present."
    )
    checks.append(
        _check(
            "workspace.scenarios",
            DoctorCategory.WORKSPACE,
            scenario_status,
            True,
            "Workspace scenario inventory",
            scenario_detail,
        )
    )
    registry_value = raw.get("registry")
    registry_path: Path | None = None
    if isinstance(registry_value, str):
        candidate = (workspace / registry_value).resolve(strict=False)
        if candidate.is_relative_to(workspace.resolve(strict=False)):
            registry_path = workspace / registry_value
        else:
            unsafe.append(registry_value)
            checks.append(
                _check(
                    "workspace.registry-path",
                    DoctorCategory.WORKSPACE,
                    DoctorCheckStatus.BLOCKED,
                    True,
                    "Workspace registry declaration",
                    "The declared registry path escapes the workspace.",
                )
            )
    else:
        checks.append(
            _check(
                "workspace.registry-path",
                DoctorCategory.WORKSPACE,
                DoctorCheckStatus.BLOCKED,
                True,
                "Workspace registry declaration",
                "The workspace registry declaration is missing or not a string.",
            )
        )
    status = _worst_workspace_status(layout_status, scenario_status, registry_path is None)
    return (
        DoctorWorkspaceDiagnosis(
            path=display,
            status=status,
            schema_version=str(schema_version),
            workspace_type=str(workspace_type),
            synthetic=raw.get("synthetic") if isinstance(raw.get("synthetic"), bool) else None,
            scenario_count=len(scenario_entries),
            missing_required_paths=sorted({*missing, *absent}),
            unsafe_declared_paths=sorted(set(unsafe)),
            registry_path=str(registry_path) if registry_path is not None else None,
        ),
        registry_path,
    )


def _inspect_declared_workspace_bundles(
    workspace: Path,
    scenarios: list[Any],
) -> tuple[list[str], list[str]]:
    root = workspace.resolve(strict=False)
    unsafe: list[str] = []
    missing: list[str] = []
    for index, entry in enumerate(scenarios):
        if not isinstance(entry, dict) or not isinstance(entry.get("bundle"), str):
            unsafe.append(f"scenario[{index}]")
            continue
        declared = str(entry["bundle"])
        candidate = (workspace / declared).resolve(strict=False)
        if not candidate.is_relative_to(root):
            unsafe.append(declared)
        elif not candidate.exists():
            missing.append(declared)
    return sorted(unsafe), sorted(missing)


def _worst_workspace_status(
    layout: DoctorCheckStatus,
    scenarios: DoctorCheckStatus,
    registry_invalid: bool,
) -> DoctorCheckStatus:
    if registry_invalid or scenarios is DoctorCheckStatus.BLOCKED:
        return DoctorCheckStatus.BLOCKED
    if DoctorCheckStatus.WARNING in {layout, scenarios}:
        return DoctorCheckStatus.WARNING
    return DoctorCheckStatus.PASS


def _diagnose_registries(
    requested: list[tuple[str, Path]],
    checks: list[DoctorCheck],
) -> list[DoctorRegistryDiagnosis]:
    grouped: dict[Path, tuple[Path, list[str]]] = {}
    for source, path in requested:
        identity = path.expanduser().resolve(strict=False)
        if identity in grouped:
            grouped[identity][1].append(source)
        else:
            grouped[identity] = (path, [source])
    results: list[DoctorRegistryDiagnosis] = []
    for index, (_, (path, sources)) in enumerate(grouped.items(), start=1):
        prefix = f"registry.target-{index}"
        display = str(path)
        if not path.is_file():
            detail = f"Registry does not exist or is not a regular file: {display}"
            checks.append(
                _check(
                    f"{prefix}.integrity",
                    DoctorCategory.REGISTRY,
                    DoctorCheckStatus.BLOCKED,
                    True,
                    "Registry integrity",
                    detail,
                    remediation="Select an existing registry; doctor will not create one.",
                )
            )
            results.append(
                DoctorRegistryDiagnosis(
                    path=display,
                    sources=sources,
                    status=DoctorCheckStatus.BLOCKED,
                    error=detail,
                )
            )
            continue
        read_ok, _ = _diagnose_path_permissions(
            checks,
            prefix,
            path,
            require_read=True,
            report_write=True,
        )
        if not read_ok:
            detail = "Registry read permission is unavailable; integrity was not inspected."
            results.append(
                DoctorRegistryDiagnosis(
                    path=display,
                    sources=sources,
                    status=DoctorCheckStatus.BLOCKED,
                    error=detail,
                )
            )
            continue
        try:
            migration = inspect_registry_migrations(path)
        except (RegistryMigrationError, OSError) as exc:
            detail = str(exc)
            checks.append(
                _check(
                    f"{prefix}.integrity",
                    DoctorCategory.REGISTRY,
                    DoctorCheckStatus.BLOCKED,
                    True,
                    "Registry integrity",
                    detail,
                    remediation="Work on a copy and follow the registry recovery/migration guide.",
                )
            )
            results.append(
                DoctorRegistryDiagnosis(
                    path=display,
                    sources=sources,
                    status=DoctorCheckStatus.BLOCKED,
                    error=detail,
                )
            )
            continue
        current = migration.state is RegistryMigrationState.CURRENT
        status = DoctorCheckStatus.PASS if current else DoctorCheckStatus.WARNING
        detail = (
            f"Registry schema v{migration.current_version} is current and SQLite integrity is ok."
            if current
            else (
                f"Registry state is {migration.state.value}; pending versions are "
                f"{migration.pending_versions}."
            )
        )
        checks.append(
            _check(
                f"{prefix}.integrity",
                DoctorCategory.REGISTRY,
                status,
                True,
                "Registry integrity",
                detail,
                observed=migration.schema_fingerprint,
                remediation="Back up and run the explicit registry migrate command."
                if not current
                else None,
            )
        )
        results.append(
            DoctorRegistryDiagnosis(
                path=display,
                sources=sources,
                status=status,
                migration=migration,
            )
        )
    return results


def _diagnose_cache(
    bundle: str | Path | None,
    cache_root: str | Path | None,
    checks: list[DoctorCheck],
) -> CanonicalCacheStatus | None:
    if bundle is None and cache_root is None:
        checks.append(
            _check(
                "cache.not_requested",
                DoctorCategory.CACHE,
                DoctorCheckStatus.UNAVAILABLE,
                False,
                "Canonical cache target",
                "No bundle/cache-root pair was requested.",
            )
        )
        return None
    if bundle is None or cache_root is None:
        missing = "--bundle" if bundle is None else "--cache-root"
        checks.append(
            _check(
                "configuration.cache-targets",
                DoctorCategory.CONFIGURATION,
                DoctorCheckStatus.BLOCKED,
                True,
                "Cache diagnostic targets",
                f"Cache diagnosis requires both --bundle and --cache-root; {missing} is missing.",
            )
        )
        return None
    bundle_path = Path(bundle)
    cache_path = Path(cache_root)
    if not bundle_path.exists():
        checks.append(
            _check(
                "cache.bundle",
                DoctorCategory.CACHE,
                DoctorCheckStatus.BLOCKED,
                True,
                "Cache source bundle",
                f"Bundle does not exist: {bundle_path}",
            )
        )
        return None
    bundle_readable, _ = _diagnose_path_permissions(
        checks,
        "cache.bundle",
        bundle_path,
        require_read=True,
        report_write=False,
    )
    if not bundle_readable:
        return None
    if cache_path.exists():
        cache_readable, _ = _diagnose_path_permissions(
            checks,
            "cache.root",
            cache_path,
            require_read=True,
            report_write=True,
        )
        if not cache_readable:
            return None
    else:
        parent = _nearest_existing_parent(cache_path)
        writable = os.access(parent, os.W_OK | os.X_OK)
        checks.append(
            _check(
                "permission.cache-root-create",
                DoctorCategory.PERMISSION,
                DoctorCheckStatus.PASS if writable else DoctorCheckStatus.WARNING,
                True,
                "Cache-root creation permission",
                (
                    f"Existing parent permits cache-root creation: {parent}"
                    if writable
                    else f"Existing parent does not permit cache-root creation: {parent}"
                ),
                remediation="Choose a writable cache parent outside the raw bundle."
                if not writable
                else None,
            )
        )
    try:
        cache = inspect_bundle_cache(bundle_path, cache_path)
    except (CanonicalCacheConfigurationError, OSError) as exc:
        checks.append(
            _check(
                "cache.integrity",
                DoctorCategory.CACHE,
                DoctorCheckStatus.BLOCKED,
                True,
                "Canonical cache integrity",
                str(exc),
            )
        )
        return None
    state_status = {
        CanonicalCacheState.HIT: DoctorCheckStatus.PASS,
        CanonicalCacheState.MISS: DoctorCheckStatus.WARNING,
        CanonicalCacheState.STALE: DoctorCheckStatus.WARNING,
        CanonicalCacheState.INCOMPATIBLE: DoctorCheckStatus.WARNING,
        CanonicalCacheState.CORRUPT: DoctorCheckStatus.WARNING,
        CanonicalCacheState.UNAVAILABLE: DoctorCheckStatus.BLOCKED,
        CanonicalCacheState.WRITE_FAILED: DoctorCheckStatus.WARNING,
        CanonicalCacheState.WRITTEN: DoctorCheckStatus.PASS,
    }[cache.state]
    checks.append(
        _check(
            "cache.integrity",
            DoctorCategory.CACHE,
            state_status,
            True,
            "Canonical cache integrity",
            f"Cache state is {cache.state.value}: {cache.detail}",
            observed=cache.cache_key,
            remediation=(
                "Inspect the exact reported entry; doctor never deletes, repairs, or overwrites it."
                if cache.state
                in {
                    CanonicalCacheState.STALE,
                    CanonicalCacheState.INCOMPATIBLE,
                    CanonicalCacheState.CORRUPT,
                }
                else None
            ),
        )
    )
    return cache


def _diagnose_path_permissions(
    checks: list[DoctorCheck],
    label: str,
    path: Path,
    *,
    require_read: bool,
    report_write: bool,
) -> tuple[bool, bool]:
    traversal = os.X_OK if path.is_dir() else 0
    readable = os.access(path, os.R_OK | traversal)
    checks.append(
        _check(
            f"permission.{label}.read",
            DoctorCategory.PERMISSION,
            DoctorCheckStatus.PASS if readable else DoctorCheckStatus.BLOCKED,
            require_read,
            f"Read access: {label}",
            (
                f"Read access is currently available: {path}"
                if readable
                else f"Read access is currently unavailable: {path}"
            ),
            remediation="Grant the TrafficTwin process read/traverse access or choose another path."
            if not readable
            else None,
        )
    )
    writable = os.access(path, os.W_OK | traversal)
    if report_write:
        checks.append(
            _check(
                f"permission.{label}.write",
                DoctorCategory.PERMISSION,
                DoctorCheckStatus.PASS if writable else DoctorCheckStatus.WARNING,
                True,
                f"Write access: {label}",
                (
                    f"Write access is currently available but was not exercised: {path}"
                    if writable
                    else f"Write access is currently unavailable: {path}"
                ),
                remediation="Grant write access only if mutation workflows are intended."
                if not writable
                else None,
            )
        )
    return readable, writable


def _nearest_existing_parent(path: Path) -> Path:
    candidate = path.expanduser().resolve(strict=False)
    while not candidate.exists() and candidate.parent != candidate:
        candidate = candidate.parent
    return candidate


def _check(
    check_id: str,
    category: DoctorCategory,
    status: DoctorCheckStatus,
    required: bool,
    title: str,
    detail: str,
    *,
    observed: str | None = None,
    remediation: str | None = None,
) -> DoctorCheck:
    return DoctorCheck(
        check_id=check_id,
        category=category,
        status=status,
        required=required,
        title=title,
        detail=detail,
        observed=observed,
        remediation=remediation,
    )


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
