"""Tests for canonical portable E2 artifact — Lane 03."""

from __future__ import annotations

import json
from collections.abc import Callable
from importlib import resources
from typing import Any

import pytest
from pydantic import ValidationError

from traffictwin.experiments.e2_research_artifact import (
    E2ResearchEvidencePackage,
    builtin_e2_research_json,
    load_builtin_e2_research,
    validate_e2_research_artifact,
)


def _load_dict() -> dict[str, Any]:
    return json.loads(builtin_e2_research_json())  # type: ignore[no-any-return]


def _mutate_and_validate(mutator: Callable[[dict[str, Any]], None]) -> None:
    data = _load_dict()
    mutator(data)
    text = json.dumps(data, sort_keys=True, separators=(",", ":"))
    with pytest.raises((ValueError, ValidationError)):
        validate_e2_research_artifact(text)


def test_builtin_json_deterministic_exact_text() -> None:
    a = builtin_e2_research_json()
    b = builtin_e2_research_json()
    assert a == b
    parsed = json.loads(a)
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
    assert a.strip() == canonical.strip()
    pkg_a = validate_e2_research_artifact(a)
    pkg_b = validate_e2_research_artifact(b)
    assert pkg_a.fingerprint() == pkg_b.fingerprint()


def test_wheel_style_resource_access() -> None:
    text_via_api = builtin_e2_research_json()
    ref = resources.files("traffictwin.resources.research").joinpath("e2_resource_strategy_v1.json")
    text_via_resources = ref.read_text(encoding="utf-8")
    assert text_via_api == text_via_resources
    pkg = validate_e2_research_artifact(text_via_resources)
    assert isinstance(pkg, E2ResearchEvidencePackage)


def test_load_builtin_returns_valid_package() -> None:
    pkg = load_builtin_e2_research()
    assert isinstance(pkg, E2ResearchEvidencePackage)
    assert pkg.source_identities.base_sha == "bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6"
    assert (
        pkg.source_identities.actor.sha256
        == "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208"
    )
    assert (
        pkg.source_identities.trace.sha256
        == "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"
    )
    assert pkg.replication_unit == "fleet_draw"
    assert pkg.evaluator_seed == 0
    assert pkg.fingerprint() == load_builtin_e2_research().fingerprint()
    # six lifecycle nulls
    for field in (
        "gate_rejected",
        "capacity_rejected",
        "started",
        "compute_completed",
        "returned",
        "dropped",
    ):
        assert getattr(pkg.task_lifecycle, field) is None
    # secondary SD/SE null
    secondary = [s for s in pkg.declared_summaries if s.comparison_id == "e2d_per_task_minus_dla"]
    assert len(secondary) == 1
    assert secondary[0].sample_sd is None
    assert secondary[0].standard_error is None


def test_builtin_json_contains_no_absolute_or_secret() -> None:
    text = builtin_e2_research_json()
    assert "/Users/" not in text
    assert "/home/" not in text
    validate_e2_research_artifact(text)


def test_validate_rejects_invalid_json() -> None:
    with pytest.raises((ValueError, ValidationError)):
        validate_e2_research_artifact("not json")
    with pytest.raises((ValueError, ValidationError)):
        validate_e2_research_artifact("")


def test_mutation_rejects_e2b_head() -> None:
    def mut(d: dict[str, Any]) -> None:
        d["source_identities"]["research_heads"]["e2b"] = "a" * 40

    _mutate_and_validate(mut)


def test_mutation_rejects_e2c_head() -> None:
    def mut(d: dict[str, Any]) -> None:
        d["source_identities"]["research_heads"]["e2c"] = "b" * 40

    _mutate_and_validate(mut)


def test_mutation_rejects_e2d_head() -> None:
    def mut(d: dict[str, Any]) -> None:
        d["source_identities"]["research_heads"]["e2d"] = "c" * 40

    _mutate_and_validate(mut)


def test_mutation_rejects_e2b_manifest() -> None:
    def mut(d: dict[str, Any]) -> None:
        d["source_identities"]["manifest_sha256_by_study"]["e2b"] = "0" * 64

    _mutate_and_validate(mut)


def test_mutation_rejects_actor_hash() -> None:
    def mut(d: dict[str, Any]) -> None:
        d["source_identities"]["actor"]["sha256"] = "0" * 64

    _mutate_and_validate(mut)


def test_mutation_rejects_trace_hash() -> None:
    def mut(d: dict[str, Any]) -> None:
        d["source_identities"]["trace"]["sha256"] = "f" * 64

    _mutate_and_validate(mut)


def test_mutation_rejects_evaluator_seed() -> None:
    def mut(d: dict[str, Any]) -> None:
        d["evaluator_seed"] = 999

    _mutate_and_validate(mut)


def test_mutation_rejects_replication_unit() -> None:
    def mut(d: dict[str, Any]) -> None:
        d["replication_unit"] = "task"

    _mutate_and_validate(mut)


@pytest.mark.parametrize("key", ["off", "jsq", "ingress_dla", "dla"])
def test_mutation_rejects_e2b_values(key: str) -> None:
    def mut(d: dict[str, Any]) -> None:
        for obs in d["observations"]:
            if obs["arm"] == key and obs["figure_id"].startswith("fig1"):
                obs["value"] = obs["value"] + 0.001

    _mutate_and_validate(mut)


@pytest.mark.parametrize("idx", [0, 1, 2, 3])
def test_mutation_rejects_e2c_per_seed(idx: int) -> None:
    def mut(d: dict[str, Any]) -> None:
        for pd in d["paired_differences"]:
            if pd["comparison_id"] == "e2c_dla_minus_ingress":
                pd["per_seed_values"][idx] += 0.0001
        for obs in d["observations"]:
            if obs["figure_id"] == f"fig2_e2c_dla_minus_ingress_seed{idx + 1}":
                obs["value"] += 0.0001

    _mutate_and_validate(mut)


def test_mutation_rejects_e2c_mean() -> None:
    def mut(d: dict[str, Any]) -> None:
        for ds in d["declared_summaries"]:
            if ds["comparison_id"] == "e2c_dla_minus_ingress":
                ds["mean"] += 0.0001

    _mutate_and_validate(mut)


def test_mutation_rejects_e2c_ci_lower() -> None:
    def mut(d: dict[str, Any]) -> None:
        for ds in d["declared_summaries"]:
            if ds["comparison_id"] == "e2c_dla_minus_ingress":
                ds["lower"] += 0.0001

    _mutate_and_validate(mut)


@pytest.mark.parametrize("idx", [0, 1, 2, 3])
def test_mutation_rejects_e2d_per_seed_vs_ingress(idx: int) -> None:
    def mut(d: dict[str, Any]) -> None:
        for pd in d["paired_differences"]:
            if pd["comparison_id"] == "e2d_per_task_minus_ingress":
                pd["per_seed_values"][idx] += 0.0001

    _mutate_and_validate(mut)


def test_mutation_rejects_e2d_mean_vs_ingress() -> None:
    def mut(d: dict[str, Any]) -> None:
        for ds in d["declared_summaries"]:
            if ds["comparison_id"] == "e2d_per_task_minus_ingress":
                ds["mean"] += 0.0001

    _mutate_and_validate(mut)


def test_mutation_rejects_e2d_ci_vs_ingress() -> None:
    def mut(d: dict[str, Any]) -> None:
        for ds in d["declared_summaries"]:
            if ds["comparison_id"] == "e2d_per_task_minus_ingress":
                ds["lower"] += 0.0001

    _mutate_and_validate(mut)


def test_mutation_rejects_e2d_mean_vs_dla() -> None:
    def mut(d: dict[str, Any]) -> None:
        for ds in d["declared_summaries"]:
            if ds["comparison_id"] == "e2d_per_task_minus_dla":
                ds["mean"] += 0.0001

    _mutate_and_validate(mut)


def test_mutation_rejects_accounting_offered() -> None:
    def mut(d: dict[str, Any]) -> None:
        d["task_lifecycle"]["offered"] += 1

    _mutate_and_validate(mut)


def test_rejects_absolute_path_injection() -> None:
    data = _load_dict()
    data["limitations"][0] = "/Users/akashx/secret " + data["limitations"][0]
    text = json.dumps(data, sort_keys=True, separators=(",", ":"))
    with pytest.raises((ValueError, ValidationError), match="forbidden|/Users/|private"):
        validate_e2_research_artifact(text)


def test_rejects_secret_like_content() -> None:
    data = _load_dict()
    data["limitations"].append("api_key: secret123")
    text = json.dumps(data, sort_keys=True, separators=(",", ":"))
    with pytest.raises((ValueError, ValidationError)):
        validate_e2_research_artifact(text)


def test_rejects_unavailable_converted_to_zero() -> None:
    for field in (
        "gate_rejected",
        "capacity_rejected",
        "started",
        "compute_completed",
        "returned",
        "dropped",
    ):
        data = _load_dict()
        data["task_lifecycle"][field] = 0
        if field in data["task_lifecycle"]["unavailable_reasons"]:
            del data["task_lifecycle"]["unavailable_reasons"][field]
        # also need to update missingness to keep schema consistent
        for m in data["missingness"]:
            if m["field"] == field:
                m["reason"] = "removed"
        text = json.dumps(data, sort_keys=True, separators=(",", ":"))
        with pytest.raises((ValueError, ValidationError)):
            validate_e2_research_artifact(text)


def test_rejects_secondary_sd_se_fabricated() -> None:
    data = _load_dict()
    for ds in data["declared_summaries"]:
        if ds["comparison_id"] == "e2d_per_task_minus_dla":
            ds["sample_sd"] = 0.0002
            ds["standard_error"] = 0.0001
    text = json.dumps(data, sort_keys=True, separators=(",", ":"))
    with pytest.raises((ValueError, ValidationError)):
        validate_e2_research_artifact(text)


def test_rejects_malformed_schema() -> None:
    data = _load_dict()
    del data["schema_version"]
    text = json.dumps(data, sort_keys=True, separators=(",", ":"))
    with pytest.raises((ValueError, ValidationError)):
        validate_e2_research_artifact(text)


# Owner-required limitation/non-claim inventory — deleting or materially mutating
# any required phrase must fail (explicit searchable wording, no inference).

_REQUIRED_LIMITATION_PHRASES: tuple[str, ...] = (
    "manchester incident hour",
    "four matched provisional fleet draws",
    "evaluator seed 0",
    "fixed 1x",
    "zero backhaul",
    "inherited deadline gate",
    "frozen vehicle actor",
    "does not observe current rsu load",
    "does not choose execution rsu",
    "e2b one-draw descriptive",
    "reuses already-observed e2c controls",
    "not independent held-out replication",
    "accounting records, not independent replicates",
    "no ordinary/free-flow control",
    "physical return is not independently instrumented",
)

_REQUIRED_NONCLAIM_PHRASES: tuple[str, ...] = (
    "kubernetes deployment",
    "cluster orchestration",
    "autonomous infrastructure control",
    "learned infrastructure placement",
    "learned rsu scheduler",
    "mappo choosing execution rsu",
    "mappo observing current rsu load",
    "manchester-wide",
    "population-wide",
    "physical rsu deployment",
    "physical result-return verification",
    "universal jsq superiority",
    "universal per_task_dla superiority",
    "free-flow validation",
    "independent held-out e2d replication",
    "task-level statistical replication",
    "zero-backhaul realism",
)


@pytest.mark.parametrize("phrase", _REQUIRED_LIMITATION_PHRASES)
def test_mutation_rejects_missing_limitation_phrase(phrase: str) -> None:
    def mut(d: dict[str, Any]) -> None:
        # Remove every limitation entry that contains the required phrase
        d["limitations"] = [s for s in d["limitations"] if phrase not in s.lower()]
        # Keep at least one entry so schema min_length passes but phrase still missing
        if not d["limitations"]:
            d["limitations"] = ["placeholder without required phrase"]

    _mutate_and_validate(mut)


@pytest.mark.parametrize("phrase", _REQUIRED_LIMITATION_PHRASES)
def test_mutation_rejects_mutated_limitation_phrase(phrase: str) -> None:
    def mut(d: dict[str, Any]) -> None:
        for i, s in enumerate(d["limitations"]):
            if phrase in s.lower():
                # Materially mutate by replacing phrase occurrence with X's
                d["limitations"][i] = s.lower().replace(phrase, "mutated-phrase-xxx")

    _mutate_and_validate(mut)


@pytest.mark.parametrize("phrase", _REQUIRED_NONCLAIM_PHRASES)
def test_mutation_rejects_missing_nonclaim_phrase(phrase: str) -> None:
    def mut(d: dict[str, Any]) -> None:
        d["non_claims"] = [s for s in d["non_claims"] if phrase not in s.lower()]
        if not d["non_claims"]:
            d["non_claims"] = ["placeholder without required phrase"]

    _mutate_and_validate(mut)


@pytest.mark.parametrize("phrase", _REQUIRED_NONCLAIM_PHRASES)
def test_mutation_rejects_mutated_nonclaim_phrase(phrase: str) -> None:
    def mut(d: dict[str, Any]) -> None:
        for i, s in enumerate(d["non_claims"]):
            if phrase in s.lower():
                d["non_claims"][i] = s.lower().replace(phrase, "mutated-phrase-xxx")

    _mutate_and_validate(mut)


def test_limitations_and_nonclaims_contain_all_required_phrases() -> None:
    data = _load_dict()
    lim_joined = " ".join(data["limitations"]).lower()
    nc_joined = " ".join(data["non_claims"]).lower()
    for phrase in _REQUIRED_LIMITATION_PHRASES:
        assert phrase in lim_joined, f"missing limitation phrase {phrase!r}"
    for phrase in _REQUIRED_NONCLAIM_PHRASES:
        assert phrase in nc_joined, f"missing non_claim phrase {phrase!r}"
