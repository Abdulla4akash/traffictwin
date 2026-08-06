# TfGM measured-traffic experiment brief

**Prepared:** 6 August 2026

**Status:** proposed provider-gated experiment; no traffic-measurement dataset has been received,
no probe has run, and no scientific contract or capability has been accepted.

**Privacy:** this is a publication-safe summary of private correspondence. It intentionally omits
the message text, personal contact details and signatures. The reply came from TfGM's UTC Unit; it
did not identify the respondent as a director.

## The point of the experiment

The experiment would test whether a bounded Greater Manchester SUMO/digital-twin scenario agrees
with independent, real TfGM road-traffic measurements.

It would provide observed vehicle counts, flows, speeds or detector occupancy for:

- calibrating candidate simulation settings on a declared development window;
- evaluating the frozen candidate on separate held-out observations;
- quantifying residual error, missing coverage and data quality;
- distinguishing observed traffic behaviour from simulated VEC task outcomes; and
- creating a defensible real-traffic foundation for later Manchester VEC studies.

This fills an important evidence gap. The current TfGM open-data integration contains static
signal locations, not traffic measurements. BODS measures buses rather than general road traffic;
DfT supplies historical counts but not measured speed in the intended contract; WebTRIS is limited
to strategic-road sites; and the current National Highways operational feeds do not provide
general Manchester counts or speeds.

Historical data is sufficient for the core calibration and validation experiment. A live feed
would additionally support near-live monitoring, but is not required to answer the initial
scientific question.

## What TfGM's response establishes

TfGM's UTC Unit provided a positive invitation to continue the academic request. The
publication-safe facts are:

- some SCOOT/UTC and related traffic-measurement data is available;
- several data sources and delivery arrangements may be possible;
- the academic request was described as free of charge;
- the request must be resent from a university email address with the tutor/supervisor copied;
- the researcher must identify the exact geographic area required;
- TfGM teams can discuss and arrange the most suitable access route;
- delivery method, request limits and data volume remain to be determined;
- detector/site metadata may be stored;
- time conventions depend on the source, with most described as UK local time;
- no commercially sensitive data was identified in the reply;
- TfGM expects acknowledgement as the data source; and
- related sources may include automatic traffic counters, automatic cycle counters and
  pedestrian/cycle sensor products.

These facts are an invitation to scope access, not delivery of data, a complete licence, approval
of a study, or permission to publish unrestricted row-level records.

## Proposed research question

> For one predeclared Greater Manchester area and time window, how closely do matched SUMO
> interval counts and/or speeds reproduce compatible TfGM measurements under a frozen calibration
> and comparison contract?

## Proposed publishable null

The simulation may fail to achieve the predeclared coverage or error criterion. Missing,
incompatible or low-quality observations will be reported as exclusions or unavailable evidence,
never filled with zero or hidden by selecting a favourable sub-area.

## Candidate data fields

Request only fields supplied and authorised by the selected product contract:

- vehicle flow/count per declared interval;
- measured speed, where genuinely available;
- detector occupancy, where defined by the provider;
- detector, counter and site identifiers;
- coordinates or sufficient location references for network matching;
- observation start/end timestamps and timezone;
- sampling/update interval;
- direction and vehicle class, where available;
- validity, quality, revision and equipment-status flags; and
- source/product/schema version.

SCOOT, UTC, UTMC, MOVA, automatic traffic counters, cycle counters and other sensor products must
remain separate until their schemas prove that their measures are compatible. Cycle/pedestrian
measurements must not be relabelled as general motor-traffic evidence.

## Defensible experiment sequence

1. **Scope the request** — agree the geographic boundary, products, dates, intervals and measures
   with the supervisor.
2. **Complete provider terms** — record dataset-specific access, limits, attribution, retention,
   publication, detector-metadata, timestamp/DST and sensitive-field conditions privately.
3. **Minimum-volume intake** — obtain a schema/sample or the smallest authorised read-only export;
   preserve exact private bytes and a secret-free receipt before parsing.
4. **Source audit** — validate schema, units, intervals, coordinates, quality flags, revisions,
   missingness and exact local-time/DST semantics.
5. **Spatial matching** — match eligible detector sites to the reviewed SUMO network under a
   predeclared distance, direction, road-class and ambiguity policy; retain unmatched sites.
6. **Calibration** — evaluate all declared parameter candidates on the same development window;
   select only a candidate for analyst review, never automatic acceptance.
7. **Held-out comparison** — freeze the candidate and compare it with separate observations using
   exact site/edge and time-interval pairing.
8. **Report** — publish coverage, exclusions, residuals and agreed metrics with TfGM attribution;
   keep restricted raw rows and credentials private.

## Candidate outcomes

The existing TrafficTwin contracts can report, once approved:

- paired observed and simulated coverage on both sides;
- signed residuals (`simulated − observed`);
- mean absolute error or root mean square error;
- site/time distributions and explicit exclusion reasons; and
- data-quality, freshness and revision summaries.

GEH or any acceptance threshold must be justified and agreed with the supervisor before use. A
software default, a favourable result or a post-hoc threshold is not an acceptable basis.

## Decisions needed from the supervisor

1. Manchester local-authority boundary, event district, selected corridors, or another exact area.
2. Historical archive, periodic export, delayed feed or live feed for the first study.
3. Primary measure: vehicle count/flow, measured speed, occupancy, or a separated set of studies.
4. Development and held-out dates/windows, including event and ordinary-day coverage.
5. Map-matching thresholds and manual-review policy.
6. Calibration objective, parameter grid, uncertainty treatment and minimum coverage.
7. Comparison metric, primary endpoint and success/null rule.
8. Whether detector identifiers/locations may appear in dissertation outputs or only aggregates.

## Provider facts still required

- exact product and data owner;
- delivery mechanism, endpoint/export format and schema sample;
- credentials, IP restrictions and account process;
- request frequency, concurrency and volume limits;
- exact units, interval boundaries, quality flags and revision semantics;
- UTC/local-time fields and daylight-saving fold/gap handling;
- geographic and temporal coverage;
- retention, backup, deletion and raw-data publication restrictions;
- permitted treatment of detector identifiers and coordinates;
- operational/security-sensitive fields, if any;
- exact acknowledgement wording and derived-publication rights; and
- support and change-notification process.

The reply stated that no formal licence was currently proposed and that TfGM should be
acknowledged, but dataset-specific retention and publication terms still need written
clarification. It also addressed commercial sensitivity, not every possible operational or
security restriction.

## Recommended follow-up request

Send the follow-up from the university account, copy the supervisor, and include:

- the exact selected map boundary or detector/site list;
- the preferred historical dates and interval resolution;
- a ranked list of required measures and metadata;
- a request for a schema/data dictionary and minimum sample before bulk access;
- confirmation of time/DST, quality/revision, rate and volume rules; and
- confirmation of attribution, retention and aggregate-publication conditions.

Do not request credentials, bulk data or a live feed until the product-specific terms and minimum
scientific design are agreed.

## Interpretation limits

- This is not yet a completed experiment.
- Provider willingness does not establish data quality, completeness or scientific validity.
- Calibration does not prove the simulation is a copy of reality.
- Observed-versus-simulated differences are descriptive, not causal.
- A Manchester traffic calibration does not automatically validate a VEC scheduler or actor.
- Real traffic input does not make synthetic tasks, RSUs, radio conditions or compute outcomes
  physically observed.
- Each TfGM product requires its own accepted contract; one reply cannot enable every source.

## Repository relationship

This proposed study would use the provider-contract boundary described in the
[v0.7 design](../traffictwin-design-v0_7.md), followed by the existing
[calibration candidate evaluator](../integration/manchester_calibration.md) and
[observed-versus-simulated comparison](../integration/manchester_comparison.md). Production
contract registries remain empty, and no real comparison has been run.
