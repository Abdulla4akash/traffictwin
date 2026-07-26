# Analyst Map-Match Review Ledger

Status: implemented `manchester-map-match-analyst-review-1.0` (ADR-064). Beta package
`BETA-D-01`, decision half. **No row has been decided: the ledger starts empty, and the 165
Manchester observations awaiting review remain visibly pending until a person decides them.**
That pending state is the deliverable of this slice, exactly as the beta backlog specifies for
the case where no human review has happened yet.

Library: `traffictwin.integration.manchester.observation_review`

## What it is

Policy v1.1 deliberately refused to auto-accept ambiguous map matches: its artifacts carry
`human_accepted: False` as a type-level literal and the CLI exposes no accept flag. The
presentation half of the review workflow already existed (`ManualReviewQueue`, with per-row
reasons and missing-evidence detail). This module adds the decision half — a typed, sealed,
append-only ledger in which a **named person** decides one row at a time.

## The three actions, and what each requires

| Action | Requires |
|---|---|
| `accept_group` | The full `ObservationMatchV11` row, so the accepted `group_key` is validated against the row's real road groups — a queue summary cannot prove a group exists, so it is not allowed to |
| `reject_all_candidates` | A written reason (all decisions require one, minimum 10 characters) |
| `defer` | Likewise; deferral is an explicit recorded action, not an absence |

Every decision carries: reviewer name and role (placeholders such as `TBD`, `agent`,
`anonymous` are refused at the model level), timestamp, reason, the v1.1 policy binding, and
type-level `False` literals for `supervisor_approved`, `scientifically_validated`, and
`bulk_operation`. The strongest label a decided row can carry is
`analyst_reviewed_candidate`.

## Structural guarantees

- **No bulk operation exists.** The API accepts exactly one decision per call; a test asserts
  no public function takes a collection of decisions.
- **Append-only.** A change of mind supersedes the earlier decision by fingerprint reference;
  both stay in the ledger. A second decision without an explicit supersession refuses, and a
  ledger containing one refuses to validate.
- **Identity-bound.** The ledger binds the exact queue fingerprint and policy fingerprint;
  decisions against a different queue, an unknown count point, a foreign policy, or a group
  the row does not offer all refuse with typed codes.
- **Sealed export.** `seal_review_ledger` writes a two-pass seal covering every byte but
  itself; `load_review_ledger` refuses unsealed (`SEAL_MISSING`) or edited
  (`SEAL_MISMATCH`) content, and a sealed ledger refuses further appends until reopened as a
  working copy.
- **Pending is visible.** `review_status` lists pending count points individually and counts
  the preserved no-candidate rows; nothing is ever silently assumed decided.

## What this does not do

It does not decide anything, present a UI, change any `MAN-*` capability state, modify the
frozen match artifacts, or upgrade owner-policy acceptance into human acceptance. Wiring the
queue and ledger into a thin review page or CLI surface is a separate slice; downstream
consumers (demand, calibration) continue to see exactly the acceptance population they saw
before until a person's decisions exist.

## Evidence and tests

- Library: `src/traffictwin/integration/manchester/observation_review.py`
- Decision record: `docs/decisions/ADR-064-analyst-map-match-review-ledger.md`
- Adversarial tests (real matcher fixtures): `tests/unit/test_manchester_observation_review.py`
