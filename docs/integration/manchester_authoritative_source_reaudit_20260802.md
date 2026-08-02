# Design — authoritative Manchester source re-audit

## Status and boundary

- Phase: 185
- Date: 2 August 2026
- State: completed bounded official-source review
- Evidence class: documentation/contract audit, not operational or scientific evidence

This audit revisits only the three facts left open by the 24 July documentation probe: the DfT
raw-count `hour` clock basis, the WebTRIS daily-report clock basis, and BODS consumer use,
registration, publication and retention terms. A current official page may close a fact only when
it states that fact. Plausible UK-local time, a page footer licence, or source silence is not enough.

## Exact owned paths

- `docs/integration/manchester_authoritative_source_reaudit_20260802.md`
- `docs/integration/evidence/manchester_authoritative_source_reaudit_20260802.json`
- `docs/integration/provider_enquiry_drafts.md`
- `docs/integration/manchester_bods_retention.md`
- `docs/integration/manchester_bods_acquisition.md`
- `docs/integration/manchester_bods_gate_b_probe.md`
- `docs/integration/manchester_live_feature_matrix.md`
- `docs/integration/manchester-source-gate-a-audit-v0_7.md`
- `docs/open-questions.md`
- `docs/v07_external_decision_pack.md`
- `docs/v07_requirement_matrix.md`
- `tests/unit/test_manchester_authoritative_source_reaudit.py`
- `docs/index.md`
- `docs/implementation-status.md`
- `docs/current_progress_v0_7.md`
- `CHANGELOG.md`
- `AGENTS.md`

## Method

Use first-party sources only: the official Road Traffic Statistics metadata/API guidance,
National Highways WebTRIS API/FAQ, GOV.UK BODS consumer/implementation/SIRI-VM guidance and, where
needed, primary legislation. Record the page, access date, exact proposition supported, and any
silence. Keep licence/use rights separate from project privacy, research governance and release
approval.

## Acceptance

The structured record must keep `GA-DFT-1` and `GA-WT-1` open unless explicit clock/timezone text is
found. For BODS it must distinguish general consumer rights, API registration/attribution
conditions, source-specific retention text, identifier persistence, and project public-output
approval. No statement may convert permission to reuse open data into approval for TrafficTwin to
publish longitudinal vehicle traces.

## Findings

### DfT raw-count hour — blocker remains open

The current official Road Traffic Statistics metadata still defines `hour` only by clock range
(for example, 7 is the interval 07:00–08:00). Searches of that document and the official API/
statistics guidance found no `timezone`, UTC, GMT or British Summer Time basis. `GA-DFT-1`
therefore remains open. Raw counts stay `(count_date, local_clock_hour_label)` evidence; no UTC
instant, BST offset or cross-source sub-day alignment is admitted.

### WebTRIS report intervals — blocker remains open

The current National Highways FAQ defines the month-in-arrears update schedule and the data-quality
calculation but gives no timezone. The current Swagger definition likewise contains no timezone,
UTC, GMT or BST statement for report dates or `Time Period Ending`. `GA-WT-1` remains open and
WebTRIS strings remain `source_string_undeclared`. WebTRIS remains historical/latest-available,
not near-live.

### BODS consumer terms — general rights and registration are documented

The deeper official BODS implementation guide resolves what the 24 July landing-page probe missed:

- bus open data is published without restrictions on use/disclosure and may be combined,
  transformed and shared commercially or non-commercially;
- consumers may copy, adapt, publish, distribute and transmit it, including for academic research;
- API consumers must register an account using an email address;
- products must attribute BODS, must not imply DfT/operator endorsement, and must state that DfT
  does not warrant source accuracy/quality; and
- access may be removed for illegal use, misuse or system-overloading behaviour.

The separate official consumer page calls timetable, vehicle-location and fares data freely
available for commercial, non-commercial and academic use. The SIRI-VM guide confirms that bus
locations are open to all, documents UTC timestamps, limits the national archive request to no more
than once every five seconds, and requires `VehicleRef` to be consistent through the day.

Accordingly, the generic BODS consumer-use/publication and API-registration blockers are closed as
source-fact questions. `GA-BODS-6` is closed. General BODS data rights no longer require a provider
reply before an attributed academic aggregate or application can be designed.

## BODS residual that is deliberately not closed

No reviewed official source states a consumer snapshot retention period or whether `VehicleRef`
persists across days; the implementation guide contains no retention or `VehicleRef` text, while
the SIRI profile states only same-day consistency. The absence of a source-specific retention cap
does not establish that longitudinal vehicle traces are harmless, non-personal or appropriate for
this project.

TrafficTwin therefore keeps raw SIRI-VM snapshots private and bounded, keeps identifiers out of
logs/public fixtures, and requires a separate project privacy/data-management and release decision
for retained longitudinal traces or row-level positions. The official general publication right
and a TrafficTwin release approval are different gates. Aggregate/public output also remains
blocked by complete Bee membership/licence reconciliation and ordinary Gate-B/Gate-F acceptance.

## Disposition

| Question | Result | TrafficTwin effect |
|---|---|---|
| DfT `hour` timezone | official sources still silent | `GA-DFT-1` open; no UTC projection |
| WebTRIS interval timezone | official sources still silent | `GA-WT-1` open; preserve strings |
| BODS general reuse/publication | explicitly permitted with conditions | generic source-rights blocker closed |
| BODS API registration | account + email documented | `GA-BODS-6` closed; no account created here |
| BODS attribution/quality/endorsement | explicit conditions documented | required in any future product/export |
| BODS snapshot retention / multi-day `VehicleRef` | no duration; multi-day persistence undocumented | precautionary private bounded retention remains |
| TrafficTwin public row-level vehicle output | no project privacy/release approval | unavailable |

No capability or gate is accepted by this re-audit. The two timezone enquiries and the narrowed
BODS identifier/retention question remain ready to send if the project chooses to contact the
providers.

## Official sources

- [Road Traffic Statistics metadata](https://storage.googleapis.com/dft-statistics/road-traffic/all-traffic-data-metadata.pdf)
- [Road Traffic Statistics API documentation](https://roadtraffic.dft.gov.uk/api-documentation)
- [National Highways WebTRIS FAQ](https://webtris.nationalhighways.co.uk/Home/Faqs)
- [National Highways WebTRIS API definition](https://webtris.nationalhighways.co.uk/api/swagger/docs/v1)
- [BODS implementation guide](https://www.gov.uk/government/publications/bus-open-data-implementation-guide/bus-open-data-implementation-guide)
- [Find and use bus open data](https://www.gov.uk/guidance/find-and-use-bus-open-data)
- [BODS SIRI-VM technical guidance](https://www.gov.uk/government/publications/technical-guidance-publishing-location-data-using-the-bus-open-data-service-siri-vm/technical-guidance-siri-vm)

## Verification

The companion JSON records each proposition, silence and residual separately. Static integrity
tests must verify official HTTPS hosts, status transitions and the continuing false values for
account creation, credential use, provider contact, raw-publication and capability acceptance.
