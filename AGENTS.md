# TrafficTwin Agent Instructions

Repository root: `diss/`

Canonical product specification: `docs/traffictwin-design-v0_5.md`

Before architectural work or implementation decisions, read the canonical specification completely. Treat it as the product and research specification, while keeping unconfirmed external integrations behind explicit capability interfaces.

The v0.5 specification is a design target, not an implementation claim. The historical
`docs/traffictwin-design-v0_4.md` remains the rationale and supervisor-meeting traceability record.
Use `docs/implementation-status.md` to determine what is actually implemented.

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

The historical `../XITS/` notes are preserved as research material. They are not active implementation blockers for the approved TrafficTwin v0.4 build.
