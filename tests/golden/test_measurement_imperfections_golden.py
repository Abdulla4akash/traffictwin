from __future__ import annotations

import json
from pathlib import Path

from traffictwin.domain.measurement import stable_measurement_fingerprint
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.synthetic.bundles import (
    synthetic_bundle_id,
    synthetic_run_id,
    write_synthetic_bundle,
)
from traffictwin.synthetic.config import load_synthetic_scenario_config
from traffictwin.synthetic.generator import generate_run_data

EXAMPLE = Path("examples/synthetic_measurement_imperfections.yaml")
EXPECTED = Path("tests/golden/expected/measurement_imperfections_known.json")


def test_known_measurement_imperfections_match_approved_audit(tmp_path: Path) -> None:
    config = load_synthetic_scenario_config(EXAMPLE)
    data = generate_run_data(config)
    audit = data.measurement_impairment_audit
    assert audit is not None
    bundle = write_synthetic_bundle(config, tmp_path / "measurement")
    validation = validate_bundle(bundle)
    assert validation.report.may_import
    projection = {
        "schema_version": audit.schema_version,
        "capability_id": "EXP-03",
        "model_version": audit.model_version,
        "bundle_id": synthetic_bundle_id(config),
        "run_id": synthetic_run_id(config),
        "configuration_fingerprint": audit.configuration_fingerprint,
        "audit_fingerprint": audit.audit_fingerprint,
        "field_audits": [item.model_dump(mode="json") for item in audit.field_audits],
        "dropout_audits": [item.model_dump(mode="json") for item in audit.dropout_audits],
        "row_counts": {kind: len(rows) for kind, rows in sorted(data.rows.items())},
        "observation_sample": {
            kind: rows[:2]
            for kind, rows in sorted(data.rows.items())
            if kind in {"infra_state", "vehicle_state", "traffic_obs"}
        },
        "outcome_tables_fingerprint": stable_measurement_fingerprint(
            {kind: data.rows.get(kind, []) for kind in ("tasks", "trips", "incidents")}
        ),
        "synthetic_evaluation": audit.synthetic_evaluation,
        "calibrated_sensor_model": audit.calibrated_sensor_model,
        "raw_source_mutated": audit.raw_source_mutated,
    }

    assert projection == json.loads(EXPECTED.read_text(encoding="utf-8"))
