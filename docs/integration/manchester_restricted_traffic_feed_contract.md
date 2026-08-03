# Restricted TfGM/NTIS traffic-feed contract intake

Phase 198 implements the pre-adapter intake boundary for five independently reviewed products:

- TfGM SCOOT;
- TfGM UTC;
- TfGM UTMC;
- TfGM automatic traffic counters; and
- National Highways NTIS measured traffic.

This is contract tooling, not a traffic-data adapter. No provider response or agreement is recorded
in the repository, no credentialed probe is authorised, and measured speed, flow, occupancy,
signal state or counter data remains unavailable. Acceptance for one product never enables a
sibling product.

## Create a private intake template

Choose exactly one product identifier from `tfgm_scoot`, `tfgm_utc`, `tfgm_utmc`,
`tfgm_automatic_counter`, or `ntis_measured_traffic`:

```bash
uv run traffictwin integration manchester provider template tfgm_scoot --format json
```

The emitted template is deliberately all-unknown and non-enabling. Store a completed copy outside
the repository. Do not copy provider email prose, agreements, contact details, credentials,
endpoint URLs, private paths or sample rows into it. Record only reviewed facts, safe internal
reference identifiers, and SHA-256 digests of private response/schema/sample evidence.

Every product must resolve its own academic eligibility, delivery mode, price/quotation,
onboarding, rate and volume limits, licence and retention, publication rights, detector treatment,
timestamp timezone and DST semantics, sensitive-field exclusions, exact schema, coverage, units,
quality, outage, support and change-notification facts. Unknown values remain blockers. Paid or
bespoke access requires a quotation decision and separately approved budget authority; the
contract never creates spending authority.

## Inspect safe readiness

Validate a private completed contract and print only its allowlisted readiness projection:

```bash
uv run traffictwin integration manchester provider status /private/path/contract.json --format text
```

Use `--format json` for the equivalent machine-readable assessment. Output contains the product,
provider family, contract fingerprint, blocker codes and next stage. It excludes the input path,
provider prose, credentials, raw rows and private evidence.

Readiness is deliberately narrow:

- `unavailable_awaiting_provider_contract` means no reviewable provider response is present;
- `provider_response_under_review` means a response exists but review or required facts remain;
- `provider_contract_refused` ends the adapter path for that product; and
- `contract_accepted_adapter_not_implemented` means contract facts passed review, but no adapter or
  probe exists.

Even the accepted state stops before implementation. The next separate stage must freeze an exact
transport and credential role, receive explicit authority for one minimum-volume read-only probe,
preserve immutable response evidence, and only then implement and test a product-specific parser.
Provider-defined fields, units, cadence, quota, timezone, identifier permissions and publication
rights are never inferred from another source.

See the canonical [`NEXT-08` design](../traffictwin-design-v0_7.md#279-next-08--provider-gated-tfgmntis-measured-traffic-adapters)
for the post-contract Gate-A/B sequence.
