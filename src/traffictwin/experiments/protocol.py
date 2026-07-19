"""Deterministic execution-protocol exports for planned experiments."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Callable, Mapping
from datetime import datetime
from enum import StrEnum
from typing import Literal

import yaml
from pydantic import Field

from traffictwin.domain.experiment import Experiment
from traffictwin.domain.scenario import ScenarioSeed, StrictModel
from traffictwin.experiments.planning import summarise_experiment_plan
from traffictwin.ingestion.manifest import BundleManifest

PROTOCOL_SCHEMA_VERSION: Literal["1.0"] = "1.0"
PROTOCOL_SOURCE: Literal["TrafficTwin Experiment Protocol Exporter"] = (
    "TrafficTwin Experiment Protocol Exporter"
)
PROTOCOL_MATCHING_FIELDS = (
    "run.experiment_id",
    "run.seed_id",
    "run.algorithm",
    "run.random_seed",
    "run.checkpoint_when_required",
    "run.run_id",
    "bundle.bundle_id",
)
PROTOCOL_CSV_COLUMNS = (
    "protocol_id",
    "input_fingerprint",
    "slot_id",
    "sequence",
    "role",
    "status",
    "experiment_id",
    "seed_id",
    "seed_schema_version",
    "seed_fingerprint",
    "algorithm",
    "checkpoint",
    "checkpoint_match_required",
    "random_seed",
    "expected_run_id",
    "expected_bundle_id",
)


class ProtocolMatchStatus(StrEnum):
    """Outcome of matching one completed bundle to a planned slot."""

    EXACT = "exact"
    COMPATIBLE = "compatible"
    MISMATCH = "mismatch"
    UNMATCHED = "unmatched"


class ExperimentProtocolSlot(StrictModel):
    """One exhaustive, deterministic slot in an experiment run sheet."""

    slot_id: str
    sequence: int = Field(ge=1)
    role: Literal["baseline", "variation"]
    status: Literal["planned"] = "planned"
    experiment_id: str
    seed_id: str
    seed_schema_version: str
    seed_fingerprint: str
    algorithm: str
    checkpoint: str | None = None
    checkpoint_match_required: bool = False
    random_seed: int = Field(ge=0)
    expected_run_id: str
    expected_bundle_id: str


class ExperimentProtocol(StrictModel):
    """Versioned, read-only execution checklist for a registered experiment."""

    schema_version: Literal["1.0"] = PROTOCOL_SCHEMA_VERSION
    protocol_id: str
    generated_at: datetime
    source: Literal["TrafficTwin Experiment Protocol Exporter"] = PROTOCOL_SOURCE
    direct_launch_supported: Literal[False] = False
    input_fingerprint: str
    experiment: Experiment
    seed_snapshots: dict[str, ScenarioSeed]
    seed_fingerprints: dict[str, str]
    slots: list[ExperimentProtocolSlot]
    matching_fields: list[str] = Field(default_factory=lambda: list(PROTOCOL_MATCHING_FIELDS))
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return a deterministic, machine-readable protocol document."""

        return json.dumps(
            self.model_dump(mode="json", by_alias=True),
            indent=2,
            ensure_ascii=True,
        )


class ProtocolFieldMismatch(StrictModel):
    """One observed manifest field that differs from a planned slot."""

    field: str
    expected: str | int | None
    observed: str | int | None


class ProtocolBundleMatch(StrictModel):
    """Read-only result of matching a manifest to an experiment protocol."""

    protocol_id: str
    status: ProtocolMatchStatus
    bundle_id: str
    run_id: str
    matched_slot_id: str | None = None
    findings: list[str] = Field(default_factory=list)
    mismatches: list[ProtocolFieldMismatch] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return deterministic JSON."""

        return json.dumps(self.model_dump(mode="json"), indent=2, ensure_ascii=True)


def build_experiment_protocol(
    experiment: Experiment,
    registered_seeds: Mapping[str, ScenarioSeed],
    *,
    max_slots: int = 10_000,
    clock: Callable[[], datetime] | None = None,
) -> ExperimentProtocol:
    """Build an exhaustive protocol without creating runs or launching work."""

    if max_slots < 1:
        raise ValueError("max_slots must be at least 1")
    summary = summarise_experiment_plan(experiment, registered_seeds, preview_limit=max_slots)
    if summary.planned_run_count > max_slots:
        raise ValueError(
            f"experiment requires {summary.planned_run_count} run slots, exceeding the "
            f"protocol limit of {max_slots}; no truncated protocol was created"
        )

    condition_ids = (experiment.baseline_seed_id, *experiment.variation_seed_ids)
    snapshots = {seed_id: registered_seeds[seed_id] for seed_id in condition_ids}
    seed_fingerprints = {
        seed_id: _fingerprint(seed.model_dump(mode="json", by_alias=True))
        for seed_id, seed in snapshots.items()
    }
    input_fingerprint = _fingerprint(
        {
            "experiment": experiment.model_dump(mode="json"),
            "seed_snapshots": {
                seed_id: snapshots[seed_id].model_dump(mode="json", by_alias=True)
                for seed_id in sorted(snapshots)
            },
        }
    )

    warnings = list(summary.warnings)
    slots: list[ExperimentProtocolSlot] = []
    unresolved_checkpoint_pairs: set[tuple[str, str]] = set()
    for sequence, cell in enumerate(summary.preview_cells, start=1):
        seed = snapshots[cell.seed_id]
        checkpoint = seed.policy.checkpoint if seed.policy.algorithm == cell.algorithm else None
        if seed.policy.algorithm != cell.algorithm:
            unresolved_checkpoint_pairs.add((cell.seed_id, cell.algorithm))
        slots.append(
            ExperimentProtocolSlot(
                slot_id=f"slot-{sequence:04d}",
                sequence=sequence,
                role=cell.role,
                experiment_id=experiment.experiment_id,
                seed_id=cell.seed_id,
                seed_schema_version=seed.schema_version,
                seed_fingerprint=seed_fingerprints[cell.seed_id],
                algorithm=cell.algorithm,
                checkpoint=checkpoint,
                checkpoint_match_required=checkpoint is not None,
                random_seed=cell.random_seed,
                expected_run_id=f"{experiment.experiment_id}-run-{sequence:04d}",
                expected_bundle_id=f"bundle-{experiment.experiment_id}-{sequence:04d}",
            )
        )

    for seed_id, algorithm in sorted(unresolved_checkpoint_pairs):
        warnings.append(
            f"Checkpoint matching is not required for seed {seed_id!r} with planned policy "
            f"{algorithm!r}: the seed snapshot describes policy "
            f"{snapshots[seed_id].policy.algorithm!r}, so no checkpoint was inferred."
        )

    generated_at = clock() if clock is not None else experiment.updated_at
    return ExperimentProtocol(
        protocol_id=f"protocol-{experiment.experiment_id}-{input_fingerprint[:12]}",
        generated_at=generated_at,
        input_fingerprint=input_fingerprint,
        experiment=experiment,
        seed_snapshots=snapshots,
        seed_fingerprints=seed_fingerprints,
        slots=slots,
        warnings=warnings,
        limitations=[
            "This protocol is a coordination checklist; it does not launch or schedule work.",
            "Expected run and bundle identifiers are suggestions, not proof of bundle identity.",
            "Environment version, command, working directory, and output path remain unresolved.",
            "A compatible match confirms manifest metadata alignment, not scientific validity.",
        ],
    )


def protocol_to_yaml(protocol: ExperimentProtocol) -> str:
    """Serialise a protocol to stable YAML."""

    return yaml.safe_dump(
        protocol.model_dump(mode="json", by_alias=True),
        sort_keys=False,
        allow_unicode=False,
    )


def protocol_to_csv(protocol: ExperimentProtocol) -> str:
    """Serialise protocol slots to a stable CSV run sheet."""

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=PROTOCOL_CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for slot in protocol.slots:
        row = slot.model_dump(mode="json")
        writer.writerow(
            {
                "protocol_id": protocol.protocol_id,
                "input_fingerprint": protocol.input_fingerprint,
                **row,
            }
        )
    return output.getvalue()


def match_bundle_manifest(
    protocol: ExperimentProtocol,
    manifest: BundleManifest,
) -> ProtocolBundleMatch:
    """Match one validated manifest to a protocol slot without mutating either."""

    identity_slots = [
        slot
        for slot in protocol.slots
        if slot.expected_run_id == manifest.run.run_id
        or slot.expected_bundle_id == manifest.bundle.bundle_id
    ]
    identity_ids = {slot.slot_id for slot in identity_slots}
    if len(identity_ids) > 1:
        return ProtocolBundleMatch(
            protocol_id=protocol.protocol_id,
            status=ProtocolMatchStatus.MISMATCH,
            bundle_id=manifest.bundle.bundle_id,
            run_id=manifest.run.run_id,
            findings=["The run and bundle identifiers point to different protocol slots."],
        )

    if identity_slots:
        slot = identity_slots[0]
        mismatches = _slot_mismatches(slot, manifest, include_identifiers=False)
        if mismatches:
            return ProtocolBundleMatch(
                protocol_id=protocol.protocol_id,
                status=ProtocolMatchStatus.MISMATCH,
                bundle_id=manifest.bundle.bundle_id,
                run_id=manifest.run.run_id,
                matched_slot_id=slot.slot_id,
                findings=[
                    "A suggested identifier matches this slot, but required manifest metadata "
                    "does not."
                ],
                mismatches=mismatches,
            )
        exact = (
            manifest.run.run_id == slot.expected_run_id
            and manifest.bundle.bundle_id == slot.expected_bundle_id
        )
        return ProtocolBundleMatch(
            protocol_id=protocol.protocol_id,
            status=ProtocolMatchStatus.EXACT if exact else ProtocolMatchStatus.COMPATIBLE,
            bundle_id=manifest.bundle.bundle_id,
            run_id=manifest.run.run_id,
            matched_slot_id=slot.slot_id,
            findings=[
                "Manifest metadata and both suggested identifiers match the protocol slot."
                if exact
                else "Manifest metadata matches the protocol slot; one suggested identifier "
                "was not adopted by the producer."
            ],
        )

    compatible_slots = [
        slot
        for slot in protocol.slots
        if not _slot_mismatches(slot, manifest, include_identifiers=False)
    ]
    if len(compatible_slots) == 1:
        slot = compatible_slots[0]
        return ProtocolBundleMatch(
            protocol_id=protocol.protocol_id,
            status=ProtocolMatchStatus.COMPATIBLE,
            bundle_id=manifest.bundle.bundle_id,
            run_id=manifest.run.run_id,
            matched_slot_id=slot.slot_id,
            findings=[
                "Core manifest metadata matches one protocol slot; producer-assigned run and "
                "bundle identifiers differ from the suggested identifiers."
            ],
            mismatches=_slot_mismatches(slot, manifest, include_identifiers=True),
        )

    return ProtocolBundleMatch(
        protocol_id=protocol.protocol_id,
        status=ProtocolMatchStatus.UNMATCHED,
        bundle_id=manifest.bundle.bundle_id,
        run_id=manifest.run.run_id,
        findings=[
            "No protocol slot has the same experiment, seed, policy, random seed, and required "
            "checkpoint metadata."
        ],
    )


def _slot_mismatches(
    slot: ExperimentProtocolSlot,
    manifest: BundleManifest,
    *,
    include_identifiers: bool,
) -> list[ProtocolFieldMismatch]:
    expected_observed: list[tuple[str, str | int | None, str | int | None]] = [
        ("run.experiment_id", slot.experiment_id, manifest.run.experiment_id),
        ("run.seed_id", slot.seed_id, manifest.run.seed_id),
        ("run.algorithm", slot.algorithm, manifest.run.algorithm),
        ("run.random_seed", slot.random_seed, manifest.run.random_seed),
    ]
    if slot.checkpoint_match_required:
        expected_observed.append(("run.checkpoint", slot.checkpoint, manifest.run.checkpoint))
    if include_identifiers:
        expected_observed.extend(
            [
                ("run.run_id", slot.expected_run_id, manifest.run.run_id),
                ("bundle.bundle_id", slot.expected_bundle_id, manifest.bundle.bundle_id),
            ]
        )
    return [
        ProtocolFieldMismatch(field=field, expected=expected, observed=observed)
        for field, expected, observed in expected_observed
        if expected != observed
    ]


def _fingerprint(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
