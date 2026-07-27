# Forked-child segfault in the accepted TOS reader — diagnosis and repair

`tests/ui/test_tos_analysis_pages.py` emitted a burst of `Fatal Python error: Segmentation
fault` dumps on every affected run while all four tests passed. This record is the
reproduction, the measured mechanism, the repair, and what was measured about the repair.

- Recorded: 27 July 2026
- Platform: macOS 25.4.0, arm64, CPython 3.12.13 (uv-managed)
- Status: diagnosed and repaired in one source file; no public API and no returned value
  changed

## Reproduction

```bash
uv run pytest tests/ui/test_tos_analysis_pages.py -q 2>&1 | grep -c "Fatal Python error"
```

**Measured over 14 baseline runs.** Six runs printed **exactly 13** segfault dumps; eight
printed **zero**. The count was never anything else — the behaviour is bimodal per process,
not per call. Every run exited `0` with `4 passed`, which is why this survived so long: the
faults are invisible to the exit status.

## Mechanism

Every one of the 13 dumps has the same innermost project frame. Taken verbatim from a
captured run:

```
Current thread 0x000000016c35b000 (most recent call first):
  File ".../python3.12/subprocess.py", line 1885 in _execute_child
  File ".../python3.12/subprocess.py", line 1026 in __init__
  File ".../python3.12/subprocess.py", line 548 in run
  File ".../src/traffictwin/integration/tos/readers.py", line 256 in package_git_commit
  File ".../src/traffictwin/integration/tos/readers.py", line 280 in package_fingerprint
  File ".../src/traffictwin/integration/tos/validation.py", line 263 in inspect_tos_package
  File ".../src/traffictwin/integration/tos/validation.py", line 304 in validate_tos_package
  File ".../src/traffictwin/ui/services/tos.py", line 78 in inspect_tos_for_ui
  File ".../src/traffictwin/ui/tos_context.py", line 24 in active_tos_package
  File ".../src/traffictwin/ui/pages/tos_replay.py", line 43 in render
  ...
  File ".../streamlit/runtime/scriptrunner/script_runner.py", line 418 in _run_script_thread
```

`subprocess.py:1885` is `self.pid = _fork_exec(...)` — CPython's forking path.

**Frame counts across the 13 dumps of one captured run**, which is how "every dump is this
one call site" was established rather than assumed:

| Innermost project frame | Dumps |
|---|---:|
| `readers.py:256` (`subprocess.run` inside `package_git_commit`) | 13 of 13 |

Reached by three routes, all of which call the same function:

| Entry route | Dumps |
|---|---:|
| `package_fingerprint` (`readers.py:280`) | 8 |
| `inspect_tos_package` / `validate_tos_package` (`validation.py:263`, `:275`, `:304`) | 3 |
| `audit_tos_package` (`audit.py:122`, `:123`) | 2 |

Rendered from three pages: `tos_training_audit.py` (10 frames), `tos_results.py` (6), and
`tos_replay.py` (2).

**The mechanism is fork-after-threads on macOS.** `package_git_commit` shells out to
`git rev-parse HEAD`. `subprocess.run(..., capture_output=True)` leaves `close_fds` at its
default `True`, and CPython's `posix_spawn` fast path (`subprocess.py:1825`) requires
`not close_fds` — so the call falls through to `_fork_exec`. That fork happens on a Streamlit
script-runner **thread**, in a process that also holds the AppTest main thread and Streamlit's
own worker. Forking a multithreaded process on macOS and then doing anything before `exec`
that is not async-signal-safe is undefined; the child faults, and pytest's faulthandler —
enabled by default and inherited across the fork — prints the shared thread state, which is
why each dump shows the *parent's* Streamlit and pytest frames rather than a child stack.

**What was ruled out by measurement, not by argument.** Disabling CPython's vfork fast path
(`subprocess._USE_VFORK = False`) across six runs still produced 13 dumps on three of them.
The fault is plain `fork()` in a threaded process, not the vfork variant specifically.

**What was not established.** The bimodal 0-or-13 pattern is per process: a run either faults
on 13 calls or on none. The process-level condition that decides this was not identified. It
does not change the repair — removing the fork removes both branches — but it is recorded as
an open observation rather than explained away.

## Impact, measured rather than assumed

The parent swallows any child failure: `package_git_commit` catches `(OSError,
subprocess.SubprocessError)` and returns `None`. That structure means a dying child would be
indistinguishable from "this package is not a git checkout", and `package_fingerprint` folds
the result in as the literal `no-git-commit`. So the *shape* of a silent wrong answer exists.

**It was looked for and not found.** Two measurements:

1. Instrumenting the failing test file recorded 16 `package_git_commit` calls per run, all
   returning `None` — but the test package is a `tmp_path` directory with no `.git`, so
   `git rev-parse HEAD` legitimately fails there and `None` is the correct answer either way.
   That run cannot distinguish a swallowed crash from a correct refusal.
2. A separate probe called the pre-fix (`close_fds=True`) lookup against a **real checkout**
   from a thread pool inside a process holding eight further live threads: 600 calls across
   three runs returned **zero** `None` results and exactly **one** distinct commit, with no
   faults at all.

So the honest statement is: the observed defect is the dump noise, and no lost or wrong
return value was reproduced. The silent-failure structure is a latent risk this repair also
removes, not a bug that was caught misbehaving.

## Candidate repairs considered

| Candidate | Verdict |
|---|---|
| Disable `_USE_VFORK` | **Rejected — measured ineffective.** 13 dumps still appeared on 3 of 6 runs, and mutating a CPython private global from library code is worse than the problem. |
| Guard on `(package / ".git").exists()` before shelling out | **Rejected — changes returned values.** `git -C <dir> rev-parse HEAD` walks up to an enclosing repository, so a package nested inside a checkout currently reports that repository's commit; the guard would return `None` instead. Matching today's answer exactly would mean reimplementing git's discovery rules, including worktree `.git` files and `GIT_CEILING_DIRECTORIES`. |
| Read `.git/HEAD` and the ref directly, no subprocess | **Rejected — too large.** It reimplements git plumbing (`packed-refs`, detached HEAD, worktree indirection) inside a reader whose contract is "return what git says". |
| Memoise before any thread starts | **Rejected — does not apply.** The first call already happens on a script-runner thread; there is no earlier point to memoise from. |
| **`close_fds=False`, taking CPython's `posix_spawn` path** | **Adopted.** |

## The repair

One keyword in one function, `src/traffictwin/integration/tos/readers.py`:

```python
result = subprocess.run(
    [git, "-C", str(package), "rev-parse", "HEAD"],
    check=True,
    capture_output=True,
    text=True,
    timeout=5,
    close_fds=False,
)
```

This satisfies every condition CPython requires for `posix_spawn` at `subprocess.py:1825`:
`_USE_POSIX_SPAWN` is `True` on darwin, `shutil.which("git")` returns an absolute path so the
executable has a directory component, there is no `preexec_fn`, no `pass_fds`, no `cwd` (the
command uses `git -C` instead), the capture pipes are above fd 2, and no session, process
group, uid, gid, or umask option is set. `posix_spawn` is a syscall on macOS; it does not
fork the calling process.

**Why `close_fds=False` is not an fd-safety relaxation here.** Since PEP 446 (Python 3.4),
descriptors Python creates are non-inheritable by default, so the spawned child receives the
same descriptors under either setting. The residual difference is descriptors created by C
extensions without `O_CLOEXEC`, inherited by a `git rev-parse` child that lives for
milliseconds and immediately execs. The command, its arguments, its parsing, its timeout, its
exception handling, and its return values are untouched.

## Verification

| Measurement | Before | After |
|---|---|---|
| Runs of `tests/ui/test_tos_analysis_pages.py` | 14 | 10 |
| Runs printing 13 segfault dumps | 6 | **0** |
| Runs printing 0 dumps | 8 | **10** |
| Test outcome | 4 passed | 4 passed |

Ten consecutive clean runs, against a required three. Full suites after the repair: **3,126
passed** across `tests/unit` and `tests/ui`, with Ruff, Ruff format, strict mypy, and
`git diff --check` clean.

A focused regression test in `tests/unit/test_tos_integration.py` asserts the call stays on
the non-forking path and that both return branches still produce their previous values. It
asserts the mechanism deliberately: the fault kills only a transient child, so the parent
process — and therefore any behavioural assertion — survives it unchanged. There is no
outcome to assert on, only the call shape that causes it.

## Boundaries

Nothing about TOS package validation, admission, fingerprinting, or capability status
changes. `package_fingerprint` hashes the same bytes and folds in the same commit value; no
recorded fingerprint moves. This is a host-platform process-spawning repair inside one
accepted reader, at the scale of the Phase 18 dtype repair.
