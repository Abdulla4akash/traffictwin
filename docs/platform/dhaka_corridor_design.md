# Design — Dhaka corridor network build (Bangladesh tier 2, optional)

**Status: IMPLEMENTED through the authorised Phase-146 network-build feasibility boundary
(`b377e0a`, amended by `a2b427e`) at the `owner_approved_candidate` ceiling. The owner
selected the Dhaka–Airport road corridor and authorised the pinned dated extract; the build
completed with an ACCEPTED receipt and zero feasibility gaps. The honest artifact remains a
receipted Dhaka-corridor *network-build feasibility result*, not proof that a calibrated or
operational twin runs in Dhaka. It is for the transferability/funding discussion, not the
admitted dissertation evidence chain.**

## 1. What is built

One Dhaka corridor network (not city-wide): pinned dated Bangladesh extract → bounded
`osmium` clip to an owner-selected corridor → controlled PBF decode → pinned `netconvert`
build → streaming structural/extent validation → durable storage with source/derived
identity separation, digests, licence and receipts.

This reuses lower-level Manchester patterns, not the exact Manchester contract.
`rebuild_baseline_network.py`, `ManchesterBaselineNetworkBinding`,
`BaselineScopeDecision` and `SubAreaCoverage` hard-code Greater Manchester, Manchester
local-authority code `E08000003`, and the Manchester method version. Passing Dhaka bytes
through them unchanged would create false provenance. The slice therefore needs either a
small region-neutral network-build contract in a disjoint module, regression-tested against
Manchester fixtures, or a new Dhaka-specific binding. Either option reuses only the generic
integrity/decode/streaming primitives. Existing Manchester bindings and evidence remain
byte-unchanged.

## 2. Frozen owner decisions and build input

- **BD-D1 — DECIDED 1 August 2026.** The owner selected the Dhaka–Airport road corridor
  (Mohakhali → Hazrat Shahjalal International) and froze its bounding box and four
  landmarks in the committed scope record.
- **BD-D2 — DECIDED 1 August 2026.** The owner authorised acquisition of the dated
  `bangladesh-260731.osm.pbf` Geofabrik artifact. Its reference date, size, SHA-256,
  provider MD5, retrieval time, licence and attribution are bound in the committed pin.

The exact decisions and measured result are recorded in
[`dhaka_corridor_feasibility_20260801.md`](../integration/dhaka_corridor_feasibility_20260801.md).
No traffic, BRTC or congestion rationale was inferred from the network build.

## 3. Known transfers and known unknowns

Transfers: workspace containment, explicit network access confirmation, source/derived
identity separation, bounded external processes, PBF sniff/decode, pinned executable
versions, streaming inspection, geometry-source accounting, private-path rejection,
licence/attribution carriage and durable receipts.

Does **not** transfer unchanged: Manchester scope literals, official-area containment,
baseline identity, acceptance thresholds, calibration, observation coverage, or the
`sub_area_probe_only` label. The Dhaka role follows from a new declared target corridor and
measured network extent. A corridor may be called `corridor_network_candidate`; whether it
contains its requested corridor is a measured field. It is not a city baseline either way.

Unknowns to measure and record, not assume: OSM road/tag/geometry completeness inside the
frozen corridor; connected components and routability; warning classes; projection chosen
by `netconvert` near the UTM 45N/46N boundary, checked against at least four owner-approved
landmarks; extent and clipping artefacts; and build resource use. Manchester's observed
36% no-shape/class mix is comparison context, not a prior claim about Dhaka.

This repository currently holds no admitted Dhaka counts, demand, live-bus observations or
calibration. That is a project data gap, not a claim that such data does not exist. The
network ships `observation_status: unavailable`, never zero; it cannot produce traffic,
congestion or VEC findings without separately governed data and protocols.

## 4. Governance

New scope/binding + build script additions use a disjoint namespace; Manchester scope,
bindings and evidence remain untouched. The build record states plainly that this artifact
carries no observations, demand, routes, calibration, behavioural model, VEC execution or
scientific validation. It is a network-layer engineering feasibility artifact only.

OSM-derived bytes retain ODbL 1.0 metadata and visible
`© OpenStreetMap contributors, ODbL 1.0` attribution through the receipt and any rendered
map. Raw PBF/XML/network outputs remain in the owner workspace unless their publication
basis is explicitly reviewed; a public source is not automatic permission to publish every
derived bundle. No private paths enter committed records.

## 5. Acceptance and tests

Offline fixtures cover the generic/Dhaka scope schema, Manchester-literal rejection,
source/derived identity separation, unsafe destination/private-path refusal, checksum and
licence drift, bounded subprocess arguments, measured extent/role classification, projection
and landmark reconciliation, no-observation labels, and deterministic receipts. The authorised
build recorded exact tool versions, resource use and warnings and passed the same deterministic
contract exercised by the offline fixtures. It ran no traffic simulation, campaign, training or
cloud compute.

Acceptance means the pinned input was verified, the requested corridor containment and
structural/routability checks were measured, receipts contain no private path, and the
artifact stays observation-empty. A failed build or incomplete network yields a typed,
reviewable feasibility-gap report; it is not silently repaired or described as a twin.

## 6. Effort and stop rule

Earlier notes estimated approximately one day. The measured build used 6.8 seconds of tool
time, with contract work recorded separately; the estimate was not authority. The stop rule
held at one selected corridor and one pinned extract. Do not expand to a city-wide build,
acquire observations, tune thresholds or launch experiments without a new owner decision.
