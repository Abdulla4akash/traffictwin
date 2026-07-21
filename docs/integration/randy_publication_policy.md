# Randy/TOS Publication-Manifest Policy

Status: implemented and accepted with the permission-manifested VEC-11 dissertation pack. The
strict policy schema remains the permission boundary; the real pack builder, offline verifier,
generated contract, tests, and checked-in three-row/aggregate pack now satisfy it.

Module: `src/traffictwin/integration/tos/publication.py`
Tests: `tests/unit/test_tos_publication_policy.py`

## Purpose

Every repository or dissertation artifact derived from Randy's `vec_env`/`tos-data` sources must
travel with a strict, deterministic, permission-aware publication manifest. The
`TosPublicationManifest` model encodes the current written-permission policy, and
`integration.vec_publication` applies it to a mechanically verifiable VEC-11 pack.

## Current permission scope

The written owner response (21 July 2026) permits only:

- sanitised samples;
- aggregate outputs.

Everything else is refused as an included artifact and must remain visible in the excluded
inventory:

- full raw datasets;
- complete repositories;
- actor/checkpoint redistribution;
- private machine information;
- third-party SUMO assets;
- anything whose permission is unknown or denied.

`default_excluded_inventory()` returns the standing entries for these five mandatory categories,
and manifest validation fails if any category is missing from the excluded list. Owner permission
is recorded as distinct from a formal software or data licence.

## Manifest requirements

A manifest validates only when all of the following hold:

1. **Citations.** Exactly one citation each for `vec_env` and `tos-data`, with a caller-supplied
   40-hex reviewed commit that appears (at least its first 12 characters) in the citation text.
   Commits are recorded as `caller_supplied`; the library never asserts that a commit was
   independently verified.
2. **Engine version.** Exactly `v2_post_nrsus_fix` (shared with the TOS adapter's expected engine
   constant) for the current policy version `tos-publication-policy-1.0`.
3. **Permission basis.** A written basis, grant date, scope statement, and licence distinction.
4. **Sanitisation declaration.** Explicit affirmations that secrets, private paths/machine
   information, actor checkpoints, third-party SUMO assets, and full raw datasets are excluded and
   that schema and units are preserved.
5. **Selected-seed disclosure.** Any artifact that uses or mentions the `_s102` best-of-seeds
   selection must set `uses_selected_seed=True`, and the manifest must then carry a
   `selected_seed_disclosure` that retains the `_s102` label.
6. **Integrity.** Every included artifact records a lowercase SHA-256 hash and a bounded positive
   size; the included set is bounded in count and total bytes.
7. **Portable paths.** Included paths are relative POSIX paths with no absolute, drive-letter,
   `~`, `.`, `..`, empty, backslash, or control-character segments. Free-text fields reject
   local-absolute-path and `file://` content.
8. **Labels.** Source-mode, campaign, scenario, fleet, actor, trace day/window, fleet-seed, and
   evaluator-seed labels are recorded where applicable.
9. **Limitations.** At least one explicit limitation statement.
10. **Strictness and determinism.** All models forbid extra fields and are frozen. Citations,
    included artifacts, and excluded artifacts are canonically sorted, so `canonical_json()` and
    the SHA-256 `fingerprint()` are order-insensitive and deterministic; no wall-clock value is
    read.

## Accepted VEC-11 application

The accepted pack contains a three-row pseudonymised and rounded matched task/trip sample plus the
26 VEC-09 aggregate metric states. Its manifest binds the exact VEC-04, VEC-05, and VEC-09 reports,
cites both pinned repositories, preserves engine and `_s102` labels, and lists every excluded
category. Pseudonymisation is explicitly not claimed as anonymity. See
[the VEC-11 guide](vec_dissertation_pack.md).

## What this policy and pack do not do

- It does not read, pull, hash, or modify `../external/vec_env` or `../external/tos-data`.
- The policy model alone does not read external repositories; the VEC-11 builder separately reads
  exact pinned Git blobs and proves both external worktrees remain unchanged.
- Unit-test values remain synthetic; only the checked-in VEC-11 pack is the permission-manifested
  real sanitised sample and admitted aggregate set.
- It provides no CLI or UI; that interface belongs to VEC-10.
- Its generated reference records the accepted pack and `capability_implemented=true`.
- Successful validation is a policy check, not a grant of legal permission or a licence.

## Related documents

- [TrafficTwin v0.6 design](../traffictwin-design-v0_6.md) (§13, `VEC-11`)
- [TOS data adapter](tos_data_adapter.md)
- [Security and privacy](../security_and_privacy.md)
- [Generated publication policy](../reference/generated/tos_publication_policy.json)
- [Generated VEC-11 contract](../reference/generated/vec_dissertation_pack_contract.json)
- [ADR-047 permission-aware deterministic RO-Crate](../decisions/ADR-047-permission-aware-deterministic-ro-crate.md)
