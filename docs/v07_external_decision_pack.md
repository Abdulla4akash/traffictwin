# v0.7 External Decision Pack

Five recorded decisions block the remaining v0.7 dependency chain. None of them is an
engineering task: each needs repository-owner approval, a provider/legal fact, supervisor or
ethics authority, or a human evaluation. This pack makes each decision ready to take by listing
the concrete options, an engineering recommendation, and the exact acceptance evidence the
canonical design requires. A recommendation here is not an approval; nothing in this document
changes capability truth.

## 1. Manchester SUMO network, licence, CRS, and date (blocks MAN-09 → MAN-11, Gates D–E)

Decision needed: which exact Manchester SUMO network is bound for map matching and calibration,
under which licence, construction method, projection, and data date.

Options:

- **A (recommended): OpenStreetMap-derived network.** Generate with SUMO `netconvert` from an
  OSM extract of the approved study boundary. Source data is ODbL-licensed; attribution and
  share-alike terms must be recorded in the network's source/licence record before binding.
  Deterministic regeneration requires pinning the extract date, boundary polygon, netconvert
  version, and options.
- **B: A supplied/authorised network** (for example from Randy or TfGM), if one exists with
  documented provenance and reuse terms. None has been supplied to date.
- **C: Defer** and keep MAN-09 real-source matching unavailable (the current state).

To approve option A, reply with: the study boundary (Manchester local authority vs Greater
Manchester — open question 1), the extract date to pin, and confirmation that ODbL terms are
acceptable for this research use. Implementation then produces the network under a reviewed
ADR with exact hashes before any matching runs.

## 2. Scientific contracts: matching thresholds, calibration objective/uncertainty, comparison metric (blocks MAN-09/MAN-10 production registries)

Decision needed: predeclared study-specific values — the design explicitly refuses software
defaults for these.

- **Map matching:** maximum distance (m), direction tolerance (degrees), road-class rule, and
  which cases force manual confirmation. The synthetic harness demonstrates the mechanics; the
  real thresholds are a research choice to predeclare.
- **Calibration:** one objective (MAE or RMSE are implemented), parameter grid/bounds,
  uncertainty treatment, and the development/held-out window design.
- **Comparison:** one versioned `ManchesterComparisonMetricContract` (pairing keys, interval,
  weighting, missingness, denominators, precision, interpretation) to register in the
  currently empty production registry.

These belong in the dissertation's methodology and should be agreed with Dr. Sampaio where they
carry scientific weight. To approve, reply with the values and their written basis; each enters
its registry through a reviewed fingerprinted contract.

## 3. Source facts: DfT/WebTRIS timezone semantics and BODS terms (blocks Gate B closure, full MAN-02/MAN-03/MAN-05)

Decision needed: provider-documented facts, not choices.

- **DfT raw-count hour timezone (`GA-DFT-1`)** and **WebTRIS clock semantics**: a bounded
  documentation probe of the official DfT and WebTRIS references can be run on request; if the
  documentation is silent, the honest outcome is a recorded provider enquiry, and the rows keep
  their typed source-local exclusions.
- **BODS identifier retention/display/publication and registration terms**: requires reading the
  current BODS service terms against the intended research use; any longitudinal retention or
  public output additionally needs your decision as data controller for this project.

Probed on 24 July 2026
([machine record](integration/evidence/manchester_source_docs_probe_20260724.json)): every
official reference page checked is silent on these facts, so the honest closing step is a
direct provider enquiry (DfT road traffic statistics team, National Highways WebTRIS support,
BODS service) or their deeper authoritative documents. Until answered, the typed source-local
exclusions and precautionary BODS retention controls remain.

## 4. v0.6 producer attestation (blocks REL-01 migration and activation)

Decision needed (open question 15): what evidence proves a registry was produced by the exact
`v0.6.0` release before compatibility migration is allowed.

**Approved on 24 July 2026** and recorded in
[ADR-058](decisions/ADR-058-v06-producer-attestation.md): only an operator clean-checkout
attestation establishes `v0.6.0` producer provenance. The typed attestation
(`traffictwin.release.attestation`) binds the exact tag commit, package version, registry hash
and size, a timezone-aware instant, and the operator's literal statement; verification re-hashes
the current bytes and fails closed on drift, sidecars, or tampered literals, and a verified
attestation approves no migration or activation by itself. The migration
preview/backup/activation/rollback build-out against attested sources is now ordinary
engineering.

## 5. Manual accessibility and participant evaluation (blocks final Gate C acceptance, RQ16)

Decision needed: human execution and authority — automation cannot substitute.

- **Manual accessibility pass:** keyboard-only navigation, screen-reader labels, zoom/contrast
  checks over the 35 routes. A checklist can be generated from the audited route inventory for
  you (or a reviewer) to execute and sign.
- **Participant usability study:** first a decision with Dr. Sampaio on whether RQ16 needs a
  formal study; if yes, the existing draft materials under `docs/evaluation/` require ethics
  approval before any recruitment. Without it, RQ16 evidence remains expert-walkthrough only,
  and that limitation is recorded honestly.

## Dependency effect of each approval

| Approval given | Work unblocked |
|---|---|
| 1 (network) + 2 (matching policy) | Real map-matching candidates and analyst review |
| + 2 (calibration) | Calibration orchestration, first reviewable baseline (Gate D) |
| + 2 (comparison contract) | Production goodness-of-fit metrics (MAN-10) |
| Gate D baseline accepted | Controlled SUMO → FCD → VEC chain (Gate E, MAN-11) |
| 3 (source facts) | Gate B closure for the affected adapters; canonical time projection |
| 4 (attestation policy) | REL-01 migration preview→backup→activation→rollback build-out |
| 5 (manual/participant) | Final Gate C acceptance and RQ16 evidence |
