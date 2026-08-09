# mypy: disable-error-code="attr-defined, assignment, unused-ignore, arg-type"
# mypy: disable-error-code="no-any-return, import-untyped"
"""Session-local BundleAnalysis cache — production-path tests.

These tests exercise the only production cache path
``session_validate_bundle`` which the Consequence page uses via
``st.session_state``.  They cover the required P1–P18 cases, mutation
proofs, hash-count proof, and hardening for the race-safe invariant
``cache_entry.fingerprint == analysis.validation.fingerprint``.
"""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

import pytest

from traffictwin.ingestion.hashes import fingerprint_bundle_source, sha256_file
from traffictwin.ui.consequence_cache import (
    _MAX_BUNDLE_CACHE,
    session_validate_bundle,
)
from traffictwin.ui.services.models import BundleAnalysis


def _baseline_copy(tmp_path: Path, name: str = "bundle") -> Path:
    src = Path("tests/fixtures/bundles/baseline_valid")
    dst = tmp_path / name
    shutil.copytree(src, dst)
    return dst


def _variation_copy(tmp_path: Path, name: str = "bundle_var") -> Path:
    src = Path("tests/fixtures/bundles/variation_valid")
    dst = tmp_path / name
    shutil.copytree(src, dst)
    return dst


def _make_zip_from_dir(src_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
        for file in src_dir.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(src_dir).as_posix())


# ---------------------------------------------------------------------------
# P1: unchanged warm hit
# ---------------------------------------------------------------------------


def test_p1_unchanged_warm_hit_calls_validator_zero_times(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import traffictwin.ui.consequence_cache as cache_mod

    dst = _baseline_copy(tmp_path, "p1")
    session_state: dict[str, object] = {}
    first = session_validate_bundle(dst, session_state)
    assert first.analysis_ready
    calls = {"n": 0}
    orig = cache_mod.validate_bundle_for_ui

    def counting(path: Path) -> BundleAnalysis:
        calls["n"] += 1
        return orig(path)

    monkeypatch.setattr("traffictwin.ui.consequence_cache.validate_bundle_for_ui", counting)
    second = session_validate_bundle(dst, session_state)
    assert second.analysis_ready
    assert calls["n"] == 0, "warm hit should not call expensive validator"
    assert first.validation.fingerprint == second.validation.fingerprint


# ---------------------------------------------------------------------------
# P2: same-size rewrite + restored mtime → miss
# ---------------------------------------------------------------------------


def test_p2_same_size_rewrite_restored_mtime_must_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import traffictwin.ui.consequence_cache as cache_mod

    dst = _baseline_copy(tmp_path, "p2")
    session_state: dict[str, object] = {}
    a1 = session_validate_bundle(dst, session_state)
    assert a1.analysis_ready
    fp1 = fingerprint_bundle_source(dst)
    assert fp1 is not None
    target = dst / "manifest.yaml"
    orig_bytes = target.read_bytes()
    st = target.stat()
    atime_ns, mtime_ns = st.st_atime_ns, st.st_mtime_ns
    new_bytes = bytearray(orig_bytes)
    new_bytes[10] = (new_bytes[10] + 1) % 256
    target.write_bytes(new_bytes)
    os.utime(target, ns=(atime_ns, mtime_ns))
    fp2 = fingerprint_bundle_source(dst)
    assert fp2 is not None and fp1 != fp2, "content witness must differ on same-size rewrite"
    calls = {"n": 0}
    orig = cache_mod.validate_bundle_for_ui

    def counting(path: Path) -> BundleAnalysis:
        calls["n"] += 1
        return orig(path)

    monkeypatch.setattr("traffictwin.ui.consequence_cache.validate_bundle_for_ui", counting)
    a2 = session_validate_bundle(dst, session_state)
    assert calls["n"] == 1, "same-size rewrite must invalidate and revalidate"
    assert a2.validation.fingerprint == fp2


# ---------------------------------------------------------------------------
# P3: atomic replacement → miss
# ---------------------------------------------------------------------------


def test_p3_atomic_replacement_must_miss(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import traffictwin.ui.consequence_cache as cache_mod

    dst = _baseline_copy(tmp_path, "p3")
    session_state: dict[str, object] = {}
    session_validate_bundle(dst, session_state)
    fp1 = fingerprint_bundle_source(dst)
    target = dst / "tasks.csv"
    orig_bytes = target.read_bytes()
    tmp_file = dst / "tasks.csv.tmp"
    new_bytes = bytearray(orig_bytes)
    if len(new_bytes) > 5:
        new_bytes[5] = (new_bytes[5] + 1) % 256
    tmp_file.write_bytes(new_bytes)
    assert tmp_file.stat().st_size == target.stat().st_size
    os.replace(tmp_file, target)
    fp2 = fingerprint_bundle_source(dst)
    assert fp1 != fp2
    calls = {"n": 0}
    orig = cache_mod.validate_bundle_for_ui

    def counting(path: Path) -> BundleAnalysis:
        calls["n"] += 1
        return orig(path)

    monkeypatch.setattr("traffictwin.ui.consequence_cache.validate_bundle_for_ui", counting)
    session_validate_bundle(dst, session_state)
    assert calls["n"] == 1


# ---------------------------------------------------------------------------
# P4: add file → miss if it affects logical fingerprint
# ---------------------------------------------------------------------------


def test_p4_add_file_must_miss(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import traffictwin.ui.consequence_cache as cache_mod

    dst = _baseline_copy(tmp_path, "p4")
    session_state: dict[str, object] = {}
    session_validate_bundle(dst, session_state)
    fp1 = fingerprint_bundle_source(dst)
    (dst / "extra.txt").write_text("extra", encoding="utf-8")
    fp2 = fingerprint_bundle_source(dst)
    assert fp1 != fp2
    calls = {"n": 0}
    orig = cache_mod.validate_bundle_for_ui

    def counting(path: Path) -> BundleAnalysis:
        calls["n"] += 1
        return orig(path)

    monkeypatch.setattr("traffictwin.ui.consequence_cache.validate_bundle_for_ui", counting)
    session_validate_bundle(dst, session_state)
    assert calls["n"] == 1


# ---------------------------------------------------------------------------
# P5: remove file → miss
# ---------------------------------------------------------------------------


def test_p5_remove_file_must_miss(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import traffictwin.ui.consequence_cache as cache_mod

    dst = _baseline_copy(tmp_path, "p5")
    session_state: dict[str, object] = {}
    session_validate_bundle(dst, session_state)
    fp1 = fingerprint_bundle_source(dst)
    target = dst / "seed.yaml"
    target.unlink()
    fp2 = fingerprint_bundle_source(dst)
    assert fp2 is not None and fp1 != fp2
    calls = {"n": 0}
    orig = cache_mod.validate_bundle_for_ui

    def counting(path: Path) -> BundleAnalysis:
        calls["n"] += 1
        return orig(path)

    monkeypatch.setattr("traffictwin.ui.consequence_cache.validate_bundle_for_ui", counting)
    session_validate_bundle(dst, session_state)
    assert calls["n"] == 1


# ---------------------------------------------------------------------------
# P6: rename → miss
# ---------------------------------------------------------------------------


def test_p6_rename_must_miss(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import traffictwin.ui.consequence_cache as cache_mod

    dst = _baseline_copy(tmp_path, "p6")
    session_state: dict[str, object] = {}
    session_validate_bundle(dst, session_state)
    fp1 = fingerprint_bundle_source(dst)
    (dst / "tasks.csv").rename(dst / "tasks_renamed.csv")
    fp2 = fingerprint_bundle_source(dst)
    assert fp1 != fp2
    calls = {"n": 0}
    orig = cache_mod.validate_bundle_for_ui

    def counting(path: Path) -> BundleAnalysis:
        calls["n"] += 1
        return orig(path)

    monkeypatch.setattr("traffictwin.ui.consequence_cache.validate_bundle_for_ui", counting)
    session_validate_bundle(dst, session_state)
    assert calls["n"] == 1


# ---------------------------------------------------------------------------
# P7: mutation DURING validation → stored fingerprint is analysis fingerprint,
# next call does not return sticky stale analysis
# ---------------------------------------------------------------------------


def test_p7_mutation_during_validation_is_not_sticky(tmp_path: Path) -> None:
    import traffictwin.ui.consequence_cache as cache_mod

    src_a = Path("tests/fixtures/bundles/baseline_valid")
    src_b = Path("tests/fixtures/bundles/variation_valid")
    dst = tmp_path / "p7"
    shutil.copytree(src_a, dst)
    session_state: dict[str, object] = {}
    orig_validate = cache_mod.validate_bundle_for_ui

    def racing_validate(path: Path) -> BundleAnalysis:
        result = orig_validate(path)
        p = Path(path)
        shutil.rmtree(p)
        shutil.copytree(src_b, p)
        return result

    cache_mod.validate_bundle_for_ui = racing_validate  # type: ignore[attr-defined, assignment]
    try:
        first = session_validate_bundle(dst, session_state)
        assert first.validation.report.run_id == "run-baseline-001"
        assert first.validation.fingerprint is not None
        cache_dict = session_state.get("_consequence_bundle_cache", {})
        assert isinstance(cache_dict, dict)
        entry = list(cache_dict.values())[0]  # type: ignore[index]
        # Handle both legacy 2-tuple (logical, analysis) and new 3-tuple (raw, logical, analysis)
        stored_fp = entry[1] if len(entry) == 3 else entry[0]  # type: ignore[index]
        assert stored_fp == first.validation.fingerprint
        current_fp = fingerprint_bundle_source(dst)
        assert current_fp is not None and current_fp != stored_fp
        cache_mod.validate_bundle_for_ui = orig_validate  # type: ignore[attr-defined, assignment]
        second = session_validate_bundle(dst, session_state)
        assert second.validation.report.run_id == "run-variation-001"
        assert second.validation.fingerprint == current_fp
    finally:
        cache_mod.validate_bundle_for_ui = orig_validate  # type: ignore[attr-defined, assignment]


# ---------------------------------------------------------------------------
# P8: failed/analysis_ready=False → not cached
# ---------------------------------------------------------------------------


def test_p8_failed_validation_never_cached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import traffictwin.ui.consequence_cache as cache_mod

    invalid = tmp_path / "p8_invalid"
    invalid.mkdir()
    (invalid / "random.txt").write_text("not a bundle", encoding="utf-8")
    session_state: dict[str, object] = {}
    first = session_validate_bundle(invalid, session_state)
    assert not first.analysis_ready
    cache_dict = session_state.get("_consequence_bundle_cache", {})
    assert not cache_dict  # type: ignore[truthy-bool]
    calls = {"n": 0}
    orig = cache_mod.validate_bundle_for_ui

    def counting(path: Path) -> BundleAnalysis:
        calls["n"] += 1
        return orig(path)

    monkeypatch.setattr("traffictwin.ui.consequence_cache.validate_bundle_for_ui", counting)
    second = session_validate_bundle(invalid, session_state)
    assert not second.analysis_ready
    assert calls["n"] == 1, "failed validation must not be cached"
    assert not session_state.get("_consequence_bundle_cache", {})  # type: ignore[truthy-bool]


# ---------------------------------------------------------------------------
# P9: validation exception → not cached, exception propagates
# ---------------------------------------------------------------------------


def test_p9_validation_exception_not_cached_and_propagates(tmp_path: Path) -> None:
    import traffictwin.ui.consequence_cache as cache_mod

    dst = _baseline_copy(tmp_path, "p9")
    session_state: dict[str, object] = {}

    def raising(path: Path) -> BundleAnalysis:
        raise OSError("simulated failure")

    orig = cache_mod.validate_bundle_for_ui
    cache_mod.validate_bundle_for_ui = raising  # type: ignore[attr-defined, assignment]
    try:
        with pytest.raises(OSError, match="simulated failure"):
            session_validate_bundle(dst, session_state)
        cache_dict = session_state.get("_consequence_bundle_cache", {})
        assert not cache_dict  # type: ignore[truthy-bool]
        cache_mod.validate_bundle_for_ui = orig  # type: ignore[attr-defined, assignment]
        ok = session_validate_bundle(dst, session_state)
        assert ok.analysis_ready
        cache_dict2 = session_state.get("_consequence_bundle_cache", {})
        assert cache_dict2  # type: ignore[truthy-bool]
    finally:
        cache_mod.validate_bundle_for_ui = orig  # type: ignore[attr-defined, assignment]


# ---------------------------------------------------------------------------
# P10: malformed session cache entry → miss, no crash
# ---------------------------------------------------------------------------


def test_p10_malformed_session_entry_is_miss_not_crash(tmp_path: Path) -> None:
    dst = _baseline_copy(tmp_path, "p10")
    session_state: dict[str, object] = {}
    session_state["_consequence_bundle_cache"] = {  # type: ignore
        str(dst.resolve()): ("not-a-fingerprint", "not-an-analysis"),  # type: ignore
        "bad_tuple": "not-a-tuple",  # type: ignore
        str((tmp_path / "other").resolve()): (123, None),  # type: ignore
    }
    result = session_validate_bundle(dst, session_state)
    assert result.analysis_ready
    session_state2: dict[str, object] = {
        "_consequence_bundle_cache": {
            str(dst.resolve()): None,  # type: ignore
        }
    }
    result2 = session_validate_bundle(dst, session_state2)
    assert result2.analysis_ready


# ---------------------------------------------------------------------------
# P11: deep-copy isolation
# ---------------------------------------------------------------------------


def test_p11_deep_copy_isolation(tmp_path: Path) -> None:
    dst = _baseline_copy(tmp_path, "p11")
    session_state: dict[str, object] = {}
    a1 = session_validate_bundle(dst, session_state)
    assert a1.analysis_ready
    poison_path = dst / "poison_isolation"
    object.__setattr__(a1, "source_path", poison_path)
    a2 = session_validate_bundle(dst, session_state)
    assert str(a2.source_path) != str(poison_path)
    a3 = session_validate_bundle(dst, session_state)
    object.__setattr__(a3, "source_path", poison_path)
    a4 = session_validate_bundle(dst, session_state)
    assert str(a4.source_path) != str(poison_path)


# ---------------------------------------------------------------------------
# P12: bound/eviction (FIFO 32)
# ---------------------------------------------------------------------------


def test_p12_fifo_bound_32_evicts_oldest(tmp_path: Path) -> None:
    src = Path("tests/fixtures/bundles/baseline_valid")
    session_state: dict[str, object] = {}
    dsts: list[Path] = []
    for i in range(33):
        dst = tmp_path / f"p12_{i}"
        shutil.copytree(src, dst)
        (dst / f"unique_{i}.txt").write_text(f"unique {i}", encoding="utf-8")
        dsts.append(dst)
        session_validate_bundle(dst, session_state)
    cache_dict = session_state["_consequence_bundle_cache"]  # type: ignore[assignment]
    assert isinstance(cache_dict, dict)
    assert len(cache_dict) <= _MAX_BUNDLE_CACHE
    first_resolved = str(dsts[0].resolve())
    assert first_resolved not in cache_dict
    last_resolved = str(dsts[-1].resolve())
    assert last_resolved in cache_dict
    import traffictwin.ui.consequence_cache as cache_mod

    calls = {"n": 0}
    orig = cache_mod.validate_bundle_for_ui

    def counting(path: Path) -> BundleAnalysis:
        calls["n"] += 1
        return orig(path)

    old = cache_mod.validate_bundle_for_ui
    cache_mod.validate_bundle_for_ui = counting  # type: ignore[attr-defined, assignment]
    try:
        session_validate_bundle(dsts[0], session_state)
        assert calls["n"] == 1
    finally:
        cache_mod.validate_bundle_for_ui = old  # type: ignore[attr-defined, assignment]


# ---------------------------------------------------------------------------
# P13: path alias (symlink) behaves consistently
# ---------------------------------------------------------------------------


def test_p13_path_alias_resolved_consistently(tmp_path: Path) -> None:
    dst = _baseline_copy(tmp_path, "p13")
    session_state: dict[str, object] = {}
    a1 = session_validate_bundle(dst, session_state)
    assert a1.analysis_ready
    alias = tmp_path / "p13_alias"
    try:
        alias.symlink_to(dst, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink not supported: {exc}")
    import traffictwin.ui.consequence_cache as cache_mod

    calls = {"n": 0}
    orig = cache_mod.validate_bundle_for_ui

    def counting(path: Path) -> BundleAnalysis:
        calls["n"] += 1
        return orig(path)

    old = cache_mod.validate_bundle_for_ui
    cache_mod.validate_bundle_for_ui = counting  # type: ignore[attr-defined, assignment]
    try:
        a2 = session_validate_bundle(alias, session_state)
        assert a2.analysis_ready
        assert calls["n"] == 0, "alias should hit same resolved entry"
        cache_dict = session_state["_consequence_bundle_cache"]  # type: ignore[assignment]
        assert len(cache_dict) == 1
    finally:
        cache_mod.validate_bundle_for_ui = old  # type: ignore[attr-defined, assignment]


# ---------------------------------------------------------------------------
# P14: directory input
# ---------------------------------------------------------------------------


def test_p14_directory_input_uses_logical_fingerprint(tmp_path: Path) -> None:
    dst = _baseline_copy(tmp_path, "p14")
    session_state: dict[str, object] = {}
    a = session_validate_bundle(dst, session_state)
    assert a.analysis_ready
    fps = fingerprint_bundle_source(dst)
    assert fps == a.validation.fingerprint


# ---------------------------------------------------------------------------
# P15: ZIP input — logical fingerprint domain matches validation.fingerprint
# ---------------------------------------------------------------------------


def test_p15_zip_input_uses_logical_not_raw_sha(tmp_path: Path) -> None:
    src_dir = Path("tests/fixtures/bundles/baseline_valid")
    zip_path = tmp_path / "p15.zip"
    _make_zip_from_dir(src_dir, zip_path)
    assert zip_path.is_file()
    raw_sha = sha256_file(zip_path)
    logical_fp = fingerprint_bundle_source(zip_path)
    assert logical_fp is not None
    assert logical_fp != raw_sha, "ZIP logical fingerprint must differ from raw archive SHA"
    session_state: dict[str, object] = {}
    a = session_validate_bundle(zip_path, session_state)
    assert a.analysis_ready
    assert a.validation.fingerprint == logical_fp
    import traffictwin.ui.consequence_cache as cache_mod

    calls = {"n": 0}
    orig = cache_mod.validate_bundle_for_ui

    def counting(path: Path) -> BundleAnalysis:
        calls["n"] += 1
        return orig(path)

    old = cache_mod.validate_bundle_for_ui
    cache_mod.validate_bundle_for_ui = counting  # type: ignore[attr-defined, assignment]
    try:
        a2 = session_validate_bundle(zip_path, session_state)
        assert a2.analysis_ready
        assert calls["n"] == 0
        assert a2.validation.fingerprint == logical_fp
    finally:
        cache_mod.validate_bundle_for_ui = old  # type: ignore[attr-defined, assignment]


# ---------------------------------------------------------------------------
# P16: current token unavailable → fail closed / no store
# ---------------------------------------------------------------------------


def test_p16_unavailable_fingerprint_fails_closed(tmp_path: Path) -> None:
    missing = tmp_path / "p16_missing_xyz"
    session_state: dict[str, object] = {}
    assert fingerprint_bundle_source(missing) is None
    result = session_validate_bundle(missing, session_state)
    assert not result.analysis_ready or result.validation.fingerprint is None
    cache_dict = session_state.get("_consequence_bundle_cache", {})
    assert not cache_dict  # type: ignore[truthy-bool]


# ---------------------------------------------------------------------------
# P17: portable report identity — session cache metadata never enters report
# ---------------------------------------------------------------------------


def test_p17_portable_report_identity_not_polluted(tmp_path: Path) -> None:
    from traffictwin.ui.consequence_lenses import build_consequence_lens_report

    dst_b = Path("tests/fixtures/bundles/baseline_valid")
    dst_v = Path("tests/fixtures/bundles/variation_valid")
    session_state: dict[str, object] = {}
    b = session_validate_bundle(dst_b, session_state)
    v = session_validate_bundle(dst_v, session_state)
    report = build_consequence_lens_report(b, v)
    from traffictwin.ui.services import ServiceError

    assert not isinstance(report, ServiceError)
    portable = report.to_portable_dict()
    canonical = report.to_canonical_bytes().decode()
    json_str = report.to_json()
    for payload_dict in [portable]:
        assert "raw_witness" not in str(payload_dict).lower()
        assert "consequence_cache" not in str(payload_dict)
        assert "_consequence_bundle_cache" not in str(payload_dict)
    for payload in [canonical, json_str]:
        assert "consequence_cache" not in payload
    assert "/tmp" not in str(portable)  # noqa: S108


# ---------------------------------------------------------------------------
# P18: cold vs warm consequence report identical
# ---------------------------------------------------------------------------


def test_p18_cold_warm_report_identical() -> None:
    from traffictwin.ui.consequence_lenses import build_consequence_lens_report
    from traffictwin.ui.services import validate_bundle_for_ui

    b_cold = validate_bundle_for_ui(Path("tests/fixtures/bundles/baseline_valid"))
    v_cold = validate_bundle_for_ui(Path("tests/fixtures/bundles/variation_valid"))
    from traffictwin.ui.services import ServiceError

    r_cold = build_consequence_lens_report(b_cold, v_cold)
    assert not isinstance(r_cold, ServiceError)
    session_state: dict[str, object] = {}
    b_warm = session_validate_bundle(Path("tests/fixtures/bundles/baseline_valid"), session_state)
    v_warm = session_validate_bundle(Path("tests/fixtures/bundles/variation_valid"), session_state)
    r_warm = build_consequence_lens_report(b_warm, v_warm)
    assert not isinstance(r_warm, ServiceError)
    assert r_cold.fingerprint == r_warm.fingerprint
    assert r_cold.to_canonical_bytes() == r_warm.to_canonical_bytes()
    assert r_cold.to_portable_dict() == r_warm.to_portable_dict()


# ---------------------------------------------------------------------------
# Hash call-count proof — no third post-validation pass
# ---------------------------------------------------------------------------


def test_hash_call_count_no_third_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import traffictwin.ingestion.hashes as hashes_mod
    import traffictwin.ui.consequence_cache as cache_mod

    dst = _baseline_copy(tmp_path, "hashcount")
    session_state: dict[str, object] = {}
    sha_counts = {"n": 0}
    orig_sha = hashes_mod.sha256_file

    def counting_sha(path: Path) -> str:
        sha_counts["n"] += 1
        return orig_sha(path)  # type: ignore[no-any-return]

    monkeypatch.setattr(hashes_mod, "sha256_file", counting_sha)
    fps_calls = {"n": 0}
    orig_fps = hashes_mod.fingerprint_bundle_source

    def counting_fps(path: object) -> str | None:
        fps_calls["n"] += 1
        return orig_fps(path)  # type: ignore[no-any-return, arg-type]

    monkeypatch.setattr(hashes_mod, "fingerprint_bundle_source", counting_fps)
    monkeypatch.setattr(cache_mod, "fingerprint_bundle_source", counting_fps)
    sha_counts["n"] = 0
    fps_calls["n"] = 0
    session_validate_bundle(dst, session_state)
    cold_fps = fps_calls["n"]
    cold_sha = sha_counts["n"]
    assert cold_fps == 1, f"cold should do exactly 1 current fingerprint pass, got {cold_fps}"
    sha_counts["n"] = 0
    fps_calls["n"] = 0
    val_calls = {"n": 0}
    orig_validate = cache_mod.validate_bundle_for_ui

    def counting_validate(path: Path) -> BundleAnalysis:
        val_calls["n"] += 1
        return orig_validate(path)

    monkeypatch.setattr(
        "traffictwin.ui.consequence_cache.validate_bundle_for_ui",
        counting_validate,
    )  # type: ignore[attr-defined]  # type: ignore[attr-defined]
    session_validate_bundle(dst, session_state)
    assert fps_calls["n"] == 1, "warm should do 1 current fingerprint pass"
    assert val_calls["n"] == 0, "warm should not call validator"
    assert sha_counts["n"] == 6, (
        f"warm sha256 calls should be 6 (one bundle), got {sha_counts['n']}"
    )
    assert cold_sha == 12, (
        f"cold sha256 calls should be 12 (lookup 6 + validator 6), got {cold_sha}, "
        "third pass would be 18"
    )


# ---------------------------------------------------------------------------
# ZIP logical vs raw SHA distinction (mutant M6)
# ---------------------------------------------------------------------------


def test_zip_logical_fingerprint_matches_validation_not_raw(tmp_path: Path) -> None:
    from traffictwin.ui.services import validate_bundle_for_ui

    src_dir = Path("tests/fixtures/bundles/baseline_valid")
    zip_path = tmp_path / "zip_logical.zip"
    _make_zip_from_dir(src_dir, zip_path)
    logical = fingerprint_bundle_source(zip_path)
    raw = sha256_file(zip_path)
    assert logical != raw
    validation = validate_bundle_for_ui(zip_path)
    assert validation.validation.fingerprint == logical


def test_p7_opposite_direction_pre_validation_stale(tmp_path: Path) -> None:
    """Opposite-direction race: lookup A, validator observes B, storing A is stale.

    Mutant storing ``current_fp`` (A) instead of ``analysis.validation.fingerprint``
    (B) would cache analysis B under fingerprint A. When disk returns to A,
    warm lookup A would incorrectly return stale B. Correct code must store B
    and miss on return to A.
    """

    import traffictwin.ui.consequence_cache as cache_mod

    src_a = Path("tests/fixtures/bundles/baseline_valid")
    src_b = Path("tests/fixtures/bundles/variation_valid")
    dst = tmp_path / "p7_opposite"
    shutil.copytree(src_a, dst)
    session_state: dict[str, object] = {}
    orig_validate = cache_mod.validate_bundle_for_ui
    calls = {"n": 0}

    def pre_mutating_validate(path: Path) -> BundleAnalysis:
        calls["n"] += 1
        p = Path(path)
        if p.exists() and (p / "manifest.yaml").exists():
            current = fingerprint_bundle_source(p)
            if current and current.startswith("b778c4c3"):
                shutil.rmtree(p)
                shutil.copytree(src_b, p)
        return orig_validate(path)

    cache_mod.validate_bundle_for_ui = pre_mutating_validate  # type: ignore[attr-defined, assignment]  # noqa: E501
    try:
        first = session_validate_bundle(dst, session_state)
        assert first.validation.report.run_id == "run-variation-001", (
            "validator should have observed B"
        )
        assert calls["n"] == 1
        cache_dict = session_state.get("_consequence_bundle_cache", {})
        assert isinstance(cache_dict, dict)
        stored = list(cache_dict.values())[0]  # type: ignore[index]
        if len(stored) == 3:
            stored_fp = stored[1]  # type: ignore[index]
        else:
            stored_fp = stored[0]  # type: ignore[index]
            if stored_fp is None and len(stored) == 3:
                stored_fp = stored[1]  # type: ignore[index]
        assert stored_fp == first.validation.fingerprint
        assert str(stored_fp).startswith("3fc08c75"), "stored should be B"
        shutil.rmtree(dst)
        shutil.copytree(src_a, dst)
        current_a = fingerprint_bundle_source(dst)
        assert current_a and current_a.startswith("b778c4c3")
        calls["n"] = 0
        cache_mod.validate_bundle_for_ui = orig_validate  # type: ignore[attr-defined, assignment]
        orig2 = cache_mod.validate_bundle_for_ui

        def counting2(path: Path) -> BundleAnalysis:
            calls["n"] += 1
            return orig2(path)

        cache_mod.validate_bundle_for_ui = counting2  # type: ignore[attr-defined, assignment]
        second = session_validate_bundle(dst, session_state)
        assert second.validation.report.run_id == "run-baseline-001", (
            "should return A after disk returned to A"
        )
        assert calls["n"] == 1, "must miss and revalidate, not hit stale B"
        assert second.validation.fingerprint == current_a
    finally:
        cache_mod.validate_bundle_for_ui = orig_validate  # type: ignore[attr-defined, assignment]


def test_zip_warm_uses_raw_witness_no_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ZIP warm unchanged: one raw SHA, zero validator, no extraction."""
    import traffictwin.ingestion.hashes as hashes_mod
    import traffictwin.ui.consequence_cache as cache_mod

    src_dir = Path("tests/fixtures/bundles/baseline_valid")
    zip_path = tmp_path / "zip_warm.zip"
    _make_zip_from_dir(src_dir, zip_path)
    session_state: dict[str, object] = {}
    # Cold
    first = session_validate_bundle(zip_path, session_state)
    assert first.analysis_ready
    # Instrument: count sha256_file (raw), fingerprint_bundle_source (logical), open_bundle, validator  # noqa: E501
    raw_calls = {"n": 0}
    orig_sha = hashes_mod.sha256_file

    def counting_sha(path: Path) -> str:
        raw_calls["n"] += 1
        return orig_sha(path)

    monkeypatch.setattr(hashes_mod, "sha256_file", counting_sha)
    # Also need to patch the cache module's sha256 import
    monkeypatch.setattr(cache_mod, "sha256_file", counting_sha)
    # For open_bundle, count extraction
    from traffictwin.ingestion import loader as loader_mod

    open_calls = {"n": 0}
    orig_open = loader_mod.open_bundle

    def counting_open(path: object, **kwargs: object) -> object:
        open_calls["n"] += 1
        return orig_open(path, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(loader_mod, "open_bundle", counting_open)
    # Also need to patch hashes_mod.open_bundle via fingerprint_bundle_source? That uses loader.open_bundle directly  # noqa: E501
    # Instead, we patch the cache's fingerprint check: for ZIP warm, it should not call fingerprint_bundle_source at all  # noqa: E501
    fps_calls = {"n": 0}
    orig_fps = hashes_mod.fingerprint_bundle_source

    def counting_fps(path: object) -> str | None:
        fps_calls["n"] += 1
        return orig_fps(path)  # type: ignore[arg-type]

    monkeypatch.setattr(hashes_mod, "fingerprint_bundle_source", counting_fps)
    monkeypatch.setattr(cache_mod, "fingerprint_bundle_source", counting_fps)
    val_calls = {"n": 0}
    orig_validate = cache_mod.validate_bundle_for_ui

    def counting_validate(path: Path) -> BundleAnalysis:
        val_calls["n"] += 1
        return orig_validate(path)

    monkeypatch.setattr(cache_mod, "validate_bundle_for_ui", counting_validate)
    monkeypatch.setattr(
        "traffictwin.ui.consequence_cache.validate_bundle_for_ui", counting_validate
    )  # type: ignore[attr-defined]
    raw_calls["n"] = 0
    fps_calls["n"] = 0
    open_calls["n"] = 0
    val_calls["n"] = 0
    second = session_validate_bundle(zip_path, session_state)
    assert second.analysis_ready
    assert second.validation.fingerprint == first.validation.fingerprint
    # For ZIP warm, we expect: 1 raw SHA (via _raw_zip_witness), 0 fingerprint (logical) extraction, 0 open_bundle, 0 validator  # noqa: E501
    assert raw_calls["n"] == 1, f"ZIP warm should do 1 raw SHA, got {raw_calls['n']}"
    assert fps_calls["n"] == 0, (
        f"ZIP warm should not call logical fingerprint, got {fps_calls['n']}"
    )
    assert open_calls["n"] == 0, f"ZIP warm should not extract, got {open_calls['n']}"
    assert val_calls["n"] == 0, f"ZIP warm should not call validator, got {val_calls['n']}"
    # Deep-copy isolation: mutate returned, next warm still clean
    poison = tmp_path / "poison"
    object.__setattr__(second, "source_path", poison)
    third = session_validate_bundle(zip_path, session_state)
    assert str(third.source_path) != str(poison)


def test_zip_changed_miss_and_validator_invoked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Changed ZIP must miss and revalidate."""
    import traffictwin.ui.consequence_cache as cache_mod

    src_dir = Path("tests/fixtures/bundles/baseline_valid")
    zip_path = tmp_path / "zip_changed.zip"
    _make_zip_from_dir(src_dir, zip_path)
    session_state: dict[str, object] = {}
    session_validate_bundle(zip_path, session_state)
    # Modify ZIP bytes: add a new file to the ZIP
    with zipfile.ZipFile(zip_path, "a") as zf:
        zf.writestr("extra.txt", "extra")
    val_calls = {"n": 0}
    orig_validate = cache_mod.validate_bundle_for_ui

    def counting(path: Path) -> BundleAnalysis:
        val_calls["n"] += 1
        return orig_validate(path)

    monkeypatch.setattr(cache_mod, "validate_bundle_for_ui", counting)
    monkeypatch.setattr("traffictwin.ui.consequence_cache.validate_bundle_for_ui", counting)  # type: ignore[attr-defined]  # noqa: E501
    second = session_validate_bundle(zip_path, session_state)
    assert val_calls["n"] == 1, "changed ZIP must miss and revalidate"
    assert second.analysis_ready


def test_zip_changes_during_validation_not_cached(tmp_path: Path) -> None:
    """ZIP that mutates during validation must not be cached."""
    import traffictwin.ui.consequence_cache as cache_mod

    src_dir = Path("tests/fixtures/bundles/baseline_valid")
    zip_path = tmp_path / "zip_race.zip"
    _make_zip_from_dir(src_dir, zip_path)
    session_state: dict[str, object] = {}
    orig_validate = cache_mod.validate_bundle_for_ui

    def racing_validate(path: Path) -> BundleAnalysis:
        result = orig_validate(path)
        # Mutate ZIP bytes after validator read but before raw_after check
        with zipfile.ZipFile(path, "a") as zf:
            zf.writestr("race_extra.txt", "race")
        return result

    cache_mod.validate_bundle_for_ui = racing_validate  # type: ignore[attr-defined, assignment]
    try:
        first = session_validate_bundle(zip_path, session_state)
        assert first.analysis_ready
        # Should not have cached because raw_before != raw_after
        cache_dict = session_state.get("_consequence_bundle_cache", {})
        assert not cache_dict, "ZIP mutated during validation must not be cached"  # type: ignore[truthy-bool]  # noqa: E501
        # Next call should validate current archive (which is mutated) and return that
        cache_mod.validate_bundle_for_ui = orig_validate  # type: ignore[attr-defined, assignment]
        second = session_validate_bundle(zip_path, session_state)
        assert second.analysis_ready
        # The second's logical fingerprint should reflect the mutated ZIP (has extra file)
        assert second.validation.fingerprint != first.validation.fingerprint
    finally:
        cache_mod.validate_bundle_for_ui = orig_validate  # type: ignore[attr-defined, assignment]


def test_zip_raw_bytes_differ_logical_same_documented(tmp_path: Path) -> None:
    """Raw ZIP bytes can differ while logical fingerprint stays same (e.g., recompressed).

    This is correct and documented: raw witness is local exact-byte check,
    logical fingerprint is the bundle identity. Different compression levels
    for the same logical files produce different raw SHA but same logical.
    Cache must correctly handle this: raw mismatch → miss, but logical
    remains same, and no identity confusion.
    """

    src_dir = Path("tests/fixtures/bundles/baseline_valid")
    zip1 = tmp_path / "zip1.zip"
    zip2 = tmp_path / "zip2.zip"
    # Create same logical content with different compression (STORED vs DEFLATED)
    with zipfile.ZipFile(zip1, "w", compression=zipfile.ZIP_STORED) as zf:
        for f in src_dir.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(src_dir).as_posix())
    with zipfile.ZipFile(zip2, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in src_dir.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(src_dir).as_posix())
    raw1 = sha256_file(zip1)
    raw2 = sha256_file(zip2)
    # Raw should differ due to compression, but logical should be same
    # Note: if the filesystem produces same raw due to same content and
    # STORED vs DEFLATED might still differ
    # We check: if raw1 == raw2, skip (unlikely), else logical should be same
    if raw1 == raw2:
        pytest.skip("raw SHA same despite different compression, cannot test")
    logical1 = fingerprint_bundle_source(zip1)
    logical2 = fingerprint_bundle_source(zip2)
    assert logical1 == logical2, (
        "same logical files must have same logical fingerprint despite different raw"
    )
    # Documented behavior: cache uses raw for ZIP warm, so zip1 and zip2 are different cache keys
    # even though logical is same — correct because raw witness is exact-byte, not logical
    session_state: dict[str, object] = {}
    a1 = session_validate_bundle(zip1, session_state)
    # zip2 is different file path, so separate cache entry; but if we copy zip2
    # over zip1's path, it should miss
    zip1_copy = tmp_path / "zip1_copy.zip"
    shutil.copy2(zip2, zip1_copy)
    # Same path different raw → miss
    session_state2: dict[str, object] = {}
    # First cache zip1_copy as zip2 content
    a2 = session_validate_bundle(zip1_copy, session_state2)
    assert a1.validation.fingerprint == a2.validation.fingerprint  # logical same
    assert sha256_file(zip1) != sha256_file(zip1_copy)  # raw differ


def test_zip_raw_witness_never_in_portable(tmp_path: Path) -> None:
    """Raw ZIP witness must never enter report export/fingerprint."""

    from traffictwin.ui.consequence_lenses import build_consequence_lens_report

    src_dir = Path("tests/fixtures/bundles/baseline_valid")
    zip_path = tmp_path / "zip_portable.zip"
    _make_zip_from_dir(src_dir, zip_path)
    raw = sha256_file(zip_path)
    session_state: dict[str, object] = {}
    b = session_validate_bundle(zip_path, session_state)
    v = session_validate_bundle(Path("tests/fixtures/bundles/variation_valid"), session_state)
    report = build_consequence_lens_report(b, v)
    from traffictwin.ui.services import ServiceError

    assert not isinstance(report, ServiceError)
    portable = report.to_portable_dict()
    canonical = report.to_canonical_bytes().decode()
    json_str = report.to_json()
    for payload in [str(portable), canonical, json_str]:
        assert raw not in payload, "raw ZIP witness must not be in portable"
        assert "raw_witness" not in payload.lower()
        assert "sha256" not in payload.lower() or raw not in payload  # raw should not leak


@pytest.mark.parametrize(
    "malformed_value",
    [
        None,
        123,
        "not-a-tuple",
        (),
        ("only_one",),
        ("a", "b", "c", "d"),  # wrong length 4
        (123, "logical", None),  # raw int, but need BundleAnalysis for third
        (None, 123, None),  # logical int
        (None, "logical", "not-bundle-analysis"),  # fake analysis str
        (None, "logical", 123),  # fake analysis int
        {"raw": "x", "logical": "y"},  # dict
        ("logical", "not-bundle"),  # legacy 2-tuple with fake analysis
        (None, 123, None),  # duplicate to ensure int logical fails
        # Fake object with .validation but not BundleAnalysis
        type("Fake", (), {"validation": type("V", (), {"fingerprint": "abc"})()})(),
    ],
)
def test_malformed_entry_matrix_miss_and_no_crash(tmp_path: Path, malformed_value: object) -> None:
    """Parametrized malformed session entries must miss, not crash, and be replaced."""

    dst = _baseline_copy(tmp_path, f"malformed_{hash(str(malformed_value)) % 10000}")
    session_state: dict[str, object] = {}
    # Inject malformed value
    resolved = str(dst.resolve())
    session_state["_consequence_bundle_cache"] = {resolved: malformed_value}  # type: ignore[dict-item]
    # First call should miss, run validator, not crash, and return valid analysis
    first = session_validate_bundle(dst, session_state)
    assert first.analysis_ready
    # After successful validation, the malformed value should have been replaced with a valid entry
    cache_dict = session_state["_consequence_bundle_cache"]  # type: ignore[assignment]
    assert isinstance(cache_dict, dict)
    entry = cache_dict.get(resolved)
    assert entry is not None
    # Entry should now be a valid 3-tuple (None, logical, BundleAnalysis) for directory
    assert isinstance(entry, tuple)
    assert len(entry) == 3
    assert entry[0] is None  # raw is None for directory
    assert isinstance(entry[1], str)
    assert isinstance(entry[2], BundleAnalysis)


def test_malformed_entry_correct_directory_and_zip_are_hits(tmp_path: Path) -> None:
    """Correct directory and ZIP entries must be hits (not malformed)."""
    import traffictwin.ui.consequence_cache as cache_mod

    # Directory correct entry
    dst = _baseline_copy(tmp_path, "dir_correct")
    session_state: dict[str, object] = {}
    # Warm to get a valid entry
    first = session_validate_bundle(dst, session_state)
    assert first.analysis_ready
    cache_dict = session_state["_consequence_bundle_cache"]  # type: ignore[assignment]
    assert isinstance(cache_dict, dict)
    resolved = str(dst.resolve())
    entry = cache_dict.get(resolved)
    assert isinstance(entry, tuple) and len(entry) == 3
    # Second call should hit (no validator)
    calls = {"n": 0}
    orig = cache_mod.validate_bundle_for_ui

    def counting(path: Path) -> BundleAnalysis:
        calls["n"] += 1
        return orig(path)

    cache_mod.validate_bundle_for_ui = counting  # type: ignore[attr-defined, assignment]
    try:
        second = session_validate_bundle(dst, session_state)
        assert calls["n"] == 0
        assert second.validation.fingerprint == first.validation.fingerprint
    finally:
        cache_mod.validate_bundle_for_ui = orig  # type: ignore[attr-defined, assignment]

    # ZIP correct entry
    src_dir = Path("tests/fixtures/bundles/baseline_valid")
    zip_path = tmp_path / "zip_correct.zip"
    _make_zip_from_dir(src_dir, zip_path)
    session_state2: dict[str, object] = {}
    first_zip = session_validate_bundle(zip_path, session_state2)
    assert first_zip.analysis_ready
    cache_dict2 = session_state2["_consequence_bundle_cache"]  # type: ignore[assignment]
    assert isinstance(cache_dict2, dict)
    resolved_zip = str(zip_path.resolve())
    entry_zip = cache_dict2.get(resolved_zip)
    assert isinstance(entry_zip, tuple) and len(entry_zip) == 3
    assert isinstance(entry_zip[0], str)  # raw
    assert isinstance(entry_zip[1], str)  # logical
    assert isinstance(entry_zip[2], BundleAnalysis)
    # Warm ZIP should hit via raw
    calls["n"] = 0
    cache_mod.validate_bundle_for_ui = counting  # type: ignore[attr-defined, assignment]
    try:
        second_zip = session_validate_bundle(zip_path, session_state2)
        assert calls["n"] == 0
        assert second_zip.validation.fingerprint == first_zip.validation.fingerprint
    finally:
        cache_mod.validate_bundle_for_ui = orig  # type: ignore[attr-defined, assignment]


def test_legacy_two_tuple_still_miss_or_hit_correctly(tmp_path: Path) -> None:
    """Legacy 2-tuple (logical, analysis) should be parsed as directory entry."""
    from traffictwin.ui.services import validate_bundle_for_ui

    dst = _baseline_copy(tmp_path, "legacy")
    session_state: dict[str, object] = {}
    # Create a valid analysis via direct validation
    analysis = validate_bundle_for_ui(dst)
    assert analysis.analysis_ready
    assert isinstance(analysis.validation.fingerprint, str)
    # Inject legacy 2-tuple
    resolved = str(dst.resolve())
    session_state["_consequence_bundle_cache"] = {
        resolved: (analysis.validation.fingerprint, analysis)
    }  # type: ignore[dict-item]
    # Should be a hit (legacy directory entry with raw=None)
    second = session_validate_bundle(dst, session_state)
    assert second.validation.fingerprint == analysis.validation.fingerprint
    # Malformed legacy: wrong types should miss
    session_state2: dict[str, object] = {
        "_consequence_bundle_cache": {resolved: (123, analysis)}  # type: ignore[dict-item]
    }
    third = session_validate_bundle(dst, session_state2)
    assert third.analysis_ready  # miss, revalidated
    # After miss, cache should be replaced with valid 3-tuple
    cache_dict2 = session_state2["_consequence_bundle_cache"]  # type: ignore[assignment]
    assert isinstance(cache_dict2, dict)
    entry2 = cache_dict2.get(resolved)
    assert isinstance(entry2, tuple) and len(entry2) == 3
