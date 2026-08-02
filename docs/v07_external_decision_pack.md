# v0.7 External Decision Pack

This pack separates the active external decisions that block the remaining v0.7 dependency chain
from two inputs already resolved in the repository. The active items need repository-owner
approval, a provider/legal fact, supervisor or ethics authority, or a human evaluation; none is a
generic engineering task. A prepared recommendation, draft or form is not an approval, and nothing
in this document changes capability truth.

## 1. Resolved input: Manchester SUMO network

Resolved on 25 July 2026 by
[ADR-059](decisions/ADR-059-greater-manchester-baseline-network.md): the Greater
Manchester OSM/Geofabrik baseline, Manchester local-authority study filter, ODbL 1.0 source class,
SUMO/netconvert 1.27.1 and network-declared UTM 30N projection are bound. The controlled
`osmium-tool` decode and full network build are complete, and Phase 179 integrates the exact
305-site candidate population.

This no longer blocks candidate generation. Gate D still needs the 174 named-person review
decisions, an explicit treatment for nine unmatched sites and the scientific contracts in §2; the
resolved network does not supply those decisions or accept a baseline.

## 2. Scientific/human inputs: mapping review, calibration and comparison (blocks MAN-09/MAN-10 production registries)

Decision needed: the remaining predeclared study-specific values and human reviews — the design
explicitly refuses software defaults for these.

- **Map matching:** owner-policy v1.1 has frozen the distance/direction/road-class/confidence
  candidate rule and generated all 305 rows. The remaining inputs are the 174 named-person review
  decisions, an explicit treatment for nine no-candidate sites, and any supervisor acceptance
  required before scientific use.
- **Calibration:** one objective (MAE or RMSE are implemented), parameter grid/bounds,
  uncertainty treatment, and the development/held-out window design.
- **Comparison:** one versioned `ManchesterComparisonMetricContract` (pairing keys, interval,
  weighting, missingness, denominators, precision, interpretation) to register in the
  currently empty production registry.

These belong in the dissertation's methodology and should be agreed with Dr. Sampaio where they
carry scientific weight. Capture them in the
[supervisor Gate-D contract decision form](evaluation/supervisor_contract_decision_form.md); each
enters its registry through a reviewed fingerprinted contract.

## 3. Source facts: DfT/WebTRIS timezone and BODS identifier/privacy residual (blocks Gate B closure, full MAN-02/MAN-03/MAN-05)

Decision needed: provider-documented time/identifier facts plus a separate project privacy/output
decision, not software defaults.

- **DfT raw-count hour timezone (`GA-DFT-1`)** and **WebTRIS clock semantics**: a bounded
  official-source re-audit is complete and both source families remain silent. The next possible
  step is a recorded provider enquiry; until a source fact arrives, the rows keep their typed
  source-local exclusions.
- **BODS identifier persistence and project privacy/public-output treatment**: general consumer
  reuse/publication and API account/email registration are documented. No official source found
  by the bounded audit defines a retention duration or multi-day `VehicleRef` persistence, so
  longitudinal retention and row-level public output still require a project data-management
  decision.

Re-audited on 2 August 2026
([human-readable record](integration/manchester_authoritative_source_reaudit_20260802.md),
[machine record](integration/evidence/manchester_authoritative_source_reaudit_20260802.json)):
DfT and WebTRIS remain silent on their clock bases, while the BODS implementation guide closes
general reuse/publication and API-registration facts. Ready-to-send DfT/WebTRIS drafts and a
narrowed BODS identifier/retention draft are in
[provider enquiry drafts](integration/provider_enquiry_drafts.md). Until the residuals are
answered, typed source-local time exclusions and precautionary BODS privacy controls remain.

## 4. Resolved policy: v0.6 producer attestation

Resolved question 15: what evidence proves a registry was produced by the exact `v0.6.0` release
before compatibility migration is allowed.

**Approved on 24 July 2026** and recorded in
[ADR-058](decisions/ADR-058-v06-producer-attestation.md): only an operator clean-checkout
attestation establishes `v0.6.0` producer provenance. The typed attestation
(`traffictwin.release.attestation`) binds the exact tag commit, package version, registry hash
and size, a timezone-aware instant, and the operator's literal statement; verification re-hashes
the current bytes and fails closed on drift, sidecars, or tampered literals, and a verified
attestation approves no migration or activation by itself. The migration
preview/backup/activation/rollback build-out against attested sources is implemented; the exact
operator steps are in the
[operator v0.6 attestation procedure](integration/v06_attestation_procedure.md).

## 5. Manual accessibility and participant evaluation (blocks final Gate C acceptance, RQ16)

Decision needed: human execution and authority — automation cannot substitute.

- **Manual accessibility pass:** keyboard-only navigation, screen-reader labels, zoom/contrast
  checks over the 35 routes. The route-by-route
  [manual accessibility checklist](evaluation/manual_accessibility_checklist.md) is ready to
  execute and sign.
- **Participant usability study:** first a decision with Dr. Sampaio on whether RQ16 needs a
  formal study; if yes, the existing draft materials under `docs/evaluation/` require ethics
  approval before any recruitment. Without it, RQ16 evidence remains expert-walkthrough only,
  and that limitation is recorded honestly.

## Dependency effect of each approval

| Approval given | Work unblocked |
|---|---|
| 1 (network) + owner-candidate matching policy | **Resolved/built:** real candidate generation and the sealed analyst-review queue |
| Human review + 2 (calibration) | Calibration orchestration and the first reviewable baseline (Gate D) |
| + 2 (comparison contract) | Production goodness-of-fit metrics (MAN-10) |
| Gate D baseline accepted | Controlled SUMO → FCD → VEC chain (Gate E, MAN-11) |
| 3 (source facts) | Gate B closure for the affected adapters; canonical time projection |
| 4 (attestation policy) | **Resolved/built:** REL-01 migration preview→backup→activation→rollback tooling; a real operator attestation/activation remains separate |
| 5 (manual/participant) | Final Gate C acceptance and RQ16 evidence |
