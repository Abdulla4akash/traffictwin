"""Evidence for the owner-approved candidate comparison contract.

The contract exists so its fingerprint is checkable. It is deliberately **not**
registered: the approved-fingerprint registry lives in a module this work does
not own, so production goodness-of-fit correctly stays unavailable.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.comparison import (
    APPROVED_PRODUCTION_CONTRACT_FINGERPRINTS,
    ManchesterComparisonMetricContract,
)
from traffictwin.integration.manchester.owner_candidate_contracts import (
    COMPARISON_CONTRACT_VERSION,
    INTERVAL_DURATION_S,
    MINIMUM_COVERAGE,
    comparison_contract_fingerprint,
    comparison_contract_is_registered,
    owner_candidate_comparison_contract,
    scope_fingerprint,
    time_basis_fingerprint,
)


class TestTheContractRecordsTheOwnersDecisions:
    def test_every_specified_decision_is_present(self) -> None:
        contract = owner_candidate_comparison_contract()
        assert contract.contract_version == COMPARISON_CONTRACT_VERSION
        assert contract.evidence_class == "production"
        assert contract.observed_source == "dft_raw_count"
        assert contract.measure == "vehicle_count"
        assert contract.unit == "vehicles_per_interval"
        assert contract.interval_duration_s == INTERVAL_DURATION_S == 3600
        assert contract.minimum_observed_coverage == MINIMUM_COVERAGE == Decimal("0.800")
        assert contract.minimum_simulated_coverage == MINIMUM_COVERAGE
        assert contract.goodness_of_fit_metrics == ("mae", "rmse")

    def test_the_pairing_keys_are_the_specified_five(self) -> None:
        assert owner_candidate_comparison_contract().pairing_key_fields == (
            "site_edge_id",
            "interval_start_s",
            "interval_end_s",
            "direction",
            "vehicle_class",
        )

    def test_missing_is_excluded_and_never_zero(self) -> None:
        contract = owner_candidate_comparison_contract()
        assert contract.missing_policy == "exclude_unpaired_never_zero"
        assert contract.duplicate_policy == "collapse_identical_exclude_conflicts"

    def test_differences_are_simulated_minus_observed_at_the_specified_precision(self) -> None:
        contract = owner_candidate_comparison_contract()
        assert contract.difference_direction == "simulated_minus_observed"
        assert contract.rounding_mode == "ROUND_HALF_EVEN"
        assert contract.result_quantum == "0.001"

    def test_interpretation_stays_descriptive_and_non_causal(self) -> None:
        assert (
            owner_candidate_comparison_contract().interpretation_policy == "descriptive_non_causal"
        )

    def test_no_source_fusion_and_no_resampling(self) -> None:
        contract = owner_candidate_comparison_contract()
        assert contract.source_fusion == "none"
        assert contract.interval_aggregation == "exact_interval_no_resampling"
        assert contract.weighting_policy == "equal_interval"


class TestTheContractIsBoundToRealArtifacts:
    def test_the_scope_fingerprint_is_derived_not_invented(self) -> None:
        from traffictwin.integration.manchester.models import sha256_hex
        from traffictwin.integration.manchester.network_scope import baseline_scope_decision

        expected = sha256_hex(baseline_scope_decision().canonical_json().encode("utf-8"))
        assert scope_fingerprint() == expected

    def test_the_time_basis_fingerprint_binds_the_local_clock_policy(self) -> None:
        from traffictwin.integration.manchester.dft_temporal_profile import (
            DftTemporalProfilePolicy,
        )
        from traffictwin.integration.manchester.models import sha256_hex

        policy = DftTemporalProfilePolicy()
        assert policy.time_basis == "local_clock_hour"
        expected = sha256_hex(policy.canonical_json().encode("utf-8"))
        assert time_basis_fingerprint() == expected

    def test_the_fingerprint_is_stable_across_calls(self) -> None:
        assert comparison_contract_fingerprint() == comparison_contract_fingerprint()
        assert len(comparison_contract_fingerprint()) == 64


class TestRegistrationIsNotPerformedHere:
    def test_the_registry_is_still_empty(self) -> None:
        # comparison.py is outside this work's grant and is read, never modified.
        assert frozenset() == APPROVED_PRODUCTION_CONTRACT_FINGERPRINTS

    def test_the_contract_is_not_registered(self) -> None:
        assert comparison_contract_is_registered() is False

    def test_a_contract_that_exists_is_not_a_contract_that_is_accepted(self) -> None:
        # Building the artifact must not make the engine admit a result.
        contract = owner_candidate_comparison_contract()
        assert contract.evidence_class == "production"
        assert comparison_contract_fingerprint() not in APPROVED_PRODUCTION_CONTRACT_FINGERPRINTS


class TestTheEngineStillRefusesIncoherentContracts:
    def test_a_dft_contract_cannot_compare_speeds(self) -> None:
        payload: dict[str, Any] = json.loads(owner_candidate_comparison_contract().canonical_json())
        payload["measure"] = "average_speed_mps"
        payload["unit"] = "m/s"
        with pytest.raises(ValidationError, match="vehicle counts only"):
            ManchesterComparisonMetricContract.model_validate_json(json.dumps(payload))

    def test_a_production_contract_cannot_select_the_synthetic_source(self) -> None:
        payload: dict[str, Any] = json.loads(owner_candidate_comparison_contract().canonical_json())
        payload["observed_source"] = "synthetic_utc_road"
        with pytest.raises(ValidationError):
            ManchesterComparisonMetricContract.model_validate_json(json.dumps(payload))

    def test_a_coverage_off_the_permitted_quantum_is_refused(self) -> None:
        payload: dict[str, Any] = json.loads(owner_candidate_comparison_contract().canonical_json())
        payload["minimum_observed_coverage"] = "0.8005"
        with pytest.raises(ValidationError, match="multiples of 0.001"):
            ManchesterComparisonMetricContract.model_validate_json(json.dumps(payload))
