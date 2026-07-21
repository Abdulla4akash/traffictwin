from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.experiments.scenario_mutation import (
    MutationTableKind,
    RowDropoutMutation,
    ScenarioMutationRequest,
    execute_scenario_mutation,
)


def test_scenario_mutation_matches_approved_change_ledger(tmp_path: Path) -> None:
    request = ScenarioMutationRequest(
        mutation_id="mutation-golden",
        title="Golden task dropout",
        mutation=RowDropoutMutation(
            table_kind=MutationTableKind.TASKS,
            drop_fraction=0.34,
            random_seed=17,
        ),
    )
    result = execute_scenario_mutation(
        "tests/fixtures/bundles/baseline_valid",
        request,
        tmp_path / "mutation",
        clock=lambda: datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
    )
    projection = {
        "schema_version": result.schema_version,
        "capability_id": "EXP-02",
        "method_version": result.method_version,
        "mutation_id": result.mutation_id,
        "operator": result.mutation.operator.value,
        "request_fingerprint": result.request_fingerprint,
        "plan_fingerprint": result.plan_fingerprint,
        "mutation_fingerprint": result.mutation_fingerprint,
        "parent_bundle_fingerprint": result.parent_bundle_fingerprint,
        "derived_bundle_fingerprint": result.derived_bundle_fingerprint,
        "parent_ids": {
            "bundle": result.parent_bundle_id,
            "run": result.parent_run_id,
            "seed": result.parent_seed_id,
        },
        "derived_ids": {
            "bundle": result.derived_bundle_id,
            "run": result.derived_run_id,
            "seed": result.derived_seed_id,
        },
        "changed_row_count": result.changed_row_count,
        "row_changes": [item.model_dump(mode="json") for item in result.row_changes],
        "file_changes": [item.model_dump(mode="json") for item in result.file_changes],
        "validation_status": result.validation_status,
        "validation_may_import": result.validation_may_import,
        "synthetic_evaluation": result.synthetic_evaluation,
        "raw_source_mutated": result.raw_source_mutated,
        "direct_launch_supported": result.direct_launch_supported,
    }

    expected = Path("tests/golden/expected/scenario_mutation_task_dropout.json")
    assert projection == json.loads(expected.read_text(encoding="utf-8"))
