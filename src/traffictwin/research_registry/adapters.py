"""Current admitted E2 adapter/service.

Inspects and reuses exact current load_admitted_builtin_e2_research /
admission receipt / typed comparison APIs. No duplicate validators,
no arbitrary filesystem reads. Converts only exact admitted E2b/E2c/E2d
into future-generic ResearchStudyRecords. Preserves separate code SHAs,
manifests, replication units/seeds/draws, arms/metrics/per-draw values,
primary vs secondary, intervals, limitations/non-claims/product links,
and admitted product standing. No task-as-replicate, no invented telemetry.
Explicit supported current lineage only. E2d is bounded construct-validity/
robustness, not universal superiority. Future E3 absent.
"""

from __future__ import annotations

from typing import Final

from traffictwin.evidence_admission.e2_research import load_admitted_builtin_e2_research
from traffictwin.experiments.e2_comparison import build_e2_comparison_view
from traffictwin.experiments.e2_research_evidence import E2ResearchEvidencePackage
from traffictwin.research_registry.ingestion import (
    AdmissionPolicy,
    AdmissionPolicyEntry,
    ResearchStudyPackage,
)
from traffictwin.research_registry.lineage import LineageEdge, RelationshipType
from traffictwin.research_registry.models import (
    AdmissionStatus,
    DeclaredSummary,
    EvidenceStanding,
    PerDrawValue,
    ResearchStudyRecord,
    StudyStatus,
)

# ---------------------------------------------------------------------------
# Frozen E2 identities (must match exact admitted sources)
# ---------------------------------------------------------------------------

E2B_STUDY: Final[str] = "E2b"
E2C_STUDY: Final[str] = "E2c"
E2D_STUDY: Final[str] = "E2d"
E2_VERSION: Final[str] = "1.0"

_E2B_HEAD: Final[str] = "fe2ed4e9bd9043b19b96a5f179390db629b01ccb"
_E2C_HEAD: Final[str] = "1a08d6e148a1e8c430da39c3d575eda3f8ea5929"
_E2D_HEAD: Final[str] = "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761"
_E2B_MANIFEST: Final[str] = "9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91"
_E2C_MANIFEST: Final[str] = "fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a"
_E2D_MANIFEST: Final[str] = "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740"

_ACTOR_SHA: Final[str] = "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208"
_TRACE_SHA: Final[str] = "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"

# ---------------------------------------------------------------------------
# Helpers to canonically revalidate at boundaries
# ---------------------------------------------------------------------------


def _load_e2_package() -> E2ResearchEvidencePackage:
    pkg, receipt = load_admitted_builtin_e2_research()
    receipt.verify()
    view = build_e2_comparison_view(pkg)
    if view.e2b.off != 0.683619229:
        raise ValueError(f"E2b off drift: expected 0.683619229, got {view.e2b.off!r}")
    if view.e2c.mean != -0.021222260935:
        raise ValueError(f"E2c mean drift: expected -0.021222260935, got {view.e2c.mean!r}")
    if view.e2d.mean != 0.005271433656:
        raise ValueError(f"E2d mean drift: expected 0.005271433656, got {view.e2d.mean!r}")
    return E2ResearchEvidencePackage.model_validate(pkg.model_dump(mode="json"))


def _limitations_for(study: str, pkg: E2ResearchEvidencePackage) -> list[str]:
    # Preserve exact limitations verbatim; filter not needed, keep all
    # Each record carries full limitations to preserve truth
    return sorted(set(pkg.limitations))


def _non_claims_for(pkg: E2ResearchEvidencePackage) -> list[str]:
    return sorted(set(pkg.non_claims))


def _product_links_for(study: str) -> list[str]:
    # Product links are bounded, no absolute paths
    base = [
        "docs/closure/v08_alignment/improved_strategy_results.json",
        "docs/closure/v08_alignment/strategy_matrix.json",
    ]
    if study == "E2d":
        base.append("docs/evaluation/e2d/e2d_per_task_placement_report_2026-08-11.md")
    elif study == "E2c":
        base.append("docs/evaluation/e2c/e2c_gated_placement_multidraw_manifest_v1.json")
    else:
        base.append("docs/evaluation/e2b/e2b_placement_admission_factorial_manifest_v1.json")
    return sorted(base)


# ---------------------------------------------------------------------------
# Conversion to ResearchStudyRecord
# ---------------------------------------------------------------------------


def build_e2b_record(pkg: E2ResearchEvidencePackage) -> ResearchStudyRecord:
    """Convert E2b (one-draw descriptive) to ResearchStudyRecord."""
    # Canonically revalidate pkg at boundary
    pkg_v = E2ResearchEvidencePackage.model_validate(pkg.model_dump(mode="json"))
    # Extract E2b values via observations
    obs_by_arm: dict[str, float] = {}
    for obs in pkg_v.observations:
        if obs.evidence_id == "e2b_factorial_comparison":
            obs_by_arm[obs.arm] = float(obs.value)
    # Verify exact values
    expected_b = {
        "off": 0.683619229,
        "jsq": 0.675681775,
        "dla": 0.694939919,
        "ingress_dla": 0.715773211,
    }
    for arm, exp in expected_b.items():
        act = obs_by_arm.get(arm)
        if act is None or abs(act - exp) > 1e-12:
            raise ValueError(f"E2b arm {arm} value drift: expected {exp}, got {act}")
    arms = sorted(expected_b.keys())
    primary_metrics = ["offered_task_deadline_attainment"]
    # Per-draw values: single draw 0, four arms
    per_draw = [
        PerDrawValue(
            draw=0, value=expected_b[arm], arm=arm, metric="offered_task_deadline_attainment"
        )
        for arm in arms
    ]
    rec = ResearchStudyRecord(
        study=E2B_STUDY,
        version=E2_VERSION,
        title="E2b: offered-task deadline attainment — one Manchester incident hour (descriptive)",
        question="Does placement and deadline-aware admission change offered-task deadline attainment in one incident hour?",  # noqa: E501
        hypothesis="Deadline-aware admission improves offered attainment over cap-only in the incident hour",  # noqa: E501
        status=StudyStatus.COMPLETED,
        predecessor=None,
        successor=None,
        supersedes=None,
        code_sha=_E2B_HEAD,
        manifest_hash=_E2B_MANIFEST,
        evaluator_id="evaluator-0",
        actor_id=_ACTOR_SHA,
        checkpoint_id=_ACTOR_SHA,
        trace_id=_TRACE_SHA,
        replication_unit="fleet_draw",
        seeds=[0],
        draws=[0],
        arms=arms,
        estimand="offered_task_deadline_attainment per arm, one fleet_draw",
        primary_metrics=primary_metrics,
        secondary_metrics=None,
        per_draw_values=per_draw,
        declared_summary=None,
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        limitations=_limitations_for(E2B_STUDY, pkg_v),
        non_claims=_non_claims_for(pkg_v),
        product_links=_product_links_for(E2B_STUDY),
    )
    # Revalidate canonically
    return ResearchStudyRecord.model_validate(rec.model_dump(mode="json"))


def build_e2c_record(pkg: E2ResearchEvidencePackage) -> ResearchStudyRecord:
    """Convert E2c (common-target DLA minus ingress_dla, 4 draws) to record."""
    pkg_v = E2ResearchEvidencePackage.model_validate(pkg.model_dump(mode="json"))
    # Paired differences for e2c
    pd_map = {pd.comparison_id: pd for pd in pkg_v.paired_differences}
    e2c_pd = pd_map.get("e2c_dla_minus_ingress")
    if e2c_pd is None:
        raise ValueError("missing e2c_dla_minus_ingress")
    expected_per_seed = [-0.022097034972, -0.020519134179, -0.021447383092, -0.020825491499]
    if [float(x) for x in e2c_pd.per_seed_values] != expected_per_seed:
        raise ValueError("E2c per_seed drift")
    ds_map = {ds.comparison_id: ds for ds in pkg_v.declared_summaries}
    e2c_ds = ds_map.get("e2c_dla_minus_ingress")
    if e2c_ds is None:
        raise ValueError("missing e2c declared_summary")
    if abs(float(e2c_ds.mean) - (-0.021222260935)) > 1e-12:
        raise ValueError("E2c mean drift")
    per_draw = [
        PerDrawValue(draw=seed, value=val, metric="offered_attainment_dla_minus_ingress_dla")
        for seed, val in zip([1, 2, 3, 4], expected_per_seed, strict=True)
    ]
    rec = ResearchStudyRecord(
        study=E2C_STUDY,
        version=E2_VERSION,
        title="E2c: common-target DLA minus ingress DLA over four matched fleet draws",
        question="Does common-target least-busy placement under deadline gate change attainment vs strongest-link ingress?",  # noqa: E501
        hypothesis="Common-target DLA differs from ingress DLA within bounded four-draw replication",  # noqa: E501
        status=StudyStatus.COMPLETED,
        code_sha=_E2C_HEAD,
        manifest_hash=_E2C_MANIFEST,
        evaluator_id="evaluator-0",
        actor_id=_ACTOR_SHA,
        checkpoint_id=_ACTOR_SHA,
        trace_id=_TRACE_SHA,
        replication_unit="fleet_draw",
        seeds=[1, 2, 3, 4],
        draws=[1, 2, 3, 4],
        arms=None,
        estimand="dla_minus_ingress_dla offered_task_deadline_attainment (paired fleet_draw differences)",  # noqa: E501
        primary_metrics=["offered_attainment_dla_minus_ingress_dla"],
        secondary_metrics=None,
        per_draw_values=per_draw,
        declared_summary=DeclaredSummary(
            estimate=-0.021222260935,
            ci_lower=-0.02233525407,
            ci_upper=-0.0201092678,
            method="two-sided Student-t 95% interval over fleet-draw differences",
            metric="offered_attainment_dla_minus_ingress_dla",
        ),
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        limitations=_limitations_for(E2C_STUDY, pkg_v),
        non_claims=_non_claims_for(pkg_v),
        product_links=_product_links_for(E2C_STUDY),
    )
    return ResearchStudyRecord.model_validate(rec.model_dump(mode="json"))


def build_e2d_record(pkg: E2ResearchEvidencePackage) -> ResearchStudyRecord:
    """Convert E2d (per_task minus ingress, 4 draws, bounded construct-validity)."""
    pkg_v = E2ResearchEvidencePackage.model_validate(pkg.model_dump(mode="json"))
    pd_map = {pd.comparison_id: pd for pd in pkg_v.paired_differences}
    e2d_pd = pd_map.get("e2d_per_task_minus_ingress")
    if e2d_pd is None:
        raise ValueError("missing e2d per_task_minus_ingress")
    expected_per_seed = [0.004636732564, 0.005867285642, 0.005071796666, 0.005509919752]
    if [float(x) for x in e2d_pd.per_seed_values] != expected_per_seed:
        raise ValueError("E2d per_seed drift")
    # Secondary comparison per_task vs common-target
    e2d_vs = pd_map.get("e2d_per_task_minus_dla")
    if e2d_vs is None:
        raise ValueError("missing e2d_per_task_minus_dla")
    expected_vs = [0.026733767536, 0.026386419821, 0.026519179758, 0.026335411251]
    if [float(x) for x in e2d_vs.per_seed_values] != expected_vs:
        raise ValueError("E2d vs per_seed drift")
    ds_map = {ds.comparison_id: ds for ds in pkg_v.declared_summaries}
    e2d_ds = ds_map.get("e2d_per_task_minus_ingress")
    if e2d_ds is None:
        raise ValueError("missing e2d declared_summary")
    if abs(float(e2d_ds.mean) - 0.005271433656) > 1e-12:
        raise ValueError("E2d mean drift")
    e2d_vs_ds = ds_map.get("e2d_per_task_minus_dla")
    if e2d_vs_ds is None:
        raise ValueError("missing e2d_vs summary")
    per_draw = [
        PerDrawValue(draw=s, value=v, metric="offered_attainment_per_task_dla_minus_ingress_dla")
        for s, v in zip([1, 2, 3, 4], expected_per_seed, strict=True)
    ]
    per_draw_vs = [
        PerDrawValue(draw=s, value=v, metric="offered_attainment_per_task_minus_dla")
        for s, v in zip([1, 2, 3, 4], expected_vs, strict=True)
    ]
    # Preserve secondary per-draw values (8 entries: 4 primary + 4 secondary) with distinct authoritative metric identities including _dla qualifier.  # noqa: E501
    # Current single DeclaredSummary encodes only the primary interval (per_task_minus_ingress); secondary interval [0.02621, 0.02677] is not a second DeclaredSummary field in this model — limitation stated via per_draw values only.  # noqa: E501
    combined_per_draw = sorted(per_draw + per_draw_vs, key=lambda x: (x.draw, x.metric or ""))
    rec = ResearchStudyRecord(
        study=E2D_STUDY,
        version=E2_VERSION,
        title="E2d: per-task DLA minus ingress DLA — bounded construct-validity (4 fleet draws)",
        question="Does per-task sequential least-busy placement reverse the common-target direction under deadline gate?",  # noqa: E501
        hypothesis="Per-task placement shows bounded directional advantage within four draws, not universal superiority",  # noqa: E501
        status=StudyStatus.COMPLETED,
        code_sha=_E2D_HEAD,
        manifest_hash=_E2D_MANIFEST,
        evaluator_id="evaluator-0",
        actor_id=_ACTOR_SHA,
        checkpoint_id=_ACTOR_SHA,
        trace_id=_TRACE_SHA,
        replication_unit="fleet_draw",
        seeds=[1, 2, 3, 4],
        draws=[1, 2, 3, 4],
        arms=None,
        estimand="per_task_dla_minus_ingress_dla offered_task_deadline_attainment (paired fleet_draw differences); secondary per_task_minus_dla",  # noqa: E501
        primary_metrics=["offered_attainment_per_task_dla_minus_ingress_dla"],
        secondary_metrics=["offered_attainment_per_task_minus_dla"],
        per_draw_values=combined_per_draw,
        declared_summary=DeclaredSummary(
            estimate=0.005271433656,
            ci_lower=0.004422143925,
            ci_upper=0.006120723387,
            method="two-sided Student-t 95% interval over fleet-draw differences",
            metric="offered_attainment_per_task_dla_minus_ingress_dla",
        ),
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        limitations=_limitations_for(E2D_STUDY, pkg_v),
        non_claims=_non_claims_for(pkg_v),
        product_links=_product_links_for(E2D_STUDY),
    )
    return ResearchStudyRecord.model_validate(rec.model_dump(mode="json"))


def build_admitted_e2_records() -> list[ResearchStudyRecord]:
    """Load exact admitted E2 and convert to future-generic records."""
    pkg = _load_e2_package()
    recs = [
        build_e2b_record(pkg),
        build_e2c_record(pkg),
        build_e2d_record(pkg),
    ]
    # Ensure sorted canonical
    recs = sorted(recs, key=lambda r: (r.study, r.version))
    # Revalidate all
    return [ResearchStudyRecord.model_validate(r.model_dump(mode="json")) for r in recs]


def build_unavailable_index_records() -> list[ResearchStudyRecord]:
    """Truthful UNAVAILABLE index for E0/E1 where authoritative v0.8 closure supports existence.

    E0: conservative historical reference baseline referenced in strategy_matrix
         (strongest_link_off) but without exact current admitted package at v0.8
         Lane 07 closure. E1: prospective waiting-room semantic sweep motivated by
         the 2.5→0.75 fail-fast accounting artefact (S-035), described in
         docs/closure/v08_alignment/use_case_b_vec_dynamic_service.md §6. Both
         are UNAVAILABLE with resolved limitations and no SHA/manifest/result.
         Future E3 is absent and not included.
    """
    records: list[ResearchStudyRecord] = []
    records.append(
        ResearchStudyRecord(
            study="E0",
            version="1.0",
            title="E0: historical reference baseline (unavailable, not admitted)",
            question="Historical baseline for TrafficTwin VEC instrumentation referenced in v08 alignment — not an exact current admitted package",  # noqa: E501
            hypothesis=None,
            status=StudyStatus.UNAVAILABLE,
            code_sha=None,
            manifest_hash=None,
            evaluator_id=None,
            actor_id=None,
            checkpoint_id=None,
            trace_id=None,
            replication_unit=None,
            seeds=None,
            draws=None,
            arms=None,
            estimand=None,
            primary_metrics=None,
            secondary_metrics=None,
            per_draw_values=None,
            declared_summary=None,
            evidence_standing=EvidenceStanding.UNAVAILABLE,
            admission_status=AdmissionStatus.NOT_ADMITTED,
            limitations=[
                "No exact current admitted E0 package at v0.8 Lane 07 closure; historical reference in docs/closure/v08_alignment/strategy_matrix.json (strongest_link_off) only, not admitted evidence",  # noqa: E501
            ],
            non_claims=["No E0 outcome is claimed as current admitted research evidence"],
            product_links=None,
        )
    )
    records.append(
        ResearchStudyRecord(
            study="E1",
            version="1.0",
            title="E1: prospective waiting-room semantic sweep (planned, unavailable)",
            question="Does a waiting-room/admission semantic sweep that corrects the 2.5→0.75 fail-fast accounting artefact change deadline attainment and latency interpretation without implying compute-capacity change?",  # noqa: E501
            hypothesis=None,
            status=StudyStatus.PLANNED,
            code_sha=None,
            manifest_hash=None,
            evaluator_id=None,
            actor_id=None,
            checkpoint_id=None,
            trace_id=None,
            replication_unit=None,
            seeds=None,
            draws=None,
            arms=None,
            estimand=None,
            primary_metrics=None,
            secondary_metrics=None,
            per_draw_values=None,
            declared_summary=None,
            evidence_standing=EvidenceStanding.UNAVAILABLE,
            admission_status=AdmissionStatus.NOT_ADMITTED,
            limitations=[
                "E1 is a prospective waiting-room semantic sweep motivated by the 2.5→0.75 fail-fast accounting artefact (S-035); no admitted E1 package, SHA, manifest, or result exists at v0.8 closure; source docs/closure/v08_alignment/use_case_b_vec_dynamic_service.md §6",  # noqa: E501
            ],
            non_claims=[
                "No E1 estimate, interval, or causal claim is made; planned investigation only, not evidence"  # noqa: E501
            ],
            product_links=None,
        )
    )
    return [ResearchStudyRecord.model_validate(r.model_dump(mode="json")) for r in records]


def build_current_lineage_edges(
    records: list[ResearchStudyRecord],
) -> list[LineageEdge]:
    """Explicit supported current lineage only.

    Supported relationships directly backed by authoritative v0.8/E2 sources:
    - E2d is bounded construct-validity/robustness of E2c and E2b, not universal superiority.
    - E2c extends E2b's one-draw descriptive with matched four-draw inference.

    Do not infer unsupported E0/E1 links.
    """
    # Map for existence check
    present = {(r.study, r.version) for r in records}
    edges: list[LineageEdge] = []
    if (E2C_STUDY, E2_VERSION) in present and (E2B_STUDY, E2_VERSION) in present:
        edges.append(
            LineageEdge.build(
                source_study=E2B_STUDY,
                source_version=E2_VERSION,
                target_study=E2C_STUDY,
                target_version=E2_VERSION,
                relationship=RelationshipType.EXTENDS,
                declared_source="docs/closure/v08_alignment/strategy_matrix.json",
                provenance_identity=_E2C_HEAD,
                rationale="E2c extends E2b descriptive one-draw baseline with four matched fleet draws and Student-t interval over paired differences; bounded to same incident hour and actor.",  # noqa: E501
            )
        )
    if (E2D_STUDY, E2_VERSION) in present and (E2C_STUDY, E2_VERSION) in present:
        edges.append(
            LineageEdge.build(
                source_study=E2C_STUDY,
                source_version=E2_VERSION,
                target_study=E2D_STUDY,
                target_version=E2_VERSION,
                relationship=RelationshipType.CONSTRUCT_VALIDITY,
                declared_source="docs/closure/v08_alignment/improved_strategy_evidence_summary.md",
                provenance_identity=_E2D_HEAD,
                rationale="E2d is a bounded construct-validity and robustness check of granularity (per-task vs common-target) within same four draws; not universal superiority; reuses E2c controls.",  # noqa: E501
            )
        )
        edges.append(
            LineageEdge.build(
                source_study=E2B_STUDY,
                source_version=E2_VERSION,
                target_study=E2D_STUDY,
                target_version=E2_VERSION,
                relationship=RelationshipType.ROBUSTNESS_CHECK,
                declared_source="docs/e2_research_product.md",
                provenance_identity=_E2D_HEAD,
                rationale="E2d robustness check over E2b baseline, bounded to Manchester incident hour, fixed 1x service, zero backhaul, four draws only; not universal superiority.",  # noqa: E501
            )
        )
    return sorted(
        edges,
        key=lambda e: (
            e.source_study,
            e.source_version,
            e.target_study,
            e.target_version,
            e.relationship.value,
        ),
    )


def build_e2_study_package() -> ResearchStudyPackage:
    """Build future-generic package from current admitted E2 records + lineage."""
    records = build_admitted_e2_records()
    edges = build_current_lineage_edges(records)
    pkg = ResearchStudyPackage.build(records=records, lineage_edges=edges)
    return ResearchStudyPackage.model_validate(pkg.model_dump(mode="json"))


def build_default_e2_admission_policy(pkg: ResearchStudyPackage | None = None) -> AdmissionPolicy:
    """Exact allowlist for current admitted E2 package only. No wildcard, no E3."""
    if pkg is None:
        pkg = build_e2_study_package()
    # Canonically revalidate pkg
    pkg_v = ResearchStudyPackage.model_validate(pkg.model_dump(mode="json"))
    entries = [
        AdmissionPolicyEntry(
            study=r.study,
            version=r.version,
            code_sha=r.code_sha or "",
            manifest_hash=r.manifest_hash or "",
            package_fingerprint=pkg_v.package_fingerprint,
        )
        for r in pkg_v.records
        if r.code_sha and r.manifest_hash
    ]
    policy = AdmissionPolicy(entries=entries)
    return AdmissionPolicy.model_validate(policy.model_dump(mode="json"))
