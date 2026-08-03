# Meeting 1–3 Live Feature Gap Audit

**Audit date:** 3 August 2026

**Repository:** `Abdulla4akash/traffictwin`

**Current repository baseline:** `main` at
`49be6a2db8a69409a1b92fb02e954db7cf1441f6`; the original live-app inspection was performed over
the integrated feature head `c3e2dc8` before its fast-forward into `main`.

**Purpose:** Compare the product and research capabilities requested in supervisor
Meetings 1, 2 and 3 with the repository and the locally running TrafficTwin app.

## Sources and interpretation

The comparison used the private local records `supervisor_meeting_1 notes`,
`supervisor_meeting 2` and `sandra meeting 3`. The two Randy meeting records were
used as supporting detail for the TOS, RSU-monitoring and explainability
requirements.

In this audit, **live** means that a feature is operational with an accepted real
workspace and real inputs. A page, contract, synthetic fixture, offline import or
backend implementation does not by itself make a capability live.

## Executive conclusion

TrafficTwin has a substantial local research interface, import-first analysis
workflow and evidence-governance backend. However, the complete Manchester
digital-twin loop described in the meetings is not operationally live.

During the 3 August live inspection, port `8501` was serving a temporary demo workspace and
no service was listening on port `8502`. The app reported:

- Manchester evidence unavailable;
- zero visible Manchester evidence layers;
- no accepted latest-available Manchester scene;
- an invalid isolated v0.7 workspace for operational acquisition;
- inactive BODS and National Highways automatic refresh;
- no forecast aggregates; and
- draft-only what-if composition with no execution.

Those nine feature commits are now integrated on default `main`, and the Python 3.11/3.12 CI run
for `49be6a2` passed. Integration changes repository availability, not operational evidence: it did
not populate a real workspace, activate a deployment, obtain a provider response, complete human
review or accept a scientific gate. The live verdicts below therefore remain unchanged.

## Features that are not live

| Meeting requirement | Current implementation | Live verdict |
|---|---|---|
| Complete current view of Manchester traffic | Manchester Operations and source-separated map contracts exist, but the running workspace has no accepted Manchester scene. | **Not live** |
| Continuous city-road flow, speed, volume and congestion | BODS covers bus positions and National Highways covers bounded Strategic Road Network events. Neither is continuous city-road traffic telemetry. | **Not live** |
| Fusion of sensors, traffic authorities, drivers, pedestrians, mobile data and social media | Source-specific adapters and contracts exist. There is no operational unified feed or driver, pedestrian, mobile or social-media ingestion. | **Not live** |
| Real-time and scheduled batch/stream ingestion | Process-lifetime BODS and National Highways workers and scheduled-session tooling exist, but the inspected workspace is invalid/unpopulated and the workers are inactive. OS-level scheduled operation is not configured. | **Backend only; not live in the inspected deployment** |
| Historical traffic store and streaming analytics | Aggregate SQLite, activation, backup/restore and analytics tooling exist. No owner-selected real store has been populated or scheduled. | **Backend only; not live** |
| One-, two- and three-hour traffic forecasting | The Forecasts route exists, but it has no activity aggregates and the held-out validation has not run. Its bounded bus climatology is not a general road-traffic forecast. | **Not live** |
| Journey-time, waiting-time, departure-time and alternative-route prediction | Journey-time views analyse imported/completed runs. They do not provide validated future Manchester route or departure advice. | **Offline analysis only** |
| User-authored what-if incidents, lane closures, signal changes and scheduled events | The composer can translate structured or natural-language scenarios and produce a surrogate prediction plus an unsigned campaign draft. It does not execute SUMO, approve a campaign or create evidence. | **Draft only; not live execution** |
| SUMO outcomes directly connected to what-if scenarios | A loopback-only controlled SUMO transport exists for a pinned synthetic square. It is not a generic or calibrated Manchester what-if service. | **Synthetic engineering capability only** |
| Decision hints, route recommendations and infrastructure recommendations | Observatory and Decision Safety pages are read-only. They have no action authority and cannot recommend or apply road, signal, route or RSU changes. | **Not live** |
| Calibrated observation-to-SUMO Manchester twin | Gate D remains `foundation_only`. All 174 named-person mapping decisions are pending, the calibration registry is empty and the preserved demand candidate failed through gridlock. | **Not live** |
| Observed-versus-simulated Manchester comparison | No accepted Manchester baseline, controlled run or compatible simulated interval set exists. | **Not live** |
| Complete Manchester SUMO-to-VEC lineage and evaluation | Contracts and lineage views exist, but there is no accepted end-to-end Manchester result. | **Not live** |
| Full capacity and multi-algorithm benchmark across seeds, traces and workload levels | The 2,400-job benchmark plan is `PROPOSED / UNSIGNED`. Only a deterministic 21-job synthetic engineering fixture has executed. | **Not live** |
| Capacity-aware follow-up reinforcement-learning model | No real capacity-aware training, checkpoint evaluation, comparison or scientific admission has been completed. | **Not live** |
| Real learned-policy inspection and explainable AI | Decision Audit contains synthetic snapshots, replay baselines and SHAP/Integrated-Gradients-shaped integrity fixtures. No authorised real actor/checkpoint or validated attribution method is connected. | **Synthetic only; real XAI not live** |
| Live RSU and vehicle resource monitoring | The RSU Monitor is explicitly historical replay over an imported simulation. It is not live monitoring and requires a TOS package import first. | **Offline replay only** |
| Automated retraining or RSU-placement recommendations | The platform can expose descriptive evidence, but it does not retrain models, execute campaigns or authoritatively recommend infrastructure changes. | **Not live** |
| Traffic-analyst, driver and end-user evaluation | No participant results, completed ethics-supported study or human usability acceptance exists. | **Not live** |
| Public or mobile deployment | The application is a local Streamlit research interface without public hosting, production authentication or mobile release acceptance. | **Not live** |

## Meeting 3 result that is available

The counter-intuitive capacity/latency investigation is available as a read-only
Mechanism Observatory. The admitted result reports that reducing the tested
capacity was associated with a mean paired latency change of approximately
`-8,310.9 ms` over five held-out paired seeds, while offloading actions remained
unchanged across the tested capacity arms.

This is a meaningful Meeting 3 outcome, but the interface correctly preserves the
following limits:

- the exact two-sided sign-test floor is `p = 0.0625`, so conventional
  significance is not claimed;
- much of the mechanism interpretation remains post-hoc or exploratory;
- the result does not establish a general causal diagnosis;
- the latency reduction occurred within already-failed tasks and does not show an
  improvement experienced by an individual vehicle; and
- no capacity-aware follow-up model or real attribution system has been admitted.

See [capacity confirmatory results](evaluation/capacity_confirmatory_results_20260728.md)
and the canonical [implementation status](implementation-status.md#data-platform-and-meeting-3-implementation-status-3-august-2026).

## Capabilities that are currently working

The following should not be described as missing:

- local task-oriented Streamlit navigation;
- synthetic scenario creation and guided demonstration;
- import and validation of generic, SUMO and TOS result artifacts;
- deterministic temporal, energy, fairness, infrastructure and RSU metrics;
- comparisons, statistical studies, diagnostics, provenance and report exports;
- historical TOS/RSU replay when an accepted package is imported;
- a bounded local SUMO/TraCI engineering smoke over the pinned synthetic square;
- draft-only what-if composition and surrogate predictions with explicit evidence
  limits; and
- read-only capacity-mechanism, evidence-matrix, observatory and decision-safety
  presentation.

## Overall status

The interface and bounded research tooling are working. The meetings' intended
real product—a populated, continuously updated and calibrated Manchester digital
twin that forecasts traffic, executes user-authored scenarios and supports
validated decisions—is **not yet live**.

Release engineering and documentation hygiene are tracked separately in the
[v0.7 housekeeping completion record](quality/v07_housekeeping_completion_20260803.md). Passing
those technical gates does not change any live verdict in this audit.
