# ADR-057: Bee Network Membership by Identifier, Never by Display Name

- Status: accepted (Gate A decision; activation blocked on `GA-BEE-1` live-feed verification at Gate B)
- Date: 2026-07-22
- Capability: `MAN-05` scope semantics; constrains `MAN-07` projection and `MAN-08` display

## Context

The v0.7 design promises "live Bee Network bus locations" without mislabelling them as general
traffic, and requires explicit scope choices (design §4.1, §10). BODS SIRI-VM is an England-wide
feed, so "Bee Network" membership must be a defined, testable predicate. The Gate A audit
([manchester-source-gate-a-audit-v0_7.md](../integration/manchester-source-gate-a-audit-v0_7.md)
§6) established, from official pages on 2026-07-22:

- The DfT SIRI-VM profile mandates `OperatorRef` = the operator's National Operator Code (NOC)
  from the Traveline NOC database, and mandates `LineRef`/`PublishedLineName`.
- The NOC database contains dedicated Bee Network operator records; observed codes: `BNDB`
  (Rotala), `BNFM` (First), `BNGN` (Go-Ahead), `BNML` (ComfortDelgro), `BNSM` (Stagecoach),
  `BNVB` — all with public name "Bee Network".
- No official machine-readable "Bee Network franchised services" list was found. The closest
  join target, TfGM's GM Public Transport Schedules (GTFS/TXC, nightly), is licensed ODbL v1.0 —
  a different licence family from OGL (`GA-BEE-3`).
- Non-franchised service-permit buses operate inside Greater Manchester, so geography cannot
  define membership; marketing wording and the franchised set are not provably identical
  (`GA-BEE-2`).
- Whether live GM publishers actually populate `OperatorRef` with the BN\* codes cannot be
  verified without an API key (`GA-BEE-1`), and the NOC database's own licence is unconfirmed
  (`GA-BEE-4`).

## Decision

1. **Membership is decided only by identifier matching.** The primary predicate is
   `OperatorRef ∈ BN-allowlist`, where the allowlist is a frozen, versioned reference artifact
   recording each admitted NOC, the evidence for it, and the audit date. The Gate A observed
   candidate set is {`BNDB`, `BNFM`, `BNGN`, `BNML`, `BNSM`, `BNVB`}, admitted as *candidates
   only* until Gate B verifies them against observed live feed data (`GA-BEE-1`).
2. **Display-name matching is prohibited as a membership test.** `PublishedLineName`, operator
   public names, "Bee" branding strings, and any free-text field never decide membership; they
   are display metadata only. This is a tested negative contract, not a convention.
3. **Optional corroboration join:** `OperatorRef` + `LineRef` may be joined against an accepted
   TfGM schedule snapshot to corroborate membership and attach service context. Because that
   dataset is ODbL, any artifact derived from the join carries an ODbL-derived publication class
   and is excluded from public export until a reviewed publication decision exists
   (`GA-BEE-3`). Membership itself must not *require* the ODbL join.
4. **Three-valued, fully accounted outcome.** Every observed vehicle is classified
   `bee_network_franchised` (allowlist match, allowlist version recorded),
   `non_franchised_or_unknown` (valid GM-scope observation, no allowlist match), or
   `out_of_scope` (outside the requested geographic/operator scope). Counts for all three plus
   `ambiguous`/`missing` identifier states are published with every projection; unknowns are
   never silently dropped or silently included, and the UI never labels the bus layer "all
   Manchester buses".
5. **Allowlist changes are versioned evidence events.** Franchising is recent and operators may
   change; every allowlist edit records its official evidence and date, and projections pin the
   allowlist version they used.
6. **Activation gate.** Until `GA-BEE-1` is resolved with observed feed evidence, the Bee
   Network membership filter is `unavailable` with that exact reason; the bus layer may still
   display BODS vehicles in the GM bounding box labelled as "buses/transit vehicles (operator
   membership unverified)".

## Consequences

- Membership becomes reproducible and auditable: a vehicle's classification is a function of
  (snapshot, allowlist version), not of string heuristics.
- Over- and under-inclusion risks are contained: parent-operator generic NOCs are never admitted
  by name similarity, and if franchised services turn out to publish under legacy NOCs, the gap
  appears as visible `non_franchised_or_unknown` counts rather than silent loss.
- The ODbL boundary is explicit before any schedule join is built, preventing a licence-mixing
  surprise in exports.
- NOC-derived reference tables stay local-lookup-only until `GA-BEE-4` resolves their
  redistribution basis.

## Rejected alternatives

- Matching on "Bee Network" display names or line branding: rejected; free text is unstable,
  unverifiable, and exactly the shortcut the design's evidence rules exist to prevent.
- Geographic bounding-box membership: rejected; non-franchised and cross-boundary services
  inside GM make geography a scope filter, not a membership test.
- Requiring the TfGM ODbL schedule join for membership: rejected; it would couple a core truth
  label to a mixed-licence dependency.
- Hard-coding the six observed NOCs as permanent truth: rejected; they are Gate A discovery
  evidence pending live-feed verification, per the AGENTS.md rule that documentation is not an
  accepted source contract.
