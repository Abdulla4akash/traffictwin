# WebTRIS near-live reassessment

Status: **near-live refused; latest-available historical workflow verified**

## Outcome

TrafficTwin cannot honestly use WebTRIS as a near-live road feed. The official WebTRIS FAQ says
data is normally processed and uploaded about one month in arrears. A controlled real-source
probe on 24 July 2026 agreed with that publication boundary:

- site `34` (`M56/8150A`) returned HTTP `204` and no body for 23 July 2026;
- 24 June 2026 returned HTTP `200` with a complete 96-interval JSON day;
- the June response passed TrafficTwin's bounded fetch, quarantine-before-parse, exact parser,
  immutable promotion, quality-row validation, and offline replay boundaries;
- all 96 intervals were accepted, no interval was filled with zero, and one quality row was
  accepted.

The machine-readable, body-free probe record is
[`manchester_webtris_recency_probe_20260724.json`](evidence/manchester_webtris_recency_probe_20260724.json).
It records response metadata and decoded-body hashes but contains no raw source body, cookie, or
credential.

## Product consequence

WebTRIS remains useful for National Highways strategic-road **historical/latest-available** charts,
site layers, replay, observed-versus-simulated preparation, and dissertation evidence. It is not a
live Manchester traffic monitor. Retrieval time cannot replace observation time, and `GA-WT-1`
still prevents UTC promotion of its source clock strings.

The 23 July response is treated as unavailable, not as a zero-traffic day. The accepted 24 June
day is labelled historical. No `MAN-*` capability changes status from this probe.

## The actual National Highways real-time route

National Highways documents a separate National Traffic Information Service (NTIS) subscriber
service for real-time incidents, journey times, speeds, flows, and signs. Its DATEX II interface
pushes messages to a subscriber-hosted callback; it is not an anonymous request/response WebTRIS
endpoint and cannot reuse the WebTRIS source contract.

Before TrafficTwin can build that path, a new Gate-A audit must obtain and freeze:

1. an approved Traffic England/NTIS subscriber account and credentials;
2. the exact subscribed data products, Manchester/strategic-road scope, and provider terms;
3. the current WSDL/DATEX II schema, source timestamps, timezone, sequence, retry, and heartbeat
   semantics;
4. an internet-reachable authenticated HTTPS callback plus ingress, replay, rate, size, XML, log,
   credential, outage, and retention controls;
5. a minimal real accepted message and permission to retain a sanitised fixture;
6. source-specific live/stale thresholds and publication/redistribution decisions.

Until those inputs exist, NTIS stays a separately named candidate and general live Manchester road
counts/speeds remain visibly unavailable. BODS remains the only currently exercised live source,
and it represents buses rather than general road traffic.

## Authoritative references

- [WebTRIS frequently asked questions](https://webtris.nationalhighways.co.uk/Home/Faqs)
- [WebTRIS service news](https://webtris.nationalhighways.co.uk/Home/News)
- [WebTRIS API documentation](https://webtris.nationalhighways.co.uk/api/swagger/ui/index)
- [Traffic England real-time services](https://www.trafficengland.com/services-info)
- [Traffic England subscriber information](https://www.trafficengland.com/general-info)
- [NTIS DATEX II interface design](https://www.trafficengland.com/resources/cms-docs/datex-eidd.pdf)
- [Current National Highways developer APIs](https://developer.data.nationalhighways.co.uk/apis)
