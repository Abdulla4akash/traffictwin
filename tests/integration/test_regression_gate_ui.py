from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest
from tests.statistical_helpers import study_collection

from traffictwin.experiments.regression_gate import (
    GoldenApprovalStatus,
    RegressionGateReport,
    RegressionGateStatus,
    RegressionToleranceSpec,
    build_regression_golden_contract,
)
from traffictwin.storage.registry import Registry
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for


def test_streamlit_statistical_page_runs_metric_regression_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = tmp_path / "registry.sqlite"
    collection = study_collection("baseline", 1, 0.8)
    Registry(registry_path).store_metric_collection(
        run_id=collection.run_id,
        metric_version=collection.metric_version,
        source_fingerprint=collection.input_fingerprint,
        payload_json=collection.model_dump_json(),
    )
    golden = build_regression_golden_contract(
        collection,
        contract_id="streamlit-regression",
        contract_version="1.0.0",
        description="Approved synthetic Streamlit regression boundary",
        tolerances=[
            RegressionToleranceSpec(
                selector="task.completion.rate",
                absolute_tolerance=0.01,
                relative_tolerance=0.0,
            )
        ],
        approval_status=GoldenApprovalStatus.APPROVED,
        approved_by="ui-test-owner",
        approval_note="Approved only for deterministic Streamlit verification",
    )
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(registry_path))

    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    # v0.7 grouped navigation is the default: route to the direct Statistical Study page rather
    # than the removed legacy sidebar radio.
    app.switch_page(page_script_for(UiPage.STATISTICAL_STUDY)).run(timeout=10)
    next(radio for radio in app.radio if radio.label == "Study type").set_value(
        "Versioned regression gate (STA-04)"
    ).run(timeout=10)
    app.file_uploader[0].upload(
        "approved-regression-golden.json",
        golden.to_json().encode("utf-8"),
        "application/json",
    ).run(timeout=10)
    next(button for button in app.button if button.label == "Evaluate regression gate").click().run(
        timeout=10
    )

    result = app.session_state["regression_gate"]
    assert not app.exception
    assert isinstance(result, RegressionGateReport)
    assert result.status is RegressionGateStatus.PASSED
    assert any(
        heading.value == "Versioned regression gate and assertion audit"
        for heading in app.subheader
    )
    assert {button.label for button in app.download_button} >= {
        "Download RegressionGate JSON",
        "Download RegressionGate Markdown",
        "Download RegressionGate CSV",
    }
