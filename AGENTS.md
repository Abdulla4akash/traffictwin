# TrafficTwin Agent Instructions

Repository root: `diss/`

Canonical product specification: `docs/traffictwin-design-v0_7.md`

Before architectural work or implementation decisions, read the canonical specification completely. Treat it as the product and research specification, while keeping unconfirmed external integrations behind explicit capability interfaces.

The v0.7 specification is the approved future product design for Manchester historical/live
evidence, observed-to-SUMO calibration, SUMO-to-VEC research flow, and the task-oriented product
interface. Every `MAN-*`, `UX-*`, and `REL-01` capability begins planned; design inclusion does not
make it implemented. The immutable `v0.6.0` release remains the implemented reproducible baseline.
VEC-01 through VEC-12 have passed their recorded evidence gates, but this does not broaden any
residual scientific, licensing, hosting, canonicalisation, or generic-launch boundary. Use
`docs/implementation-status.md` for current truth.

## Non-Negotiable Constraints

- The guaranteed workflow is import-first.
- Direct Randy VEC/SUMO launch is conditional and must not be faked.
- Metrics must be computed by deterministic code.
- Diagnostic hypotheses must be produced by deterministic rules.
- An LLM, if added later, may only render already-computed findings into prose.
- Do not let an LLM calculate metrics, invent findings, or recommend unsupported actions.
- Do not fabricate Randy schemas, CSV fields, simulator capabilities, launch commands, live data, experimental results, paper claims, or performance numbers.
- Preserve raw inputs unchanged.
- Keep unsupported or unknown functionality visibly unavailable rather than silently simulated.
- Use synthetic fixtures only when clearly labelled synthetic.
- Keep the UI thin over tested library code.

## Project Records

As the project evolves, update:

- `docs/implementation-status.md`
- `docs/assumption-register.md`
- `docs/open-questions.md`
- `docs/architecture.md` when architecture decisions change

## v0.7 Work Coordination

### Active parallel ownership grant: Claude UI presentation Phase 1

- Claude owns advisory presentation groundwork for `UX-01`–`UX-03` on
  `claude/ui-redesign`, forked from the first pushed lead v0.7 integration commit after
  `c2160999c6c66ab3b871b2ebd0ef6645a1ee6952` that records this grant. This grant does not accept a
  gate or permit any capability-status change.
- The exclusive Phase 1 file set is `.streamlit/config.toml`,
  `src/traffictwin/ui/theme.py`, `src/traffictwin/ui/tables.py`, every tracked source file under
  `src/traffictwin/ui/components/`, and new tests named
  `tests/unit/ui/test_components_*.py` or `tests/unit/ui/test_tables_display.py`.
- Existing public functions, imports, arguments, and return shapes in the claimed presentation
  modules must remain backward compatible because lead-owned in-flight pages consume them. New
  display models and helpers may be additive; removing or renaming an existing API requires a new
  lead review.
- Claude must not edit `src/traffictwin/ui/app.py`, either navigation module,
  `src/traffictwin/ui/manchester_operations.py`, any file under `src/traffictwin/ui/pages/`, any
  existing test outside the exact new-test allowance, `pyproject.toml`, `uv.lock`, integration or
  CLI code, shared project records, generated references, documentation indexes, changelog, or
  this `AGENTS.md` file.
- If the branch was created earlier, it must be rebased onto that pushed integration commit before
  work continues. Merge is conditional on focused component tests, existing UI tests, the full
  relevant unit suite, light- and dark-theme smoke checks, and lead review of the complete branch
  diff. Phase 2 page or navigation work requires a fresh disjointness check and a separate
  ownership grant.

- Use `MAN-01`–`MAN-11`, `UX-01`–`UX-03`, `REL-01`, and Gates A–F from the v0.7 design as units of
  ownership. Record the capability and files owned before editing; agents sharing one checkout
  must use disjoint file sets.
- v0.7 Gate A is accepted in
  `docs/integration/manchester-source-gate-a-audit-v0_7.md` and ADR-054 through ADR-057. It is the
  serial prerequisite for source-specific schema, time/freshness, licence, publication, transport,
  and parser work. Agents may implement Gate B only against those frozen decisions and scoped
  blockers; documentation or a successful API response alone still does not accept an adapter or
  complete `MAN-01`.
- Acquisition, parsing, normalisation, map matching, calibration, comparison, and UI work must
  remain separate tested boundaries. Streamlit pages read accepted local snapshots through
  services and must not fetch external APIs or implement scientific formulas.
- Treat the v0.6 tag and valuable v0.6 workspaces as immutable. v0.7 compatibility is read-only and
  copy-on-write until `REL-01` passes migration, rollback, and side-by-side acceptance.
- Shared integration surfaces—CLI, capability manifests, generated references, navigation,
  changelog, documentation indexes, and project records—remain lead-owned merge files unless
  ownership is explicitly transferred.
- No agent may independently mark a v0.7 capability implemented. The integrating agent reconciles
  code, tests, real-source acceptance evidence, security/licence checks, UI acceptance, generated
  contracts, documentation, and capability truth.

## Preserved v0.6 Evidence Boundaries

- Use the v0.6 capability IDs and Gates A–G as the unit of ownership. Record the capability and
  files owned before editing; agents sharing one checkout must use disjoint file sets.
- v0.6 Gate A (`VEC-01`) is the serial prerequisite and is now accepted in
  `docs/integration/randy-source-snapshot-audit-v0_6.md` plus its generated machine record. No
  agent may implement a schema, mapping, join, or launcher from the email alone; use the pinned
  observed contract, limits, hashes, and blockers from that audit.
- After v0.6 Gate A, contract/fixture work (`VEC-02`), read-only identity/trip joins (`VEC-03`–`VEC-05`),
  and preprocessing/runner work (`VEC-06`–`VEC-08`) may proceed in separate worktrees or explicitly
  disjoint modules. `VEC-09` and `VEC-10` consume only accepted upstream artifacts; `VEC-11` is
  accepted through its permission-manifested pack, and `VEC-12` closes the final reconciliation
  gate with an offline-verifiable artifact.
- Gate C read-only joins (`VEC-03`–`VEC-05`), Gate D (`VEC-06`), the library-level `VEC-07` runner,
  the pinned-case `VEC-08` reproduction verifier, and Gate F scientific admission (`VEC-09`) are
  accepted. VEC-03 identities are valid only inside
  exact reconciled inclusive occupancy spans and a snapshot is bound to the complete trace
  fingerprint. `VEC-07` may consume only
  an exact Gate-A-reviewed trace or a trace identified by a completed, validated VEC-06 receipt; it
  must not bypass preflight or execute an arbitrary script/NPZ. VEC-08 establishes scoped numerical
  equivalence only for its recorded full weekend protocol-seed CPU case.
- VEC-09 admits only contract-compatible task/latency/decision/trip-duration metrics plus separately
  named TOS deadline-success, slot-tier, and no-target measures. It must keep physical completion,
  per-task energy, canonical infrastructure, confirmed-target, protected-attribute fairness, and
  occupancy-cohort trip completion unavailable. R1, R2, and R7 remain blocked; R6 is conditional
  and no threshold or finding was evaluated during admission.
- VEC-10 is accepted as a thin interface. Its VEC evaluator control is conditional on the exact
  request-specific VEC-07 preflight and foreground current-process execution. Do not add arbitrary
  commands, detached/background jobs, a persistent queue, training, dependency installation, or
  source mutation. Default generic/SUMO direct launch remains false.
- VEC-02 and VEC-11 are accepted together at Gate B/G: the exact observed contract is accompanied
  by the reviewed three-row pseudonymised/rounded `_s102` sample and VEC-09 aggregates. Never add
  raw IDs, identity mappings, clocks, targets, private paths, checkpoints, repositories, or
  third-party SUMO assets. Pseudonymisation is not anonymity; public hosting remains unauthorised
  until the project licence and every external publication basis are explicit.
- VEC-12 is accepted at the final Gate-G boundary. Its deterministic 27-member ZIP may embed only
  the allowlisted audit/software metadata and VEC-11 sanitised sample/aggregates. Preserve the
  VEC-08 protocol-seed versus VEC-09/VEC-11 `_s102` run distinction, complete limitations and
  exclusions, fixed ZIP metadata, checksums, offline verification, and new-only publication. Do
  not add raw external/execution bytes or strengthen licensing, hosting, anonymity, completion,
  energy, transfer, diagnostic, causal, scenario, or platform claims.
- Treat shared integration surfaces—`src/traffictwin/cli.py`, capability manifests, generated
  references, documentation indexes, changelog, and project records—as lead-owned merge files.
  Feature agents should expose tested library APIs first and leave final shared-surface wiring to
  the integrating agent unless ownership is explicitly transferred.
- External repositories under `../external/` are read-only evidence. One designated audit owner
  may synchronise them after confirming a clean state; no agent may edit, commit, clean, switch,
  merge, or push those repositories as part of TrafficTwin implementation.
- Each handoff must include exact source commits, inspected relative paths and hashes, changed
  files, tests run, residual blockers, and capability truth. Agents cannot independently mark a
  v0.6 capability implemented; the integrating agent reconciles code, tests, docs, generated
  references, and acceptance evidence first.
- Prefer separate branches/worktrees. If agents must share the current checkout, do not run broad
  formatters, generators, staging, commits, or cleanup while another agent owns overlapping files.

The historical `../XITS/` notes are preserved as research material. They are not active
implementation blockers for the approved TrafficTwin design.
