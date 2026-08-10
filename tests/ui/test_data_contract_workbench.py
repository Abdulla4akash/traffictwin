"""UI tests for Data Contract Workbench."""

from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from pathlib import Path

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.state import default_session_state, load_ui_config


def test_data_contract_workbench_page_renders() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]  # noqa: N806
    app = app_test.from_file(
        f"src/traffictwin/ui/{page_script_for(UiPage.DATA_CONTRACT_WORKBENCH)}"
    )  # noqa: E501
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    app.run(timeout=20)

    assert not app.exception
    # Check title or header contains workbench
    assert (
        any("Data Contract Workbench" in str(title.value) for title in app.title)
        or any("Data Contract Workbench" in str(header.value) for header in app.header)
        or any("Data Contract Workbench" in str(sub.value) for sub in app.subheader)
    )
    # Check inspect button exists
    assert any(button.label == "Inspect sample" for button in app.button)
    # Check warning about not importing
    assert any("does not import data" in warning.value for warning in app.warning) or any(
        "does not import" in str(warning.value).lower() for warning in app.warning
    )


def test_data_contract_workbench_candidate_vs_frozen_state() -> None:
    """Seed frozen version and observation, then verify drift summary renders."""
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]  # noqa: N806
    import csv
    import tempfile

    from traffictwin.data_contract.drift import compare_observation_to_contract
    from traffictwin.data_contract.inspection import inspect_tabular_sample
    from traffictwin.data_contract.models import (
        FieldContract,
        LogicalType,
        PublicationClass,
        RightsAndRetentionContract,
        SourceDataContract,
    )
    from traffictwin.data_contract.service import create_frozen_version

    tmp = Path(tempfile.mkdtemp())
    p = tmp / "sample.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["a", "b"])
        w.writerow(["1", "2"])
    obs = inspect_tabular_sample(
        p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    contract = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[
            FieldContract(field_name="a", required=True, logical_type=LogicalType.STRING),
            FieldContract(field_name="b", required=True, logical_type=LogicalType.STRING),
        ],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    frozen = create_frozen_version(contract)
    # Candidate missing required field
    p2 = tmp / "cand.csv"
    with p2.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["a"])
        w.writerow(["1"])
    obs2 = inspect_tabular_sample(
        p2, max_rows=10, max_bytes=1_000_000, observation_id="obs_002", source_label="local"
    )
    report = compare_observation_to_contract(frozen, obs2)

    app = app_test.from_file(
        f"src/traffictwin/ui/{page_script_for(UiPage.DATA_CONTRACT_WORKBENCH)}"
    )  # noqa: E501
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    app.session_state["dcw_observation"] = obs.model_dump(mode="json")
    app.session_state["dcw_frozen_version"] = frozen.model_dump(mode="json")
    app.session_state["dcw_drift_report"] = report.model_dump(mode="json")
    app.session_state["dcw_candidate_observation"] = obs2.model_dump(mode="json")
    app.run(timeout=20)

    assert not app.exception
    # Should show blocked severity via metrics or warnings/errors
    assert (
        any("blocked" in str(metric.label).lower() for metric in app.metric)
        or any("BLOCKED" in str(w.value) for w in app.warning)
        or any("BLOCKED" in str(e.value) for e in app.error)
        or any("BLOCKED" in str(w.value) for w in app.warning)
    )


def test_data_contract_workbench_blocked_review_compatible_summaries() -> None:
    """Check that severity summaries are displayed."""
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]  # noqa: N806

    from traffictwin.data_contract.models import (
        SchemaDriftFinding,
        SchemaDriftReport,
        SchemaDriftSeverity,
    )

    report = SchemaDriftReport(
        contract_fingerprint="a" * 64,
        candidate_fingerprint="b" * 64,
        contract_version="1.0.0",
        source_id="src1",
        overall_severity=SchemaDriftSeverity.REVIEW_REQUIRED,
        findings=[
            SchemaDriftFinding(
                field_name="a",
                severity=SchemaDriftSeverity.BLOCKED,
                code="REQUIRED_FIELD_REMOVED",
                message="blocked",
            ),
            SchemaDriftFinding(
                field_name="b",
                severity=SchemaDriftSeverity.REVIEW_REQUIRED,
                code="OPTIONAL_FIELD_ADDED",
                message="review",
            ),
            SchemaDriftFinding(
                field_name="c",
                severity=SchemaDriftSeverity.COMPATIBLE,
                code="TYPE_COMPATIBLE",
                message="compatible",
            ),
        ],
        summary={"blocked": 1, "review_required": 1, "compatible": 1, "total": 3},
        fingerprint="c" * 64,
    )
    app = app_test.from_file(
        f"src/traffictwin/ui/{page_script_for(UiPage.DATA_CONTRACT_WORKBENCH)}"
    )  # noqa: E501
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    app.session_state["dcw_drift_report"] = report.model_dump(mode="json")
    # Need a frozen version to show drift section? The drift section renders if drift exists regardless of frozen  # noqa: E501
    # But our UI checks drift not None, so it will render summary
    from traffictwin.data_contract.models import (
        FieldContract,
        LogicalType,
        PublicationClass,
        RightsAndRetentionContract,
        SourceDataContract,
    )
    from traffictwin.data_contract.service import create_frozen_version

    contract = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[FieldContract(field_name="a", required=True, logical_type=LogicalType.STRING)],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    frozen = create_frozen_version(contract)
    app.session_state["dcw_frozen_version"] = frozen.model_dump(mode="json")
    app.run(timeout=20)

    assert not app.exception
    # Metrics for blocked/review/compatible should be present
    labels = [m.label for m in app.metric]
    assert any("Blocked" in label for label in labels)
    assert any("Review" in label for label in labels)
    assert any("Compatible" in label for label in labels)
