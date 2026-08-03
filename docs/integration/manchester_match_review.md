# Resumable Named-Person Map-Match Review

Phase 197 implements the bounded `NEXT-07` workflow over the existing
`manchester-map-match-analyst-review-1.0` append-only ledger (ADR-064). The registered real queue is
the exact private 305-row policy-v1.1 reproduction recorded on 28 July 2026: SHA-256
`12f1e67246cae4591f33786f745626965e7171b19f12def5ebffec56e3d8ab09`, policy fingerprint
`f0bc213b…`, 174 queued rows, and nine no-suitable-candidate rows. Software has made none of their
decisions.

## Opening and resuming

The page accepts no artifact, ledger or export path. It searches one verified v0.7 workspace for
the fixed registered member `manchester/match_results_v11_20260728.json`, then verifies its exact
digest, 305-row total, 174-row queue and policy identity before showing it. A missing or changed
member stays unavailable. Rebuild/import is a bounded operator action outside the page.

The working-ledger filename is derived from the registration, queue and policy fingerprints under
the workspace's private `manchester/review/` directory. Reopening the page therefore resumes that
exact unsealed ledger. The default is the first pending row unless the local page session contains
an explicit bookmark. Queue, policy, pending/accepted/rejected/deferred, no-candidate and revision
counts remain visible.

Search covers count-point ID, signed reference, road name, review reason, missing evidence,
disposition and decision state. Filters also cover candidate-group count; sorting is by count point,
candidate count or disposition. These operations return presentation views only and do not reorder
or mutate the queue or ledger.

## One real person, one decision

A real reviewer name and role are entered once in the local page session and displayed on every
form. Placeholder, anonymous and agent identities are refused. Each form admits exactly one of:

| Action | Required evidence |
|---|---|
| `accept_group` | One `group_key` present on the exact row |
| `reject_all_candidates` | A written reason of at least ten characters |
| `defer` | A written reason of at least ten characters |

There is no recommended selection, accept-recommended shortcut, bulk endpoint, unattended action,
confidence shortcut or LLM suggestion. A saved decision is locked, checked for a concurrent
editor, written through a private temporary file, fsynced, atomically replaced, read back and
revalidated. Only then can the person choose **Next pending**. Another editor's stale context is
refused rather than merged.

A correction explicitly supersedes the current decision fingerprint. The prior identity, reason
and decision stay in the append-only ledger. Sealing publishes a new content-addressed, owner-only,
tamper-evident export through new-only atomic publication and leaves the working ledger unchanged.

## Evidence presented and remaining limit

The page presents source road type/name/reference; queue disposition, reasons and missing evidence;
candidate road group/class/reference/distance; exact-reference and override use; preserved family
mismatch; and each candidate member's edge, class, distance and geometry-source label.

The registered v1.1 row contract does **not** retain the source point coordinates or candidate edge
shapes. Consequently Phase 197 draws no map and says geometry is unavailable; visual proximity is
never inferred from an edge ID or distance. Map/text equivalence and its keyboard/contrast human
acceptance remain blocked until a separately versioned, exact-bound private geometry companion is
available. This limit does not block the complete text/table review workflow.

Tests exercise registered-artifact digest/row/queue/policy reconciliation, a 174-row synthetic
named-reviewer session with midpoint restart, filters, revisions, content-addressed sealing,
concurrent editors, atomic-write interruption, readback, no path inputs and no bulk action. Fixture
reviewer decisions are synthetic tests only; they are not Manchester row decisions.

See the [canonical v0.7 design](../traffictwin-design-v0_7.md#278-next-07--resumable-named-person-map-match-review),
[ADR-064](../decisions/ADR-064-analyst-map-match-review-ledger.md), and the
[Gate-D decision support](manchester_gate_d_decision_support_20260802.md).
