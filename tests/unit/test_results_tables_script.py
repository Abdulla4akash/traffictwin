"""Results-table generation: structure, verbatim values, labels, and determinism.

Every fixture is a synthetic analysis built in memory and written under
``tmp_path``. Nothing here reads a committed campaign directory or the generated
tables in `docs/`, so the tests cannot pass merely because a real artifact
happens to be present.

The assertions that matter are the ones about honesty: values reach the table at
full precision, the exploratory/confirmatory label is read from the artifact
rather than inferred, an undeclared seed cohort says so, and regeneration on
unchanged input rewrites identical bytes.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

from traffictwin.experiments.statistical_study import (
    PairedStudyConfig,
    evaluate_paired_statistical_study,
)
from traffictwin.integration.vec_campaign.analysis import (
    VecArmDescriptives,
    VecCampaignAnalysis,
    VecCampaignComparison,
)
from traffictwin.metrics.results import MetricCollection, MetricStatus, MetricValue

NOW = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)
METRIC_KEY = "tos.task.deadline_success.rate"
SECONDARY_KEY = "task.latency.mean_ms"
ALGORITHM = "ukfleettrain_mappo_model_c_17"
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "generate_results_tables.py"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_results_tables_under_test", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CLI = _module()

#: Deliberately awkward values: a long-tailed float that a 6-significant-figure
#: formatter would silently shorten, and an exact zero.
BASELINE_VALUES = {0: 0.7924845945705774, 1: 0.8127939588722564, 2: 0.7659568496556425}
VARIATION_VALUES = {0: 0.792816188514216, 1: 0.8127939588722564, 2: 0.7659568496556425}


def _collection(arm: str, seed: int, value: float) -> MetricCollection:
    run_id = f"vec:fresh:{arm}-{seed}"
    return MetricCollection(
        run_id=run_id,
        metric_version="test-1.0",
        results=[
            MetricValue(
                metric_key=METRIC_KEY,
                status=MetricStatus.AVAILABLE,
                value=value,
                unit="ratio",
                scope="run",
                implementation_version="test-1.0",
                run_id=run_id,
                experiment_id="tables-unit",
                seed_id=arm,
                algorithm=ALGORITHM,
                checkpoint=f"checkpoints/{ALGORITHM}.npz",
                random_seed=seed,
                synthetic=False,
                environment="randy-vec",
                environment_version="v2",
                environment_commit="0" * 40,
                computed_at=NOW,
            )
        ],
        unavailable_count=0,
        partial_count=0,
        generated_at=NOW,
        input_fingerprint="f" * 64,
    )


def _analysis(*, secondary: bool = True) -> VecCampaignAnalysis:
    collections = [
        *(_collection("cap-2.5", seed, value) for seed, value in BASELINE_VALUES.items()),
        *(_collection("cap-0.75", seed, value) for seed, value in VARIATION_VALUES.items()),
    ]
    study = evaluate_paired_statistical_study(
        collections,
        PairedStudyConfig(
            experiment_id="tables-unit",
            baseline_seed_id="cap-2.5",
            variation_seed_id="cap-0.75",
            algorithm=ALGORITHM,
            checkpoint=f"checkpoints/{ALGORITHM}.npz",
            metric_key=METRIC_KEY,
            bootstrap_repetitions=1_000,
            randomisation_repetitions=1_000,
            expected_random_seeds=[0, 1, 2],
        ),
    )
    primary = [
        VecArmDescriptives(
            arm_label=arm,
            metric_key=METRIC_KEY,
            seed_values={str(seed): value for seed, value in values.items()},
            mean=sum(values.values()) / len(values),
            minimum=min(values.values()),
            maximum=max(values.values()),
        )
        for arm, values in (("cap-2.5", BASELINE_VALUES), ("cap-0.75", VARIATION_VALUES))
    ]
    secondary_rows = (
        [
            VecArmDescriptives(
                arm_label=arm,
                metric_key=SECONDARY_KEY,
                seed_values={"0": 9942.563797951792, "1": 6277.913026456375, "2": 0.0},
                mean=5406.825608136056,
                minimum=0.0,
                maximum=9942.563797951792,
            )
            for arm in ("cap-2.5", "cap-0.75")
        ]
        if secondary
        else []
    )
    return VecCampaignAnalysis(
        experiment_id="vec-tables-unit",
        design_fingerprint="a" * 64,
        campaign_status="completed",
        primary_metric_key=METRIC_KEY,
        baseline_label="cap-2.5",
        admitted_collection_count=len(collections),
        comparisons=[
            VecCampaignComparison(
                variation_label="cap-0.75",
                study_status=study.status.value,
                admitted_pair_count=study.pairing_audit.eligible_pair_count,
                mean_paired_difference=study.estimate.mean_paired_difference,
                bootstrap_lower=study.bootstrap_interval.lower,
                bootstrap_upper=study.bootstrap_interval.upper,
                randomisation_p_value=study.randomisation_test.p_value,
                study=study,
            )
        ],
        primary_descriptives=primary,
        secondary_descriptives=secondary_rows,
        generated_at_utc=NOW.isoformat(),
        limitations=["synthetic results-table fixture"],
    )


def _write_analysis(root: Path, analysis: VecCampaignAnalysis, *, phase: str | None) -> Path:
    campaign = root / "campaign"
    campaign.mkdir(parents=True, exist_ok=True)
    path = campaign / "campaign_analysis.json"
    path.write_text(analysis.model_dump_json(), encoding="utf-8")
    if phase is not None:
        (campaign / "campaign_receipt.json").write_text(
            json.dumps({"phase": phase}), encoding="utf-8"
        )
    return path


def _generate(root: Path, *, phase: str | None = "pilot", secondary: bool = True) -> list[Path]:
    source = _write_analysis(root, _analysis(secondary=secondary), phase=phase)
    return cast("list[Path]", CLI.generate(source, root / "tables"))


# --------------------------------------------------------------------------- #
# Structure
# --------------------------------------------------------------------------- #


def test_generates_both_tables_a_figure_and_a_provenance_note(tmp_path: Path) -> None:
    written = _generate(tmp_path)

    names = sorted(path.name for path in written)
    assert names == [
        "vec_tables_unit_arm_descriptives.tex",
        "vec_tables_unit_predeclared_comparisons.svg",
        "vec_tables_unit_predeclared_comparisons.tex",
        "vec_tables_unit_provenance.md",
    ]
    assert all(path.is_file() for path in written)


def test_descriptives_table_carries_every_arm_and_metric_with_its_role(tmp_path: Path) -> None:
    written = _generate(tmp_path)
    table = written[0].read_text(encoding="utf-8")

    assert r"Arm & Metric & Role & Seeds & Mean & Minimum & Maximum & Per-seed values \\" in table
    assert table.count(" & primary & ") == 2
    assert table.count(" & secondary & ") == 2
    assert "cap-2.5" in table
    assert "cap-0.75" in table


def test_comparisons_table_carries_the_three_predeclared_statistics(tmp_path: Path) -> None:
    written = _generate(tmp_path)
    table = written[1].read_text(encoding="utf-8")

    assert "Mean paired difference" in table
    assert "Bootstrap interval" in table
    assert "Randomisation p" in table
    assert "cap-0.75 vs cap-2.5" in table
    assert "@ 0.95" in table


def test_descriptives_table_ships_without_a_figure(tmp_path: Path) -> None:
    _generate(tmp_path)

    assert not (tmp_path / "tables" / "vec_tables_unit_arm_descriptives.svg").exists()
    assert (tmp_path / "tables" / "vec_tables_unit_predeclared_comparisons.svg").is_file()


# --------------------------------------------------------------------------- #
# Values reach the table verbatim
# --------------------------------------------------------------------------- #


def test_values_are_copied_at_full_precision_not_rounded(tmp_path: Path) -> None:
    analysis = _analysis()
    source = _write_analysis(tmp_path, analysis, phase="pilot")
    CLI.generate(source, tmp_path / "tables")

    descriptives = (tmp_path / "tables" / "vec_tables_unit_arm_descriptives.tex").read_text(
        encoding="utf-8"
    )
    comparisons = (tmp_path / "tables" / "vec_tables_unit_predeclared_comparisons.tex").read_text(
        encoding="utf-8"
    )
    comparison = analysis.comparisons[0]

    assert repr(BASELINE_VALUES[0]) in descriptives
    assert repr(analysis.primary_descriptives[0].mean) in descriptives
    assert comparison.mean_paired_difference is not None
    assert repr(comparison.mean_paired_difference) in comparisons
    assert repr(comparison.randomisation_p_value) in comparisons


def test_a_six_significant_figure_rounding_would_have_been_visible(tmp_path: Path) -> None:
    """Guard the precision choice itself, not just today's happen-to-fit values."""

    value = BASELINE_VALUES[0]
    assert f"{value:.6g}" != repr(value)
    descriptives = _generate(tmp_path)[0].read_text(encoding="utf-8")
    assert f"{value:.6g} " not in descriptives


def test_missing_statistics_render_as_unavailable_not_zero(tmp_path: Path) -> None:
    analysis = _analysis()
    stripped = analysis.model_copy(
        update={
            "comparisons": [
                analysis.comparisons[0].model_copy(
                    update={
                        "mean_paired_difference": None,
                        "bootstrap_lower": None,
                        "bootstrap_upper": None,
                        "randomisation_p_value": None,
                    }
                )
            ]
        }
    )
    source = _write_analysis(tmp_path, stripped, phase="pilot")
    CLI.generate(source, tmp_path / "tables")

    table = (tmp_path / "tables" / "vec_tables_unit_predeclared_comparisons.tex").read_text(
        encoding="utf-8"
    )
    assert table.count("unavailable") >= 3
    assert "& 0.0 &" not in table


# --------------------------------------------------------------------------- #
# Labels are read, never inferred
# --------------------------------------------------------------------------- #


def test_status_label_comes_from_the_analysis_payload(tmp_path: Path) -> None:
    written = _generate(tmp_path)
    descriptives = written[0].read_text(encoding="utf-8")

    assert "exploratory" in descriptives
    assert "owner\\_approved\\_candidate" in descriptives
    assert "confirmatory;" not in descriptives


def test_seed_cohort_comes_from_the_sibling_receipt(tmp_path: Path) -> None:
    written = _generate(tmp_path, phase="held_out")

    assert "cohort held\\_out" in written[0].read_text(encoding="utf-8")
    assert "seed cohort (from the sibling campaign receipt): held_out" in (
        written[3].read_text(encoding="utf-8").lower()
    )


def test_absent_receipt_reports_the_cohort_as_undeclared_rather_than_guessing(
    tmp_path: Path,
) -> None:
    written = _generate(tmp_path, phase=None)

    assert "cohort undeclared" in written[0].read_text(encoding="utf-8")
    assert "vec-tables-unit" in written[0].read_text(encoding="utf-8")


def test_provenance_records_the_source_digest_and_published_checksums(tmp_path: Path) -> None:
    analysis = _analysis()
    source = _write_analysis(tmp_path, analysis, phase="pilot")
    written = CLI.generate(source, tmp_path / "tables")
    provenance = written[3].read_text(encoding="utf-8")

    assert hashlib.sha256(source.read_bytes()).hexdigest() in provenance
    assert analysis.design_fingerprint in provenance
    for table in written[:3]:
        assert hashlib.sha256(table.read_bytes()).hexdigest() in provenance
        assert table.name in provenance
    assert "synthetic results-table fixture" in provenance
    assert "computes no metric" in provenance


def test_provenance_explains_why_the_descriptives_table_has_no_figure(tmp_path: Path) -> None:
    provenance = _generate(tmp_path)[3].read_text(encoding="utf-8")

    assert "mix units" in provenance
    assert "shared linear scale" in provenance


# --------------------------------------------------------------------------- #
# Determinism and refusals
# --------------------------------------------------------------------------- #


def test_regeneration_on_unchanged_input_rewrites_identical_bytes(tmp_path: Path) -> None:
    analysis = _analysis()
    source = _write_analysis(tmp_path, analysis, phase="pilot")
    first = CLI.generate(source, tmp_path / "tables")
    digests = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in first}

    second = CLI.generate(source, tmp_path / "tables", overwrite=True)

    assert {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in second} == digests


def test_no_timestamp_or_local_path_reaches_an_output(tmp_path: Path) -> None:
    written = _generate(tmp_path)

    for path in written[:3]:
        text = path.read_text(encoding="utf-8")
        assert str(tmp_path) not in text
        assert NOW.isoformat() not in text
        assert "2026-07-27T08:00" not in text


def test_existing_outputs_are_never_silently_replaced(tmp_path: Path) -> None:
    analysis = _analysis()
    source = _write_analysis(tmp_path, analysis, phase="pilot")
    CLI.generate(source, tmp_path / "tables")
    provenance = tmp_path / "tables" / "vec_tables_unit_provenance.md"
    provenance.write_text("owner's own notes\n", encoding="utf-8")

    with pytest.raises((CLI.ResultsTableError, FileExistsError, ValueError)):
        CLI.generate(source, tmp_path / "tables")
    assert provenance.read_text(encoding="utf-8") == "owner's own notes\n"


def test_an_unreadable_analysis_is_refused_rather_than_partly_rendered(tmp_path: Path) -> None:
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    broken = campaign / "campaign_analysis.json"
    broken.write_text("{}", encoding="utf-8")

    with pytest.raises(CLI.ResultsTableError, match="not a valid campaign analysis"):
        CLI.generate(broken, tmp_path / "tables")
    with pytest.raises(CLI.ResultsTableError, match="missing or unsafe"):
        CLI.generate(campaign / "absent.json", tmp_path / "tables")
    assert not (tmp_path / "tables").exists()


def test_cli_reports_a_failure_with_a_non_zero_exit_code(tmp_path: Path) -> None:
    assert CLI.main([str(tmp_path / "absent.json"), "--output-dir", str(tmp_path / "tables")]) == 1


def test_cli_generates_into_an_explicit_output_directory(tmp_path: Path) -> None:
    analysis = _analysis()
    source = _write_analysis(tmp_path, analysis, phase="pilot")

    assert CLI.main([str(source), "--output-dir", str(tmp_path / "tables")]) == 0
    assert (tmp_path / "tables" / "vec_tables_unit_arm_descriptives.tex").is_file()
