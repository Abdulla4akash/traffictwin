"""Owner-approved candidate contracts for Manchester comparison and calibration.

The engines already exist: :mod:`~traffictwin.integration.manchester.comparison`
implements MAE/RMSE with full exclusion and coverage handling, and
:mod:`~traffictwin.integration.manchester.calibration` implements the bounded
evaluator. Both refuse to produce a production result until the exact contract
fingerprint appears in their approved registry, and **both registries are
empty**. This module builds the contract the owner authorised so that the
fingerprint exists and is checkable.

**Registration is deliberately not performed here.** `comparison.py` and
`calibration.py` are outside this agent's grant and are read, never modified, so
the approved-fingerprint frozensets stay as they are. The consequence is honest
and intended: production goodness-of-fit stays **unavailable** until whoever owns
those modules registers the fingerprint below. A contract that exists is not a
contract that has been accepted.

Research status is ``owner_approved_candidate``. The owner authorised these
values on 25 July 2026; the supervisor contract decision form is unsigned and is
neither edited nor represented as complete.

Interpretation is fixed ``descriptive_non_causal`` by the contract model itself.
A low error is not evidence of validity, causality, or generalisation, and
nothing here may describe it as such.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from traffictwin.integration.manchester.comparison import ManchesterComparisonMetricContract
from traffictwin.integration.manchester.dft_temporal_profile import DftTemporalProfilePolicy
from traffictwin.integration.manchester.models import sha256_hex
from traffictwin.integration.manchester.network_scope import baseline_scope_decision

OWNER_CANDIDATE_CONTRACTS_METHOD_VERSION: Literal["manchester-owner-candidate-contracts-1.0"] = (
    "manchester-owner-candidate-contracts-1.0"
)
RESEARCH_STATUS: Literal["owner_approved_candidate"] = "owner_approved_candidate"

#: The owner's identifier for the comparison contract. The engine's label pattern
#: admits lowercase, digits, hyphen, and underscore only, so the version reads
#: ``1-0`` rather than ``1.0``.
COMPARISON_CONTRACT_VERSION = "manchester-dft-comparison-owner-candidate-1-0"

#: Manchester local authority is the observation scope; Greater Manchester
#: outside it has no DfT observations and stays uncovered.
SCOPE_LABEL = "manchester-local-authority"

#: The temporal-profile policy fixes ``local_clock_hour`` and is the time basis
#: any comparison must share.
TIME_BASIS_LABEL = "local-clock-hour"

#: Exact hourly windows, no resampling.
INTERVAL_DURATION_S = 3_600

#: Both sides must reach this coverage before a result is admitted. Below it the
#: outcome is *unavailable*, never a failure and never a zero.
MINIMUM_COVERAGE = Decimal("0.800")


def scope_fingerprint() -> str:
    """Fingerprint of the approved Manchester scope decision."""

    return sha256_hex(baseline_scope_decision().canonical_json().encode("utf-8"))


def time_basis_fingerprint() -> str:
    """Fingerprint of the approved temporal-profile policy.

    Binding the comparison to this policy is what keeps the local-clock-hour
    basis from silently becoming a UTC one: a contract carrying a different
    time-basis fingerprint cannot be reconciled with a profile built under
    another basis.
    """

    return sha256_hex(DftTemporalProfilePolicy().canonical_json().encode("utf-8"))


def owner_candidate_comparison_contract() -> ManchesterComparisonMetricContract:
    """Build the owner-approved candidate comparison contract.

    Every methodological field the owner specified is either supplied here or
    already fixed as a literal by the engine's own model — pairing keys, no
    source fusion, exact-interval aggregation, equal-interval weighting,
    exclude-unpaired-never-zero missing handling, collapse-identical
    exclude-conflicts duplicates, simulated-minus-observed differences,
    ROUND_HALF_EVEN at 0.001, MAE and RMSE, and descriptive non-causal
    interpretation.
    """

    return ManchesterComparisonMetricContract(
        contract_version=COMPARISON_CONTRACT_VERSION,
        evidence_class="production",
        observed_source="dft_raw_count",
        scope_label=SCOPE_LABEL,
        scope_fingerprint=scope_fingerprint(),
        time_basis_label=TIME_BASIS_LABEL,
        time_basis_fingerprint=time_basis_fingerprint(),
        interval_duration_s=INTERVAL_DURATION_S,
        measure="vehicle_count",
        unit="vehicles_per_interval",
        minimum_observed_coverage=MINIMUM_COVERAGE,
        minimum_simulated_coverage=MINIMUM_COVERAGE,
    )


def comparison_contract_fingerprint() -> str:
    """The fingerprint that would have to be registered to admit a result.

    Handed over rather than registered: the registry lives in a module this
    agent does not own, and production goodness-of-fit correctly stays
    unavailable until the owner of that module registers it.
    """

    return sha256_hex(owner_candidate_comparison_contract().canonical_json().encode("utf-8"))


def comparison_contract_is_registered() -> bool:
    """Report whether the engine would currently admit a production result."""

    from traffictwin.integration.manchester.comparison import (
        APPROVED_PRODUCTION_CONTRACT_FINGERPRINTS,
    )

    return comparison_contract_fingerprint() in APPROVED_PRODUCTION_CONTRACT_FINGERPRINTS
