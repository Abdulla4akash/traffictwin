"""Typed structures for the TrafficTwin Analyst.

The Analyst sits above existing deterministic services. Its packet only
restates facts those services already computed; its classification is a
deterministic mapping over existing diagnostic rule outcomes; and its
optional prose rendering never calculates, invents, or promotes anything.
This preserves ADR-005: deterministic diagnostics before LLM rendering.
"""

from __future__ import annotations

import json
from enum import StrEnum
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ANALYST_PACKET_SCHEMA_VERSION: Literal["analyst-packet-1.0"] = "analyst-packet-1.0"
ANALYST_CLASSIFIER_VERSION: Literal["analyst-classifier-1.0"] = "analyst-classifier-1.0"

JsonScalar = bool | int | float | str | None

INFRASTRUCTURE_SIDE_RULE_IDS: tuple[str, ...] = ("R2", "R4")
MODEL_SIDE_RULE_IDS: tuple[str, ...] = ("R1", "R5")


class AnalystModel(BaseModel):
    """Frozen, closed base for every Analyst structure."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class AnalystSignal(StrEnum):
    """The bounded model-vs-infrastructure interpretation vocabulary."""

    INFRASTRUCTURE_SIDE_SIGNAL = "INFRASTRUCTURE_SIDE_SIGNAL"
    MODEL_SIDE_SIGNAL = "MODEL_SIDE_SIGNAL"
    MIXED_SIGNAL = "MIXED_SIGNAL"
    NO_MATERIAL_PROBLEM_DETECTED = "NO_MATERIAL_PROBLEM_DETECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


SIGNAL_DISPLAY_NAMES: dict[AnalystSignal, str] = {
    AnalystSignal.INFRASTRUCTURE_SIDE_SIGNAL: "Infrastructure-side signal",
    AnalystSignal.MODEL_SIDE_SIGNAL: "Model-side signal",
    AnalystSignal.MIXED_SIGNAL: "Mixed signal",
    AnalystSignal.NO_MATERIAL_PROBLEM_DETECTED: "No material problem detected",
    AnalystSignal.INSUFFICIENT_EVIDENCE: "Insufficient evidence",
}


class AnalystRefusalCode(StrEnum):
    """Typed failure states the Analyst surfaces instead of guessing."""

    NO_SELECTED_RUN = "NO_SELECTED_RUN"
    NO_SELECTED_COMPARISON = "NO_SELECTED_COMPARISON"
    INCOMPATIBLE_PAIR = "INCOMPATIBLE_PAIR"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    PROVENANCE_INCOMPLETE = "PROVENANCE_INCOMPLETE"
    EVIDENCE_STANDING_TOO_WEAK = "EVIDENCE_STANDING_TOO_WEAK"
    UNSUPPORTED_CAUSAL_REQUEST = "UNSUPPORTED_CAUSAL_REQUEST"
    UNSUPPORTED_RECOMMENDATION = "UNSUPPORTED_RECOMMENDATION"
    LLM_NOT_CONFIGURED = "LLM_NOT_CONFIGURED"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_MALFORMED_RESPONSE = "LLM_MALFORMED_RESPONSE"
    PRIVATE_CONTENT_REFUSED = "PRIVATE_CONTENT_REFUSED"


class AnalystRefusalError(RuntimeError):
    """Typed refusal: the Analyst names its gap instead of interpreting."""

    def __init__(self, code: AnalystRefusalCode, message: str) -> None:
        super().__init__(f"{code.value}: {message}")
        self.code = code
        self.refusal_message = message


class AnalystIdentity(AnalystModel):
    """Who is being analysed, with the existing compatibility contract."""

    subject_kind: Literal["single_run", "comparison"]
    baseline_run_id: str | None = None
    variation_run_id: str | None = None
    experiment_id: str | None = None
    metric_version: str | None = None
    baseline_standing: Literal["SYNTHETIC", "IMPORTED", "UNKNOWN"]
    variation_standing: Literal["SYNTHETIC", "IMPORTED", "UNKNOWN"] | None = None
    same_experiment: bool | None = None
    same_random_seed: bool | None = None
    same_metric_version: bool | None = None
    synthetic_match: bool | None = None
    comparison_compatible: bool | None = None


class AnalystMetricFact(AnalystModel):
    """One metric restated from an existing service, never recomputed."""

    metric_key: str
    label: str
    unit: str | None = None
    baseline: JsonScalar = None
    variation: JsonScalar = None
    absolute_delta: float | None = None
    relative_delta: float | None = None
    status: str
    reason_codes: tuple[str, ...] = ()
    denominator: str | None = None
    source_service: Literal["consequence_lens", "metric_collection"]


class AnalystFindingFact(AnalystModel):
    """One deterministic rule finding, cited verbatim."""

    finding_id: str
    statement: str
    evidence_keys: tuple[str, ...] = ()
    observed_values: dict[str, JsonScalar] = Field(default_factory=dict)
    expected_condition: str
    support: str


class AnalystRecommendationFact(AnalystModel):
    """One existing conditional recommendation, cited verbatim."""

    action: str
    rationale: str
    expected_direction: str
    prerequisite: str
    verification_step: str
    conditional: Literal[True] = True


class AnalystRuleFact(AnalystModel):
    """One deterministic diagnostic rule outcome, restated."""

    rule_id: str
    title: str
    status: str
    confidence: str
    hypothesis: str | None = None
    evidence_keys: tuple[str, ...] = ()
    findings: tuple[AnalystFindingFact, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    recommendations: tuple[AnalystRecommendationFact, ...] = ()
    limitations: tuple[str, ...] = ()


class AnalystCrossRuleFact(AnalystModel):
    """One existing cross-rule relationship, restated."""

    relation_type: str
    source_rule_id: str
    target_rule_id: str
    statement: str


class AnalystDiagnostics(AnalystModel):
    """Deterministic diagnostic outcomes for the analysed subject."""

    subject_side: Literal["variation", "single_run"]
    subject_readiness: str
    subject_ruleset_version: str
    subject_rules: tuple[AnalystRuleFact, ...] = ()
    baseline_readiness: str | None = None
    baseline_triggered_rule_ids: tuple[str, ...] = ()
    cross_rule: tuple[AnalystCrossRuleFact, ...] = ()
    conflict_observations: tuple[str, ...] = ()


class AnalystProvenance(AnalystModel):
    """Digests binding every packet claim to its source artifacts."""

    baseline_bundle_fingerprint: str | None = None
    variation_bundle_fingerprint: str | None = None
    baseline_metrics_input_fingerprint: str | None = None
    variation_metrics_input_fingerprint: str | None = None
    subject_diagnostic_fingerprint: str | None = None
    baseline_diagnostic_fingerprint: str | None = None
    consequence_lens_fingerprint: str | None = None


class AnalystEvidencePacket(AnalystModel):
    """The bounded, validated structure everything downstream consumes.

    The packet carries no wall-clock field, so identical inputs produce an
    identical canonical form and fingerprint.
    """

    schema_version: Literal["analyst-packet-1.0"] = ANALYST_PACKET_SCHEMA_VERSION
    identity: AnalystIdentity
    traffic_facts: tuple[AnalystMetricFact, ...] = ()
    vec_facts: tuple[AnalystMetricFact, ...] = ()
    infrastructure_facts: tuple[AnalystMetricFact, ...] = ()
    changed_parameters: tuple[dict[str, JsonScalar], ...] = ()
    diagnostics: AnalystDiagnostics
    provenance: AnalystProvenance
    unavailable_metric_keys: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    creates_new_evidence: Literal[False] = False
    scientific_recomputation_performed: Literal[False] = False
    causal_claim_supported: Literal[False] = False

    def canonical_json(self) -> str:
        """Deterministic canonical form for fingerprinting and transport.

        The two diagnostic-report citation digests are normalised out: the
        upstream report identity embeds its generation instant, while the
        report's content is already restated verbatim in ``diagnostics``.
        Everything the packet asserts is therefore covered without making
        identical inputs produce different fingerprints.
        """
        payload = self.model_dump(mode="json")
        payload["provenance"]["subject_diagnostic_fingerprint"] = None
        payload["provenance"]["baseline_diagnostic_fingerprint"] = None
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()


class AnalystClassification(AnalystModel):
    """The deterministic interpretation; the LLM can never change it."""

    classifier_version: Literal["analyst-classifier-1.0"] = ANALYST_CLASSIFIER_VERSION
    signal: AnalystSignal
    statement: str
    rule_basis: tuple[str, ...] = ()
    supported_facts: tuple[str, ...] = ()
    not_supported: tuple[str, ...] = ()
    confidence: str
    confidence_basis: str
    next_investigation: str | None = None
    packet_fingerprint: str
    causal_claim_supported: Literal[False] = False
    execution_authority: Literal[False] = False
