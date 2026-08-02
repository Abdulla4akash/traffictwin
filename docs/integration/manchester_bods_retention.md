# Private BODS snapshot retention

Status: **candidate MAN-05 privacy control — `MAN-05` remains `planned`**

`traffictwin.integration.manchester.bods_retention` provides a preview-first cleanup boundary for
private BODS SIRI-VM snapshot families. It exists because immutable raw BODS snapshots can retain
vehicle identifiers even though parser outputs replace `VehicleRef` with snapshot-scoped tokens.
The control is a precautionary local engineering default, not an assertion that the project's
legal or research data-management retention basis has been approved.

The 2 August 2026
[authoritative-source re-audit](manchester_authoritative_source_reaudit_20260802.md) documents the
general BODS consumer rights to copy, adapt, publish, distribute, and transmit the data, together
with the API account/email registration requirement. It does not document an official retention
duration or multi-day `VehicleRef` persistence. The limits below therefore remain a project
privacy safeguard; they are not presented as a BODS licence ban or an official 24-hour rule.

## Default bounds

The versioned `bods-private-retention-v1` policy proposes:

- a maximum age of 24 hours;
- at most 240 BODS snapshot families;
- preservation of at least the newest family;
- preservation of every family referenced by the current local live-vehicle scene;
- accepted and quarantine directories deleted together; and
- private-only handling with no public export.

These bounds can be made stricter through the typed policy. Code-enforced maxima prevent a caller
from silently converting the control into indefinite retention: 168 hours, 1,440 families, and 24
minimum-newest families are the largest representable values. The policy explicitly records
`legal_retention_basis_approved=False` and `secure_erasure_guaranteed=False`.

## Preview and apply

`preview_bods_retention` is read-only. It validates the isolated v0.7 workspace, verifies every
BODS accepted snapshot and quarantine artifact through MAN-01, reconciles paired raw fingerprints
and retrieval windows, refuses symlinks, validates the current live scene, and counts the complete
private byte footprint. It returns deterministic, fingerprinted keep/delete decisions with exact
reasons.

`apply_bods_retention` requires the preview's exact confirmation text. It recomputes the entire
preview at the original evaluation timestamp and refuses if any snapshot, scene reference, byte,
or policy decision drifted. Only the explicitly previewed BODS directories under the exact
`accepted/` and `quarantine/` parents are eligible. There is no timer, background task, startup
cleanup, wildcard deletion, arbitrary path input, or API-triggered cleanup. A successful in-memory
receipt reports exact deleted snapshot IDs, directory counts, and private bytes.

The Manchester UI exposes **Preview private snapshot cleanup** under the live-bus controls. A
separate form displays the plan-bound confirmation phrase and requires it verbatim before apply.
The UI never removes data during ordinary reruns or live fetches.

## Limits

Portable filesystem deletion does not guarantee physical secure erasure, particularly on SSDs,
copy-on-write filesystems, backups, or snapshots. The control does not delete published aggregate
evidence, infer a lawful basis, authorize public hosting, or approve longitudinal analysis.
General BODS reuse and registration facts are now documented, but identifier persistence,
project privacy/data-management approval, complete Bee membership/licence reconciliation, and
release acceptance remain unresolved. Until those decisions are recorded, retention remains a
visible residual MAN-05 acceptance condition.

Offline tests in `tests/unit/test_manchester_bods_retention.py` prove read-only preview, newest and
active-scene protection, exact-confirmation enforcement, complete accepted/quarantine deletion,
inventory-drift refusal, empty-workspace behavior, symlink refusal, and persisted-plan count
integrity. Tests use only synthetic BODS fixtures and temporary workspaces.
