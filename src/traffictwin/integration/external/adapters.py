"""Reference implementations of the general external-source interface."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from traffictwin.integration.external.models import (
    ConversionLevel,
    DiscoveryStatus,
    ExternalAdapterContract,
    ExternalBlocker,
    ExternalConversionProfile,
    ExternalFieldSemantic,
    ExternalProvenanceObservation,
    ExternalProvenanceRequirement,
    ExternalSourceDiscovery,
    ExternalValidationSummary,
    MarkerKind,
    SemanticStatus,
    SourceMarker,
    ValidationOutcome,
)
from traffictwin.integration.sumo.contract import (
    sumo_results_capability_manifest,
    sumo_source_contract,
)
from traffictwin.integration.sumo.models import SUMO_ADAPTER_VERSION, SUMO_VALIDATOR_VERSION
from traffictwin.integration.sumo.validation import validate_sumo_results
from traffictwin.integration.tos.capabilities import tos_data_capability_manifest
from traffictwin.integration.tos.contract import tos_source_contract
from traffictwin.integration.tos.models import TOS_ADAPTER_VERSION
from traffictwin.integration.tos.validation import validate_tos_package

_INTERFACE_OPERATIONS = ["discover", "contract", "validate", "inspect"]


class SumoExternalSourceAdapter:
    """General-interface view of the public SUMO result adapter."""

    adapter_id = "sumo_results_v1"
    adapter_version = SUMO_ADAPTER_VERSION

    def contract(self) -> ExternalAdapterContract:
        """Return the source-neutral projection of the evidenced SUMO contract."""

        source = sumo_source_contract()
        semantics: list[ExternalFieldSemantic] = []
        for mapping in source.mappings:
            if mapping.source.startswith("tripinfo"):
                artifact = "declared tripinfo XML"
                evidence = [source.documentation["tripinfo"]]
            elif mapping.source.startswith("summary"):
                artifact = "declared summary XML"
                evidence = [source.documentation["summary"]]
            else:
                artifact = "SUMO FCD output"
                evidence = ["separate explicit mapping required"]
            status = (
                SemanticStatus.UNSUPPORTED
                if mapping.status == "unsupported"
                else SemanticStatus.CONFIRMED
            )
            semantics.append(
                ExternalFieldSemantic(
                    source_field=mapping.source,
                    artifact=artifact,
                    meaning=mapping.rule,
                    unit=mapping.unit,
                    status=status,
                    canonical_target=mapping.destination,
                    evidence=evidence,
                    limitations=(
                        ["The source field remains preserved but is not canonicalised."]
                        if mapping.destination is None
                        else []
                    ),
                )
            )
        return ExternalAdapterContract(
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            source_family="Eclipse SUMO completed result package",
            interface_operations=_INTERFACE_OPERATIONS,
            discovery_markers=[
                SourceMarker(
                    relative_path="sumo-source.yaml",
                    kind=MarkerKind.FILE,
                    required=True,
                    meaning="TrafficTwin SUMO provenance and immutable-file manifest.",
                )
            ],
            field_semantics=semantics,
            capabilities=sumo_results_capability_manifest(),
            provenance_requirements=[
                ExternalProvenanceRequirement(
                    key="scenario_id",
                    description="Declared scenario identity.",
                    required=True,
                    evidence_rule="Read only from sumo-source.yaml.",
                ),
                ExternalProvenanceRequirement(
                    key="scenario_url",
                    description="Retrievable source-scenario reference.",
                    required=True,
                    evidence_rule="Read only from sumo-source.yaml.",
                ),
                ExternalProvenanceRequirement(
                    key="source_version",
                    description="Exact declared SUMO version.",
                    required=True,
                    evidence_rule="Must match the adapter's supported version prefix.",
                ),
                ExternalProvenanceRequirement(
                    key="source_commit",
                    description="Optional source/scenario revision.",
                    required=False,
                    evidence_rule="Record only when explicitly declared.",
                ),
                ExternalProvenanceRequirement(
                    key="licence_spdx",
                    description="Declared reuse licence identifier.",
                    required=True,
                    evidence_rule="Must be non-empty in sumo-source.yaml.",
                ),
                ExternalProvenanceRequirement(
                    key="retrieval_date",
                    description="Declared source retrieval date.",
                    required=True,
                    evidence_rule="Must be present in sumo-source.yaml.",
                ),
                ExternalProvenanceRequirement(
                    key="redistribution_allowed",
                    description="Explicit redistribution permission state.",
                    required=True,
                    evidence_rule="Never inferred from public accessibility.",
                ),
                ExternalProvenanceRequirement(
                    key="raw_file_sha256",
                    description="Exact hashes of the declared raw XML files.",
                    required=True,
                    evidence_rule="Recomputed and matched before parsing.",
                ),
            ],
            conversion=ExternalConversionProfile(
                level=ConversionLevel.PARTIAL_CANONICAL,
                canonical_outputs=["TripRecord for departed valid tripinfo records"],
                source_specific_outputs=["SumoTripObservation", "SumoSummaryStep"],
                registry_outputs=[
                    "imported Run metadata",
                    "canonical trip MetricCollection",
                ],
                unavailable_outputs=[
                    "canonical traffic counts from summary snapshots",
                    "canonical FCD vehicle observations",
                    "task, RSU, energy, fairness, and spatial VEC evidence",
                    "source launch or rerun",
                ],
                rules=[
                    "Only fields with documented compatible semantics enter canonical tables.",
                    "Summary occupancy snapshots remain source-specific rather than interval flow.",
                    "Partial canonical conversion does not imply a complete generic run bundle.",
                ],
            ),
            blockers=[
                ExternalBlocker(
                    code="SUMO_DIRECT_LAUNCH_UNSUPPORTED",
                    status=SemanticStatus.CONFIRMED,
                    affected_capabilities=["direct_launch", "asynchronous_launch"],
                    reason="The adapter accepts completed results and contains no launcher.",
                    evidence=["sumo source contract", "adapter implementation"],
                    required_evidence=[
                        "separately approved versioned launcher and execution-output contract"
                    ],
                ),
                ExternalBlocker(
                    code="SUMO_FCD_MAPPING_REQUIRED",
                    status=SemanticStatus.CONFIRMED,
                    affected_capabilities=["canonical_vehicle_state", "spatial_metrics"],
                    reason="FCD has no approved TrafficTwin canonical mapping in this adapter.",
                    evidence=["sumo source contract"],
                    required_evidence=[
                        "field, identity, coordinate-frame, unit, and coverage mapping contract"
                    ],
                ),
                ExternalBlocker(
                    code="SUMO_SUMMARY_SOURCE_SPECIFIC",
                    status=SemanticStatus.CONFIRMED,
                    affected_capabilities=["canonical_traffic_counts", "windowed_traffic_metrics"],
                    reason="The running field is an occupancy snapshot, not interval traffic flow.",
                    evidence=[source.documentation["summary"]],
                    required_evidence=[
                        "a distinct compatible canonical occupancy model or approved mapping"
                    ],
                ),
                ExternalBlocker(
                    code="SUMO_VERSION_SCOPE_LIMITED",
                    status=SemanticStatus.CONFIRMED,
                    affected_capabilities=["additional_sumo_versions"],
                    reason="Acceptance evidence currently covers SUMO 1.27.x only.",
                    evidence=source.supported_sumo_versions,
                    required_evidence=[
                        "version-pinned public fixtures and compatibility tests for each version"
                    ],
                ),
            ],
            interpretation_limits=source.interpretation_limits
            + [
                "The conversion level is a description of outputs, not a quality score.",
                "SUMO and TOS contracts are not interchangeable merely because both implement "
                "this interface.",
            ],
        )

    def discover(self, source: Path) -> ExternalSourceDiscovery:
        """Discover the exact SUMO manifest marker."""

        return _discover_from_contract(source, self.contract())

    def validate(
        self,
        source: Path,
        *,
        deep: bool = False,
    ) -> tuple[ExternalValidationSummary, list[ExternalProvenanceObservation]]:
        """Run existing immutable SUMO validation and project its portable evidence."""

        del deep
        result = validate_sumo_results(source)
        outcome = _validation_outcome(result.report.status.value)
        counts = Counter(finding.severity.value for finding in result.report.findings)
        findings = sorted({_enum_text(finding.code) for finding in result.report.findings})
        summary = ExternalValidationSummary(
            outcome=outcome,
            accepted_for_declared_import=result.report.may_import,
            validator_version=SUMO_VALIDATOR_VERSION,
            source_fingerprint=result.fingerprint,
            finding_counts=dict(counts),
            finding_codes=findings,
            output_counts={
                "canonical_trips": len(result.canonical.trips),
                "source_summary_steps": len(result.summary_steps),
                "source_trip_observations": len(result.trip_observations),
            },
            source_report_type="SumoValidationResult",
        )
        manifest = result.manifest
        raw_hashes = [f"{item.path}:{item.sha256}" for item in result.raw_files]
        observations = [
            _observation(
                "scenario_id",
                manifest.source.scenario_id if manifest else None,
                "sumo-source.yaml",
            ),
            _observation(
                "scenario_url",
                manifest.source.scenario_url if manifest else None,
                "sumo-source.yaml",
            ),
            _observation(
                "source_version",
                manifest.source.sumo_version if manifest else None,
                "sumo-source.yaml",
            ),
            _observation(
                "source_commit",
                manifest.source.source_commit if manifest else None,
                "sumo-source.yaml",
                required=False,
            ),
            _observation(
                "licence_spdx",
                manifest.source.licence_spdx if manifest else None,
                "sumo-source.yaml",
            ),
            _observation(
                "retrieval_date",
                manifest.source.retrieval_date.isoformat() if manifest else None,
                "sumo-source.yaml",
            ),
            _observation(
                "redistribution_allowed",
                manifest.source.redistribution_allowed if manifest else None,
                "sumo-source.yaml",
            ),
            _observation(
                "raw_file_sha256",
                raw_hashes or None,
                "recomputed declared raw files",
            ),
        ]
        return summary, observations

    def inspect(
        self,
        source: Path,
        *,
        deep: bool = False,
    ) -> tuple[ExternalValidationSummary, list[ExternalProvenanceObservation]]:
        """Return the portable validation projection."""

        return self.validate(source, deep=deep)


class TosExternalSourceAdapter:
    """General-interface view of the read-only TOS Data package adapter."""

    adapter_id = "tos_data_read_only"
    adapter_version = TOS_ADAPTER_VERSION

    def contract(self) -> ExternalAdapterContract:
        """Return a source-neutral projection without promoting TOS-only semantics."""

        source = tos_source_contract()
        semantics = [
            ExternalFieldSemantic(
                source_field=field.field,
                artifact=field.artifact,
                meaning=field.meaning,
                unit=field.unit,
                status=SemanticStatus(field.status.value),
                canonical_target=None,
                evidence=field.evidence,
                limitations=field.limitations,
            )
            for field in source.fields
        ]
        return ExternalAdapterContract(
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            source_family="Randy TOS/vec_env completed evaluation package",
            interface_operations=_INTERFACE_OPERATIONS,
            discovery_markers=[
                SourceMarker(
                    relative_path="evals/eval_results_master.csv",
                    kind=MarkerKind.FILE,
                    required=True,
                    meaning="Documented source evaluation matrix.",
                ),
                SourceMarker(
                    relative_path="DATA_DICTIONARY.md",
                    kind=MarkerKind.FILE,
                    required=False,
                    meaning="Package-authored field documentation.",
                ),
                SourceMarker(
                    relative_path="instrumented",
                    kind=MarkerKind.DIRECTORY,
                    required=False,
                    meaning="Optional source-specific per-step and per-task arrays.",
                ),
                SourceMarker(
                    relative_path="traces",
                    kind=MarkerKind.DIRECTORY,
                    required=False,
                    meaning="Optional processed FCD NPZ traces.",
                ),
                SourceMarker(
                    relative_path="training",
                    kind=MarkerKind.DIRECTORY,
                    required=False,
                    meaning="Optional source training histories and summaries.",
                ),
            ],
            field_semantics=semantics,
            capabilities=tos_data_capability_manifest(),
            provenance_requirements=[
                ExternalProvenanceRequirement(
                    key="package_fingerprint",
                    description="Fingerprint of the inspected package evidence.",
                    required=True,
                    evidence_rule="Recomputed from the bounded package inventory.",
                ),
                ExternalProvenanceRequirement(
                    key="package_commit",
                    description="Package repository commit when present.",
                    required=False,
                    evidence_rule="Record only from the inspected package repository.",
                ),
                ExternalProvenanceRequirement(
                    key="semantics_source_commit",
                    description="vec_env commit used as field-semantics evidence.",
                    required=True,
                    evidence_rule="Pinned in the versioned TOS source contract.",
                ),
                ExternalProvenanceRequirement(
                    key="source_versions",
                    description="Observed evaluation engine versions.",
                    required=True,
                    evidence_rule="Read from every evaluation row and validate compatibility.",
                ),
                ExternalProvenanceRequirement(
                    key="licence_statement",
                    description="Licence covering package reuse and redistribution.",
                    required=True,
                    evidence_rule="Must be supplied by the owner; never inferred.",
                ),
                ExternalProvenanceRequirement(
                    key="redistribution_permission",
                    description="Explicit permission for public redistribution.",
                    required=True,
                    evidence_rule="Must be supplied by the owner; private access is not consent.",
                ),
                ExternalProvenanceRequirement(
                    key="data_dictionary",
                    description="Package-level source field documentation.",
                    required=False,
                    evidence_rule="Confirmed only when the declared document is present directly.",
                ),
            ],
            conversion=ExternalConversionProfile(
                level=ConversionLevel.AGGREGATE_SUMMARY,
                canonical_outputs=[],
                source_specific_outputs=[
                    "TosEvaluationRun source rows",
                    "TOS source-summary metrics",
                    "time-local vehicle-slot replay",
                    "source-specific RSU active-task/backlog views",
                    "bounded per-task showcase samples",
                ],
                registry_outputs=[
                    "imported Run and Experiment metadata",
                    "source-summary MetricCollection",
                    "partial EvidencePack",
                ],
                unavailable_outputs=source.unavailable_outputs
                + [
                    "canonical TaskRecord conversion",
                    "canonical InfrastructureRecord conversion",
                    "ordinary generic run-bundle conversion",
                ],
                rules=[
                    "Source summaries stay labelled as producer-provided aggregate evidence.",
                    "Time-local slots are never promoted to persistent vehicle identities.",
                    "RSU active-task and backlog fields are not relabelled as CPU utilisation.",
                    "No source field enters canonical tables without a compatible mapping "
                    "contract.",
                ],
            ),
            blockers=[
                ExternalBlocker(
                    code="TOS_DIRECT_LAUNCH_BLOCKED",
                    status=SemanticStatus.CONFIRMED,
                    affected_capabilities=["direct_launch", "asynchronous_launch"],
                    reason="Required checkpoints, writer evidence, and a tested portable runtime "
                    "are unavailable.",
                    evidence=source.execution.blockers,
                    required_evidence=[
                        "checkpoint permission and payloads",
                        "portable evaluator contract and runtime acceptance evidence",
                        "instrumentation writer and output reconciliation",
                    ],
                ),
                ExternalBlocker(
                    code="TOS_CANONICAL_TASK_CONVERSION_BLOCKED",
                    status=SemanticStatus.CONFIRMED,
                    affected_capabilities=[
                        "canonical_task_conversion",
                        "canonical_vehicle_conversion",
                        "fairness_metrics",
                    ],
                    reason=(
                        "Persistent task/vehicle identities, per-vehicle tiers, and target joins "
                        "are not exported."
                    ),
                    evidence=source.unavailable_outputs,
                    required_evidence=[
                        "producer/writer schema with stable row identity and complete join "
                        "semantics"
                    ],
                ),
                ExternalBlocker(
                    code="TOS_INFRASTRUCTURE_MAPPING_BLOCKED",
                    status=SemanticStatus.CONFIRMED,
                    affected_capabilities=["canonical_infrastructure", "spatial_rsu_metrics"],
                    reason="rsu_load and rsu_busy_ms do not satisfy canonical utilisation or queue "
                    "semantics.",
                    evidence=["vec_env field contract for rsu_load and rsu_busy_ms"],
                    required_evidence=[
                        "compatible denominator, queue, target, coverage, and unit semantics"
                    ],
                ),
                ExternalBlocker(
                    code="TOS_TRIP_OUTPUTS_UNAVAILABLE",
                    status=SemanticStatus.CONFIRMED,
                    affected_capabilities=["trip_metrics", "journey_time_analysis"],
                    reason="The package contains processed traces but no compatible trip output.",
                    evidence=["TOS package inventory", "TOS source contract"],
                    required_evidence=[
                        "immutable trip records with identity and timestamp semantics"
                    ],
                ),
                ExternalBlocker(
                    code="TOS_PUBLICATION_PERMISSION_UNKNOWN",
                    status=SemanticStatus.UNKNOWN,
                    affected_capabilities=["public_redistribution", "public_research_object"],
                    reason=(
                        "A package licence and owner redistribution permission are not established."
                    ),
                    evidence=[],
                    required_evidence=[
                        "written owner permission and an applicable data licence statement"
                    ],
                ),
            ],
            interpretation_limits=source.interpretation_limits
            + [
                "Aggregate-summary conversion and partial-canonical conversion are different "
                "boundaries, not quality ranks.",
                "Implementing the shared interface does not make TOS equivalent to SUMO or a "
                "generic TrafficTwin bundle.",
            ],
        )

    def discover(self, source: Path) -> ExternalSourceDiscovery:
        """Discover the exact TOS evaluation-matrix marker and optional inventory markers."""

        return _discover_from_contract(source, self.contract())

    def validate(
        self,
        source: Path,
        *,
        deep: bool = False,
    ) -> tuple[ExternalValidationSummary, list[ExternalProvenanceObservation]]:
        """Run existing TOS validation and project only portable evidence."""

        report = validate_tos_package(source, deep=deep)
        outcome = _validation_outcome(report.status.value)
        counts = Counter(finding.severity.value for finding in report.findings)
        inventory = report.inventory.model_dump(mode="json")
        summary = ExternalValidationSummary(
            outcome=outcome,
            accepted_for_declared_import=report.may_import_summaries,
            validator_version=f"tos-package-{report.adapter_version}",
            source_fingerprint=report.package_fingerprint,
            finding_counts=dict(counts),
            finding_codes=sorted({finding.code for finding in report.findings}),
            output_counts={key: int(value) for key, value in inventory.items()},
            source_report_type="TosValidationReport",
        )
        data_dictionary = source / "DATA_DICTIONARY.md"
        dictionary_present = (
            data_dictionary.is_file()
            and not data_dictionary.is_symlink()
            and not _has_symlink_parent(source, data_dictionary)
        )
        observations = [
            _observation(
                "package_fingerprint",
                report.package_fingerprint,
                "bounded TOS package inventory",
            ),
            _observation(
                "package_commit",
                report.package_commit,
                "inspected package repository",
                required=False,
            ),
            _observation(
                "semantics_source_commit",
                report.semantics_source_commit,
                "versioned TOS source contract",
            ),
            _observation(
                "source_versions",
                report.engine_versions or None,
                "evals/eval_results_master.csv",
            ),
            ExternalProvenanceObservation(
                key="licence_statement",
                status=SemanticStatus.UNKNOWN,
                limitation="No package licence is inferred from access or filenames.",
            ),
            ExternalProvenanceObservation(
                key="redistribution_permission",
                status=SemanticStatus.UNKNOWN,
                limitation="Written owner permission is required for public redistribution.",
            ),
            _observation(
                "data_dictionary",
                "DATA_DICTIONARY.md" if dictionary_present else None,
                "direct package marker",
                required=False,
            ),
        ]
        return summary, observations

    def inspect(
        self,
        source: Path,
        *,
        deep: bool = False,
    ) -> tuple[ExternalValidationSummary, list[ExternalProvenanceObservation]]:
        """Return the portable validation projection."""

        return self.validate(source, deep=deep)


def _discover_from_contract(
    source: Path,
    contract: ExternalAdapterContract,
) -> ExternalSourceDiscovery:
    root = Path(source)
    if root.is_symlink():
        return ExternalSourceDiscovery(
            adapter_id=contract.adapter_id,
            adapter_version=contract.adapter_version,
            status=DiscoveryStatus.BLOCKED,
            unsafe_markers=["<source-root>"],
            detail="source root is a symbolic link and was not inspected",
        )
    if not root.is_dir():
        return ExternalSourceDiscovery(
            adapter_id=contract.adapter_id,
            adapter_version=contract.adapter_version,
            status=DiscoveryStatus.NOT_MATCHED,
            missing_required_markers=sorted(
                marker.relative_path for marker in contract.discovery_markers if marker.required
            ),
            detail="source is not a directory",
        )
    matched: list[str] = []
    missing: list[str] = []
    unsafe: list[str] = []
    for marker in contract.discovery_markers:
        candidate = root.joinpath(*marker.relative_path.split("/"))
        if candidate.is_symlink() or _has_symlink_parent(root, candidate):
            unsafe.append(marker.relative_path)
            continue
        exists = candidate.is_file() if marker.kind is MarkerKind.FILE else candidate.is_dir()
        if exists:
            matched.append(marker.relative_path)
        elif marker.required:
            missing.append(marker.relative_path)
    if unsafe:
        status = DiscoveryStatus.BLOCKED
        detail = "one or more discovery markers are symbolic links"
    elif missing:
        status = DiscoveryStatus.NOT_MATCHED
        detail = "required adapter markers are absent"
    else:
        status = DiscoveryStatus.MATCHED
        detail = "all required adapter markers matched directly"
    return ExternalSourceDiscovery(
        adapter_id=contract.adapter_id,
        adapter_version=contract.adapter_version,
        status=status,
        matched_markers=sorted(matched),
        missing_required_markers=sorted(missing),
        unsafe_markers=sorted(unsafe),
        detail=detail,
    )


def _has_symlink_parent(root: Path, candidate: Path) -> bool:
    current = candidate.parent
    while current != root:
        if current.is_symlink():
            return True
        if current == current.parent:
            return True
        current = current.parent
    return False


def _validation_outcome(value: str) -> ValidationOutcome:
    try:
        return ValidationOutcome(value)
    except ValueError:
        return ValidationOutcome.UNAVAILABLE


def _enum_text(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


def _observation(
    key: str,
    value: str | int | bool | list[str] | None,
    evidence: str,
    *,
    required: bool = True,
) -> ExternalProvenanceObservation:
    if value is None:
        return ExternalProvenanceObservation(
            key=key,
            status=SemanticStatus.UNKNOWN,
            limitation=(
                "Required provenance was not established."
                if required
                else "Optional provenance was not present."
            ),
        )
    return ExternalProvenanceObservation(
        key=key,
        status=SemanticStatus.CONFIRMED,
        value=value,
        evidence=[evidence],
    )
