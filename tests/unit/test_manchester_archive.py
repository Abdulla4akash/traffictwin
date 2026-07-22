from __future__ import annotations

import gzip
import io
import stat
import zipfile

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.archive import (
    ArchivePolicy,
    ManchesterArchiveError,
    decompress_gzip,
    read_bounded_zip,
)


def _policy(**updates: object) -> ArchivePolicy:
    values: dict[str, object] = {
        "max_compressed_bytes": 10_000,
        "max_decompressed_bytes": 2_000,
        "max_member_bytes": 1_000,
        "max_members": 10,
        "max_compression_ratio": 100.0,
        "allowed_suffixes": (".csv", ".json"),
    }
    values.update(updates)
    return ArchivePolicy.model_validate(values)


def _zip(entries: list[tuple[str, bytes]], *, symlink: str | None = None) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, contents in entries:
            archive.writestr(name, contents)
        if symlink is not None:
            info = zipfile.ZipInfo(symlink)
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, "target.csv")
    return output.getvalue()


def test_gzip_round_trip_is_exact() -> None:
    raw = b"synthetic,fixture\n1,2\n"
    assert decompress_gzip(gzip.compress(raw), policy=_policy()) == raw


def test_gzip_rejects_input_output_ratio_and_malformed_payloads() -> None:
    raw = b"x" * 200
    with pytest.raises(ManchesterArchiveError, match="compressed payload"):
        decompress_gzip(gzip.compress(raw), policy=_policy(max_compressed_bytes=5))
    with pytest.raises(ManchesterArchiveError, match="decompressed output"):
        decompress_gzip(
            gzip.compress(raw),
            policy=_policy(max_decompressed_bytes=100, max_member_bytes=100),
        )
    with pytest.raises(ManchesterArchiveError, match="compression ratio"):
        decompress_gzip(gzip.compress(raw), policy=_policy(max_compression_ratio=2.0))
    with pytest.raises(ManchesterArchiveError, match="malformed"):
        decompress_gzip(b"not gzip", policy=_policy())


def test_zip_inventory_is_sorted_and_only_selected_bytes_are_returned() -> None:
    payload = _zip([("z.json", b"{}"), ("data/a.csv", b"a,b\n1,2\n")])
    result = read_bounded_zip(payload, policy=_policy(), selected_members={"data/a.csv"})
    assert [member.path for member in result.members] == ["data/a.csv", "z.json"]
    assert result.selected == {"data/a.csv": b"a,b\n1,2\n"}


@pytest.mark.parametrize(
    "name",
    [
        "../escape.csv",
        "/absolute.csv",
        "folder\\escape.csv",
        "folder//escape.csv",
        "folder/./escape.csv",
        "C:/drive.csv",
    ],
)
def test_zip_rejects_unsafe_member_paths(name: str) -> None:
    with pytest.raises(ManchesterArchiveError, match="path is unsafe"):
        read_bounded_zip(_zip([(name, b"x")]), policy=_policy(), selected_members=set())


def test_zip_rejects_symlinks_nested_archives_and_unexpected_types() -> None:
    with pytest.raises(ManchesterArchiveError, match="symbolic-link"):
        read_bounded_zip(
            _zip([("safe.csv", b"x")], symlink="link.csv"),
            policy=_policy(),
            selected_members=set(),
        )
    with pytest.raises(ManchesterArchiveError, match="nested archives"):
        read_bounded_zip(_zip([("nested.zip", b"x")]), policy=_policy(), selected_members=set())
    with pytest.raises(ManchesterArchiveError, match="type is not admitted"):
        read_bounded_zip(_zip([("page.html", b"x")]), policy=_policy(), selected_members=set())


def test_zip_rejects_duplicate_paths_and_missing_selected_members() -> None:
    duplicate = io.BytesIO()
    with zipfile.ZipFile(duplicate, mode="w") as archive:
        archive.writestr("same.csv", b"one")
        with pytest.warns(UserWarning):
            archive.writestr("same.csv", b"two")
    with pytest.raises(ManchesterArchiveError, match="duplicate"):
        read_bounded_zip(duplicate.getvalue(), policy=_policy(), selected_members=set())
    with pytest.raises(ManchesterArchiveError, match="absent"):
        read_bounded_zip(
            _zip([("one.csv", b"x")]),
            policy=_policy(),
            selected_members={"missing.csv"},
        )


def test_zip_enforces_member_count_member_size_total_size_and_ratio() -> None:
    with pytest.raises(ManchesterArchiveError, match="member count"):
        read_bounded_zip(
            _zip([("one.csv", b"1"), ("two.csv", b"2")]),
            policy=_policy(max_members=1),
            selected_members=set(),
        )
    with pytest.raises(ManchesterArchiveError, match="member size"):
        read_bounded_zip(
            _zip([("one.csv", b"12345")]),
            policy=_policy(max_member_bytes=4),
            selected_members=set(),
        )
    with pytest.raises(ManchesterArchiveError, match="decompressed output"):
        read_bounded_zip(
            _zip([("one.csv", b"1234"), ("two.csv", b"5678")]),
            policy=_policy(max_decompressed_bytes=7, max_member_bytes=7),
            selected_members=set(),
        )
    with pytest.raises(ManchesterArchiveError, match="compression ratio"):
        read_bounded_zip(
            _zip([("one.csv", b"x" * 500)]),
            policy=_policy(max_compression_ratio=2.0),
            selected_members=set(),
        )


def test_archive_policy_is_strict_and_canonical() -> None:
    with pytest.raises(ValidationError):
        _policy(unknown=True)
    with pytest.raises(ValidationError, match="lowercase"):
        _policy(allowed_suffixes=(".CSV",))
    with pytest.raises(ValidationError, match="cannot exceed"):
        _policy(max_decompressed_bytes=10, max_member_bytes=11)
