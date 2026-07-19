from __future__ import annotations

import csv
import io
from copy import deepcopy

import pytest
import yaml

from tests.unit.test_experiment_planning import _experiment, _seeds
from traffictwin.domain.experiment import Experiment
from traffictwin.experiments.protocol import (
    ProtocolMatchStatus,
    build_experiment_protocol,
    match_bundle_manifest,
    protocol_to_csv,
    protocol_to_yaml,
)
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.ingestion.manifest import BundleManifest


def test_protocol_is_exhaustive_deterministic_and_does_not_mutate_inputs() -> None:
    experiment = _experiment()
    seeds = _seeds()
    before_experiment = deepcopy(experiment)
    before_seeds = deepcopy(seeds)

    first = build_experiment_protocol(experiment, seeds)
    second = build_experiment_protocol(experiment, seeds)

    assert first == second
    assert experiment == before_experiment
    assert seeds == before_seeds
    assert first.direct_launch_supported is False
    assert len(first.slots) == 8
    assert [slot.slot_id for slot in first.slots] == [f"slot-{index:04d}" for index in range(1, 9)]
    assert [slot.role for slot in first.slots[:5]] == [
        "baseline",
        "baseline",
        "baseline",
        "baseline",
        "variation",
    ]
    assert first.slots[0].expected_run_id == "exp-planner-run-0001"
    assert first.slots[0].expected_bundle_id == "bundle-exp-planner-0001"
    assert len(first.input_fingerprint) == 64
    assert set(first.seed_fingerprints) == set(seeds)


def test_protocol_refuses_truncated_export() -> None:
    with pytest.raises(ValueError, match="exceeding the protocol limit of 7"):
        build_experiment_protocol(_experiment(), _seeds(), max_slots=7)


def test_protocol_checkpoint_is_required_only_when_evidenced_by_seed() -> None:
    seeds = _seeds()
    baseline = seeds["s1-gridlock-x2"]
    seeds[baseline.seed_id] = baseline.model_copy(
        update={"policy": baseline.policy.model_copy(update={"checkpoint": "checkpoint-42"})}
    )
    protocol = build_experiment_protocol(_experiment(), seeds)

    aligned = next(
        slot
        for slot in protocol.slots
        if slot.seed_id == baseline.seed_id and slot.algorithm == "synthetic-balanced"
    )
    assert aligned.checkpoint is None
    assert not aligned.checkpoint_match_required
    assert any("no checkpoint was inferred" in warning for warning in protocol.warnings)

    experiment = _experiment().model_copy(update={"algorithms": ["MAPPO"]})
    aligned_protocol = build_experiment_protocol(experiment, seeds)
    assert all(slot.checkpoint == "checkpoint-42" for slot in aligned_protocol.slots[:2])
    assert all(slot.checkpoint_match_required for slot in aligned_protocol.slots[:2])


def test_protocol_yaml_and_csv_are_stable_and_machine_path_free() -> None:
    protocol = build_experiment_protocol(_experiment(), _seeds())

    yaml_payload = protocol_to_yaml(protocol)
    csv_payload = protocol_to_csv(protocol)

    assert yaml_payload == protocol_to_yaml(protocol)
    assert csv_payload == protocol_to_csv(protocol)
    assert yaml.safe_load(yaml_payload)["protocol_id"] == protocol.protocol_id
    rows = list(csv.DictReader(io.StringIO(csv_payload)))
    assert len(rows) == 8
    assert rows[0]["slot_id"] == "slot-0001"
    assert rows[-1]["slot_id"] == "slot-0008"
    assert "/Users/" not in yaml_payload + csv_payload
    assert "C:\\" not in yaml_payload + csv_payload


def test_manifest_matching_supports_exact_and_compatible_identifiers() -> None:
    validation = validate_bundle("tests/fixtures/bundles/baseline_valid")
    assert validation.manifest is not None
    assert validation.seed is not None
    manifest = validation.manifest
    experiment = _manifest_experiment(manifest)
    protocol = build_experiment_protocol(experiment, {validation.seed.seed_id: validation.seed})
    slot = protocol.slots[0]

    compatible = match_bundle_manifest(protocol, manifest)
    assert compatible.status is ProtocolMatchStatus.COMPATIBLE
    assert compatible.matched_slot_id == slot.slot_id
    assert {item.field for item in compatible.mismatches} == {
        "run.run_id",
        "bundle.bundle_id",
    }

    exact_manifest = manifest.model_copy(
        update={
            "run": manifest.run.model_copy(update={"run_id": slot.expected_run_id}),
            "bundle": manifest.bundle.model_copy(update={"bundle_id": slot.expected_bundle_id}),
        }
    )
    exact = match_bundle_manifest(protocol, exact_manifest)
    assert exact.status is ProtocolMatchStatus.EXACT
    assert not exact.mismatches


def test_manifest_matching_reports_metadata_mismatch_and_unmatched_bundle() -> None:
    validation = validate_bundle("tests/fixtures/bundles/baseline_valid")
    assert validation.manifest is not None
    assert validation.seed is not None
    manifest = validation.manifest
    protocol = build_experiment_protocol(
        _manifest_experiment(manifest),
        {validation.seed.seed_id: validation.seed},
    )
    slot = protocol.slots[0]

    conflicting = manifest.model_copy(
        update={
            "run": manifest.run.model_copy(
                update={"run_id": slot.expected_run_id, "random_seed": 99}
            )
        }
    )
    mismatch = match_bundle_manifest(protocol, conflicting)
    assert mismatch.status is ProtocolMatchStatus.MISMATCH
    assert mismatch.matched_slot_id == slot.slot_id
    assert [item.field for item in mismatch.mismatches] == ["run.random_seed"]

    unrelated = manifest.model_copy(
        update={
            "run": manifest.run.model_copy(
                update={
                    "run_id": "run-unrelated",
                    "experiment_id": "exp-unrelated",
                    "random_seed": 99,
                }
            ),
            "bundle": manifest.bundle.model_copy(update={"bundle_id": "bundle-unrelated"}),
        }
    )
    unmatched = match_bundle_manifest(protocol, unrelated)
    assert unmatched.status is ProtocolMatchStatus.UNMATCHED
    assert unmatched.matched_slot_id is None


def _manifest_experiment(manifest: BundleManifest) -> Experiment:
    typed_manifest = manifest
    return Experiment(
        experiment_id=typed_manifest.run.experiment_id,
        research_question="Can the completed bundle be aligned to the planned slot?",
        baseline_seed_id=typed_manifest.run.seed_id,
        algorithms=[typed_manifest.run.algorithm],
        common_random_seed_set=[typed_manifest.run.random_seed],
        planned_replicates=1,
    )
