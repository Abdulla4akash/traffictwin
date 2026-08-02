"""Mechanism and policy observatory (post-v1 O-1): read-only, evidence-bound.

Implements ``docs/platform/mechanism_policy_observatory_design.md``: one
inspectable place for what the actor observes, why capacity was excluded
from its observation, whether the policy changes, and what mechanism
explains the counter-intuitive headline — WITHOUT diagnosing causality,
recommending a policy, executing anything, or upgrading any result's
standing.

The headline stays narrow and coherence-checked: standard VEC QoS metrics
can improve when the system is degraded; capacity is the instrument, not the
whole contribution. The −8,310.9 ms latency delta may render ONLY beside its
bootstrap interval, the unanimous five-seed direction, the exact p = 0.0625
sign-test floor, the effectively-flat deadline fact, and the statement that
the reduction lives inside already-failed tasks — a template missing any
companion refuses rather than rendering.

Every card binds the committed records it derives from by content digest at
build time; no scientific endpoint is recalculated here; and the forbidden
vocabulary (``ground_truth``, ``causal``, ``validated_policy``, ``optimal``,
``production_ready``) refuses at the model boundary.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

METHOD_VERSION: Literal["mechanism-observatory-1.0"] = "mechanism-observatory-1.0"
DESIGN_REFERENCE: Literal["docs/platform/mechanism_policy_observatory_design.md"] = (
    "docs/platform/mechanism_policy_observatory_design.md"
)
CITATION_REFERENCE: Literal["docs/producer_citation_requirements.md"] = (
    "docs/producer_citation_requirements.md"
)

EvidenceRole = Literal["protocol_confirmed", "post_hoc", "exploratory", "descriptive"]
AdmissionQualifier = Literal["clean", "admitted_with_execution_deviation", "non_admitted"]
SupportState = Literal["supported", "not_supported", "not_tested", "incompatible", "unavailable"]

PUBLIC_DISPLAY_ORDER = (
    "standing_scope_deviation",
    "primary_endpoint",
    "uncertainty",
    "companion_metrics",
    "mechanisms",
    "limitations",
    "citations",
)

#: Language no card may carry, per design §4 — refused at the model boundary.
FORBIDDEN_LANGUAGE = (
    "ground_truth",
    "causal",
    "validated_policy",
    "optimal",
    "production_ready",
)

_PRIVATE_MARKERS = ("/Users/", "/home/", "\\Users\\")

SIGN_TEST_WORDING = (
    "all five paired held-out seeds moved in the same direction; the exact two-sided "
    "sign-test floor at n=5 is p=0.0625, so conventional significance is not claimed"
)


class ObservatoryError(RuntimeError):
    """Typed refusal; the observatory fails closed, never silently."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ObservatoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)

    @model_validator(mode="after")
    def refuse_forbidden_language(self) -> ObservatoryModel:
        material = json.dumps(self.model_dump(mode="json"), sort_keys=True).lower()
        for term in FORBIDDEN_LANGUAGE:
            if term in material:
                raise ValueError(
                    f"observatory cards must not carry the term '{term}'; the design "
                    "forbids it outright"
                )
        for marker in _PRIVATE_MARKERS:
            if marker in material:
                raise ValueError("observatory cards must not carry private paths")
        return self


class SourceBinding(ObservatoryModel):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class StudyCard(ObservatoryModel):
    """One study boundary; execution and admission remain explicit fields."""

    study_id: str
    design_fingerprint: str
    trace_family: str
    actor_family: str
    capacity_arms: tuple[str, ...]
    seed_set: tuple[int, ...]
    evidence_role: EvidenceRole
    admission_status: Literal["admitted", "non_admitted"]
    admission_qualifier: AdmissionQualifier
    execution_deviations: tuple[str, ...] = ()
    sources: tuple[SourceBinding, ...] = Field(min_length=1)


class MechanismCard(ObservatoryModel):
    """One mechanism statistic with its role, support and limitations."""

    card_id: str
    title: str
    statistic: str
    support: str
    evidence_role: EvidenceRole
    limitations: tuple[str, ...] = Field(min_length=1)
    sources: tuple[SourceBinding, ...] = Field(min_length=1)


class PolicyContractCard(ObservatoryModel):
    """What a policy could condition on — never what it internally learned."""

    card_id: str
    actor_family: str
    checkpoint: str
    observation_summary: str
    rsu_capacity_in_observation: bool
    action_space: str
    reward_summary: str
    measured_capacity_envelope: str
    sources: tuple[SourceBinding, ...] = Field(min_length=1)


class ActionInvarianceCard(ObservatoryModel):
    """Paired action summaries across arms; absence is unavailable, not zero."""

    card_id: str
    state: SupportState
    statement: str
    support: str
    evidence_role: EvidenceRole
    sources: tuple[SourceBinding, ...] = Field(min_length=1)


class ConfirmedHeadlineCard(ObservatoryModel):
    """The five-seed capacity study with every companion fact REQUIRED."""

    card_id: Literal["confirmed-capacity-headline"] = "confirmed-capacity-headline"
    evidence_role: Literal["protocol_confirmed"] = "protocol_confirmed"
    mean_latency_delta_ms: float
    bootstrap_low_ms: float
    bootstrap_high_ms: float
    unanimous_direction: Literal[True]
    sign_test_wording: str
    deadline_attainment_fact: str
    locus_fact: str
    sources: tuple[SourceBinding, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_coherence(self) -> ConfirmedHeadlineCard:
        if "p=0.0625" not in self.sign_test_wording:
            raise ValueError("the sign-test floor wording is a required companion")
        if "flat" not in self.deadline_attainment_fact:
            raise ValueError("the flat-deadline fact is a required companion")
        if "already-failed" not in self.locus_fact:
            raise ValueError("the inside-already-failed-tasks fact is a required companion")
        return self


class CoherenceCheck(ObservatoryModel):
    """Presence check only; it never recomputes the companion metrics."""

    check_id: str
    state: SupportState
    required_metrics: tuple[str, ...] = Field(min_length=1)
    present_metrics: tuple[str, ...]
    limitation: str
    sources: tuple[SourceBinding, ...] = Field(min_length=1)


class ObservatoryBundle(ObservatoryModel):
    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["mechanism-observatory-1.0"] = METHOD_VERSION
    design_reference: Literal["docs/platform/mechanism_policy_observatory_design.md"] = (
        DESIGN_REFERENCE
    )
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    evidence: Literal[False] = False
    public_display_order: tuple[str, ...]
    studies: tuple[StudyCard, ...] = Field(min_length=1)
    headline: ConfirmedHeadlineCard
    mechanism_cards: tuple[MechanismCard, ...]
    policy_contracts: tuple[PolicyContractCard, ...]
    action_invariance: ActionInvarianceCard
    coherence_checks: tuple[CoherenceCheck, ...] = Field(min_length=1)
    appendix_non_admitted: tuple[MechanismCard, ...]
    citation_reference: Literal["docs/producer_citation_requirements.md"] = CITATION_REFERENCE
    bundle_digest: str

    @model_validator(mode="after")
    def validate_public_display_order(self) -> ObservatoryBundle:
        if self.public_display_order != PUBLIC_DISPLAY_ORDER:
            raise ValueError("public display order must match the owner-selected safe order")
        return self


def _bind(repo_root: Path, paths: tuple[str, ...]) -> tuple[SourceBinding, ...]:
    bindings = []
    for path in paths:
        absolute = repo_root / path
        if not absolute.is_file():
            raise ObservatoryError(
                "SOURCE_DIGEST_MISMATCH", f"committed record '{path}' is missing"
            )
        digest = hashlib.sha256(absolute.read_bytes()).hexdigest()
        expected = EXPECTED_SOURCE_DIGESTS.get(path)
        if expected is None or digest != expected:
            raise ObservatoryError(
                "SOURCE_DIGEST_MISMATCH",
                f"committed record '{path}' no longer matches the reviewed source digest",
            )
        bindings.append(SourceBinding(path=path, sha256=digest))
    return tuple(bindings)


_CONFIRMATORY = "docs/evaluation/capacity_confirmatory_results_20260728.md"
_TAIL = "docs/evaluation/latency_tail_analysis_20260728.md"
_DYNAMICS = "docs/evaluation/pilot_dynamics_analysis_20260728.md"
_FINDINGS = "docs/evaluation/capacity_study_detailed_findings.md"
_CROSSOVER = "docs/evaluation/actor_crossover_results_20260730.md"
_CEILING = "docs/evaluation/ceiling_law_prediction_results_20260729.md"
_CATALOGUE = "docs/evaluation/experiment_catalogue_20260730.md"
_SPARSE64_CLEAN = "docs/evaluation/bbus_sparse64_clean_rerun_results_20260730.md"
_SPARSE64_ADMISSION = "docs/evaluation/bbus_sparse64_clean_rerun_owner_admission_20260802.json"
_SPARSE64_EARLIER = "docs/evaluation/bbus_sparse64_homecoming_results_20260730.md"

EXPECTED_SOURCE_DIGESTS: dict[str, str] = {
    _CONFIRMATORY: "5659be5530dc0dce97123206e35359c6a1d7bf84e95a7ebaee54a4a69600ed76",
    _TAIL: "e2ca014469ed853c52c0eccea1f74d2a07f0dc33e8f6898b70a4d6b5d471488e",
    _DYNAMICS: "7f5b5fb6574fdcf2cfa05d8220bf0ea3792ea9c4b782186dbe3105f0ff571687",
    _FINDINGS: "18dc5b64799235253d49880cd8c96fa645038bc24727512315d8eb461d77b54a",
    _CROSSOVER: "2802fa01102f73005b223dbc26536b4e7381c1677a4d612641a77396ebea1fbf",
    _CEILING: "5f3349c64e9171331ac5de1c89ca9ec4b375c472904095be4d9dc06176885575",
    _CATALOGUE: "3e21aa4e47c36c7f42d7e9d3d14489f40165e8ee2f17a59c7404dc32b3e65434",
    "docs/evaluation/rsu_association_analysis_20260729.md": (
        "13e2de44ef8a1a67a6d29f63944aa84a6c0d3597f6c3be922f3d64ff28bd2b14"
    ),
    _SPARSE64_CLEAN: "052b1e295675a68052f90b081195c836810c53133232640b0d1b0c2ec788dfb6",
    _SPARSE64_ADMISSION: ("7e1eb25c156d423db9d6e3608505b8e9b373ec5de07d06dd1f92203b546d3696"),
    _SPARSE64_EARLIER: ("4bd46731ebf24f5ca3145aea767dcb99d066e4e2d234be7bcf0d50f59c013b3e"),
}


def build_observatory_bundle(repo_root: Path) -> ObservatoryBundle:
    """Bind every card to its committed sources; refuse anything missing."""

    studies = (
        StudyCard(
            study_id="vec-capacity-confirmatory",
            design_fingerprint="f289db31ce28b636",
            trace_family="inc",
            actor_family="ukfleettrain_mappo",
            capacity_arms=("cap-2.5", "cap-0.75"),
            seed_set=(10, 11, 12, 13, 14),
            evidence_role="protocol_confirmed",
            admission_status="admitted",
            admission_qualifier="clean",
            sources=_bind(repo_root, (_CONFIRMATORY, _CATALOGUE)),
        ),
        StudyCard(
            study_id="bbus-sparse64-clean-rerun",
            design_fingerprint="not_recorded",
            trace_family="derived bus (Sparse-64)",
            actor_family="GPU-track training returns",
            capacity_arms=("cap-2.5", "cap-0.75"),
            seed_set=(30, 31, 32, 33, 34),
            evidence_role="descriptive",
            admission_status="admitted",
            admission_qualifier="admitted_with_execution_deviation",
            execution_deviations=(
                "one unintended second fixed held-out evaluation and return followed a "
                "terminal-state ordering timeout; the first complete archive was overwritten",
            ),
            sources=_bind(repo_root, (_SPARSE64_CLEAN, _SPARSE64_ADMISSION)),
        ),
    )
    headline = ConfirmedHeadlineCard(
        mean_latency_delta_ms=-8310.9,
        bootstrap_low_ms=-9097.5,
        bootstrap_high_ms=-7524.3,
        unanimous_direction=True,
        sign_test_wording=SIGN_TEST_WORDING,
        deadline_attainment_fact=(
            "deadline attainment was effectively flat across the same paired seeds "
            "(0.7709 vs 0.7721 descriptively)"
        ),
        locus_fact=(
            "the reduction occurred inside already-failed tasks — it is not an "
            "improvement experienced by any individual vehicle"
        ),
        sources=_bind(repo_root, (_CONFIRMATORY, _TAIL)),
    )
    mechanism_cards = (
        MechanismCard(
            card_id="ceiling-law",
            title="Capacity-scaled latency ceiling",
            statistic=(
                "p95-of-missed = K x capacity with K = 39,959 ms (sample sigma 166) over "
                "36 pilot cell-class pairs; pre-registered prediction HELD 27/27 on "
                "deep-inc with a monotone sag (+1.08 to +3.42% on the worst class)"
            ),
            support="12 admitted pilot cells + 12 deep-inc cells, 3 seeds each",
            evidence_role="protocol_confirmed",
            limitations=(
                "an RSU-queue property of the saturated collapse hour; ~92% of missed "
                "tasks are offloaded, so the law says nothing about local execution",
            ),
            sources=_bind(repo_root, (_DYNAMICS, _CEILING)),
        ),
        MechanismCard(
            card_id="tail-composition",
            title="Latency mass lives in the tail",
            statistic=(
                "p50 = 44.3 ms at every capacity (−0.10% over a 3.3x squeeze); p99 falls "
                "69.9%; 97.9–99.4% of latency mass sits above 1 s"
            ),
            support="39,228,702 active tasks per arm, pooled over pilot seeds {0,1,2}",
            evidence_role="post_hoc",
            limitations=(
                "tail-versus-mean is not novel in queueing; the contribution is the "
                "rigorous demonstration in VEC offloading",
            ),
            sources=_bind(repo_root, (_TAIL,)),
        ),
        MechanismCard(
            card_id="bimodal-partition",
            title="The policy is a fixed partition, not a probabilistic rate",
            statistic=(
                "per seed: ~1,413 slots never offload, ~988 always do, only ~87 ever mix; "
                "identical at all four capacities; always-offload is 100% tier-0 in every "
                "measured cell"
            ),
            support="12 pilot cells, 3 seeds; tier check replicated on 5 deep cells",
            evidence_role="post_hoc",
            limitations=(
                "attainment (~79%) is a fleet-composition artifact of the tier mix, "
                "not a per-situation success probability",
            ),
            sources=_bind(repo_root, (_DYNAMICS, _FINDINGS)),
        ),
        MechanismCard(
            card_id="failure-concentration",
            title="Failure is concentrated on a persistent minority",
            statistic=(
                "failure-rate Gini 0.616–0.627 with the worst decile carrying 34–36% of "
                "all failures, while task-count Gini is 0.028"
            ),
            support="12 admitted pilot cells, 3 seeds",
            evidence_role="post_hoc",
            limitations=(
                "near-perfect service for most vehicles coexists with near-total failure "
                "for a persistent minority; a mean hides this",
            ),
            sources=_bind(repo_root, (_DYNAMICS,)),
        ),
        MechanismCard(
            card_id="rsu-placement",
            title="RSU load asymmetry",
            statistic=(
                "3 of 10 RSUs carry exactly zero load at every capacity; four RSUs at "
                "96–98% occupancy carry ~99.1% of load; squeeze does not redistribute "
                "(Gini 0.486 to 0.467)"
            ),
            support="12 admitted pilot cells, 3 seeds",
            evidence_role="exploratory",
            limitations=(
                "the per-vehicle RSU-association attribution was WITHDRAWN the same day "
                "it was drafted (wrong unit of analysis); the placement asymmetry and "
                "zero-load trio stand, the association mechanism is undetermined",
            ),
            sources=_bind(repo_root, ("docs/evaluation/rsu_association_analysis_20260729.md",)),
        ),
        MechanismCard(
            card_id="sparse64-clean-rerun",
            title="Sparse-64 clean rerun — ADMITTED WITH EXECUTION DEVIATION",
            statistic=(
                "owner-admitted descriptive return: equal-weight held-out peak deadline "
                "completion was 0.501355 at capacity 0.75 and 0.501233 at capacity 2.5; "
                "mean latency was 895.561 and 1,055.814 ms/task respectively"
            ),
            support="five model seeds {30,31,32,33,34}; 23,686,959 tasks at capacity 0.75",
            evidence_role="descriptive",
            limitations=(
                "one unintended second fixed evaluation occurred after a terminal-state "
                "ordering timeout; the first archive was overwritten and cross-return metric "
                "identity cannot be verified",
                "dawn-trained and peak-evaluated with simulated task outcomes and 64 generated "
                "analysis sites; it is outside VEC-06 and is never pooled with corridor evidence",
                "the owner admission does not establish a general Manchester, observed-RSU, "
                "real-computing-task, supervisor or production claim",
            ),
            sources=_bind(repo_root, (_SPARSE64_CLEAN, _SPARSE64_ADMISSION)),
        ),
    )
    policy_contracts = (
        PolicyContractCard(
            card_id="trained-actor-contract",
            actor_family="ukfleettrain_mappo",
            checkpoint="model_c_17 (audited)",
            observation_summary=(
                "17-dimensional per-vehicle observation; every input is vehicle-side and "
                "bit-identical across capacity arms"
            ),
            rsu_capacity_in_observation=False,
            action_space="discrete offload-target selection",
            reward_summary="producer-defined reward (cited, not re-derived here)",
            measured_capacity_envelope=(
                "inc [0.1, 2.5] via pilot + deep; we/ev/wd_am/wd_pm measured inert above "
                "their onsets"
            ),
            sources=_bind(repo_root, (_FINDINGS, _CATALOGUE)),
        ),
        PolicyContractCard(
            card_id="baseline-actor-contract",
            actor_family="baseline",
            checkpoint="model_c_17 family (audited)",
            observation_summary=(
                "same observation contract; no RSU-load or capacity term exists in it"
            ),
            rsu_capacity_in_observation=False,
            action_space="discrete offload-target selection",
            reward_summary="producer-defined reward (cited, not re-derived here)",
            measured_capacity_envelope="ev [0.75, 2.5]; inc [0.75, 2.5]",
            sources=_bind(repo_root, (_CROSSOVER, _CATALOGUE)),
        ),
    )
    action_invariance = ActionInvarianceCard(
        card_id="keyed-action-identity",
        state="supported",
        statement=(
            "offloading decisions are bit-identical across capacity arms: zero mismatches "
            "over 8.9M keyed action cells x 9 arm pairs; the confirmed latency delta "
            "coexists with unchanged actions"
        ),
        support="keyed comparison over all pilot arms and seeds",
        evidence_role="post_hoc",
        sources=_bind(repo_root, (_FINDINGS, _CATALOGUE)),
    )
    coherence_checks = (
        CoherenceCheck(
            check_id="confirmed-capacity-outcome-coherence",
            state="supported",
            required_metrics=(
                "mean_latency",
                "bootstrap_interval",
                "deadline_attainment",
                "action_change",
                "failure_locus",
            ),
            present_metrics=(
                "mean_latency",
                "bootstrap_interval",
                "deadline_attainment",
                "action_change",
                "failure_locus",
            ),
            limitation=(
                "five paired held-out seeds bound exact-test resolution; conventional "
                "significance is not claimed"
            ),
            sources=_bind(repo_root, (_CONFIRMATORY, _TAIL, _FINDINGS)),
        ),
    )
    appendix = (
        MechanismCard(
            card_id="sparse64-appendix",
            title="Earlier Sparse-64 147-repeat return — NON_ADMITTED appendix",
            statistic=(
                "the earlier retained return completed compute (5/5) but remains "
                "NON_ADMITTED; peak completion 0.519215 at cap-0.75 vs 0.519108 at "
                "cap-2.5 is a descriptive observation only"
            ),
            support="one retained archive after 148 returns; execution-deviated",
            evidence_role="descriptive",
            limitations=(
                "147 unintended repeated returns and archive replacement remain first-class; "
                "these numbers never join admitted views",
            ),
            sources=_bind(repo_root, (_SPARSE64_EARLIER,)),
        ),
    )
    material = json.dumps(
        {
            "studies": [card.model_dump(mode="json") for card in studies],
            "headline": headline.model_dump(mode="json"),
            "mechanisms": [card.model_dump(mode="json") for card in mechanism_cards],
            "contracts": [card.model_dump(mode="json") for card in policy_contracts],
            "invariance": action_invariance.model_dump(mode="json"),
            "coherence": [check.model_dump(mode="json") for check in coherence_checks],
            "appendix": [card.model_dump(mode="json") for card in appendix],
            "public_display_order": PUBLIC_DISPLAY_ORDER,
        },
        sort_keys=True,
    )
    return ObservatoryBundle(
        public_display_order=PUBLIC_DISPLAY_ORDER,
        studies=studies,
        headline=headline,
        mechanism_cards=mechanism_cards,
        policy_contracts=policy_contracts,
        action_invariance=action_invariance,
        coherence_checks=coherence_checks,
        appendix_non_admitted=appendix,
        bundle_digest=hashlib.sha256(material.encode("utf-8")).hexdigest(),
    )


# --- views and refusals ------------------------------------------------------


def select_mechanism_cards(
    bundle: ObservatoryBundle,
    *,
    evidence_role: EvidenceRole | None = None,
    include_non_admitted_appendix: bool = False,
) -> tuple[MechanismCard, ...]:
    """Filter cards without pooling roles or promoting the appendix."""

    cards = list(bundle.mechanism_cards)
    if include_non_admitted_appendix:
        if evidence_role is not None and evidence_role != "descriptive":
            raise ObservatoryError(
                "NON_ADMITTED_PROMOTION",
                "the non-admitted appendix joins only the separately labelled "
                "descriptive view, never a confirmed/post-hoc selection",
            )
        cards.extend(bundle.appendix_non_admitted)
    if evidence_role is None:
        return tuple(cards)
    return tuple(card for card in cards if card.evidence_role == evidence_role)


def compare_roles(
    bundle: ObservatoryBundle, first: EvidenceRole, second: EvidenceRole
) -> tuple[MechanismCard, ...]:
    """A cross-role comparison is a refusal, not a merge."""

    if first != second:
        raise ObservatoryError(
            "EVIDENCE_ROLE_MIXED",
            f"'{first}' and '{second}' results are never pooled; render them as "
            "separate, labelled views",
        )
    return select_mechanism_cards(bundle, evidence_role=first)


def compare_actors(bundle: ObservatoryBundle, first: str, second: str) -> str:
    """Actor comparison is legitimate only on the recorded shared frame."""

    families = {card.actor_family for card in bundle.policy_contracts}
    if first not in families or second not in families:
        raise ObservatoryError(
            "INCOMPATIBLE_ACTORS",
            f"no policy contract card exists for one of ('{first}', '{second}')",
        )
    return (
        "actor comparison is reported only through the committed crossover analysis "
        "(+6.09 pp margin at every capacity, NO crossover); the uk2030 preset matches "
        "the trained actor's training distribution, so preset mismatch remains a live "
        "alternative explanation"
    )


def render_headline(bundle: ObservatoryBundle) -> str:
    """The coherence-checked headline template; companions are mandatory."""

    card = bundle.headline
    invariance = bundle.action_invariance
    if invariance.state == "unavailable":
        raise ObservatoryError(
            "ACTION_LOG_UNAVAILABLE",
            "the action-invariance companion is unavailable; the headline does not "
            "render without it",
        )
    lines = [
        "CONFIRMED (held-out, protocol-confirmed): standard VEC QoS metrics can be "
        "improved by degrading the system.",
        f"- mean paired latency delta {card.mean_latency_delta_ms} ms, bootstrap "
        f"[{card.bootstrap_low_ms}, {card.bootstrap_high_ms}] ms",
        f"- {card.sign_test_wording}",
        f"- {card.deadline_attainment_fact}",
        f"- {card.locus_fact}",
        f"- companion: {invariance.statement}",
        f"citation set: {bundle.citation_reference}",
    ]
    rendered = "\n".join(lines)
    if "p=0.0625" not in rendered or "already-failed" not in rendered:
        raise ObservatoryError(
            "REQUIRED_COMPANION_METRIC_MISSING",
            "a required companion fact fell out of the headline template",
        )
    return rendered


def bundle_to_json(bundle: ObservatoryBundle) -> str:
    return json.dumps(bundle.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)
