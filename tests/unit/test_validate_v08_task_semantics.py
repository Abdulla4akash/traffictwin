"""Tests for v08 task semantics validator — discriminating mutations."""

from __future__ import annotations

import json
from typing import Any

import pytest
from scripts.validate_v08_task_semantics import (
    CONTRACT_PATH,
    HANDCHECK_PATH,
    load_json,
    validate_accounting,
    validate_contract_structure,
    validate_handcheck,
)


def _load_contract_and_handcheck() -> tuple[dict[str, Any], dict[str, Any]]:
    contract = load_json(CONTRACT_PATH)
    handcheck = load_json(HANDCHECK_PATH)
    return contract, handcheck


def test_contract_structure_passes() -> None:
    contract = load_json(CONTRACT_PATH)
    errs = validate_contract_structure(contract)
    assert errs == [], f"contract structure errors: {errs}"


def test_handcheck_passes() -> None:
    contract, handcheck = _load_contract_and_handcheck()
    errs = validate_handcheck(handcheck, contract)
    assert errs == [], f"handcheck errors: {errs}"


def test_hand_example_passes_accounting() -> None:
    contract, handcheck = _load_contract_and_handcheck()
    acc = handcheck["hand_example"]["accounting"]
    errs = validate_accounting(acc, contract=contract)
    assert errs == [], f"hand accounting errors: {errs}"


def test_e2d_reconciliation_conservation() -> None:
    _, handcheck = _load_contract_and_handcheck()
    raw = handcheck["e2d_reconciliation"]["raw_cell"]
    assert raw["offered"] == raw["admitted"] + raw["rejected_total"]


def test_denominators_headline_is_offered() -> None:
    _, handcheck = _load_contract_and_handcheck()
    he = handcheck["hand_example"]
    acc = he["accounting"]
    dens = he["denominators"]
    assert dens["offered_completion_headline"] == pytest.approx(
        acc["deadline_success"] / acc["offered"]
    )
    assert dens["admitted_completion_diagnostic"] == pytest.approx(
        acc["deadline_success"] / acc["admitted"]
    )
    # headline must be offered, not admitted
    assert dens["offered_completion_headline"] < dens["admitted_completion_diagnostic"]


def test_lifecycle_partial_order_hand_example() -> None:
    _, handcheck = _load_contract_and_handcheck()
    acc = handcheck["hand_example"]["accounting"]
    assert (
        acc["offered"]
        >= acc["admitted"]
        >= acc["started"]
        >= acc["compute_completed"]
        >= acc["returned"]
        >= acc["deadline_success"]
    )
    assert acc["compute_completed"] == acc["returned"] + acc["dropped"]
    assert acc["forwarded"] <= acc["admitted"]


def test_waiting_room_ceiling_not_compute_power() -> None:
    contract = load_json(CONTRACT_PATH)
    wrc = contract["lifecycle"]["waiting_room_ceiling"]["definition"]
    assert "waiting" in wrc.lower() or "waiting-room" in wrc.lower()
    assert "not compute" in wrc.lower()


def test_forwarded_is_path_event_not_separate_class() -> None:
    contract = load_json(CONTRACT_PATH)
    assert contract["lifecycle"]["path_event"] == "forwarded"
    _, handcheck = _load_contract_and_handcheck()
    acc = handcheck["hand_example"]["accounting"]
    # forwarded tasks are within admitted, not added to offered
    assert acc["offered"] == acc["admitted"] + acc["gate_rejected"] + acc["capacity_rejected"]


def test_mutation_conservation_imbalance_fails() -> None:
    contract, handcheck = _load_contract_and_handcheck()
    acc = dict(handcheck["hand_example"]["accounting"])
    acc["offered"] = acc["offered"] + 1  # break conservation
    errs = validate_accounting(acc, contract=contract)
    assert any("conservation" in e.lower() for e in errs), (
        f"expected conservation error, got {errs}"
    )


def test_mutation_zero_latency_rejected_completion_fails() -> None:
    contract, handcheck = _load_contract_and_handcheck()
    acc = dict(handcheck["hand_example"]["accounting"])
    acc["zero_latency_completed"] = acc["gate_rejected"] + acc["capacity_rejected"]
    acc["rejected_latency_ms"] = 0
    errs = validate_accounting(acc, contract=contract)
    assert any("zero-latency" in e.lower() or "zero_latency" in e.lower() for e in errs), (
        f"expected zero-latency error, got {errs}"
    )


def test_mutation_returned_equals_compute_conflation_fails() -> None:
    contract, handcheck = _load_contract_and_handcheck()
    acc = dict(handcheck["hand_example"]["accounting"])
    # conflate returned with compute_completed
    acc["returned"] = acc["compute_completed"]
    acc["dropped"] = 0
    # no allow flag
    errs = validate_accounting(acc, contract=contract)
    assert any("conflation" in e.lower() or "returned==compute" in e.lower() for e in errs), (
        f"expected conflation error, got {errs}"
    )


def test_unknown_field_honesty_e2d_marks_unavailable() -> None:
    _, handcheck = _load_contract_and_handcheck()
    avail = handcheck["e2d_reconciliation"]["availability"]
    for field in ("compute_completed", "returned", "dropped"):
        assert "UNAVAILABLE" in str(avail[field])


def test_contract_json_is_valid_json() -> None:
    assert CONTRACT_PATH.exists()
    assert HANDCHECK_PATH.exists()
    # ensure both are valid JSON and contain expected top-level keys
    c = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    h = json.loads(HANDCHECK_PATH.read_text(encoding="utf-8"))
    assert "lifecycle" in c
    assert "hand_example" in h
    assert "e2d_reconciliation" in h


def test_rejected_not_in_deadline_success() -> None:
    _, handcheck = _load_contract_and_handcheck()
    acc = handcheck["hand_example"]["accounting"]
    # deadline_success must be <= returned, and rejected are not counted
    assert acc["deadline_success"] <= acc["returned"]
    assert acc["gate_rejected"] + acc["capacity_rejected"] + acc["admitted"] == acc["offered"]
