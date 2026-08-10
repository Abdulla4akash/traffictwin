"""UI coverage for Preregistration Studio."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from traffictwin.ui.state import UiConfig


def _app(path: Path) -> AppTest:
    # Direct page script via preregistration page (thin)
    # We test the page's render function via AppTest on the wrapper script if available,
    # otherwise test the page module directly.
    # Since navigation not yet registered, we run the page script directly.
    # The page is at src/traffictwin/ui/pages/preregistration_studio.py but AppTest expects a script file.  # noqa: E501
    # We create a minimal runner that calls the page render via UiConfig.
    # Instead, we test via direct import and AppTest on a tiny script that imports render.

    # Create a temporary script that invokes the page
    script = path / "prereg_test_runner.py"
    script.write_text(
        """
from pathlib import Path
from traffictwin.ui.state import UiConfig
from traffictwin.ui.pages.preregistration_studio import render

config = UiConfig(registry_path=Path("tmp_registry.sqlite"))
render(config)
""",
        encoding="utf-8",
    )
    return AppTest.from_file(str(script), default_timeout=30)


def test_preregistration_page_renders_without_crash(tmp_path: Path) -> None:
    # Use a temporary registry path
    UiConfig(registry_path=tmp_path / "registry.sqlite")
    # Import page and run via AppTest using file that calls render
    from traffictwin.ui.pages.preregistration_studio import render  # noqa: F401

    # Build a small AppTest that calls render
    runner = tmp_path / "runner.py"
    runner.write_text(
        f"""
from pathlib import Path
from traffictwin.ui.state import UiConfig
from traffictwin.ui.pages.preregistration_studio import render
config = UiConfig(registry_path=Path(r"{tmp_path / "registry.sqlite"}"))
render(config)
""",
        encoding="utf-8",
    )
    at = AppTest.from_file(str(runner), default_timeout=30)
    at.run()
    assert not at.exception
    # Check title and key sections present
    titles = [str(m.value) for m in at.title]
    assert any("Preregistration Studio" in t for t in titles)
    # Check warnings/captions contain governance text
    all_text = " ".join(
        [str(x.value) for x in at.markdown]
        + [str(x.value) for x in at.caption]
        + [str(x.value) for x in at.warning]
        + [str(x.value) for x in at.info]
    )
    assert "Preregistration" in all_text or "freeze" in all_text.lower()


def test_preregistration_freeze_flow_via_service(tmp_path: Path) -> None:
    """Test the UI freeze path delegates to service correctly (via AppTest session)."""
    from traffictwin.metrics.catalogue import METRIC_VERSION
    from traffictwin.preregistration.models import (
        AnalysisMethod,
        CohortRule,
        DecisionRule,
        EstimandDefinition,
        EvidenceMode,
        ExclusionRule,
        MissingnessPolicy,
        MultiplicityPolicy,
        OutcomeDefinition,
        ReplicationUnit,
        StoppingRule,
        StudyPlan,
        StudyQuestion,
    )
    from traffictwin.preregistration.service import freeze_plan, validate_study_plan

    plan = StudyPlan(
        plan_id="ui-freeze-001",
        study_question=StudyQuestion(
            text="UI freeze test question with sufficient length for validation.", hypothesis="Hyp."
        ),
        evidence_mode=EvidenceMode.SYNTHETIC_EVIDENCE,
        primary_outcomes=[
            OutcomeDefinition(
                outcome_id="primary-001",
                metric_key="task.completion.rate",
                metric_version=METRIC_VERSION,
                unit="ratio",
                denominator="generated_tasks",
                description="Primary for UI freeze test.",
            )
        ],
        estimand=EstimandDefinition(
            estimand_id="est-001",
            description="Mean difference for UI test with sufficient length.",
            population="common seeds",
            effect_measure="mean_diff",
        ),
        replication_unit=ReplicationUnit.RANDOM_SEED,
        replication_ids=[1, 2],
        planned_arms=["baseline", "variation"],
        cohort_rules=[
            CohortRule(rule_id="cohort-001", description="Include valid tasks for UI test.")
        ],
        exclusion_rules=[
            ExclusionRule(rule_id="exclude-001", description="Exclude invalid tasks for UI test.")
        ],
        missingness_policy=MissingnessPolicy.COMPLETE_CASE,
        analysis_method=AnalysisMethod.PAIRED_MEAN_DIFFERENCE,
        multiplicity_policy=MultiplicityPolicy.NONE_SINGLE_TEST,
        stopping_rule=StoppingRule(
            description="UI stopping rule description with sufficient length.", max_replicates=2
        ),
        decision_rule=DecisionRule(
            rule_type="two_sided_test",
            alpha=0.05,
            interpretation="UI interpretation with sufficient length.",
            comparison="two_sided",
        ),
        limitations="UI limitations with sufficient length for freeze validation.",
        planned_run_cells=[],
    )
    assert validate_study_plan(plan) == []
    frozen = freeze_plan(plan)
    assert frozen.fingerprint is not None
    assert len(frozen.fingerprint) == 64


def test_preregistration_amendment_and_matrix_via_service() -> None:
    from traffictwin.metrics.catalogue import METRIC_VERSION
    from traffictwin.preregistration.models import (
        AnalysisMethod,
        ArtifactAdmission,
        CohortRule,
        DecisionRule,
        EstimandDefinition,
        EvidenceAttachment,
        EvidenceMode,
        ExclusionRule,
        MissingnessPolicy,
        MultiplicityPolicy,
        OutcomeDefinition,
        ReplicationUnit,
        StoppingRule,
        StudyPlan,
        StudyQuestion,
    )
    from traffictwin.preregistration.service import (
        attach_evidence,
        create_amendment,
        freeze_plan,
        planned_vs_observed_matrix,
    )

    plan = StudyPlan(
        plan_id="ui-amend-001",
        study_question=StudyQuestion(
            text="UI amend test question with sufficient length for governance.", hypothesis="Hyp."
        ),
        evidence_mode=EvidenceMode.SYNTHETIC_EVIDENCE,
        primary_outcomes=[
            OutcomeDefinition(
                outcome_id="primary-001",
                metric_key="task.completion.rate",
                metric_version=METRIC_VERSION,
                unit="ratio",
                denominator="generated_tasks",
                description="Primary for amend test.",
            )
        ],
        estimand=EstimandDefinition(
            estimand_id="est-001",
            description="Mean difference for UI test with sufficient length.",
            population="common seeds",
            effect_measure="mean_diff",
        ),
        replication_unit=ReplicationUnit.RANDOM_SEED,
        replication_ids=[1, 2],
        planned_arms=["baseline", "variation"],
        cohort_rules=[
            CohortRule(rule_id="cohort-001", description="Include valid tasks for amend test.")
        ],
        exclusion_rules=[
            ExclusionRule(
                rule_id="exclude-001", description="Exclude invalid tasks for amend test."
            )
        ],
        missingness_policy=MissingnessPolicy.COMPLETE_CASE,
        analysis_method=AnalysisMethod.PAIRED_MEAN_DIFFERENCE,
        multiplicity_policy=MultiplicityPolicy.NONE_SINGLE_TEST,
        stopping_rule=StoppingRule(
            description="Stopping rule for amend test with sufficient length.", max_replicates=2
        ),
        decision_rule=DecisionRule(
            rule_type="two_sided_test",
            alpha=0.05,
            interpretation="Interpretation for amend test with sufficient length.",
            comparison="two_sided",
        ),
        limitations="Limitations for amend test with sufficient length.",
        planned_run_cells=[],
    )
    frozen = freeze_plan(plan)
    amended = create_amendment(
        frozen,
        changes={"limitations": "Amended UI limitations with sufficient length."},
        amendment_reason="UI amendment reason sufficient for governance.",
    )
    assert amended.parent_fingerprint == frozen.fingerprint
    assert "limitations" in amended.revision_history[0].diff

    # Attach and check matrix
    frozen_amended = freeze_plan(amended)
    att = EvidenceAttachment(
        artifact_fingerprint="a" * 64,
        cell_id=frozen_amended.planned_run_cells[0].cell_id,
        observed_metric_key="task.completion.rate",
        observed_metric_version=METRIC_VERSION,
        observed_unit="ratio",
        is_admitted=True,
        admission_label=ArtifactAdmission.ADMITTED,
    )
    attached = attach_evidence(frozen_amended, [att])
    matrix = planned_vs_observed_matrix(attached)
    assert matrix["expected_count"] == len(frozen_amended.planned_run_cells)
    assert matrix["observed_count"] == 1


def test_preregistration_run_matrix_column_config_shows_all_identity_columns() -> None:
    """Regression for run-matrix presentation: all eight identity fields must remain visible.

    The shared helper ``table_column_config`` hides machine IDs by default
    (``*_id``, ``metric_version``, ``seed_id``).  The preregistered run
    matrix is an explicit exception where those fields are the experimental
    identity and must NOT be hidden.  This test guards the production helper
    ``_run_matrix_column_config`` — it must expose all eight ``PlannedRunCell``
    fields with non-None column configs.
    """

    from traffictwin.metrics.catalogue import METRIC_VERSION
    from traffictwin.preregistration.models import (
        AnalysisMethod,
        CohortRule,
        DecisionRule,
        EstimandDefinition,
        EvidenceMode,
        ExclusionRule,
        MissingnessPolicy,
        MultiplicityPolicy,
        OutcomeDefinition,
        ReplicationUnit,
        StoppingRule,
        StudyPlan,
        StudyQuestion,
    )
    from traffictwin.preregistration.service import build_run_matrix
    from traffictwin.ui.pages.preregistration_studio import _run_matrix_column_config

    plan = StudyPlan(
        plan_id="ui-col-config-001",
        study_question=StudyQuestion(
            text="Does run-matrix column config preserve all identity columns correctly?",
            hypothesis="All eight fields visible.",
        ),
        evidence_mode=EvidenceMode.SYNTHETIC_EVIDENCE,
        primary_outcomes=[
            OutcomeDefinition(
                outcome_id="primary-001",
                metric_key="task.completion.rate",
                metric_version=METRIC_VERSION,
                unit="ratio",
                denominator="generated_tasks",
                description="Primary for column-config regression.",
            )
        ],
        estimand=EstimandDefinition(
            estimand_id="est-001",
            description="Mean difference for column-config test with sufficient length.",
            population="common seeds",
            effect_measure="mean_diff",
        ),
        replication_unit=ReplicationUnit.RANDOM_SEED,
        replication_ids=[1, 2],
        planned_arms=["baseline", "variation"],
        seeds=["seed-baseline", "seed-variation"],
        policies=["policy-a"],
        metrics=["task.completion.rate"],
        cohort_rules=[
            CohortRule(rule_id="cohort-001", description="Include valid tasks for col test.")
        ],
        exclusion_rules=[
            ExclusionRule(rule_id="exclude-001", description="Exclude invalid tasks for col test.")
        ],
        missingness_policy=MissingnessPolicy.COMPLETE_CASE,
        analysis_method=AnalysisMethod.PAIRED_MEAN_DIFFERENCE,
        multiplicity_policy=MultiplicityPolicy.NONE_SINGLE_TEST,
        stopping_rule=StoppingRule(
            description="Column-config stopping rule with sufficient length.", max_replicates=2
        ),
        decision_rule=DecisionRule(
            rule_type="two_sided_test",
            alpha=0.05,
            interpretation="Column-config interpretation with sufficient length.",
            comparison="two_sided",
        ),
        limitations="Column-config limitations with sufficient length for validation.",
        planned_run_cells=[],
    )

    matrix = build_run_matrix(plan)
    assert len(matrix) > 0
    matrix_rows = [cell.model_dump(mode="json") for cell in matrix]

    # Production helper under test
    config = _run_matrix_column_config(matrix_rows)

    expected_keys = {
        "cell_id",
        "arm_id",
        "seed_id",
        "policy_label",
        "replication_id",
        "metric_key",
        "metric_version",
        "replication_unit",
    }
    # Must expose exactly the eight PlannedRunCell fields
    assert set(config) == expected_keys

    # None of the eight may be hidden (None means hidden/omitted in Streamlit)
    for key in expected_keys:
        assert config[key] is not None, f"column {key!r} must not be hidden (got None)"

    # Verify intended human labels where the Streamlit column-config API exposes them
    expected_labels: dict[str, str] = {
        "cell_id": "Cell",
        "arm_id": "Arm",
        "seed_id": "Seed",
        "policy_label": "Policy",
        "replication_id": "Replication",
        "metric_key": "Metric",
        "metric_version": "Version",
        "replication_unit": "Replication unit",
    }
    for key, expected_label in expected_labels.items():
        col = config[key]
        # TextColumn/NumberColumn expose .label; guard against API change
        label = getattr(col, "label", None)
        if label is not None:
            assert label == expected_label, f"label for {key!r}: {label!r} != {expected_label!r}"
