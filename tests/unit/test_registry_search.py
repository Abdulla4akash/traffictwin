from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from traffictwin.annotations import (
    AnalystAnnotationRequest,
    AnalystAnnotationTargetKind,
    AnalystArtifactReference,
    AnalystDecisionLabel,
)
from traffictwin.config.capabilities import CapabilitySupport, default_export_import_manifest
from traffictwin.domain.experiment import Experiment
from traffictwin.domain.run import Run
from traffictwin.integration.sumo import sumo_results_capability_manifest
from traffictwin.integration.tos import tos_data_capability_manifest
from traffictwin.registry_search import (
    ABSOLUTE_PATH_REDACTION,
    RegistrySearchError,
    SearchCategory,
    registry_search_contract,
    search_registry,
)
from traffictwin.storage.registry import Registry


def _build_search_workspace(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    report_dir = workspace / "reports"
    report_dir.mkdir(parents=True)
    registry_path = workspace / "registry.sqlite"
    registry = Registry(registry_path)
    registry.initialize()
    registry.add_experiment(
        Experiment(
            experiment_id="exp-urban-load",
            research_question="Does urban congestion reduce completion reliability?",
            hypothesis="Completion falls under stadium demand.",
            baseline_seed_id="seed-baseline",
            variation_seed_ids=["seed-stadium"],
            algorithms=["round-robin", "mappo"],
            common_random_seed_set=[7, 11],
        )
    )
    run = Run(
        run_id="run-alpha",
        experiment_id="exp-urban-load",
        seed_id="seed-stadium",
        algorithm="round-robin",
        random_seed=7,
    )
    registry.register_bundle_import(
        run=run,
        bundle_id="bundle-alpha",
        source_reference="/Users/researcher/private/bundle-alpha",
        fingerprint="a" * 64,
        manifest_json="{}",
        validation_report_json=json.dumps(
            {
                "findings": [
                    {
                        "code": "VALIDATION_QUEUE_WARNING",
                        "severity": "warning",
                        "message": "Queue observations are incomplete near the stadium.",
                    }
                ]
            }
        ),
    )
    registry.append_analyst_annotation(
        AnalystAnnotationRequest(
            target=AnalystArtifactReference(
                kind=AnalystAnnotationTargetKind.RUN,
                artifact_id="run-alpha",
            ),
            author_label="reviewer-a",
            note=(
                "Review congestion collapse before acceptance; source retained at "
                "/Users/researcher/private/source.csv"
            ),
            decision_label=AnalystDecisionLabel.FOLLOW_UP,
        )
    )
    registry.store_evidence_pack(
        pack_id="evidence-run-alpha",
        run_id="run-alpha",
        source_fingerprint="b" * 64,
        payload_json=json.dumps(
            {
                "metric_collection": {
                    "results": [
                        {
                            "metric_key": "task.completion.rate",
                            "value": 0.61,
                            "status": "available",
                        }
                    ]
                },
                "provenance": {"bundle_reference": "bundle-alpha"},
            }
        ),
    )
    report_payload = {
        "title": "Stadium congestion diagnostic",
        "report_type": "diagnostics",
        "source_reference": "/Users/researcher/private/report-source",
        "sections": [["Diagnosis", ["Queue collapse follows the stadium demand window."]]],
        "diagnostic": {
            "findings": [
                {
                    "finding_id": "R4-F1",
                    "statement": "Congestion collapse is concentrated at one RSU.",
                    "evidence_keys": ["infrastructure.rsu.active_tasks.max"],
                    "support": "supports",
                }
            ]
        },
        "claim_references": [
            {
                "claim_id": "claim:metric:task.completion.rate",
                "claim_kind": "metric_result",
                "artifact_key": "task.completion.rate",
                "section": "Task metrics",
                "label": "Task completion rate",
            }
        ],
        "claim_snapshots": [
            {
                "claim_id": "claim:rule:R4",
                "claim_kind": "rule_result",
                "artifact_key": "R4",
                "section": "Diagnostics",
                "availability": "available",
                "status": "triggered",
                "details": {"confidence": "moderate"},
            }
        ],
    }
    (report_dir / "stadium-diagnostic.json").write_text(
        json.dumps(report_payload), encoding="utf-8"
    )
    (report_dir / "summary.md").write_text(
        "# Supervisor summary\n\nCompletion reliability requires review.\n", encoding="utf-8"
    )
    return registry_path, workspace


def test_search_contract_and_capabilities_are_closed() -> None:
    contract = registry_search_contract()

    assert contract.capability_id == "REP-05"
    assert contract.categories == list(SearchCategory)
    assert contract.fingerprint() == registry_search_contract().fingerprint()
    assert (
        default_export_import_manifest().supports.full_text_registry_search
        is CapabilitySupport.TRUE
    )
    assert (
        sumo_results_capability_manifest().supports.full_text_registry_search
        is CapabilitySupport.FALSE
    )
    assert (
        tos_data_capability_manifest().supports.full_text_registry_search is CapabilitySupport.FALSE
    )


def test_search_covers_all_rep05_categories_with_stable_ranking(tmp_path: Path) -> None:
    registry, workspace = _build_search_workspace(tmp_path)

    finding = search_registry(registry, "R4 F1", workspace_path=workspace)
    annotation = search_registry(registry, "review acceptance", workspace_path=workspace)
    report = search_registry(registry, "supervisor summary", workspace_path=workspace)
    run = search_registry(registry, "run alpha", workspace_path=workspace)
    experiment = search_registry(registry, "urban congestion", workspace_path=workspace)
    evidence = search_registry(registry, "completion rate", workspace_path=workspace)

    assert finding.hits[0].category is SearchCategory.FINDING
    assert annotation.hits[0].category is SearchCategory.ANNOTATION
    assert report.hits[0].category is SearchCategory.REPORT
    assert run.hits[0].category is SearchCategory.RUN
    assert experiment.hits[0].category is SearchCategory.EXPERIMENT
    assert evidence.hits[0].category is SearchCategory.EVIDENCE_REFERENCE
    assert [hit.rank for hit in finding.hits] == list(range(1, len(finding.hits) + 1))
    assert (
        finding.fingerprint()
        == search_registry(registry, "R4 F1", workspace_path=workspace).fingerprint()
    )


def test_search_is_read_only_and_redacts_paths_before_matching(tmp_path: Path) -> None:
    registry, workspace = _build_search_workspace(tmp_path)
    before = hashlib.sha256(registry.read_bytes()).hexdigest()
    files_before = sorted(path.name for path in registry.parent.iterdir())

    result = search_registry(registry, "review congestion", workspace_path=workspace)
    path_term = search_registry(registry, "researcher private", workspace_path=workspace)
    redacted_query = search_registry(
        registry,
        "review /Users/researcher/private/query.txt",
        workspace_path=workspace,
    )
    after = hashlib.sha256(registry.read_bytes()).hexdigest()
    files_after = sorted(path.name for path in registry.parent.iterdir())

    assert before == after
    assert files_before == files_after
    assert result.redaction_count >= 2
    assert ABSOLUTE_PATH_REDACTION in result.canonical_json()
    assert "/Users/researcher" not in result.canonical_json()
    assert not path_term.hits
    assert path_term.matching_count == 0
    assert redacted_query.query == f"review {ABSOLUTE_PATH_REDACTION}"
    assert "/Users/researcher" not in redacted_query.canonical_json()


def test_category_filter_limit_and_count_reconciliation(tmp_path: Path) -> None:
    registry, workspace = _build_search_workspace(tmp_path)

    result = search_registry(
        registry,
        "completion",
        workspace_path=workspace,
        categories=[SearchCategory.REPORT],
        limit=1,
    )

    assert result.selected_categories == [SearchCategory.REPORT]
    assert result.returned_count == 1
    assert result.matching_count == result.returned_count + result.omitted_match_count
    assert all(hit.category is SearchCategory.REPORT for hit in result.hits)


@pytest.mark.parametrize(
    ("query", "categories", "limit", "message"),
    [
        ("", None, 50, "must not be empty"),
        ("---", None, 50, "alphanumeric"),
        (" ".join(f"term{i}" for i in range(17)), None, 50, "at most 16"),
        ("valid", [], 50, "at least one"),
        ("valid", None, 201, "between 1 and 200"),
    ],
)
def test_search_rejects_unbounded_or_empty_requests(
    tmp_path: Path,
    query: str,
    categories: list[SearchCategory] | None,
    limit: int,
    message: str,
) -> None:
    registry, workspace = _build_search_workspace(tmp_path)

    with pytest.raises(RegistrySearchError, match=message):
        search_registry(
            registry,
            query,
            workspace_path=workspace,
            categories=categories,
            limit=limit,
        )


def test_search_skips_symlinked_and_oversized_reports(tmp_path: Path) -> None:
    registry, workspace = _build_search_workspace(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("secret external report", encoding="utf-8")
    (workspace / "reports" / "linked.md").symlink_to(outside)
    (workspace / "reports" / "oversized.md").write_text("x" * 2_000_001, encoding="utf-8")

    result = search_registry(registry, "secret", workspace_path=workspace)

    assert result.skipped_report_count == 2
    assert not result.hits


def test_search_rejects_symlinked_report_directory(tmp_path: Path) -> None:
    registry, _ = _build_search_workspace(tmp_path)
    outside = tmp_path / "outside-reports"
    outside.mkdir()
    linked_workspace = tmp_path / "linked-workspace"
    linked_workspace.mkdir()
    (linked_workspace / "reports").symlink_to(outside, target_is_directory=True)

    with pytest.raises(RegistrySearchError, match="report directory.*symbolic link"):
        search_registry(registry, "anything", workspace_path=linked_workspace)


def test_search_bounds_untrusted_report_titles(tmp_path: Path) -> None:
    registry, workspace = _build_search_workspace(tmp_path)
    (workspace / "reports" / "long-title.json").write_text(
        json.dumps({"title": "oversized " + ("t" * 5_000), "sections": []}),
        encoding="utf-8",
    )

    result = search_registry(registry, "oversized", workspace_path=workspace)

    assert result.hits[0].category is SearchCategory.REPORT
    assert len(result.hits[0].title) == 4_000
    assert result.hits[0].title.endswith(" …")
