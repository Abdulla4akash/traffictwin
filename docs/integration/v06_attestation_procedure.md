# Operator Procedure — First Real v0.6 Producer Attestation

This procedure records the ADR-058 operator clean-checkout attestation for a valuable v0.6
registry so it can later be activated in a v0.7 workspace. **Running the commands is your
statement** that the immutable `v0.6.0` release produced or re-verified the registry from a clean
checkout; TrafficTwin cannot verify that human step and the attestation approves no migration by
itself. See [ADR-058](decisions/ADR-058-v06-producer-attestation.md) and
[v0.7 workspace isolation](../v07_release_compatibility.md).

## Prerequisites

- The valuable v0.6 registry is **closed and checkpointed**: no application is using it and no
  `-wal`, `-shm`, or `-journal` sidecar files exist beside it.
- You have a clean checkout of the immutable `v0.6.0` tag (commit
  `1c50a25246426128ac6e8530240eff362d16be02`), separate from any v0.7 checkout.
- The registry is not itself the active registry of the target v0.7 workspace.

## Step 1 — Re-verify from the clean v0.6.0 checkout (the human step)

From a clean, separate checkout of the `v0.6.0` tag, confirm the release opens the registry
read-only and reports the expected structure — for example with that checkout's own
`traffictwin doctor --workspace <workspace>` (v0.6 CLI) against the registry's workspace. This is
what makes the attestation truthful; do not skip it. Keep the registry closed afterwards.

## Step 2 — Record the attestation (v0.7 CLI)

```bash
traffictwin release v06-attest /path/to/valuable-v0.6-registry.sqlite \
  --operator "Abdulla Al Mamun Akash" \
  --output /path/to/attestation.json
```

The command binds the exact registry SHA-256 and size, the `v0.6.0` tag/commit, the package
version, a timezone-aware instant, and your literal operator statement, and prints
`migration_approved: false` and `capability_status: planned`. It refuses an open/uncheckpointed
registry (sidecars present) and never writes to the registry.

## Step 3 — Verify (optional but recommended)

```bash
traffictwin release v06-migrate-preview /path/to/valuable-v0.6-registry.sqlite \
  workspace-v0.7 --attestation /path/to/attestation.json
```

A read-only preview that reports `operation: attested_same_schema_activation` and
`source_product_version: 0.6.0 (operator attested)` confirms the attestation binds the current
bytes. Any later byte change to the registry invalidates the attestation
(`ATTESTATION_NOT_VERIFIED`), and you must re-run Step 2.

## What this does and does not establish

- **Does:** record that `v0.6.0` produced/re-verified this exact registry, enabling attested
  activation with durable backup and receipt-gated rollback.
- **Does not:** approve migration, activate anything, prove scientific validity, or change any
  capability status. `REL-01` remains `planned`.

## After attestation

To activate the attested registry in a v0.7 workspace and keep a rollback point:

```bash
traffictwin release v06-migrate  /path/to/valuable-v0.6-registry.sqlite \
  workspace-v0.7 --attestation /path/to/attestation.json
# ... and to undo while the active registry still matches the receipt:
traffictwin release v06-rollback workspace-v0.7 \
  --receipt workspace-v0.7/compatibility/backups/mig-<id>/migration-receipt.json
```

Keep the source v0.6 registry and the published backup unchanged; both are byte-verified on
rollback.
