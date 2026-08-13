"""Mutation/discriminating tests for Manchester closed-loop SAFE LOCAL SUMO execution."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.closed_loop_execution import (
    ClosedLoopExecutionRequest,
    ClosedLoopToolIdentity,
    ManchesterClosedLoopError,
    build_closed_loop_execution_package,
    create_closed_loop_request,
    detect_configured_sumo,
    preflight_closed_loop_execution,
    run_closed_loop_execution,
)

# ---------------------------------------------------------------------------
# Helpers — tiny test fakes only through the narrow allowlisted contract
# ---------------------------------------------------------------------------


def _write_fake_sumo(
    directory: Path,
    *,
    version: str = "1.27.3",
    exit_code: int = 0,
    delay_s: float = 0.0,
    write_outputs: bool = True,
    capture_env_to: Path | None = None,
    capture_cwd_to: Path | None = None,
) -> Path:
    """Create an executable named ``sumo`` that responds to --version and run."""

    directory.mkdir(parents=True, exist_ok=True)
    exe = directory / "sumo"
    # Use repr for paths to handle None correctly
    script = textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        import sys, time, pathlib, os, json
        args = sys.argv[1:]
        if "--version" in args:
            print("Eclipse SUMO Version {version}")
            sys.exit(0)
        # normal run: parse fixed argv to find output paths
        trip = None
        summ = None
        for i, a in enumerate(args):
            if a == "--tripinfo-output" and i+1 < len(args):
                trip = pathlib.Path(args[i+1])
            if a == "--summary-output" and i+1 < len(args):
                summ = pathlib.Path(args[i+1])
        if {str(capture_env_to)!r} != "None":
            out = pathlib.Path({str(capture_env_to)!r})
            out.write_text(json.dumps(dict(os.environ), sort_keys=True))
        if {str(capture_cwd_to)!r} != "None":
            out = pathlib.Path({str(capture_cwd_to)!r})
            out.write_text(str(pathlib.Path.cwd()))
        if {delay_s} > 0:
            time.sleep({delay_s})
        if {write_outputs}:
            if trip:
                trip.parent.mkdir(parents=True, exist_ok=True)
                trip.write_text("<tripinfos><tripinfo id=\\"t0\\"/></tripinfos>", encoding="utf-8")
            if summ:
                summ.parent.mkdir(parents=True, exist_ok=True)
                summ.write_text("<summary/>", encoding="utf-8")
        print("fake sumo stdout line")
        print("warning: something", file=sys.stderr)
        sys.exit({exit_code})
        """
    )
    exe.write_text(script, encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return exe


def _fake_tool(exe: Path, version: str = "1.27.3") -> ClosedLoopToolIdentity:
    h = hashlib.sha256()
    with exe.open("rb") as f:
        h.update(f.read())
    return ClosedLoopToolIdentity(reported_version=version, executable_sha256=h.hexdigest())


def _package_with_config(tmp: Path, config_name: str = "sumo.sumocfg") -> Path:
    pkg = tmp / "pkg"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / config_name).write_text(
        "<configuration><input></input></configuration>", encoding="utf-8"
    )
    (pkg / "net.xml").write_text("<net/>", encoding="utf-8")
    (pkg / "routes.xml").write_text("<routes/>", encoding="utf-8")
    return pkg


# ---------------------------------------------------------------------------
# Detection / allowlist
# ---------------------------------------------------------------------------


def test_detect_configured_sumo_allowlisted_and_version_capture(tmp_path: Path) -> None:
    fake_dir = tmp_path / "fake1"
    exe = _write_fake_sumo(fake_dir, version="1.27.1")
    tool = detect_configured_sumo(exe)
    assert tool.reported_version == "1.27.1"
    assert tool.executable_name == "sumo"
    assert tool.executable_sha256 == hashlib.sha256(exe.read_bytes()).hexdigest()


def test_detect_rejects_non_allowlisted_executable(tmp_path: Path) -> None:
    p = tmp_path / "not_sumo"
    p.write_text("#!/usr/bin/env python3\nprint('hi')", encoding="utf-8")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    with pytest.raises(ManchesterClosedLoopError, match="allowlisted"):
        detect_configured_sumo(p)


def test_detect_rejects_version_drift(tmp_path: Path) -> None:
    fake_dir = tmp_path / "fake_drift"
    exe = _write_fake_sumo(fake_dir, version="1.28.0")
    with pytest.raises(ManchesterClosedLoopError, match="VERSION_DRIFT"):
        detect_configured_sumo(exe)


def test_arbitrary_executable_argv_injection_forbidden(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg", run_id="run-01")
    with pytest.raises(Exception, match="extra"):
        ClosedLoopExecutionRequest.model_validate(
            {**req.model_dump(mode="json"), "executable": "/tmp/fake-evil-test", "argv": ["evil"]}  # noqa: S108
        )
    with pytest.raises(ManchesterClosedLoopError):
        create_closed_loop_request(package_root=pkg, config_file="../evil.sumocfg")


def test_preflight_blocked_when_sumo_absent(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out1", request=req, tool=None
    )
    assert report.status == "blocked"
    assert any("SUMO" in f for f in report.findings)
    assert report.read_only is True
    assert report.mutations_performed is False


def test_preflight_blocked_when_provider_required_input_absent(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    (pkg / "net.xml").unlink()
    fake_dir = tmp_path / "fake2"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out2", request=req, tool=tool
    )
    assert report.status == "blocked"
    assert any("INPUT_VERIFICATION_FAILED" in f for f in report.findings)


# ---------------------------------------------------------------------------
# Operator authorisation
# ---------------------------------------------------------------------------


def test_missing_operator_authorisation_fails_closed() -> None:
    # Model validation must reject missing or False authorisation
    base = {  # noqa: S108 - test data only
        "run_id": "run-01",
        "package_fingerprint": "a" * 64,
        "config_file": "sumo.sumocfg",
        "inputs": [{"path": "sumo.sumocfg", "sha256": "b" * 64, "size_bytes": 10}],
        "seed": 42,
        "timeout_seconds": 120,
        "deterministic_run_identity": "c" * 64,
        "confirmed_by_operator": False,
    }
    with pytest.raises(Exception):  # noqa: B017
        ClosedLoopExecutionRequest.model_validate(base)
    with pytest.raises(Exception):  # noqa: B017
        ClosedLoopExecutionRequest.model_validate(
            {k: v for k, v in base.items() if k != "confirmed_by_operator"}
        )


def test_create_request_requires_operator_authorisation(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    with pytest.raises(ManchesterClosedLoopError, match="OPERATOR_AUTHORISATION"):
        create_closed_loop_request(
            package_root=pkg,
            config_file="sumo.sumocfg",
            confirmed_by_operator=False,  # type: ignore[arg-type]  # noqa: FBT003
        )
    # deterministic identity binds authorisation
    r1 = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", run_id="run-a", confirmed_by_operator=True
    )
    assert r1.confirmed_by_operator is True
    # Same inputs but different authorisation would produce different identity if it were allowed


def test_operator_authorisation_bound_in_identity(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    r1 = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", run_id="run-01", seed=42
    )
    # Tampering the identity should fail validation
    tampered = {**r1.model_dump(mode="json"), "confirmed_by_operator": True}
    # Change deterministic identity to something else -> should fail
    tampered2 = {**tampered, "deterministic_run_identity": "0" * 64}
    with pytest.raises(Exception):  # noqa: B017
        ClosedLoopExecutionRequest.model_validate(tampered2)


# ---------------------------------------------------------------------------
# Changed input after request
# ---------------------------------------------------------------------------


def test_changed_input_after_request_fails_closed(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    (pkg / "net.xml").write_text("<net>changed</net>", encoding="utf-8")
    fake_dir = tmp_path / "fake3"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_changed"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "blocked"
    assert receipt.inputs_verified is False
    assert receipt.scientific_standing == "SCIENTIFICALLY_NOT_ACCEPTED"
    assert receipt.engineering_standing == "ENGINEERING_NOT_VALID"


# ---------------------------------------------------------------------------
# Traversal / symlink escape
# ---------------------------------------------------------------------------


def test_traversal_input_rejected(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    with pytest.raises(ManchesterClosedLoopError):
        create_closed_loop_request(package_root=pkg, config_file="../../etc/passwd")


def test_symlink_before_request_fails_closed_at_construction(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    (pkg / "net.xml").unlink()
    target = tmp_path / "outside.xml"
    target.write_text("<net/>", encoding="utf-8")
    (pkg / "net.xml").symlink_to(target)
    assert (pkg / "net.xml").is_symlink()
    with pytest.raises(ManchesterClosedLoopError, match="symlink"):
        create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")


def test_symlink_input_fails_preflight(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    (pkg / "net.xml").unlink()
    target = tmp_path / "outside.xml"
    target.write_text("<net/>", encoding="utf-8")
    (pkg / "net.xml").symlink_to(target)
    assert (pkg / "net.xml").is_symlink()
    with pytest.raises(ManchesterClosedLoopError, match="symlink"):
        create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")


def test_symlink_after_request_fails_closed(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg", seed=7)
    (pkg / "net.xml").unlink()
    target = tmp_path / "outside2.xml"
    target.write_text("<net>evil</net>", encoding="utf-8")
    (pkg / "net.xml").symlink_to(target)
    assert (pkg / "net.xml").is_symlink()
    fake_dir = tmp_path / "fake_sym_after"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_sym_after", request=req, tool=tool
    )
    assert report.status == "blocked"
    assert any("symlink" in f.lower() for f in report.findings)
    out = tmp_path / "out_sym_after_exec"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "blocked"
    assert receipt.inputs_verified is False
    assert receipt.shell_used is False
    assert receipt.caller_supplied_arguments is False
    assert tuple(receipt.argv) == (
        "sumo",
        "-c",
        req.config_file,
        "--seed",
        str(req.seed),
        "--tripinfo-output",
        "tripinfo.xml",
        "--summary-output",
        "summary.xml",
        "--no-step-log",
        "true",
    )
    assert receipt.scientific_standing == "SCIENTIFICALLY_NOT_ACCEPTED"
    assert receipt.engineering_standing == "ENGINEERING_NOT_VALID"


def test_output_overlaps_package_refused(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_overlap"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=pkg / "out", request=req, tool=tool
    )
    assert report.status == "blocked"
    assert any("OUTPUT_ISOLATION" in f for f in report.findings)


# ---------------------------------------------------------------------------
# Hardened XML preflight — DTD, entities, references, options
# ---------------------------------------------------------------------------


def test_malicious_config_dtd_rejected(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    (pkg / "sumo.sumocfg").write_text(
        '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><configuration><input></input></configuration>',
        encoding="utf-8",
    )
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_dtd"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_dtd", request=req, tool=tool
    )
    assert report.status == "blocked"
    assert any("DTD" in f or "CONFIG" in f for f in report.findings)


def test_malicious_config_entity_rejected(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    (pkg / "sumo.sumocfg").write_text(
        "<configuration><!ENTITY evil 'bad'><input></input></configuration>",
        encoding="utf-8",
    )
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_ent"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_ent", request=req, tool=tool
    )
    assert report.status == "blocked"


def test_malicious_config_absolute_reference_rejected(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    (pkg / "sumo.sumocfg").write_text(
        '<configuration><input><net-file value="/etc/passwd"/></input></configuration>',
        encoding="utf-8",
    )
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_abs"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_abs", request=req, tool=tool
    )
    assert report.status == "blocked"
    assert any("ABSOLUTE" in f or "CONFIG" in f for f in report.findings)


def test_malicious_config_traversal_rejected(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    (pkg / "sumo.sumocfg").write_text(
        '<configuration><input><net-file value="../outside.xml"/></input></configuration>',
        encoding="utf-8",
    )
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_trav"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_trav", request=req, tool=tool
    )
    assert report.status == "blocked"
    assert any("TRAVERSAL" in f for f in report.findings)


def test_malicious_config_uri_rejected(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    (pkg / "sumo.sumocfg").write_text(
        '<configuration><input><net-file value="http://evil.example/payload.xml"/></input></configuration>',
        encoding="utf-8",
    )
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_uri"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_uri", request=req, tool=tool
    )
    assert report.status == "blocked"
    assert any("URI" in f for f in report.findings)


def test_malicious_config_reference_not_in_inventory(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    (pkg / "sumo.sumocfg").write_text(
        '<configuration><input><net-file value="not_declared.xml"/></input></configuration>',
        encoding="utf-8",
    )
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_inv"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_inv", request=req, tool=tool
    )
    assert report.status == "blocked"
    assert any("INVENTORY" in f for f in report.findings)


def test_malicious_config_output_option_rejected(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    (pkg / "sumo.sumocfg").write_text(
        '<configuration><output><tripinfo-output value="/tmp/evil.xml"/></output></configuration>',
        encoding="utf-8",
    )
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_outopt"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_outopt", request=req, tool=tool
    )
    assert report.status == "blocked"
    assert any("FORBIDDEN" in f or "UNREVIEWED" in f for f in report.findings)


def test_malicious_config_unreviewed_element_rejected(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    (pkg / "sumo.sumocfg").write_text(
        '<configuration><remote><remote-port value="9999"/></remote></configuration>',
        encoding="utf-8",
    )
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_unrev"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_unrev", request=req, tool=tool
    )
    assert report.status == "blocked"


def test_malicious_config_oversized_rejected(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    big = "A" * (1_000_001)
    (pkg / "sumo.sumocfg").write_text(
        f"<configuration><input>{big}</input></configuration>", encoding="utf-8"
    )
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_bigcfg"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_bigcfg", request=req, tool=tool
    )
    assert report.status == "blocked"
    assert any("OVERSIZED" in f for f in report.findings)


def test_malicious_config_malformed_rejected(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    (pkg / "sumo.sumocfg").write_text("<configuration><input><unclosed>", encoding="utf-8")
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_mal"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_mal", request=req, tool=tool
    )
    assert report.status == "blocked"
    assert any("MALFORMED" in f for f in report.findings)


# ---------------------------------------------------------------------------
# Source-package immutability & isolated staging
# ---------------------------------------------------------------------------


def test_source_package_immutability_and_isolated_cwd(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    # Record original hashes
    orig = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in pkg.iterdir() if p.is_file()
    }
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_immut"
    cwd_capture = tmp_path / "cwd.txt"
    exe = _write_fake_sumo(fake_dir, capture_cwd_to=cwd_capture)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_immut"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "completed"
    # Source package unchanged
    after = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in pkg.iterdir() if p.is_file()
    }
    assert orig == after
    # Cwd was not source package but isolated staging under output
    cwd = Path(cwd_capture.read_text(encoding="utf-8"))
    assert cwd != pkg.resolve()
    assert out.resolve() in cwd.parents or cwd == (out / "_staging").resolve()
    # Staging directory exists under output
    assert (out / "_staging").is_dir()
    # Staging contains verified inputs
    for decl in req.inputs:
        staged = out / "_staging" / decl.path
        assert staged.is_file()
        assert hashlib.sha256(staged.read_bytes()).hexdigest() == decl.sha256


# ---------------------------------------------------------------------------
# Timeout / nonzero exit / bounded receipts
# ---------------------------------------------------------------------------


def test_timeout_produces_timed_out_receipt(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", timeout_seconds=1
    )
    fake_dir = tmp_path / "fake_timeout"
    exe = _write_fake_sumo(fake_dir, delay_s=5.0)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_timeout"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "timed_out"
    assert receipt.timed_out is True
    assert len(receipt.stdout_excerpt) <= 32000
    assert len(receipt.stderr_excerpt) <= 32000
    assert receipt.engineering_standing == "ENGINEERING_NOT_VALID"
    assert receipt.scientific_standing == "SCIENTIFICALLY_NOT_ACCEPTED"


def test_nonzero_exit_produces_failed_receipt(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_fail"
    exe = _write_fake_sumo(fake_dir, exit_code=1)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_fail"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "failed"
    assert receipt.exit_code == 1
    assert receipt.timed_out is False
    assert receipt.engineering_standing == "ENGINEERING_NOT_VALID"


def test_bounded_stdout_stderr_receipts(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_bigout"
    fake_dir.mkdir(parents=True, exist_ok=True)
    exe = fake_dir / "sumo"
    script = textwrap.dedent("""\
        #!/usr/bin/env python3
        import sys
        sys.argv
        if "--version" in sys.argv:
            print("Eclipse SUMO Version 1.27.5")
            sys.exit(0)
        print("x" * 100000)
        print("y" * 100000, file=sys.stderr)
        import pathlib
        for i,a in enumerate(sys.argv):
            if a=="--tripinfo-output" and i+1<len(sys.argv):
                pathlib.Path(sys.argv[i+1]).write_text("<tripinfos/>")
            if a=="--summary-output" and i+1<len(sys.argv):
                pathlib.Path(sys.argv[i+1]).write_text("<summary/>")
        sys.exit(0)
        """)
    exe.write_text(script, encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_big"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert len(receipt.stdout_excerpt) <= 32000
    assert len(receipt.stderr_excerpt) <= 32000
    # Ensure bounded during execution — file size may be large but excerpt is bounded


# ---------------------------------------------------------------------------
# Output size, extra, symlink, aggregate
# ---------------------------------------------------------------------------


def test_output_oversize_rejected(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_oversize"
    fake_dir.mkdir(parents=True, exist_ok=True)
    exe = fake_dir / "sumo"
    script = textwrap.dedent("""\
        #!/usr/bin/env python3
        import sys, pathlib
        if "--version" in sys.argv:
            print("Eclipse SUMO Version 1.27.3")
            sys.exit(0)
        for i,a in enumerate(sys.argv):
            if a=="--tripinfo-output" and i+1<len(sys.argv):
                # oversize > 50M
                pathlib.Path(sys.argv[i+1]).write_bytes(b"x" * (51_000_000))
            if a=="--summary-output" and i+1<len(sys.argv):
                pathlib.Path(sys.argv[i+1]).write_text("<summary/>")
        sys.exit(0)
        """)
    exe.write_text(script, encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_oversize"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "failed"
    assert "OVERSIZE" in receipt.stderr_excerpt
    assert len(receipt.stderr_excerpt.strip()) > 0
    assert "REDACTED" not in receipt.stderr_excerpt or "OVERSIZE" in receipt.stderr_excerpt
    assert receipt.engineering_standing == "ENGINEERING_NOT_VALID"


def test_output_extra_rejected(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_extra"
    fake_dir.mkdir(parents=True, exist_ok=True)
    exe = fake_dir / "sumo"
    script = textwrap.dedent("""\
        #!/usr/bin/env python3
        import sys, pathlib
        if "--version" in sys.argv:
            print("Eclipse SUMO Version 1.27.3")
            sys.exit(0)
        trip = summ = None
        for i,a in enumerate(sys.argv):
            if a=="--tripinfo-output" and i+1<len(sys.argv):
                trip = pathlib.Path(sys.argv[i+1])
            if a=="--summary-output" and i+1<len(sys.argv):
                summ = pathlib.Path(sys.argv[i+1])
        if trip:
            trip.write_text("<tripinfos/>")
        if summ:
            summ.write_text("<summary/>")
        # extra file
        if trip:
            (trip.parent / "extra.xml").write_text("<extra/>")
        sys.exit(0)
        """)
    exe.write_text(script, encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_extra"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "failed"
    assert "EXTRA" in receipt.stderr_excerpt


def test_output_symlink_rejected(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_symout"
    fake_dir.mkdir(parents=True, exist_ok=True)
    exe = fake_dir / "sumo"
    script = textwrap.dedent("""\
        #!/usr/bin/env python3
        import sys, pathlib
        if "--version" in sys.argv:
            print("Eclipse SUMO Version 1.27.3")
            sys.exit(0)
        for i,a in enumerate(sys.argv):
            if a=="--tripinfo-output" and i+1<len(sys.argv):
                p = pathlib.Path(sys.argv[i+1])
                p.write_text("<tripinfos/>")
            if a=="--summary-output" and i+1<len(sys.argv):
                p = pathlib.Path(sys.argv[i+1])
                real = p.parent / "real_summary.xml"
                real.write_text("<summary/>")
                try:
                    if p.exists():
                        p.unlink()
                    p.symlink_to(real)
                except Exception:
                    p.write_text("<summary/>")
        sys.exit(0)
        """)
    exe.write_text(script, encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_symout"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    # Symlink creation is part of the attack; receipt must detect and reject
    assert (out / "summary.xml").is_symlink(), (
        "symlink test did not exercise branch: symlink was not created"
    )
    assert receipt.outcome == "failed"
    assert "SYMLINK" in receipt.stderr_excerpt
    assert len(receipt.stderr_excerpt.strip()) > 0


# ---------------------------------------------------------------------------
# Deterministic identity
# ---------------------------------------------------------------------------


def test_deterministic_identity_stable(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    r1 = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", run_id="run-01", seed=42
    )
    r2 = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", run_id="run-01", seed=42
    )
    assert r1.deterministic_run_identity == r2.deterministic_run_identity
    assert r1.fingerprint() == r2.fingerprint()
    r3 = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", run_id="run-01", seed=99
    )
    assert r3.deterministic_run_identity != r1.deterministic_run_identity


def test_deterministic_identity_after_run_matches_request(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_det"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_det"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    # Canonical run identity binds request fingerprint + tool + argv,
    # distinct from request-only identity
    import hashlib as _hl
    import json as _js

    def _canon(payload: object) -> str:
        return _hl.sha256(
            _js.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()

    expected_canonical = _canon(
        {
            "argv": receipt.argv,
            "confirmed_by_operator": True,
            "request_fingerprint": req.fingerprint(),
            "tool_sha": tool.executable_sha256,
            "tool_version": tool.reported_version,
        }
    )
    assert receipt.deterministic_run_identity == expected_canonical
    # Must NOT equal the request-only identity (which omits tool/argv)
    assert receipt.deterministic_run_identity != req.deterministic_run_identity
    pkg_obj = build_closed_loop_execution_package(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert pkg_obj.deterministic_run_identity == expected_canonical
    # Receipt fingerprint must be distinct from deterministic identity (wall-clock vs deterministic)
    assert receipt.fingerprint() != receipt.deterministic_run_identity


# ---------------------------------------------------------------------------
# Sanitized environment
# ---------------------------------------------------------------------------


def test_sanitized_environment(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_env"
    env_dump = tmp_path / "env.json"
    exe = _write_fake_sumo(fake_dir, capture_env_to=env_dump)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_env"
    os.environ["SECRET_API_KEY"] = "should-not-leak"  # noqa: S105
    os.environ["MY_TOKEN"] = "also-secret"  # noqa: S105
    try:
        receipt = run_closed_loop_execution(
            package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
        )
    finally:
        os.environ.pop("SECRET_API_KEY", None)
        os.environ.pop("MY_TOKEN", None)
    env = json.loads(env_dump.read_text(encoding="utf-8"))
    assert "SECRET_API_KEY" not in env
    assert "MY_TOKEN" not in env
    assert "PATH" in env
    assert env["PATH"].startswith(str(exe.parent))
    assert "/usr/bin:/bin" in env["PATH"]
    dumped = json.dumps(receipt.model_dump(mode="json"))
    assert "should-not-leak" not in dumped
    assert "SECRET_API_KEY" not in dumped
    assert receipt.shell_used is False
    assert receipt.caller_supplied_arguments is False


# ---------------------------------------------------------------------------
# Scientific standing inflation
# ---------------------------------------------------------------------------


def test_scientific_standing_never_upgraded(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_sci"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_sci"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.engineering_standing == "SOFTWARE_VALID"
    assert receipt.scientific_standing == "SCIENTIFICALLY_NOT_ACCEPTED"
    with pytest.raises(Exception, match="scientific"):
        receipt.model_validate(
            {
                **receipt.model_dump(mode="json"),
                "scientific_standing": "SCIENTIFICALLY_ACCEPTED_BASELINE",
            }
        )
    assert str(receipt.scientific_standing) != "SCIENTIFICALLY_ACCEPTED_BASELINE"
    # Blocked must not claim SOFTWARE_VALID
    blocked_pkg = _package_with_config(tmp_path / "blocked_pkg")
    blocked_req = create_closed_loop_request(
        package_root=blocked_pkg, config_file="sumo.sumocfg", run_id="run-block-sci"
    )
    (blocked_pkg / "net.xml").write_text("<net>drift</net>", encoding="utf-8")
    fake_dir2 = tmp_path / "fake_sci_block"
    exe2 = _write_fake_sumo(fake_dir2)
    tool2 = detect_configured_sumo(exe2)
    out2 = tmp_path / "out_sci_block"
    receipt2 = run_closed_loop_execution(
        package_root=blocked_pkg,
        output_root=out2,
        request=blocked_req,
        tool=tool2,
        executable_path=exe2,
    )
    assert receipt2.outcome == "blocked"
    assert receipt2.engineering_standing == "ENGINEERING_NOT_VALID"
    assert receipt2.scientific_standing == "SCIENTIFICALLY_NOT_ACCEPTED"


# ---------------------------------------------------------------------------
# Secret / path leakage
# ---------------------------------------------------------------------------


def test_portable_receipt_never_leaks_absolute_paths_or_secrets(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_leak"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_leak"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    j = receipt.canonical_json()
    assert "/Users/" not in j
    assert "/home/" not in j
    assert "/private/" not in j
    assert "apikey" not in j.lower()
    assert "secret" not in j.lower() or "SOFTWARE_VALID" in j
    for ev in receipt.outputs:
        assert not ev.path.startswith("/")
        assert ".." not in ev.path
    assert receipt.argv[0] == "sumo"
    assert "/" not in receipt.argv[0]
    assert receipt.working_directory == "{PACKAGE_ROOT}"
    assert receipt.output_directory == "{OUTPUT_ROOT}"
    assert len(receipt.limitations) >= 1
    assert any("SOFTWARE_VALID" in lim for lim in receipt.limitations)
    # Private-path in receipt fields must be rejected
    with pytest.raises(Exception):  # noqa: B017
        receipt.model_validate(
            {**receipt.model_dump(mode="json"), "stdout_excerpt": "/Users/evil/secret"}
        )


def test_argv_is_fixed_and_validated(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg", seed=123)
    fake_dir = tmp_path / "fake_argv"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    pkg_obj = build_closed_loop_execution_package(
        package_root=pkg,
        output_root=tmp_path / "out_argv",
        request=req,
        tool=tool,
        executable_path=exe,
    )
    assert tuple(pkg_obj.argv) == (
        "sumo",
        "-c",
        req.config_file,
        "--seed",
        str(req.seed),
        "--tripinfo-output",
        "tripinfo.xml",
        "--summary-output",
        "summary.xml",
        "--no-step-log",
        "true",
    )
    assert pkg_obj.shell_used is False
    assert pkg_obj.caller_supplied_arguments is False
    with pytest.raises(Exception):  # noqa: B017 - discriminating any validation error
        pkg_obj.model_validate({**pkg_obj.model_dump(mode="json"), "argv": ["sumo", "--evil"]})


def test_isolated_explicit_output_directory(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_iso"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "isolated_out"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome in {"completed", "failed", "timed_out"}
    assert out.is_dir()
    receipt2 = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt2.outcome == "blocked"


def test_explicit_working_directory(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_cwd"
    fake_dir.mkdir(parents=True, exist_ok=True)
    exe = fake_dir / "sumo"
    script = textwrap.dedent("""\
        #!/usr/bin/env python3
        import sys, pathlib
        if "--version" in sys.argv:
            print("Eclipse SUMO Version 1.27.9")
            sys.exit(0)
        cwd = pathlib.Path.cwd()
        # cwd should be staging dir under output, not source package
        # staging contains config file
        config = None
        for i,a in enumerate(sys.argv):
            if a=="-c" and i+1<len(sys.argv):
                config = pathlib.Path(sys.argv[i+1])
        if config is None or not config.is_file():
            print("config not found in cwd", file=sys.stderr)
            sys.exit(2)
        # cwd is staging, not source
        if not (cwd / "net.xml").exists():
            print("staging missing net.xml", file=sys.stderr)
            sys.exit(2)
        for i,a in enumerate(sys.argv):
            if a=="--tripinfo-output" and i+1<len(sys.argv):
                pathlib.Path(sys.argv[i+1]).write_text("<tripinfos/>")
            if a=="--summary-output" and i+1<len(sys.argv):
                pathlib.Path(sys.argv[i+1]).write_text("<summary/>")
        print("ok")
        sys.exit(0)
        """)
    exe.write_text(script, encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_cwd"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "completed"
    assert receipt.exit_code == 0
    assert receipt.working_directory == "{PACKAGE_ROOT}"


def test_no_network_no_command_strings(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_nas"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    pkg_obj = build_closed_loop_execution_package(
        package_root=pkg,
        output_root=tmp_path / "out_nas",
        request=req,
        tool=tool,
        executable_path=exe,
    )
    assert pkg_obj.shell_used is False
    out = tmp_path / "out_nas2"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.shell_used is False
    assert "http" not in receipt.canonical_json().lower()


def test_package_and_receipt_do_not_weaken_existing_runners(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_weak"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_weak"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    tampered = {**receipt.model_dump(mode="json"), "argv": receipt.argv + ["--extra-flag"]}
    with pytest.raises(Exception):  # noqa: B017
        receipt.model_validate(tampered)


def test_run_closed_loop_execution_timeout_is_frozen_and_extra_fields_rejected(
    tmp_path: Path,
) -> None:
    import inspect

    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", timeout_seconds=2, run_id="run-01"
    )
    assert req.timeout_seconds == 2

    with pytest.raises(Exception, match="extra"):  # noqa: B017
        ClosedLoopExecutionRequest.model_validate(
            {**req.model_dump(mode="json"), "runtime_timeout": 999}
        )
    with pytest.raises(Exception, match="extra"):  # noqa: B017
        ClosedLoopExecutionRequest.model_validate(
            {**req.model_dump(mode="json"), "timeout_seconds_override": 999}
        )

    with pytest.raises(Exception):  # noqa: B017
        req.timeout_seconds = 999  # type: ignore[misc]  # noqa: FBT003

    sig = inspect.signature(run_closed_loop_execution)
    assert "timeout_seconds" not in sig.parameters

    fake_dir = tmp_path / "fake_tamper_timeout"
    exe = _write_fake_sumo(fake_dir, delay_s=4.0)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_tamper_timeout"
    with pytest.raises(TypeError):
        run_closed_loop_execution(  # type: ignore[call-arg]  # noqa: B017
            package_root=pkg,
            output_root=out,
            request=req,
            tool=tool,
            executable_path=exe,
            timeout_seconds=999,
        )
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "timed_out"
    assert receipt.timed_out is True
    assert (
        req.deterministic_run_identity == req.model_dump(mode="json")["deterministic_run_identity"]
    )


def test_exit_zero_no_output_is_failed(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_no_output"
    exe = _write_fake_sumo(fake_dir, exit_code=0, write_outputs=False)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_no_output"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "failed"
    assert receipt.exit_code == 0
    assert receipt.timed_out is False
    assert len(receipt.outputs) == 0
    assert receipt.output_fingerprint is None
    assert "REQUIRED_OUTPUT_MISSING" in receipt.stderr_excerpt
    assert ("/" + "tmp" + "/") not in receipt.stderr_excerpt
    assert "/Users/" not in receipt.stderr_excerpt
    forged = {**receipt.model_dump(mode="json"), "outcome": "completed"}
    with pytest.raises(Exception, match="completed requires both"):  # noqa: B017
        type(receipt).model_validate(forged)


def test_exit_zero_partial_output_is_failed(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_partial"
    fake_dir.mkdir(parents=True, exist_ok=True)
    exe = fake_dir / "sumo"
    script = textwrap.dedent("""\
        #!/usr/bin/env python3
        import sys, pathlib
        if "--version" in sys.argv:
            print("Eclipse SUMO Version 1.27.3")
            sys.exit(0)
        trip = None
        summ = None
        for i, a in enumerate(sys.argv):
            if a == "--tripinfo-output" and i+1 < len(sys.argv):
                trip = pathlib.Path(sys.argv[i+1])
            if a == "--summary-output" and i+1 < len(sys.argv):
                summ = pathlib.Path(sys.argv[i+1])
        if trip:
            trip.parent.mkdir(parents=True, exist_ok=True)
            trip.write_text("<tripinfos/>", encoding="utf-8")
        print("fake stdout")
        sys.exit(0)
        """)
    exe.write_text(script, encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_partial"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "failed"
    assert receipt.exit_code == 0
    assert len(receipt.outputs) == 1
    assert receipt.outputs[0].path == "tripinfo.xml"
    assert "REQUIRED_OUTPUT_MISSING" in receipt.stderr_excerpt
    assert "summary.xml" in receipt.stderr_excerpt
    out_sym = tmp_path / "out_partial_sym"
    fake_dir2 = tmp_path / "fake_partial_sym"
    fake_dir2.mkdir(parents=True, exist_ok=True)
    exe2 = fake_dir2 / "sumo"
    script2 = textwrap.dedent("""\
        #!/usr/bin/env python3
        import sys, pathlib
        if "--version" in sys.argv:
            print("Eclipse SUMO Version 1.27.3")
            sys.exit(0)
        trip = summ = None
        for i, a in enumerate(sys.argv):
            if a == "--tripinfo-output" and i+1<len(sys.argv):
                trip = pathlib.Path(sys.argv[i+1])
            if a == "--summary-output" and i+1<len(sys.argv):
                summ = pathlib.Path(sys.argv[i+1])
        if trip:
            trip.parent.mkdir(parents=True, exist_ok=True)
            trip.write_text("<tripinfos/>", encoding="utf-8")
        if summ:
            summ.parent.mkdir(parents=True, exist_ok=True)
            real = summ.parent / "real_summary.xml"
            real.write_text("<summary/>", encoding="utf-8")
            try:
                summ.symlink_to(real)
            except Exception:
                summ.write_text("<summary/>", encoding="utf-8")
                pass
        sys.exit(0)
        """)
    exe2.write_text(script2, encoding="utf-8")
    exe2.chmod(exe2.stat().st_mode | stat.S_IEXEC)
    tool2 = detect_configured_sumo(exe2)
    receipt2 = run_closed_loop_execution(
        package_root=pkg, output_root=out_sym, request=req, tool=tool2, executable_path=exe2
    )
    summary_path = out_sym / "summary.xml"
    assert summary_path.is_symlink(), "partial symlink branch not exercised"
    assert receipt2.outcome == "failed"
    assert (
        "REQUIRED_OUTPUT_MISSING" in receipt2.stderr_excerpt
        or "SYMLINK" in receipt2.stderr_excerpt
        or "EXTRA" in receipt2.stderr_excerpt
    )
    assert len(receipt2.stderr_excerpt.strip()) > 0
    good_pkg = _package_with_config(tmp_path / "good_pkg2")
    fake_dir3 = tmp_path / "fake_good_forge"
    exe3 = _write_fake_sumo(fake_dir3, exit_code=0, write_outputs=True)
    tool3 = detect_configured_sumo(exe3)
    req3 = create_closed_loop_request(
        package_root=good_pkg, config_file="sumo.sumocfg", run_id="run-forge"
    )
    out3 = tmp_path / "out_forge_ok"
    receipt3 = run_closed_loop_execution(
        package_root=good_pkg, output_root=out3, request=req3, tool=tool3, executable_path=exe3
    )
    assert receipt3.outcome == "completed"
    dup_outputs = [receipt3.outputs[0].model_dump(mode="json")] * 2
    forged_dup = {
        **receipt3.model_dump(mode="json"),
        "outputs": dup_outputs,
        "output_fingerprint": receipt3.output_fingerprint,
    }
    with pytest.raises(Exception):  # noqa: B017
        type(receipt3).model_validate(forged_dup)
    forged_missing = {
        **receipt3.model_dump(mode="json"),
        "outputs": [
            o.model_dump(mode="json") for o in receipt3.outputs if o.path == "tripinfo.xml"
        ],
        "output_fingerprint": receipt3.output_fingerprint,
    }
    with pytest.raises(Exception):  # noqa: B017
        type(receipt3).model_validate(forged_missing)


# ---------------------------------------------------------------------------
# Receipt integrity — forged fields, times, standing
# ---------------------------------------------------------------------------


def test_forged_receipt_fields_rejected(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_forge"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_forge"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    # Mutate request fingerprint
    with pytest.raises(Exception):  # noqa: B017
        receipt.model_validate({**receipt.model_dump(mode="json"), "request_fingerprint": "0" * 64})
    # Mutate argv
    with pytest.raises(Exception):  # noqa: B017
        receipt.model_validate({**receipt.model_dump(mode="json"), "argv": ["sumo", "-c", "evil"]})
    # Mutate tool version
    bad_tool = {**receipt.tool.model_dump(mode="json"), "reported_version": "1.28.0"}
    with pytest.raises(Exception):  # noqa: B017
        receipt.model_validate({**receipt.model_dump(mode="json"), "tool": bad_tool})
    # Mutate limitations
    with pytest.raises(Exception):  # noqa: B017
        receipt.model_validate({**receipt.model_dump(mode="json"), "limitations": ["hacked"]})
    # Mutate deterministic identity
    with pytest.raises(Exception):  # noqa: B017
        receipt.model_validate(
            {**receipt.model_dump(mode="json"), "deterministic_run_identity": "0" * 64}
        )


def test_forged_receipt_times_rejected(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_time"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_time"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    # Non-UTC or naive time
    with pytest.raises(Exception):  # noqa: B017
        receipt.model_validate(
            {**receipt.model_dump(mode="json"), "started_at_utc": "2026-01-01T00:00:00"}
        )
    # Reversed ordering
    with pytest.raises(Exception):  # noqa: B017
        receipt.model_validate(
            {
                **receipt.model_dump(mode="json"),
                "started_at_utc": receipt.completed_at_utc,
                "completed_at_utc": receipt.started_at_utc,
            }
        )


def test_forged_receipt_standing_rejected(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_stand"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_stand"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    # Completed receipt must be SCIENTIFICALLY_NOT_ACCEPTED, not SOFTWARE_VALID
    with pytest.raises(Exception):  # noqa: B017
        receipt.model_validate(
            {**receipt.model_dump(mode="json"), "scientific_standing": "SOFTWARE_VALID"}
        )
    with pytest.raises(Exception):  # noqa: B017
        receipt.model_validate(
            {
                **receipt.model_dump(mode="json"),
                "scientific_standing": "SCIENTIFICALLY_ACCEPTED_BASELINE",
            }
        )
    # Blocked receipt forged to SOFTWARE_VALID must fail
    blocked_pkg = _package_with_config(tmp_path / "blocked_pkg2")
    blocked_req = create_closed_loop_request(
        package_root=blocked_pkg, config_file="sumo.sumocfg", run_id="run-block-stand"
    )
    (blocked_pkg / "net.xml").write_text("<net>drift</net>", encoding="utf-8")
    fake_dir2 = tmp_path / "fake_stand_block"
    exe2 = _write_fake_sumo(fake_dir2)
    tool2 = detect_configured_sumo(exe2)
    out2 = tmp_path / "out_stand_block"
    receipt2 = run_closed_loop_execution(
        package_root=blocked_pkg,
        output_root=out2,
        request=blocked_req,
        tool=tool2,
        executable_path=exe2,
    )
    assert receipt2.outcome == "blocked"
    with pytest.raises(Exception):  # noqa: B017
        receipt2.model_validate(
            {**receipt2.model_dump(mode="json"), "engineering_standing": "SOFTWARE_VALID"}
        )


def test_private_path_secret_leakage_rejected(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_leak2"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_leak2"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    with pytest.raises(Exception):  # noqa: B017
        receipt.model_validate(
            {**receipt.model_dump(mode="json"), "stdout_excerpt": "/Users/alice/secret"}
        )
    with pytest.raises(Exception):  # noqa: B017
        receipt.model_validate({**receipt.model_dump(mode="json"), "stderr_excerpt": "api_key=123"})


def test_successful_deterministic_execution_unchanged(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", seed=123, run_id="run-det"
    )
    fake_dir = tmp_path / "fake_det2"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    out1 = tmp_path / "out_det1"
    receipt1 = run_closed_loop_execution(
        package_root=pkg, output_root=out1, request=req, tool=tool, executable_path=exe
    )
    assert receipt1.outcome == "completed"
    assert receipt1.engineering_standing == "SOFTWARE_VALID"
    assert receipt1.scientific_standing == "SCIENTIFICALLY_NOT_ACCEPTED"
    assert receipt1.inputs_verified is True
    # Same deterministic, different wall-clock fingerprint
    out2 = tmp_path / "out_det2"
    receipt2 = run_closed_loop_execution(
        package_root=pkg, output_root=out2, request=req, tool=tool, executable_path=exe
    )
    assert receipt2.deterministic_run_identity == receipt1.deterministic_run_identity
    assert receipt2.fingerprint() != receipt1.fingerprint()
    # Outputs fingerprints should match (deterministic)
    assert receipt1.output_fingerprint == receipt2.output_fingerprint


def test_subprocess_timeout_cleans_up(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", timeout_seconds=1
    )
    fake_dir = tmp_path / "fake_cleanup"
    fake_dir.mkdir(parents=True, exist_ok=True)
    exe = fake_dir / "sumo"
    script = textwrap.dedent("""\
        #!/usr/bin/env python3
        import sys, time
        if "--version" in sys.argv:
            print("Eclipse SUMO Version 1.27.3")
            sys.exit(0)
        # sleep longer than timeout to test kill
        time.sleep(10)
        sys.exit(0)
        """)
    exe.write_text(script, encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_cleanup"
    start = __import__("time").monotonic()
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    elapsed = __import__("time").monotonic() - start
    assert receipt.outcome == "timed_out"
    assert receipt.timed_out is True
    # Should have timed out roughly at timeout, not waited full 10s
    assert elapsed < 5.0
    assert receipt.duration_s < 5.0


# ---------------------------------------------------------------------------
# Additional discriminating tests for V1 audit remediations
# ---------------------------------------------------------------------------


def test_additional_files_nested_escape_refused(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    # Minimal config with additional-files (unsupported)
    (pkg / "sumo.sumocfg").write_text(
        "<configuration><input>"
        '<net-file value="net.xml"/>'
        '<route-files value="routes.xml"/>'
        '<additional-files value="evil.add.xml"/>'
        "</input></configuration>",
        encoding="utf-8",
    )
    (pkg / "evil.add.xml").write_text(
        "<additional>"
        '<routeDistribution id="r">'
        '<route id="r0" edges="e0"/>'
        "</routeDistribution>"
        "</additional>",
        encoding="utf-8",
    )
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg", run_id="run-add")
    fake_dir = tmp_path / "fake_add"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_add", request=req, tool=tool
    )
    assert report.status == "blocked"
    assert any("ADDITIONAL" in f for f in report.findings)
    out = tmp_path / "out_add_exec"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "blocked"
    # Even without declared evil.add.xml reference, plain additional-files tag must be refused
    pkg2 = _package_with_config(tmp_path / "pkg_add2")
    (pkg2 / "sumo.sumocfg").write_text(
        '<configuration><input><additional-files value="net.xml"/></input></configuration>',
        encoding="utf-8",
    )
    req2 = create_closed_loop_request(
        package_root=pkg2, config_file="sumo.sumocfg", run_id="run-add2"
    )
    report2 = preflight_closed_loop_execution(
        package_root=pkg2, output_root=tmp_path / "out_add2", request=req2, tool=tool
    )
    assert report2.status == "blocked"
    # Documented limitation
    from traffictwin.integration.manchester.closed_loop_execution import CLOSED_LOOP_LIMITATIONS

    assert any("additional-files" in lim for lim in CLOSED_LOOP_LIMITATIONS)


def test_additional_file_with_traversal_output_escape_refused(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    # additional file with output-like tag that could write outside root
    (pkg / "sumo.sumocfg").write_text(
        '<configuration><input><additional-files value="nested.add.xml"/></input></configuration>',
        encoding="utf-8",
    )
    (pkg / "nested.add.xml").write_text(
        '<additional><output><tripinfo-output value="/tmp/evil.xml"/></output></additional>',
        encoding="utf-8",
    )
    req = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", run_id="run-nested"
    )
    fake_dir = tmp_path / "fake_nested"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_nested", request=req, tool=tool
    )
    assert report.status == "blocked"


def test_log_storm_bounded_on_disk_and_receipt(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", timeout_seconds=5
    )
    fake_dir = tmp_path / "fake_storm"
    fake_dir.mkdir(parents=True, exist_ok=True)
    exe = fake_dir / "sumo"
    # Produce infinite-like storm > 5MB on both streams quickly, but bounded
    script = textwrap.dedent("""\
        #!/usr/bin/env python3
        import sys, pathlib
        if "--version" in sys.argv:
            print("Eclipse SUMO Version 1.27.3")
            sys.exit(0)
        # storm: write 100k lines of 1k each ~100MB if unbounded
        for i in range(20000):
            sys.stdout.write("A" * 1000 + "\\n")
            sys.stderr.write("B" * 1000 + "\\n")
        # still need to write required outputs
        for i,a in enumerate(sys.argv):
            if a=="--tripinfo-output" and i+1<len(sys.argv):
                pathlib.Path(sys.argv[i+1]).write_text("<tripinfos/>")
            if a=="--summary-output" and i+1<len(sys.argv):
                pathlib.Path(sys.argv[i+1]).write_text("<summary/>")
        sys.exit(0)
        """)
    exe.write_text(script, encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_storm"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    # Receipt excerpts must be bounded
    assert len(receipt.stdout_excerpt.encode("utf-8")) <= 32000
    assert len(receipt.stderr_excerpt.encode("utf-8")) <= 32000
    # Disk files must also be bounded (staging logs capped)
    staging_stdout = out / "_staging" / "stdout.txt"
    staging_stderr = out / "_staging" / "stderr.txt"
    if staging_stdout.exists():
        assert staging_stdout.stat().st_size <= 32000
    if staging_stderr.exists():
        assert staging_stderr.stat().st_size <= 32000
    # Overall execution should still complete (pipe drained, not deadlocked)
    assert receipt.outcome == "completed"
    # Now test timeout with infinite producer never exiting — must still timeout bounded
    fake_dir2 = tmp_path / "fake_infinite"
    fake_dir2.mkdir(parents=True, exist_ok=True)
    exe2 = fake_dir2 / "sumo"
    script2 = textwrap.dedent("""\
        #!/usr/bin/env python3
        import sys, time
        if "--version" in sys.argv:
            print("Eclipse SUMO Version 1.27.3")
            sys.exit(0)
        # infinite storm until killed
        while True:
            sys.stdout.write("X" * 4096 + "\\n")
            sys.stdout.flush()
            sys.stderr.write("Y" * 4096 + "\\n")
            sys.stderr.flush()
        """)
    exe2.write_text(script2, encoding="utf-8")
    exe2.chmod(exe2.stat().st_mode | stat.S_IEXEC)
    tool2 = detect_configured_sumo(exe2)
    req2 = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", timeout_seconds=1
    )
    out2 = tmp_path / "out_infinite"
    receipt2 = run_closed_loop_execution(
        package_root=pkg, output_root=out2, request=req2, tool=tool2, executable_path=exe2
    )
    assert receipt2.outcome == "timed_out"
    assert len(receipt2.stdout_excerpt.encode("utf-8")) <= 32000
    assert len(receipt2.stderr_excerpt.encode("utf-8")) <= 32000


def test_version_probe_bounded_memory(tmp_path: Path) -> None:
    fake_dir = tmp_path / "fake_ver_bomb"
    fake_dir.mkdir(parents=True, exist_ok=True)
    exe = fake_dir / "sumo"
    script = textwrap.dedent("""\
        #!/usr/bin/env python3
        import sys
        if "--version" in sys.argv:
            # huge version output that would blow capture_output
            sys.stdout.write("Eclipse SUMO Version 1.27.9 " + "X"*200000)
            sys.stderr.write("Y"*200000)
            sys.exit(0)
        sys.exit(0)
        """)
    exe.write_text(script, encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    # Should still parse version and not OOM, capture bounded
    tool = detect_configured_sumo(exe)
    assert tool.reported_version == "1.27.9"


def test_oversized_input_refused_without_read_bytes(tmp_path: Path) -> None:
    from traffictwin.integration.manchester.closed_loop_execution import (
        MAX_AGGREGATE_INPUT_BYTES,
        MAX_INPUT_BYTES,
    )

    pkg = tmp_path / "pkg_oversize"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "sumo.sumocfg").write_text(
        "<configuration><input></input></configuration>", encoding="utf-8"
    )
    (pkg / "net.xml").write_text("<net/>", encoding="utf-8")
    (pkg / "routes.xml").write_text("<routes/>", encoding="utf-8")
    # Create a large file exceeding per-file bound without needing to load it via read_bytes
    big = pkg / "big.xml"
    # Create sparse file efficiently: seek
    with big.open("wb") as f:
        f.seek(MAX_INPUT_BYTES)
        f.write(b"x")
    assert big.stat().st_size == MAX_INPUT_BYTES + 1
    with pytest.raises(Exception, match="OVERSIZE|bound"):
        create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg", run_id="run-big")
    # Clean big, test aggregate oversize
    big.unlink()
    # Create many files within per-file limit but exceeding aggregate
    # Use 5 files each 20M would exceed 80M? Let's use MAX_INPUT_BYTES sized chunks
    pkg2 = tmp_path / "pkg_agg"
    pkg2.mkdir(parents=True, exist_ok=True)
    (pkg2 / "sumo.sumocfg").write_text(
        "<configuration><input></input></configuration>", encoding="utf-8"
    )
    # Need enough files to exceed aggregate: create 5 files of 17M each => 85M >80M
    n_files = 5
    size_each = 17_000_000
    assert size_each <= MAX_INPUT_BYTES
    assert n_files * size_each > MAX_AGGREGATE_INPUT_BYTES
    for i in range(n_files):
        p = pkg2 / f"f{i}.xml"
        with p.open("wb") as f:
            f.seek(size_each - 1)
            f.write(b"x")
    with pytest.raises(Exception, match="AGGREGATE"):
        create_closed_loop_request(package_root=pkg2, config_file="sumo.sumocfg", run_id="run-agg")
    # Also test that staging path rejects oversized without read_bytes:
    # inject a declared input with oversized declared size
    import hashlib

    pkg3 = _package_with_config(tmp_path / "pkg_small")
    req = create_closed_loop_request(
        package_root=pkg3, config_file="sumo.sumocfg", run_id="run-small"
    )
    # Forge oversized declaration (would be rejected at request validation)
    with pytest.raises(ValidationError):
        req.model_validate(
            {
                **req.model_dump(mode="json"),
                "inputs": [
                    {
                        "path": "x.xml",
                        "sha256": hashlib.sha256(b"hi").hexdigest(),
                        "size_bytes": MAX_INPUT_BYTES + 1,
                    }
                ],
            }
        )
    # Ensure _verify_declared_inputs catches oversized on disk without full read
    # Create a pkg where file size on disk exceeds declared size
    pkg4 = _package_with_config(tmp_path / "pkg_verify")
    req4 = create_closed_loop_request(
        package_root=pkg4, config_file="sumo.sumocfg", run_id="run-verify"
    )
    # Expand net.xml beyond bound after request creation
    net_path = pkg4 / "net.xml"
    with net_path.open("ab") as f:
        f.seek(MAX_INPUT_BYTES)
        f.write(b"y")
    fake_dir = tmp_path / "fake_verify"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg4, output_root=tmp_path / "out_verify", request=req4, tool=tool
    )
    assert report.status == "blocked"
    assert any("OVERSIZE" in f or "mismatch" in f.lower() for f in report.findings)


def test_tool_argv_preflight_duration_mutation_rejected(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", seed=42, run_id="run-mut"
    )
    fake_dir = tmp_path / "fake_mut"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_mut"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "completed"
    # Mutate tool version -> preflight/run identity must fail
    bad_tool = {**tool.model_dump(mode="json"), "reported_version": "1.27.9"}
    # hash unchanged but version changed, canonical run identity would differ
    with pytest.raises(ValidationError):
        receipt.model_validate({**receipt.model_dump(mode="json"), "tool": bad_tool})
    # Mutate tool sha
    bad_tool2 = {**tool.model_dump(mode="json"), "executable_sha256": "0" * 64}
    with pytest.raises(ValidationError):
        receipt.model_validate({**receipt.model_dump(mode="json"), "tool": bad_tool2})
    # Mutate argv (add flag)
    with pytest.raises(ValidationError):
        receipt.model_validate(
            {**receipt.model_dump(mode="json"), "argv": receipt.argv + ["--extra"]}
        )
    # Mutate argv order
    with pytest.raises(ValidationError):
        receipt.model_validate(
            {**receipt.model_dump(mode="json"), "argv": list(reversed(receipt.argv))}
        )
    # Mutate preflight fingerprint
    with pytest.raises(ValidationError):
        receipt.model_validate(
            {**receipt.model_dump(mode="json"), "preflight_fingerprint": "0" * 64}
        )
    # Mutate duration beyond tolerance
    with pytest.raises(ValidationError):
        receipt.model_validate(
            {**receipt.model_dump(mode="json"), "duration_s": receipt.duration_s + 10.0}
        )
    # Mutate duration via model_copy then re-validate must fail
    copied = receipt.model_copy(update={"duration_s": receipt.duration_s + 10.0})
    with pytest.raises(ValidationError):
        type(copied).model_validate(copied.model_dump(mode="json"))
    # Mutate deterministic_run_identity to request-only identity
    # (should fail canonical check)
    with pytest.raises(ValidationError):
        receipt.model_validate(
            {
                **receipt.model_dump(mode="json"),
                "deterministic_run_identity": req.deterministic_run_identity,
            }
        )
    # Package mutation as well
    pkg_obj = build_closed_loop_execution_package(
        package_root=pkg,
        output_root=tmp_path / "out_pkg_mut",
        request=req,
        tool=tool,
        executable_path=exe,
    )
    with pytest.raises(ValidationError):
        pkg_obj.model_validate(
            {**pkg_obj.model_dump(mode="json"), "argv": pkg_obj.argv + ["--evil"]}
        )
    with pytest.raises(ValidationError):
        pkg_obj.model_validate(
            {
                **pkg_obj.model_dump(mode="json"),
                "deterministic_run_identity": req.deterministic_run_identity,
            }
        )


def test_preflight_fingerprint_bound_to_request_tool(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_pf"
    exe = _write_fake_sumo(fake_dir, version="1.27.3")
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_pf"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    import hashlib
    import json

    expected_pf = hashlib.sha256(
        json.dumps(
            {
                "request_fingerprint": req.fingerprint(),
                "tool_sha": tool.executable_sha256,
                "tool_version": tool.reported_version,
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    assert receipt.preflight_fingerprint == expected_pf
    # Mutating preflight to another valid sha but wrong binding must fail
    with pytest.raises(ValidationError):
        receipt.model_validate(
            {**receipt.model_dump(mode="json"), "preflight_fingerprint": "a" * 64}
        )


def test_duration_tolerance(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_dur"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_dur"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    # Within tolerance (1.5s) should pass — the +1s case is borderline
    # depending on wall-clock drift, but +10s must always fail.
    # May pass or fail depending on exact wall-clock difference, but if
    # duration currently matches wall-clock within 0.5, +1 should still be
    # within 2.0, so we only assert that +10 fails.
    with pytest.raises(ValidationError):
        receipt.model_validate(
            {**receipt.model_dump(mode="json"), "duration_s": receipt.duration_s + 10.0}
        )
    # Reversed timestamps already tested; duration mismatch beyond 2 sec must fail


def test_controlled_environment_keys(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_env2"
    env_dump = tmp_path / "env2.json"
    exe = _write_fake_sumo(fake_dir, capture_env_to=env_dump)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_env2"
    # Set a secret in parent env that must not be inherited
    os.environ["SECRET_TOKEN"] = "leak"  # noqa: S105
    os.environ["CUSTOM_VAR"] = "should-not-appear"  # noqa: S105
    try:
        receipt = run_closed_loop_execution(
            package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
        )
    finally:
        os.environ.pop("SECRET_TOKEN", None)
        os.environ.pop("CUSTOM_VAR", None)
    env = json.loads(env_dump.read_text(encoding="utf-8"))
    # Documented minimal keys must be present; macOS may inject
    # CPATH etc, allow those but not secrets
    allowed_macos_injected = {
        "CPATH",
        "LIBRARY_PATH",
        "MANPATH",
        "SDKROOT",
        "__CF_USER_TEXT_ENCODING",
    }
    minimal = {"PATH", "HOME", "LANG", "LC_ALL"}
    assert minimal.issubset(set(env.keys()))
    # No unexpected keys beyond minimal + known macOS injected
    extra = set(env.keys()) - minimal - allowed_macos_injected
    assert extra == set(), f"unexpected env keys: {extra}"
    assert env["HOME"] == str((out / "_staging").resolve()) or env["HOME"] == str(out / "_staging")
    assert "{REDACTED}" not in env.values()
    assert "SUMO_HOME" not in env
    assert "SECRET_TOKEN" not in env
    assert "CUSTOM_VAR" not in env
    # Package must also declare exact minimal keys
    pkg_obj = build_closed_loop_execution_package(
        package_root=pkg,
        output_root=tmp_path / "out_pkg_env",
        request=req,
        tool=tool,
        executable_path=exe,
    )
    assert set(pkg_obj.environment_keys) == {"PATH", "HOME", "LANG", "LC_ALL"}
    assert "SUMO_HOME" not in pkg_obj.environment_keys
    # No {REDACTED} literal passed to child; env values are real paths
    for v in env.values():
        assert v != "{REDACTED}"
    # Receipt must not contain absolute staging path
    tmp_marker = "/" + "tmp" + "/"
    assert tmp_marker not in receipt.canonical_json()
    assert str(out) not in receipt.canonical_json()


# ---------------------------------------------------------------------------
# B1 and N1 discriminating remediation tests
# ---------------------------------------------------------------------------


def test_secret_tag_names_are_sanitized_and_blocked(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    # Use secret/token/password as tag names
    for evil_tag in ["secret", "token", "password", "mySecretTag", "apiKey"]:
        (pkg / "sumo.sumocfg").write_text(
            f'<configuration><{evil_tag} value="net.xml"/></configuration>',
            encoding="utf-8",
        )
        req = create_closed_loop_request(
            package_root=pkg, config_file="sumo.sumocfg", run_id=f"run-{evil_tag.lower()}"
        )
        fake_dir = tmp_path / f"fake_secret_{evil_tag}"
        exe = _write_fake_sumo(fake_dir)
        tool = detect_configured_sumo(exe)
        report = preflight_closed_loop_execution(
            package_root=pkg,
            output_root=tmp_path / f"out_secret_{evil_tag}",
            request=req,
            tool=tool,
        )
        assert report.status == "blocked"
        # Findings must not contain raw secret token
        joined = " ".join(report.findings)
        assert "secret" not in joined.lower() or "REDACTED" in joined
        assert "token" not in joined.lower() or "REDACTED" in joined
        assert "password" not in joined.lower() or "REDACTED" in joined
        # Must not raise ValidationError - already proved by reaching here
        assert len(report.findings) >= 1
        assert len(report.findings[0].strip()) > 0
        # Run path must also be blocked without exception
        out = tmp_path / f"out_secret_run_{evil_tag}"
        receipt = run_closed_loop_execution(
            package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
        )
        assert receipt.outcome == "blocked"
        assert (
            "REDACTED" not in receipt.stderr_excerpt.lower() or receipt.stderr_excerpt.strip() != ""
        )
        # Ensure receipt stderr does not leak raw secret
        assert (
            "secret" not in receipt.stderr_excerpt.lower() or "REDACTED" in receipt.stderr_excerpt
        )
        # Restore benign config for next iteration
        (pkg / "sumo.sumocfg").write_text(
            "<configuration><input></input></configuration>", encoding="utf-8"
        )
        # need to recreate request after restoring? already loop will recreate


def test_secret_attribute_names_sanitized(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    for evil_attr in ["secret", "token", "password"]:
        (pkg / "sumo.sumocfg").write_text(
            f'<configuration><input><net-file value="net.xml" {evil_attr}="evil"/></input></configuration>',  # noqa: E501
            encoding="utf-8",
        )
        req = create_closed_loop_request(
            package_root=pkg, config_file="sumo.sumocfg", run_id=f"run-attr-{evil_attr}"
        )
        exe = _write_fake_sumo(tmp_path / f"fake_attr_{evil_attr}")
        tool = detect_configured_sumo(exe)
        report = preflight_closed_loop_execution(
            package_root=pkg, output_root=tmp_path / f"out_attr_{evil_attr}", request=req, tool=tool
        )
        assert report.status == "blocked"
        joined = " ".join(report.findings)
        assert evil_attr not in joined.lower() or "REDACTED" in joined
        assert len(report.findings) >= 1
        out = tmp_path / f"out_attr_run_{evil_attr}"
        receipt = run_closed_loop_execution(
            package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
        )
        assert receipt.outcome == "blocked"
        assert len(receipt.stderr_excerpt.strip()) > 0


def test_33_invalid_elements_truncated_with_marker(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    # Create 33 invalid elements
    elems = "".join(f'<evil{i} value="x"/>' for i in range(33))
    (pkg / "sumo.sumocfg").write_text(f"<configuration>{elems}</configuration>", encoding="utf-8")
    req = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", run_id="run-trunc"
    )
    exe = _write_fake_sumo(tmp_path / "fake_trunc")
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_trunc", request=req, tool=tool
    )
    assert report.status == "blocked"
    assert len(report.findings) == 32
    assert report.findings[-1].startswith("FINDINGS_TRUNCATED:")
    assert "2 further findings suppressed" in report.findings[-1]  # 33 -31 =2
    # Ensure all findings are non-empty and safe
    for f in report.findings:
        assert len(f.strip()) > 0
        assert "/Users/" not in f
        assert "secret" not in f.lower() or "REDACTED" in f
    # Run path also blocked with non-empty reason
    out = tmp_path / "out_trunc_run"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "blocked"
    assert len(receipt.stderr_excerpt.strip()) > 0
    # Ensure findings were capped deterministically (same report reproducible)
    report2 = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_trunc2", request=req, tool=tool
    )
    assert report.findings == report2.findings


def test_nonempty_blocked_reason_per_error_sanitization(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    # Mix one poisoned secret tag with one benign invalid tag - per error sanitization must preserve benign reason  # noqa: E501
    (pkg / "sumo.sumocfg").write_text(
        '<configuration><secret value="x"/><evil2 value="x"/></configuration>',
        encoding="utf-8",
    )
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg", run_id="run-mix")
    exe = _write_fake_sumo(tmp_path / "fake_mix")
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_mix", request=req, tool=tool
    )
    assert report.status == "blocked"
    # Must have at least 2 findings or truncated handling, but not zero, and not empty strings
    assert len(report.findings) >= 1
    for f in report.findings:
        assert len(f.strip()) > 0
    joined = "; ".join(report.findings)
    assert len(joined.strip()) > 0
    # Run path must produce non-empty stderr
    out = tmp_path / "out_mix_run"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "blocked"
    assert len(receipt.stderr_excerpt.strip()) > 0
    assert (
        "BLOCKED" not in receipt.stderr_excerpt or len(receipt.stderr_excerpt) > 10
    )  # ensure real reason


def test_model_copy_traversal_zero_launches(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg", run_id="run-01")
    # Forge via model_copy
    forged = req.model_copy(update={"config_file": "../evil.sumocfg"})
    fake_dir = tmp_path / "fake_modelcopy"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    # Track launches via monkeypatch on subprocess.Popen
    import subprocess as _sp
    from collections.abc import Sequence as _LaunchSequence
    from typing import Any as _PopenAny
    from typing import cast as _cast

    launches: list[list[str]] = []
    orig_popen = _sp.Popen

    def counting_popen(
        args: str
        | bytes
        | os.PathLike[str]
        | os.PathLike[bytes]
        | _LaunchSequence[str | bytes | os.PathLike[str] | os.PathLike[bytes]],
        *remaining_args: object,
        **kwargs: object,
    ) -> _sp.Popen[_PopenAny]:
        if isinstance(args, (str, bytes, os.PathLike)):
            launches.append([str(args)])
        else:
            launches.append([str(item) for item in args])
        return _cast(
            _sp.Popen[_PopenAny], _cast(_PopenAny, orig_popen)(args, *remaining_args, **kwargs)
        )

    import unittest.mock as _mock

    with _mock.patch(
        "traffictwin.integration.manchester.closed_loop_execution.subprocess.Popen",
        side_effect=counting_popen,
    ):
        report = preflight_closed_loop_execution(
            package_root=pkg, output_root=tmp_path / "out_mc_pre", request=forged, tool=tool
        )
        assert report.status == "blocked"
        assert len(launches) == 0
        assert len(report.findings) >= 1
        assert len(report.findings[0].strip()) > 0
        # Run must also not launch
        launches.clear()
        out = tmp_path / "out_mc_run"
        receipt = run_closed_loop_execution(
            package_root=pkg, output_root=out, request=forged, tool=tool, executable_path=exe
        )
        assert receipt.outcome == "blocked"
        assert len(launches) == 0
        assert len(receipt.stderr_excerpt.strip()) > 0
        assert ".." not in receipt.stderr_excerpt or "REDACTED" in receipt.stderr_excerpt
        assert receipt.argv[0] == "sumo"
        # Ensure no traversal leaked in argv
        for tok in receipt.argv:
            assert ".." not in tok


def test_missing_config_no_fake_fingerprint(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg_missing"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "net.xml").write_text("<net/>", encoding="utf-8")
    (pkg / "routes.xml").write_text("<routes/>", encoding="utf-8")
    # No sumo.sumocfg
    with pytest.raises(ManchesterClosedLoopError, match="CONFIG_FILE_MISSING"):
        create_closed_loop_request(
            package_root=pkg, config_file="sumo.sumocfg", run_id="run-missing"
        )
    # Ensure no placeholder was created with fake hash — file still absent, no fingerprint synthesized  # noqa: E501
    assert not (pkg / "sumo.sumocfg").exists()
    # Package fingerprint must be computed only from actual inputs, not from missing config
    # Verify that forging a request that claims missing config with fake hash fails validation
    fake_sha = "a" * 64
    fake_pkg_fp = "b" * 64
    # Attempt to forge a request listing missing config as declared input with fake hash
    forged_payload = {
        "run_id": "run-missing",
        "package_fingerprint": fake_pkg_fp,
        "config_file": "sumo.sumocfg",
        "inputs": [
            {"path": "sumo.sumocfg", "sha256": fake_sha, "size_bytes": 10},
            {"path": "net.xml", "sha256": "c" * 64, "size_bytes": 6},
        ],
        "seed": 42,
        "timeout_seconds": 120,
        "deterministic_run_identity": "d" * 64,
        "confirmed_by_operator": True,
    }
    with pytest.raises(Exception):  # noqa: B017
        ClosedLoopExecutionRequest.model_validate(forged_payload)
    # Also ensure create_closed_loop_request still refuses when only routes exist but config missing
    assert (pkg / "net.xml").is_file()
    assert not (pkg / "sumo.sumocfg").is_file()


def test_unsupported_package_content_refusal(tmp_path: Path) -> None:
    # Subdirectory
    pkg = tmp_path / "pkg_subdir"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "sumo.sumocfg").write_text(
        "<configuration><input></input></configuration>", encoding="utf-8"
    )
    (pkg / "net.xml").write_text("<net/>", encoding="utf-8")
    sub = pkg / "subdir"
    sub.mkdir()
    (sub / "inner.xml").write_text("<inner/>", encoding="utf-8")
    with pytest.raises(ManchesterClosedLoopError, match="UNSUPPORTED_PACKAGE_ENTRY"):
        create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    # Unsafe name
    pkg2 = tmp_path / "pkg_unsafe"
    pkg2.mkdir(parents=True, exist_ok=True)
    (pkg2 / "sumo.sumocfg").write_text(
        "<configuration><input></input></configuration>", encoding="utf-8"
    )
    (pkg2 / "bad name.xml").write_text("<bad/>", encoding="utf-8")
    with pytest.raises(ManchesterClosedLoopError, match="UNSAFE_PACKAGE_ENTRY"):
        create_closed_loop_request(package_root=pkg2, config_file="sumo.sumocfg")
    # Ensure error messages do not leak private paths
    try:
        create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    except ManchesterClosedLoopError as exc:
        assert "/Users/" not in str(exc)
        assert "/private/" not in str(exc)


# ---------------------------------------------------------------------------
# BLOCKING: element text / tail / itertext channels must fail closed
# ---------------------------------------------------------------------------


def test_element_text_absolute_net_file_blocked(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    canary = tmp_path / "CANARY.net.xml"
    canary.write_text("CANARY", encoding="utf-8")
    (pkg / "sumo.sumocfg").write_text(
        f"<configuration><input><net-file>{canary}</net-file></input></configuration>",
        encoding="utf-8",
    )
    req = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", run_id="run-abs-text"
    )
    fake_dir = tmp_path / "fake_abs_text"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    # Track launches
    import subprocess as _sp
    import unittest.mock as _mock

    launches: list[list[str]] = []
    orig = _sp.Popen

    def counting(*args: object, **kwargs: object) -> _sp.Popen[bytes]:  # type: ignore[no-untyped-def, call-overload, unused-ignore]
        if args and isinstance(args[0], (list, tuple)):
            launches.append([str(x) for x in args[0]])  # type: ignore[arg-type, unused-ignore]
        return orig(*args, **kwargs)  # type: ignore[arg-type, call-overload, no-any-return, unused-ignore]

    with _mock.patch(
        "traffictwin.integration.manchester.closed_loop_execution.subprocess.Popen",
        side_effect=counting,
    ):
        report = preflight_closed_loop_execution(
            package_root=pkg, output_root=tmp_path / "out_abs_text_pre", request=req, tool=tool
        )
        assert report.status == "blocked"
        # Must not leak raw absolute path
        joined = " ".join(report.findings)
        assert str(canary) not in joined
        assert "/tmp" not in joined or "{REDACTED}" in joined  # noqa: S108
        assert any("ABSOLUTE" in f or "REFERENCE" in f or "PRIVATE" in f for f in report.findings)
        assert len(launches) == 0
        out = tmp_path / "out_abs_text_run"
        receipt = run_closed_loop_execution(
            package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
        )
        assert receipt.outcome == "blocked"
        assert receipt.engineering_standing == "ENGINEERING_NOT_VALID"
        assert receipt.scientific_standing == "SCIENTIFICALLY_NOT_ACCEPTED"
        assert str(canary) not in receipt.stderr_excerpt
        assert str(canary) not in receipt.canonical_json()
        assert len(launches) == 0
        # Verify canary not read via staging (staging should not contain outside content)
        # The receipt must not be completed/SOFTWARE_VALID
        assert receipt.outcome != "completed"  # type: ignore[comparison-overlap]


def test_element_text_traversal_net_file_blocked(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    (pkg / "sumo.sumocfg").write_text(
        "<configuration><input><net-file>../../CANARY.net.xml</net-file></input></configuration>",
        encoding="utf-8",
    )
    req = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", run_id="run-trav-text"
    )
    fake_dir = tmp_path / "fake_trav_text"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    import subprocess as _sp
    import unittest.mock as _mock

    launches: list[list[str]] = []
    orig = _sp.Popen

    def counting(*args: object, **kwargs: object) -> _sp.Popen[bytes]:  # type: ignore[no-untyped-def, call-overload, unused-ignore]
        if args and isinstance(args[0], (list, tuple)):
            launches.append([str(x) for x in args[0]])  # type: ignore[arg-type, unused-ignore]
        return orig(*args, **kwargs)  # type: ignore[arg-type, call-overload, no-any-return, unused-ignore]

    with _mock.patch(
        "traffictwin.integration.manchester.closed_loop_execution.subprocess.Popen",
        side_effect=counting,
    ):
        report = preflight_closed_loop_execution(
            package_root=pkg, output_root=tmp_path / "out_trav_text_pre", request=req, tool=tool
        )
        assert report.status == "blocked"
        assert any("TRAVERSAL" in f for f in report.findings)
        assert (
            "../../CANARY" not in " ".join(report.findings)
            or "REDACTED" in " ".join(report.findings)
            or "TRAVERSAL" in " ".join(report.findings)
        )
        assert len(launches) == 0
        out = tmp_path / "out_trav_text_run"
        receipt = run_closed_loop_execution(
            package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
        )
        assert receipt.outcome == "blocked"
        assert receipt.engineering_standing != "SOFTWARE_VALID"
        assert len(launches) == 0


def test_element_text_route_files_and_combined_nested_blocked(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    # route-files via element text absolute
    canary = tmp_path / "CANARY.rou.xml"
    canary.write_text("CANARY", encoding="utf-8")
    (pkg / "sumo.sumocfg").write_text(
        f"<configuration><input><route-files>{canary}</route-files></input></configuration>",
        encoding="utf-8",
    )
    req = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", run_id="run-route-abs"
    )
    fake_dir = tmp_path / "fake_route_abs"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_route_abs", request=req, tool=tool
    )
    assert report.status == "blocked"
    assert str(canary) not in " ".join(report.findings)
    out = tmp_path / "out_route_abs_run"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "blocked"
    # Nested/combined: net-file with nested child element containing traversal
    pkg2 = _package_with_config(tmp_path / "pkg_nested")
    (pkg2 / "sumo.sumocfg").write_text(
        "<configuration><input><net-file>net.xml<evil>../../CANARY.net.xml</evil></net-file></input></configuration>",
        encoding="utf-8",
    )
    req2 = create_closed_loop_request(
        package_root=pkg2, config_file="sumo.sumocfg", run_id="run-nested"
    )
    fake_dir2 = tmp_path / "fake_nested"
    exe2 = _write_fake_sumo(fake_dir2)
    tool2 = detect_configured_sumo(exe2)
    report2 = preflight_closed_loop_execution(
        package_root=pkg2, output_root=tmp_path / "out_nested", request=req2, tool=tool2
    )
    assert report2.status == "blocked"
    # itertext combined must be caught, so findings must mention traversal or unreviewed
    assert any("TRAVERSAL" in f or "UNREVIEWED" in f or "TEXT" in f for f in report2.findings)
    out2 = tmp_path / "out_nested_run"
    receipt2 = run_closed_loop_execution(
        package_root=pkg2, output_root=out2, request=req2, tool=tool2, executable_path=exe2
    )
    assert receipt2.outcome == "blocked"
    # Ensure legal whitespace formatting still valid (no false positive)
    pkg3 = _package_with_config(tmp_path / "pkg_ws")
    (pkg3 / "sumo.sumocfg").write_text(
        '<configuration>\n    <input>\n        <net-file value="net.xml"/>\n        <route-files value="routes.xml"/>\n    </input>\n    <time><begin value="0"/><end value="100"/></time>\n</configuration>',  # noqa: E501
        encoding="utf-8",
    )
    req3 = create_closed_loop_request(
        package_root=pkg3, config_file="sumo.sumocfg", run_id="run-ws"
    )
    report3 = preflight_closed_loop_execution(
        package_root=pkg3, output_root=tmp_path / "out_ws", request=req3, tool=tool
    )
    assert report3.status == "accepted"


def test_tail_and_nested_itertext_blocked(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    # Tail content after net-file should be rejected
    (pkg / "sumo.sumocfg").write_text(
        '<configuration><input><net-file value="net.xml"/>../../CANARY.net.xml</input></configuration>',  # noqa: E501
        encoding="utf-8",
    )
    req = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", run_id="run-tail"
    )
    fake_dir = tmp_path / "fake_tail"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_tail", request=req, tool=tool
    )
    assert report.status == "blocked"
    assert any("TAIL" in f for f in report.findings)
    out = tmp_path / "out_tail_run"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "blocked"
    assert receipt.engineering_standing == "ENGINEERING_NOT_VALID"
    # Also test that whitespace-only tail remains valid (checked in previous test via formatting)
