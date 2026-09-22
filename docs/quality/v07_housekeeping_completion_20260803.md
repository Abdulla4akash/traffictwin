# v0.7 housekeeping completion record

## Scope and baseline

- Date: 3 August 2026
- Repository: `Abdulla4akash/traffictwin`
- Verified starting branch: clean `main`
- Starting commit and fetched `origin/main`:
  `49be6a2db8a69409a1b92fb02e954db7cf1441f6`
- Housekeeping branch: `housekeeping/v0.7-completion`
- Starting GitHub Actions evidence:
  [TrafficTwin CI run 30800943000](https://github.com/Abdulla4akash/traffictwin/actions/runs/30800943000),
  successful on Python 3.11 and 3.12 for the exact starting commit
- Immutable baseline: tag `v0.6.0` still dereferences to
  `1c50a25246426128ac6e8530240eff362d16be02`
- Publication state at start: no final `v0.7.0` tag, no GitHub Release and no open pull request

This record separates safe repository housekeeping from unfinished product capabilities. It does
not accept a formal capability, provider contract, scientific result, real workspace, licence,
publication, tag, deployment or production status.

## Classification 1 — housekeeping completed

| Area | Finding | Bounded correction/evidence |
|---|---|---|
| Version and release metadata | Package, import version, citation, lock and changelog already agreed on `0.7.0`; the final tag/release remained absent | Preserved the version identity and added no publication action |
| Current status documents | The workflow still described the alpha.8 branch, an unfinished UI phase, 165 rather than the full 174-row decision queue, a non-final package version and missing Docker-only work | Replaced it with a current main/Phase-198 workflow and explicit housekeeping/product tracks |
| Live-feature audit | The audit still said the feature branch was nine commits ahead of `main` | Re-anchored it to integrated main while preserving every not-live verdict; code integration is explicitly not operational evidence |
| Requirement/status reconciliation | The matrix still treated the now-built Greater Manchester network as an external blocker; the progress record mixed Phase-190 design state with later bounded implementation | Reconciled the network, 174-row/nine-no-candidate boundary, later `NEXT-*` slices and Gate-F wording without advancing formal status |
| Compatibility/migration documentation | The generated workspace contract and guide still said package/version alignment was pending | Updated the source contract to the actual residuals: licence/publication, owner-authorised tag/release, real owner-workspace acceptance and conditional future cross-schema work; added a regression assertion |
| Evidence accuracy | Current navigation repeated a withdrawn claim that Geofabrik mutated a dated extract | Corrected the changelog, project guide and current research/action surfaces to the recorded N1 verdict: internal source/decoded identity conflation, no provider mutation, original canonical network reproduced; historical text remains labelled as such |
| Documentation navigation | Offline scan found two broken repository-local targets | Repaired the Streamlit services-directory link and ADR-058 relative link; added `scripts/check_markdown_links.py` and a CI gate |
| Documentation currency | Reproducibility/testing pages advertised the obsolete OPS-05 count and `.venv` commands; the release guide exposed tagging commands without an authority boundary | Centralised volatile results in this dated record, aligned active commands with `uv`/CI and made tag/release/package/deployment actions explicitly owner-only |
| Generated references | The compatibility limitation was semantically stale even though generation itself was deterministic | Regenerated the committed reference set from the corrected contract and required a clean generated-reference diff |
| Packaging and installation | CI built distributions but did not install the wheel into a clean environment | Added Python 3.11/3.12 clean-wheel install/import/CLI smoke steps after the build |
| Test, lint, typing, CI and fixtures | Existing gates were present; link and wheel-install coverage were missing, and the checkout/setup actions still used the deprecated Node 20 runtime | Extended CI while retaining locked dependencies, Ruff, strict mypy, full coverage suite, standalone demo, fixture immutability, generated references, package build and Python 3.12 container build; moved checkout/setup to their Node 24-compatible majors |
| Historical status labels | Old `Blocked`, `Not Started` and quality-gate headings deep in implementation status looked current | Marked the earlier phase chronology and initial repository assessment as historical without rewriting their evidence |

No feature implementation, provider acquisition, real-data generation, scientific choice or
operational deployment was performed as housekeeping.

## Classification 2 — remaining product-completion work

| Product outcome | Current bounded foundation | What genuine completion still requires |
|---|---|---|
| Continuously updated Manchester digital twin | Source-specific adapters, explicit workers, immutable snapshots, stale fallback, source health and bounded local run profiles | Owner-selected populated workspace, authorised credentials/contracts, sustained operational runs, retention/privacy/publication decisions and city-road measured-traffic coverage |
| Complete real Manchester scene/fusion | Separate transit, road-event, survey and infrastructure contracts/layers | Accepted compatible real sources; driver, pedestrian, mobile/social or other approved inputs if kept in scope; no silent source fusion |
| One/two/three-hour traffic and journey prediction | Bounded bus climatology/surrogate and offline imported-run journey views | Prospective road-traffic/route/departure methods, held-out real validation and accepted scientific evidence |
| Executable user-authored what-if scenarios | Draft composer, unsigned campaign draft and fixed synthetic-square loopback SUMO transport | Approved generic Manchester execution, accepted network/demand/baseline, safe authority model and evidence-producing runs |
| Calibrated observation-to-SUMO Manchester baseline | Complete network foundation, candidate matches/review UI, real DfT profile candidate and deterministic calibration contracts | 174 named-person decisions, treatment of nine no-candidate sites, approved uncertainty/calibration/demand choices, viable demand/runs and human baseline acceptance |
| Observed-versus-simulated evaluation | Pairing, exclusions, coverage, lineage and error engines | Registered accepted contract, compatible observed/simulated intervals and accepted real comparison |
| Manchester SUMO-to-VEC evaluation | VEC identity, execution/admission and strict lineage foundations | Accepted Manchester SUMO baseline/FCD/network, complete controlled VEC chain and admitted results |
| Capacity-aware training and real explainability | Unsigned 2,400-job plan, 21-job synthetic worker, synthetic snapshots/replay/integrity fixtures | Signed protocol, authorised actors/checkpoints/runtime/compute, real evaluation and literature-grounded validated attribution; no causal/optimality claim from fixtures |
| Decision, route and infrastructure recommendations | Read-only observatory and decision-safety views | Explicit product/authority decisions, validated models/evidence and safe human governance; no current action authority |
| Human evaluation and accessibility | Automated semantics, responsive layouts and bounded browser evidence | Completed human keyboard/screen-reader/zoom/contrast audit and any ethics-approved participant study |
| Public/mobile/production operation | Local research UI, synthetic static demo and standalone container | Licence/publication/security/hosting/authentication/operations decisions and evidence; explicit owner deployment authority |

The detailed row-level verdict remains in the
[Meeting 1–3 live feature-gap audit](../meeting_1_2_3_live_feature_gap_audit.md). All formal
`MAN-01`–`MAN-11`, `UX-01`–`UX-03` and `REL-01` rows remain `planned` under the complete-gate rule.

## Owner decisions and real inputs still blocking completion

- DfT raw-count and WebTRIS clock/timezone answers; remaining BODS identifier/privacy/retention,
  public-row and complete Bee-scope decisions.
- Exact TfGM/NTIS measured-traffic product access, schema/sample, rate, time, security, licence and
  publication contracts plus authorised credentials/probes if those products remain in scope.
- A real named reviewer for all 174 mapping decisions and an explicit treatment for nine
  no-candidate sites.
- Supervisor/owner scientific decisions for calibration, uncertainty, demand reconstruction,
  comparison contract registration, baseline acceptance and any GEH use.
- An owner-selected real v0.7 workspace and a legitimately attested valuable v0.6 registry if a
  real compatibility activation is required.
- Signed benchmark/training protocols, authorised actors/checkpoints/runtime/compute and compatible
  real method evidence.
- Human accessibility review, ethics/supervisor authority and participant inputs where applicable.
- Repository licence, third-party publication classes, GitHub Release, PyPI publication and
  deployment decisions. The final Git tag was separately owner-authorised after this housekeeping
  pass and is no longer an open item.

## Verification

| Gate | Result |
|---|---|
| `uv lock --check` | Passed; 91 packages resolved without lock change |
| `ruff format --check .` | Passed; 1,002 files already formatted |
| `ruff check .` | Passed with no findings |
| `mypy` | Passed across 916 configured source/test files |
| Focused release/compatibility regression | 33 passed |
| Full suite with coverage | 4,233 passed, 2 expected environment-gated skips; 87% total statement coverage; 787.87 s on Python 3.12.13 |
| Expected skips | Only the two fresh-VEC chain checks requiring `TRAFFICTWIN_VEC_FRESH_RESULT_DIR` and a separately published full VEC-07 result; no result was fabricated |
| Generated-reference consistency | All 69 files were byte-identical before/after a second complete generation; the committed compatibility contract is generated from corrected source |
| Documentation navigation | 2,103 repository-local Markdown targets checked; no broken target remains |
| Package build | Isolated build produced `traffictwin-0.7.0.tar.gz` and `traffictwin-0.7.0-py3-none-any.whl` |
| Clean-wheel installation | Fresh Python 3.12 environment installed the wheel, imported `traffictwin.__version__ == "0.7.0"` and ran `traffictwin synthetic presets` |
| Standalone demo smoke | Temporary workspace initialised; all 62 bundles verified (62 accepted, zero rejected); provenance JSON, run Markdown, full HTML and staged site succeeded |
| Static-site boundary | `synthetic: true`, `live_data: false`; licence remained unspecified |
| Release smoke | `scripts/verify_release.py` passed |
| Fixture immutability | `git diff --exit-code -- tests/fixtures examples` passed before and after the full suite/demo/build checks |
| Diff/whitespace | `git diff --check` passed; commit-candidate review found only the intended housekeeping files |
| GitHub Actions | The starting-main matrix passed in run 30800943000. Final-head branch run 30808623991 and draft-PR run 30808626666 passed on Python 3.11/3.12, including wheel-install smokes and the Python 3.12 container build. |

The local environment did not need to manufacture provider, Docker, VEC-result or real-workspace
inputs. The branch CI owns the container-build repetition and both supported Python-version wheel
installations after publication.

## Post-completion owner-authorised tag action

After the exact housekeeping head passed both published matrices, the repository owner explicitly
authorised the annotated `v0.7.0` Git tag. Tag object
`ba513f9fd52803b7644f1130a6a0202cd2043752` resolves to
`e840be6c09ac4579e3604665110db2e3209fc7dd`. The tag message preserves the feature, evidence,
licence, publication and production boundaries in this record.

The tag-push workflow run 30810803992 failed before checkout or runner assignment because GitHub
reported an account payment/spending-limit block. The exact tagged commit's branch and draft-PR
matrices had already passed; the tag event supplies no additional test evidence and must not be
reported as a code failure. No GitHub Release, package upload, licence, deployment or tag movement
was performed.

## Post-tag CI efficiency amendment

The housekeeping branch now runs feature-branch changes once through `pull_request` CI instead of
starting an identical full matrix for both the branch push and its open pull request. Direct pushes
to `main` and pushes of `v*` tags retain their own matrix, so integration and tag events remain
covered. Workflow-level concurrency also cancels an older in-progress run for the same pull request
or Git ref when a newer event supersedes it. The Python 3.11/3.12 jobs and every quality, package,
demo, fixture and Python 3.12 container step are unchanged.

Two repository tests pin the event and concurrency policy, and the workflow parses as YAML with the
expected branch/tag filters. This amendment is later than the immutable `v0.7.0` tag and does not
move it. Hosted verification remains pending while GitHub refuses Actions jobs before runner
assignment because of the recorded account billing/spending-limit state; that external refusal is
not reported as a code or test failure.

Complete local validation also exposed a pre-existing timing defect in the synthetic TfGM ZIP test
builder: it inherited the wall-clock ZIP-member timestamp, so byte identity could change during a
slow suite and invalidate a same-snapshot refusal test. The synthetic helper now fixes archive-member
timestamps and has a byte/metadata determinism regression test. Production acquisition behavior,
provider evidence and fixtures are unchanged. The final clean rerun reports 4,236 passed and the two
expected fresh-VEC environment skips, with 87% total statement coverage; lock, repository Ruff,
strict mypy over 917 files, generated references, all 2,104 local documentation links, fixture
immutability and diff checks also pass.

## Release standing

- **Technically clean:** yes for the tagged housekeeping head; its branch and draft-PR CI matrices
  passed before tagging.
- **Feature-complete for Meetings 1–3:** no.
- **Production-ready:** no.
- **Formally accepted v0.7 release:** no; package identity and the final Git tag are `v0.7.0`, but
  the GitHub Release, licence/publication decisions, real-workspace acceptance and Gate-F
  acceptance remain absent.
