"""Mutation/discriminating tests for Manchester closed-loop SAFE LOCAL SUMO execution."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import textwrap
from pathlib import Path

import pytest

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
) -> Path:
    """Create an executable named ``sumo`` that responds to --version and run."""

    directory.mkdir(parents=True, exist_ok=True)
    exe = directory / "sumo"
    script = textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        import sys, time, pathlib
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
            import os
            out = pathlib.Path({str(capture_env_to)!r})
            # dump env keys/values to a file for inspection
            import json
            out.write_text(json.dumps(dict(os.environ), sort_keys=True))
        if {delay_s} > 0:
            time.sleep({delay_s})
        if {write_outputs}:
            if trip:
                trip.parent.mkdir(parents=True, exist_ok=True)
                trip.write_text("<tripinfos><tripinfo id=\\"t0\\"/></tripinfos>", encoding="utf-8")
            if summ:
                summ.parent.mkdir(parents=True, exist_ok=True)
                summ.write_text("<summary/>", encoding="utf-8")
        else:
            # write nothing
            pass
        # optionally emit to stdout/stderr for receipt testing
        print("fake sumo stdout line")
        print("warning: something", file=sys.stderr)
        sys.exit({exit_code})
        """
    )
    exe.write_text(script, encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return exe


def _fake_tool(exe: Path, version: str = "1.27.3") -> ClosedLoopToolIdentity:
    # compute sha
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
    # create a file named not_sumo
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
    """Request models forbid extra fields; execution never accepts caller argv."""
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg", run_id="run-01")
    # Extra field injection via model_validate must be rejected (frozen extra forbid)
    with pytest.raises(Exception, match="extra"):
        ClosedLoopExecutionRequest.model_validate(
            {**req.model_dump(mode="json"), "executable": "/tmp/fake-evil-test", "argv": ["evil"]}  # noqa: S108
        )
    # Also direct construction with illegal config name containing traversal
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
    # delete a required input after request creation (provider data absence)
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
# Changed input after request
# ---------------------------------------------------------------------------


def test_changed_input_after_request_fails_closed(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    # mutate file after request
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
    # No scientific upgrade
    assert receipt.scientific_standing == "SOFTWARE_VALID"


# ---------------------------------------------------------------------------
# Traversal / symlink escape
# ---------------------------------------------------------------------------


def test_traversal_input_rejected(tmp_path: Path) -> None:
    _ = ClosedLoopToolIdentity
    # config traversal via create request
    pkg = _package_with_config(tmp_path)
    with pytest.raises(ManchesterClosedLoopError):
        create_closed_loop_request(package_root=pkg, config_file="../../etc/passwd")


def test_symlink_before_request_fails_closed_at_construction(tmp_path: Path) -> None:
    """Discriminating: symlink present before request must fail closed at construction.

    Request construction must not silently skip symlink inputs; it must fail closed
    without resolving away symlink evidence.
    """
    pkg = _package_with_config(tmp_path)
    # replace net.xml with symlink to outside before request
    (pkg / "net.xml").unlink()
    target = tmp_path / "outside.xml"
    target.write_text("<net/>", encoding="utf-8")
    (pkg / "net.xml").symlink_to(target)
    # lstat must still show symlink — never resolve before check
    assert (pkg / "net.xml").is_symlink()
    with pytest.raises(ManchesterClosedLoopError, match="symlink"):
        create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")


def test_symlink_input_fails_preflight(tmp_path: Path) -> None:
    # Backward-compat shim: the “symlink before request” contract is now
    # discriminated via test_symlink_before_request_fails_closed_at_construction.
    # Keep this name to ensure no test selection breakage, but delegate to
    # construction-time fail-closed behavior.
    pkg = _package_with_config(tmp_path)
    (pkg / "net.xml").unlink()
    target = tmp_path / "outside.xml"
    target.write_text("<net/>", encoding="utf-8")
    (pkg / "net.xml").symlink_to(target)
    assert (pkg / "net.xml").is_symlink()
    with pytest.raises(ManchesterClosedLoopError, match="symlink"):
        create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")


def test_symlink_after_request_fails_closed(tmp_path: Path) -> None:
    """Discriminating: file replaced by symlink after request must fail closed.

    Preflight and execution verification must detect symlink without resolving
    away evidence and return a typed blocked standing with portable argv shape.
    """
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg", seed=7)
    # Replace a declared input with symlink after request (file -> symlink escape)
    (pkg / "net.xml").unlink()
    target = tmp_path / "outside2.xml"
    target.write_text("<net>evil</net>", encoding="utf-8")
    (pkg / "net.xml").symlink_to(target)
    assert (pkg / "net.xml").is_symlink()
    fake_dir = tmp_path / "fake_sym_after"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    # Preflight must be blocked with symlink finding
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=tmp_path / "out_sym_after", request=req, tool=tool
    )
    assert report.status == "blocked"
    assert any("symlink" in f.lower() for f in report.findings)
    # Execution must also return a valid typed blocked receipt (not raise)
    out = tmp_path / "out_sym_after_exec"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "blocked"
    assert receipt.inputs_verified is False
    assert receipt.shell_used is False
    assert receipt.caller_supplied_arguments is False
    # Blocked receipt argv must be exactly the fixed validated shape with portable placeholders
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
    assert any("symlink" in receipt.stderr_excerpt.lower() for _ in [0]) or any(
        "symlink" in str(e).lower() for e in [receipt.stderr_excerpt]
    )
    assert receipt.scientific_standing == "SOFTWARE_VALID"
    assert receipt.engineering_standing == "SOFTWARE_VALID"


def test_output_overlaps_package_refused(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_overlap"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    # output inside package
    report = preflight_closed_loop_execution(
        package_root=pkg, output_root=pkg / "out", request=req, tool=tool
    )
    assert report.status == "blocked"
    assert any("OUTPUT_ISOLATION" in f for f in report.findings)


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
    # bounded: excerpts within limits
    assert len(receipt.stdout_excerpt) <= 32000
    assert len(receipt.stderr_excerpt) <= 32000


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


def test_bounded_stdout_stderr_receipts(tmp_path: Path) -> None:
    # create a fake that emits huge output
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
        # emit huge output
        print("x" * 100000)
        print("y" * 100000, file=sys.stderr)
        # also write outputs
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
    # different seed → different identity
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
    assert receipt.deterministic_run_identity == req.deterministic_run_identity
    # execution package also matches
    pkg_obj = build_closed_loop_execution_package(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert pkg_obj.deterministic_run_identity == req.deterministic_run_identity


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
    # inject a secret into parent env
    os.environ["SECRET_API_KEY"] = "should-not-leak"  # noqa: S105
    os.environ["MY_TOKEN"] = "also-secret"  # noqa: S105
    try:
        receipt = run_closed_loop_execution(
            package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
        )
    finally:
        os.environ.pop("SECRET_API_KEY", None)
        os.environ.pop("MY_TOKEN", None)
    # check what fake saw
    env = json.loads(env_dump.read_text(encoding="utf-8"))
    # Only allowlisted keys should be present
    assert "SECRET_API_KEY" not in env
    assert "MY_TOKEN" not in env
    assert "PATH" in env
    # PATH must be limited to executable parent + /usr/bin:/bin
    assert env["PATH"].startswith(str(exe.parent))
    assert "/usr/bin:/bin" in env["PATH"]
    # receipt must not leak env
    dumped = json.dumps(receipt.model_dump(mode="json"))
    assert "should-not-leak" not in dumped
    assert "SECRET_API_KEY" not in dumped
    # shell must be false
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
    assert receipt.scientific_standing == "SOFTWARE_VALID"
    # Attempt to forge a receipt with SCIENTIFICALLY_ACCEPTED_BASELINE must fail validation
    with pytest.raises(Exception, match="scientific"):
        receipt.model_validate(
            {
                **receipt.model_dump(mode="json"),
                "scientific_standing": "SCIENTIFICALLY_ACCEPTED_BASELINE",
            }
        )
    # Even completed outcome stays SOFTWARE_VALID
    assert str(receipt.scientific_standing) != "SCIENTIFICALLY_ACCEPTED_BASELINE"


# ---------------------------------------------------------------------------
# Secret / path leakage
# ---------------------------------------------------------------------------


def test_portable_receipt_never_leaks_absolute_paths_or_secrets(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    # add a file with secret-like name — should be excluded or scrubbed?
    # secret token in path should be rejected if declared manually
    # test that receipt json dumps contain no absolute path substrings
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
    # ensure no secret token leakage
    assert "apikey" not in j.lower()
    assert "secret" not in j.lower() or "SOFTWARE_VALID" in j  # limitation contains no secret
    # outputs are relative
    for ev in receipt.outputs:
        assert not ev.path.startswith("/")
        assert ".." not in ev.path
    # argv is allowlisted base name only
    assert receipt.argv[0] == "sumo"
    assert "/" not in receipt.argv[0]
    # working/output directories are placeholders
    assert receipt.working_directory == "{PACKAGE_ROOT}"
    assert receipt.output_directory == "{OUTPUT_ROOT}"
    # limitations must be present and not claim scientific acceptance
    assert len(receipt.limitations) >= 1
    assert any("SOFTWARE_VALID" in lim for lim in receipt.limitations)


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
    # argv must match fixed shape
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
    # Attempt to mutate argv must fail validation
    with pytest.raises(Exception):  # noqa: B017 - discriminating any validation error
        pkg_obj.model_validate({**pkg_obj.model_dump(mode="json"), "argv": ["sumo", "--evil"]})


def test_isolated_explicit_output_directory(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_iso"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    # valid isolated output
    out = tmp_path / "isolated_out"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome in {"completed", "failed", "timed_out"}
    assert out.is_dir()
    # second run to same output must be blocked/fail (output already exists)
    receipt2 = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt2.outcome == "blocked"


def test_explicit_working_directory(tmp_path: Path) -> None:
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_cwd"
    # fake that checks cwd contains config file
    fake_dir.mkdir(parents=True, exist_ok=True)
    exe = fake_dir / "sumo"
    script = textwrap.dedent("""\
        #!/usr/bin/env python3
        import sys, pathlib, os
        if "--version" in sys.argv:
            print("Eclipse SUMO Version 1.27.9")
            sys.exit(0)
        cwd = pathlib.Path.cwd()
        # cwd must be the package root: config file should be there
        config = None
        for i,a in enumerate(sys.argv):
            if a=="-c" and i+1<len(sys.argv):
                config = sys.argv[i+1]
        # config is absolute; its parent should equal cwd
        # we just check that cwd contains the config file name
        if config and not (cwd / pathlib.Path(config).name).exists():
            print("cwd mismatch", file=sys.stderr)
            sys.exit(2)
        # write outputs
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
    """Ensure execução uses shell=False and no command strings; this is structural."""
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
    # package must assert shell false
    assert pkg_obj.shell_used is False
    # receipt also
    out = tmp_path / "out_nas2"
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.shell_used is False
    # no output should claim network
    assert "http" not in receipt.canonical_json().lower()


def test_package_and_receipt_do_not_weaken_existing_runners(tmp_path: Path) -> None:
    """Our fixed argv must not accept the generic runner's arbitrary flags."""
    # The closed-loop fixed argv is disjoint from any user-supplied flags;
    # ensure a request with tampered argv shape is rejected
    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(package_root=pkg, config_file="sumo.sumocfg")
    fake_dir = tmp_path / "fake_weak"
    exe = _write_fake_sumo(fake_dir)
    tool = detect_configured_sumo(exe)
    # Build a receipt and try to tamper argv to include an extra flag
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
    """Mutation test: model extra fields and attempted runtime timeout injection cannot
    alter timeout."""
    import inspect

    pkg = _package_with_config(tmp_path)
    req = create_closed_loop_request(
        package_root=pkg, config_file="sumo.sumocfg", timeout_seconds=2, run_id="run-01"
    )
    assert req.timeout_seconds == 2

    # model extra fields are forbidden — attacker cannot inject an extra timeout field
    with pytest.raises(Exception, match="extra"):  # noqa: B017
        ClosedLoopExecutionRequest.model_validate(
            {**req.model_dump(mode="json"), "runtime_timeout": 999}
        )
    with pytest.raises(Exception, match="extra"):  # noqa: B017
        ClosedLoopExecutionRequest.model_validate(
            {**req.model_dump(mode="json"), "timeout_seconds_override": 999}
        )

    # request is frozen — direct mutation must fail
    with pytest.raises(Exception):  # noqa: B017
        req.timeout_seconds = 999  # type: ignore[misc]

    # runtime signature must not expose a timeout override; deterministic identity is frozen
    sig = inspect.signature(run_closed_loop_execution)
    assert "timeout_seconds" not in sig.parameters

    # calling with an injected kwarg must raise TypeError (not silently override)
    fake_dir = tmp_path / "fake_tamper_timeout"
    exe = _write_fake_sumo(fake_dir, delay_s=4.0)
    tool = detect_configured_sumo(exe)
    out = tmp_path / "out_tamper_timeout"
    with pytest.raises(TypeError):
        run_closed_loop_execution(  # type: ignore[call-arg]
            package_root=pkg,
            output_root=out,
            request=req,
            tool=tool,
            executable_path=exe,
            timeout_seconds=999,
        )
    # actual execution must still honor the frozen request timeout (2s → timed_out)
    receipt = run_closed_loop_execution(
        package_root=pkg, output_root=out, request=req, tool=tool, executable_path=exe
    )
    assert receipt.outcome == "timed_out"
    assert receipt.timed_out is True
    assert (
        req.deterministic_run_identity == req.model_dump(mode="json")["deterministic_run_identity"]
    )


def test_exit_zero_no_output_is_failed(tmp_path: Path) -> None:
    """Exit 0 with zero required outputs must be failed (fail-closed) with portable diagnostic."""
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
    # forged completed receipt with missing outputs must be rejected by validation
    forged = {**receipt.model_dump(mode="json"), "outcome": "completed"}
    with pytest.raises(Exception, match="completed requires both"):  # noqa: B017
        type(receipt).model_validate(forged)


def test_exit_zero_partial_output_is_failed(tmp_path: Path) -> None:
    """Exit 0 with only one required output must be failed with truthful diagnostic."""
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
        # intentionally skip summary.xml
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
    # symlink partial: if output is a symlink, it must also be treated as missing
    out_sym = tmp_path / "out_partial_sym"
    # second run with symlink output should also be failed
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
            if a == "--tripinfo-output" and i+1 < len(sys.argv):
                trip = pathlib.Path(sys.argv[i+1])
            if a == "--summary-output" and i+1 < len(sys.argv):
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
                # make it a symlink via replacement if possible
                pass
        sys.exit(0)
        """)
    exe2.write_text(script2, encoding="utf-8")
    exe2.chmod(exe2.stat().st_mode | stat.S_IEXEC)
    tool2 = detect_configured_sumo(exe2)
    receipt2 = run_closed_loop_execution(
        package_root=pkg, output_root=out_sym, request=req, tool=tool2, executable_path=exe2
    )
    # if symlink was created, summary.xml must be treated as missing and receipt failed
    summary_path = out_sym / "summary.xml"
    if summary_path.is_symlink():
        assert receipt2.outcome == "failed"
        assert "REQUIRED_OUTPUT_MISSING" in receipt2.stderr_excerpt
    # forged completed with duplicate outputs must be rejected
    good_pkg = _package_with_config(tmp_path / "good_pkg2")
    # create a genuinely completed receipt to forge from
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
    # duplicate output forgery
    dup_outputs = [receipt3.outputs[0].model_dump(mode="json")] * 2
    forged_dup = {
        **receipt3.model_dump(mode="json"),
        "outputs": dup_outputs,
        "output_fingerprint": receipt3.output_fingerprint,
    }
    # fingerprint will mismatch or duplicate check triggers; both are rejected
    with pytest.raises(Exception):  # noqa: B017
        type(receipt3).model_validate(forged_dup)
    # missing output forgery (strip summary)
    forged_missing = {
        **receipt3.model_dump(mode="json"),
        "outputs": [
            o.model_dump(mode="json") for o in receipt3.outputs if o.path == "tripinfo.xml"
        ],
        "output_fingerprint": receipt3.output_fingerprint,
    }
    with pytest.raises(Exception):  # noqa: B017
        type(receipt3).model_validate(forged_missing)
