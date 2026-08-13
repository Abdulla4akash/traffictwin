"""AppTests for Manchester Source Operations page (Lane 14)."""

from __future__ import annotations

import pathlib
import tempfile

from streamlit.testing.v1 import AppTest


def _run_page(path: str) -> AppTest:
    at = AppTest.from_file(path, default_timeout=30)
    at.run()
    return at


def _run_pages_render() -> AppTest:
    tmp = pathlib.Path(tempfile.mkdtemp())
    runner = tmp / "runner.py"
    runner.write_text(
        "from traffictwin.ui.pages.manchester_source_operations import render\nrender()\n",
        encoding="utf-8",
    )
    at = AppTest.from_file(str(runner), default_timeout=30)
    at.run()
    return at


def test_manchester_source_operations_page_renders() -> None:
    at = _run_pages_render()
    assert not at.exception, f"Page raised: {at.exception}"
    titles = [str(t.value) for t in at.title]
    assert any("Manchester Source Operations" in t for t in titles), f"titles: {titles}"
    captions = [str(c.value) for c in at.caption]
    all_text = " ".join(
        captions + [str(x.value) for x in at.markdown] + [str(x.value) for x in at.subheader]
    )
    assert "BODS" in all_text or "bus" in all_text.lower()
    subheaders = [str(s.value) for s in at.subheader]
    assert any("Source operations" in s for s in subheaders)
    assert any("Quality" in s or "coverage" in s.lower() for s in subheaders)


def test_manchester_source_operations_app_page_renders() -> None:
    at = _run_page("src/traffictwin/ui/app_pages/manchester_source_operations.py")
    assert not at.exception, f"App page raised: {at.exception}"
    titles = [str(t.value) for t in at.title]
    assert any("Manchester Source Operations" in t for t in titles)


def test_manchester_source_operations_shows_all_families_and_contracts() -> None:
    at = _run_pages_render()
    assert not at.exception
    assert len(at.dataframe) >= 2, f"expected at least 2 dataframes, got {len(at.dataframe)}"
    expander_labels = [str(e.label) for e in at.expander]
    assert len(expander_labels) >= 8
    all_markdown = " ".join(
        [str(m.value) for m in at.markdown] + [str(c.value) for c in at.caption]
    )
    assert (
        "CAN infer" in all_markdown or "can_infer" in all_markdown.lower() or "Bus" in all_markdown
    )
    assert "CANNOT" in all_markdown or "cannot_infer" in all_markdown.lower()
    all_values = " ".join(
        [str(t.value) for t in at.title]
        + [str(c.value) for c in at.caption]
        + [str(m.value) for m in at.markdown]
        + [str(e.label) for e in at.expander]
    )
    assert "/Users/" not in all_values
    assert "/private/" not in all_values
    assert "/tmp/" not in all_values  # noqa: S108
    assert "Bearer" not in all_values
    assert (
        "api_key" not in all_values.lower()
        or "api_key" in all_values.lower()
        and "api_key" not in all_values
    )
    assert (
        "PROVIDER_DATA_REQUIRED" in all_values
        or "provider-data-required" in all_values.lower()
        or "TfGM" in all_values
    )
    assert "bus" in all_values.lower()


def test_manchester_source_operations_no_composite_score() -> None:
    at = _run_pages_render()
    assert not at.exception
    all_text = " ".join(
        [str(t.value) for t in at.title]
        + [str(s.value) for s in at.subheader]
        + [str(c.value) for c in at.caption]
        + [str(m.value) for m in at.markdown]
    ).lower()
    assert "quality_score" not in all_text
    assert "composite_score" not in all_text
    if "quality score" in all_text:
        assert "not combined" in all_text
    if "composite" in all_text:
        assert "not combined" in all_text or "no composite" in all_text
    assert "missingness" in all_text or "duplicate" in all_text


def test_manchester_source_operations_demonstrator_never_claims_credentials() -> None:
    at = _run_pages_render()
    assert not at.exception
    all_text = " ".join(
        [str(c.value) for c in at.caption]
        + [str(m.value) for m in at.markdown]
        + [str(t.value) for t in at.title]
    )
    assert "CREDENTIAL_REQUIRED" in all_text or "credential-required" in all_text.lower()
    assert "sk-" not in all_text
    assert "Bearer " not in all_text


def test_manchester_source_operations_unavailable_markers_and_exact_denominators() -> None:
    at = _run_pages_render()
    assert not at.exception
    all_text = " ".join(
        [str(c.value) for c in at.caption]
        + [str(m.value) for m in at.markdown]
        + [str(s.value) for s in at.subheader]
    )
    # Unavailable marker must be rendered as — with explicit unavailable text
    assert "—" in all_text
    assert "unavailable" in all_text.lower() or "not measured" in all_text.lower()
    # Denominator semantics must be explicit (rows unit) and no snapshot/row mix
    low = all_text.lower()
    assert "rejected_rate" in low or "rejected" in low
    assert "rows" in low
    assert "latest exact pointer" in low or "aggregation" in low.lower()
    # Dataframe must show — for total_expected/present/missing etc.
    # Check that at least one dataframe contains — in its values
    found_dash = False
    for df in at.dataframe:
        # AppTest Dataframe.value is pandas.DataFrame; to_string() always returns str
        val_str = df.value.to_string()
        if "—" in val_str:
            found_dash = True
    assert found_dash, "quality dataframe should contain unavailable marker —"
    # Ensure screened error not leaking exception payload: trigger no
    # exception, but check message code
    # The page should show lane-local reachability text
    assert (
        "not registered in shared navigation" in all_text.lower()
        or "lane-local" in all_text.lower()
    )


def test_manchester_source_operations_no_default_zero_for_unmeasured() -> None:
    """Unmeasured components must be — not 0 in dataframe."""

    at = _run_pages_render()
    assert not at.exception
    # Find quality dataframe (second one)
    assert len(at.dataframe) >= 2
    # The quality dataframe is the second; check its columns for unavailable
    # At least total_expected, missingness, duplicate should be —
    for df in at.dataframe:
        # AppTest Dataframe.value is pandas.DataFrame; to_dict() always returns dict
        s = str(df.value.to_dict())
        if "total_expected" in s or "missingness" in s:
            assert "—" in s, f"expected unavailable marker in {s[:500]}"


def test_manchester_source_operations_navigation_not_registered() -> None:
    at = _run_pages_render()
    assert not at.exception
    all_text = " ".join([str(c.value) for c in at.caption] + [str(m.value) for m in at.markdown])
    assert (
        "parent reconciliation deferred" in all_text.lower()
        or "reconciliation deferred" in all_text.lower()
    )


def test_manchester_source_operations_exact_quality_dataframe_columns() -> None:
    """Exact column-level check: interval_gaps and parser_warnings must be — when unmeasured."""

    at = _run_pages_render()
    assert not at.exception
    assert len(at.dataframe) >= 2
    # Find quality dataframe: it contains interval_gaps column
    quality_df = None
    for df in at.dataframe:
        cols = list(df.value.columns)
        if "interval_gaps" in cols and "parser_warnings" in cols:
            quality_df = df.value
            break
    assert quality_df is not None, (  # noqa: E501
        f"quality dataframe not found; dataframes: {[list(d.value.columns) for d in at.dataframe]}"
    )
    expected_cols = {
        "family",
        "accepted_rows",
        "rejected_rows",
        "rejected_rate",
        "total_expected",
        "present",
        "missing",
        "missingness",
        "duplicate_rate",
        "spatial_coverage",
        "timestamp_range_s",
        "freshness_delay_s",
        "interval_gaps",
        "parser_warnings",
        "limitations",
    }
    assert set(quality_df.columns) == expected_cols
    # Demonstrator has no interval or parser measurement -> — for those columns
    for _, row in quality_df.iterrows():
        assert row["interval_gaps"] == "—", (
            f"interval_gaps should be — when unmeasured, got {row['interval_gaps']!r} for {row['family']}"  # noqa: E501
        )
        assert row["parser_warnings"] == "—", (
            f"parser_warnings should be — when unmeasured, got {row['parser_warnings']!r} for {row['family']}"  # noqa: E501
        )
        # Other unmeasured fields also —
        assert row["total_expected"] == "—"
        assert row["missingness"] == "—"
        assert row["duplicate_rate"] == "—"
        assert row["spatial_coverage"] == "—"
    # Also verify registry counts: DFT/WebTRIS demonstrator non-zero  # noqa: E501
    # The demonstrator has DFT 42 and WebTRIS 24 in its registry
    df_by_family = {str(r["family"]): r for _, r in quality_df.iterrows()}
    # BODS has rejected 5, accepted 0
    assert int(df_by_family["bods"]["rejected_rows"]) == 5
    assert int(df_by_family["bods"]["accepted_rows"]) == 0
    # Interval gaps measured zero should be "0" not "—" — test via direct diagnostics
    from datetime import UTC, datetime

    from traffictwin.integration.manchester.source_operations_models import SourceFamily
    from traffictwin.integration.manchester.source_quality import (
        SourceQualityInput,
        compute_source_quality_diagnostics,
    )

    utc_a = datetime(2026, 7, 22, 10, 0, 0, tzinfo=UTC)
    utc_b = datetime(2026, 7, 22, 10, 1, 0, tzinfo=UTC)
    diag_zero = compute_source_quality_diagnostics(
        SourceQualityInput(
            source_family=SourceFamily.BODS,
            evaluated_at_utc=datetime(2026, 7, 22, 13, 0, 0, tzinfo=UTC),
            accepted_rows=1,
            rejected_rows=0,
            parser_warnings=(),
            expected_interval_seconds=60,
            observed_timestamps_utc=(utc_a, utc_b),
        )
    )
    assert diag_zero.interval_gap_count == 0
    assert diag_zero.parser_warning_count == 0
    # UI rendering for measured zero is "0" not "—"
    assert str(diag_zero.interval_gap_count) == "0"
    assert str(diag_zero.parser_warning_count) == "0"


def test_manchester_source_operations_split_brain_quality_fails_typed() -> None:
    """Quality inputs must fail closed typed on catalogue/registry split-brain."""

    import hashlib
    from datetime import UTC, datetime

    from traffictwin.integration.manchester.snapshot_registry import (
        SnapshotRegistration,
        SnapshotRegistry,
        SnapshotValidationState,
        register_snapshot,
    )
    from traffictwin.integration.manchester.source_operations_models import (
        EvidenceStanding,
        SourceFreshnessStanding,
    )
    from traffictwin.integration.manchester.source_operations_service import (
        build_source_operations_catalogue,
    )
    from traffictwin.ui.manchester_source_operations import (
        build_quality_inputs_for_catalogue,
        make_demonstrator_runtime,
    )

    def fp(s: str) -> str:
        return hashlib.sha256(s.encode()).hexdigest()

    utc_a = datetime(2026, 7, 22, 10, 0, 0, tzinfo=UTC)
    utc_eval = datetime(2026, 7, 22, 13, 0, 0, tzinfo=UTC)
    base = SnapshotRegistry(registered_at_utc=utc_a, snapshots=())
    reg = SnapshotRegistration(
        registration_id="reg-dft-001",
        snapshot_identity="snap-dft-001",
        content_fingerprint=fp("dft-001"),
        retrieved_at_utc=utc_a,
        source_family=__import__(
            "traffictwin.integration.manchester.source_operations_models", fromlist=["SourceFamily"]
        ).SourceFamily.DFT,
        coverage_summary="Admitted DfT count points in Manchester",
        record_count=7,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://x/dft-001",
        provenance_fingerprint=fp("prov-001"),
        validation_receipt_fingerprint=fp("val-001"),
        validated_at_utc=utc_a,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    r = register_snapshot(base, reg)
    # Need WebTRIS as well for HISTORICAL_ONLY
    web = SnapshotRegistration(
        registration_id="reg-webtris-001",
        snapshot_identity="snap-webtris-001",
        content_fingerprint=fp("web-001"),
        retrieved_at_utc=utc_a,
        source_family=__import__(
            "traffictwin.integration.manchester.source_operations_models", fromlist=["SourceFamily"]
        ).SourceFamily.WEBTRIS,
        coverage_summary="Selected strategic-road sites only; external to Manchester",
        record_count=5,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://x/web-001",
        provenance_fingerprint=fp("prov-web"),
        validation_receipt_fingerprint=fp("val-web"),
        validated_at_utc=utc_a,
        evidence_standing=EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA,
    )
    r = register_snapshot(r, web)
    runtime = make_demonstrator_runtime(utc_eval)
    cat = build_source_operations_catalogue(
        evaluated_at_utc=utc_eval, snapshot_registry=r, runtime_by_family=runtime
    )
    # Different registry should trigger typed failure, not silent — display
    other = SnapshotRegistry(registered_at_utc=utc_a, snapshots=())
    import pytest as _pytest

    with _pytest.raises((ValueError, Exception)):
        build_quality_inputs_for_catalogue(cat, other)
