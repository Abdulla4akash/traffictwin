from __future__ import annotations

import zipfile
from pathlib import Path

from tests.helpers import fixed_clock

from traffictwin.provenance.query import (
    build_provenance_context,
    get_metric_provenance,
    get_rule_provenance,
)


def test_bundle_to_metric_and_diagnostic_provenance() -> None:
    metric_context = build_provenance_context(
        "tests/fixtures/bundles/baseline_valid",
        clock=fixed_clock,
    )
    rule_context = build_provenance_context(
        "tests/fixtures/bundles/variation_valid",
        clock=fixed_clock,
    )

    metric_trace = get_metric_provenance(metric_context, "task.completion.rate", clock=fixed_clock)
    rule_trace = get_rule_provenance(rule_context, "R2", clock=fixed_clock)

    assert metric_trace.root_node_id == "metric_result:run-baseline-001:task.completion.rate"
    assert rule_trace.root_node_id == "rule_result:R2"
    assert any(node.node_id == "source_file:tasks.csv" for node in metric_trace.nodes)
    assert any(node.node_id.startswith("metric_result:") for node in rule_trace.nodes)


def test_directory_and_zip_metric_trace_are_equivalent(tmp_path: Path) -> None:
    source = Path("tests/fixtures/bundles/baseline_valid")
    zip_path = tmp_path / "baseline.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for path in source.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source).as_posix())

    directory_context = build_provenance_context(source, clock=fixed_clock)
    zip_context = build_provenance_context(zip_path, clock=fixed_clock)
    directory_trace = get_metric_provenance(
        directory_context,
        "task.completion.rate",
        clock=fixed_clock,
    )
    zip_trace = get_metric_provenance(zip_context, "task.completion.rate", clock=fixed_clock)

    assert directory_trace.source_fingerprint == zip_trace.source_fingerprint
    assert [node.node_id for node in directory_trace.nodes] == [
        node.node_id for node in zip_trace.nodes
    ]
    assert [edge.model_dump(mode="json") for edge in directory_trace.edges] == [
        edge.model_dump(mode="json") for edge in zip_trace.edges
    ]
