# v0.7 main-branch release integration

## Decision and scope

- Date: 3 August 2026
- Owner direction: integrate the complete `claude/complete-v0.7` line into `main`
  and make `main` carry the TrafficTwin `0.7.0` package identity.
- Previous remote `main`: `2f297d6` (`feat: refresh BODS live positions automatically`)
- Integrated feature head: `c3e2dc8` (`phase 198: add provider contract intake`)
- Integration shape: conflict-free fast-forward of the nine feature commits that were
  ahead of the previous remote `main`, followed by one release-reconciliation commit.

The immutable `v0.6.0` tag and its commit remain unchanged. No force-push or tag move is
part of this integration.

## Release identity reconciliation

The following current surfaces now agree on `0.7.0`:

- `pyproject.toml`;
- `src/traffictwin/__init__.py`;
- `CITATION.cff`;
- installed release metadata;
- `uv.lock`;
- the generated dissertation software-version appendix;
- package, deployment and operator documentation; and
- the v0.7 release-reconciliation tests.

The release remains labelled **research prototype; not production-ready**. Package identity
does not accept a scientific capability, create real evidence or turn an unavailable source
into a live service. The canonical capability and residual-boundary truth remains in
[`docs/implementation-status.md`](../implementation-status.md).

## Verification performed

| Check | Result |
|---|---|
| Focused release, compatibility, migration, historical-audit and appendix tests | 74 passed |
| Full repository suite | 4,233 passed; 2 expected environment-gated skips |
| Ruff format | 1,001 files already formatted |
| Ruff lint | Passed |
| Strict mypy | Passed across 916 source files |
| Release smoke | Passed |
| Lock reconciliation | 91 packages resolved; `uv lock --check` passed |
| Generated CLI/schema references | Regenerated from the 0.7 environment; no stale tracked drift |
| Dissertation software-version appendix | Regenerated at `0.7.0` |
| Source and wheel build | `traffictwin-0.7.0.tar.gz` and `traffictwin-0.7.0-py3-none-any.whl` built |
| Isolated wheel install | Imported as `0.7.0`; synthetic preset CLI passed |
| v0.6.0/v0.7 coexistence smoke | Both isolated servers returned HTTP 200; registries remained distinct and byte-unchanged |
| Whitespace integrity | `git diff --check` passed |

The two skipped tests require `TRAFFICTWIN_VEC_FRESH_RESULT_DIR` and a separately published
full VEC-07 result; no result was fabricated for release testing.

Docker was not installed in the release environment, so a new container build was not
performed. The Python package build, isolated wheel installation and dual-server smoke were
completed instead.

## Deliberately unchanged boundaries

- no final `v0.7.0` Git tag or GitHub Release was created by this integration;
- no public package was uploaded;
- no licence or publication decision was invented;
- no private real workspace, credential or provider response was committed;
- no Manchester Gate-D, participant, accessibility or production acceptance was claimed; and
- unavailable, historical, synthetic, draft-only and read-only UI states remain explicit.

See the [Meeting 1–3 live feature gap audit](../meeting_1_2_3_live_feature_gap_audit.md) for the
operational capabilities that remain non-live after the code integration.
