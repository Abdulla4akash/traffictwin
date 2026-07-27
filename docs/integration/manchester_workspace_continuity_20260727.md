# Manchester Workspace Continuity Audit — 27 July 2026

A read-only filesystem audit of which research artifacts survive outside Git, prompted by the
Match Review page needing the real v1.1 match-rows artifact and the demand-rebuild
predeclaration needing its diagnosis inputs. Session-scoped scratchpad workspaces from the
25 July phases no longer exist; this records exactly what that costs and how recovery runs.

## What survives

| Artifact | Where | State |
|---|---|---|
| Option-A edgeData counts (1,788 cells / 149 edges) | `docs/integration/evidence/manchester_edgedata_counts_option_a.xml` | committed, 77 KB — the demand stage's observation-side input is fully preserved |
| Candidate demand (746,440 vehicles) | `docs/integration/evidence/manchester_candidate_demand.rou.xml` | **local only, gitignored, 6.17 GB — and measured TRUNCATED** (parse ends at line 10,652,017 with no closing element; the copy was interrupted mid-write). The intact demand therefore survives nowhere; it is regenerable deterministically by re-running routeSampler with the recorded seed over the rebuilt pool and the surviving edgeData counts. The truncated file still yields a large honest sample for the route-distribution diagnosis, reported as a sample |
| Candidate demand flows | same directory | local only, gitignored, 437 MB |
| DfT count points (342 rows) | workspace quarantine `dft_count_points-20260723T231609Z…` | complete single-member acquisition |
| BODS sessions (20 snapshots incl. the cadence probe) | workspace quarantine | complete, receipted |
| TfGM / WebTRIS / AADF probes | workspace quarantine | as acquired |
| All evidence records, receipts, fingerprints | `docs/integration/evidence/` (26 tracked files) | committed |
| Pilot campaign outputs and registry | `data/vec-fresh/`, `.demo/registry-capacity-pilot.sqlite` | live, growing |

## What is dead (was only in session-scoped workspaces)

| Artifact | Consequence |
|---|---|
| Greater Manchester parent network (1.25 GB net.xml) | rebuildable deterministically from the pinned extract |
| Study subnetwork (285,794 edges) | rebuilt by clipping the rebuilt parent |
| Edge spatial index | derived from the network |
| v1.1 match-rows artifact (305 sites) | regenerable: deterministic policy over rebuilt index + surviving count points |
| Route pool (43,200 routes, seed 42) | regenerable from recorded seed and envelope over the rebuilt subnetwork |
| Full DfT raw-counts acquisition (79 pages, 39,072 rows) | only a 1-page probe survives in quarantine; a fresh bounded re-acquisition through the accepted machinery is required if raw counts themselves are needed again — the derived Option-A edgeData counts survive, so the demand stage itself does **not** need it |

## The external pin, measured tonight

`greater-manchester-260724.osm.pbf` still returns HTTP 200 from Geofabrik. **Caveat recorded
before trusting it:** the served file's `Last-Modified` is 25 July 2026 — after the original
acquisition — so the re-download verifies against the recorded identity
(`sha256 233af3fa6dd34b1541ec022f0139a543f44355fe1748fd9d609ed653c8c9edf1`,
996,913,352 bytes) before anything consumes it. A mismatch means Geofabrik regenerated the
dated file; that would be a new network identity requiring a fresh ADR-059-style pin decision,
not a silent substitution.

## Recovery plan (running)

1. Re-download the pinned extract; verify sha256 against the recorded identity (in progress).
2. `osmium` decode under the ADR-060 boundary (conversion only, sealed receipt).
3. `netconvert` 1.27.1 rebuild (~90 s measured); semantic-identity check against the recorded
   canonical digest, remembering reproducibility is measured, never assumed (roundabout
   grouping was intermittently non-canonical on 1 of 3 builds).
4. Clip the study subnetwork (`--keep-edges.in-geo-boundary`, ~33 s measured); verify all 233
   bound edges present as before.
5. Rebuild the edge index; regenerate the 305-row v1.1 match artifact with the frozen policy;
   reconcile dispositions against the recorded 131/165/9 split — a difference is a finding,
   not a correction.
6. Regenerate the route pool (seed 42, recorded envelope) for the demand-rebuild diagnosis.

Meanwhile the surviving 6.17 GB demand file is being stream-measured for its route
edge-count distribution — the demand-side half of the predeclared diagnosis that needs no
network.

## Lesson recorded

Products of session-scoped workspaces that later phases depend on (network, index, pool,
match rows) must either be regenerable from committed pins — which everything above is — or
be moved to a durable ignored location like the giant demand artifacts were. Regenerability
held; convenience did not.
