# ADR-064: Sealed Append-Only Ledger for Analyst Map-Match Review

- Status: accepted (owner-directed, 26 July 2026)
- Date: 2026-07-26
- Capability: none accepted or changed; implements the decision half of beta package
  `BETA-D-01` under `MAN-09`, which remains `planned`.

## Context

Owner policy v1.1 left 165 of 305 Manchester count points awaiting manual review, 9 with no
suitable candidate, and encoded its own restraint as type-level literals
(`human_accepted: False`) plus a CLI that deliberately has no accept flag. The presentation
half of the review workflow existed — `ManualReviewQueue` carries per-row reasons and
missing-evidence detail — but there was no way to *record* a person's decision. The beta
backlog's requirement is precise: reviewer identity and explicit action required, no
auto-acceptance, rejected candidates and no-candidate rows preserved, policy version and
fingerprints recorded, and if no human is available the tooling is finished and rows stay
visibly pending.

## Decision

1. **A separate layered artifact, not a modification.** Decisions live in a new ledger that
   references the frozen match artifacts by fingerprint; `ObservationMatchV11` rows are never
   edited, so their `human_accepted: False` stays true of the matching itself forever. This is
   the same layering pattern as fresh-run admission over the VEC-10 structural record.
2. **A named person, one row at a time.** Every decision requires a reviewer name and role
   (placeholder identities refuse at the model level), a written reason, and an explicit kind —
   accept a named group, reject all candidates, or defer. The API accepts exactly one decision
   per call and no function in the module accepts a collection; a test asserts that shape.
3. **Accepting a group requires the row's own evidence.** The accepted `group_key` is
   validated against the full `ObservationMatchV11` row's actual groups, bound to the same
   policy fingerprint as the ledger. A queue summary cannot prove a group exists, so accepting
   from a summary alone is structurally impossible.
4. **Append-only with explicit supersession.** A changed mind supersedes the live decision by
   fingerprint reference; both entries remain. A silent second decision refuses at write time,
   and a ledger containing one refuses to validate at load time — the invariant holds even
   against hand-edited files.
5. **Two-pass sealed export.** The exported ledger carries a seal over every byte but itself;
   unsealed or tampered content refuses to load, and a sealed ledger refuses further appends.
   The pattern follows ADR-060's sealed receipts.
6. **The label ceiling is `analyst_reviewed_candidate`.** `supervisor_approved` and
   `scientifically_validated` are type-level `False`; forging them, or the bulk flag, fails
   validation. Analyst review is a real person's software-recorded judgement — it is not
   supervisor approval and the model cannot say otherwise.

## Consequences

**What this unblocked.** When a person sits down to review the 165 rows, their decisions
become durable, auditable, exportable evidence with complete provenance — and the demand
pipeline's dependency on "analyst-accepted matches" acquires a concrete artifact to consume.

**What it did not change.** No row is decided; the ledger starts empty and every queued row
is visibly pending. `MAN-09` remains `planned`; downstream consumers see the same acceptance
population as before until real decisions exist. UI/CLI wiring is a separate slice on
lead-owned surfaces.

**Cost.** Reviewing 165 rows one at a time with written reasons is deliberate friction —
that is the point, and the backlog's explicit design. The tests build their fixtures through
the real v1.1 matcher rather than hand-forged rows, which makes them slower than pure model
tests by a few hundred milliseconds and keeps them honest.
