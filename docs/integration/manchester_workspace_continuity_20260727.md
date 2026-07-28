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

## CORRECTION (28 July 2026): the pin did not fail — this section is superseded

**The section below is retained for provenance and is wrong.** Re-examination on 28 July
([evidence](evidence/n1_reexamination_and_peak_concurrency_20260728.json)) established:
the dated Geofabrik extract is, and always was, **50,502,348 bytes with md5
`c73b16ec…`** — exactly what the *first* acquisition record
(`evidence/manchester_baseline_network_build_20260725.json`) recorded with
`md5_reconciled: true`. The 996,913,352-byte / `233af3fa…` identity treated below as the
"source extract" is byte-identical to that same record's **decoded XML** output: the
second evidence record stored a derived artifact's identity in its source fields, so its
md5 was computed over decoded XML and compared against the provider's checksum for the
compressed file — a comparison that could never match. Decoding the on-disk file today
reproduces 996,913,352 bytes / `233af3fa…` **exactly** (2.665 s), so the artifact called
"not re-derivable externally" below is deterministically re-derivable right now.

**Consequences:** no provider mutation occurred; N1 as recorded is withdrawn; the network
chain is rebuildable from a verified input without forcing a new network identity; and no
claim that Geofabrik mutates dated files may appear in any output. The real findings are
ours: an identity-recording bug conflated derived output with source input, and a
checksum mismatch was rationalised as a provider warning instead of failing closed.

## Recovery halted at step 1: the pin failed, measured

The re-downloaded `greater-manchester-260724.osm.pbf` is **50,502,348 bytes with
sha256 `38f18e98441e89f7376678eab72d1245454547ffad4df80b76a5ac1c9ccfef3e`** — neither the
recorded 996,913,352 bytes nor the recorded `233af3fa…`. Geofabrik's dated files are therefore
**mutable**: the file was regenerated on 25 July after our acquisition. The acquisition-time
record already contained the early warning — the locally computed md5 (`b7fa4a2a…`) did not
match the provider-published md5 (`c73b16ec…`) even then.

Consequences, none of them silently adopted:

1. The original 997 MB input can no longer be obtained from the provider; the recorded network
   identity is not re-derivable externally.
2. Building from today's 50 MB file produces a **different network identity**, breaking the
   binding of the 233 bound edge ids, the match rows, and the subnetwork identity. That is a
   new pin decision of exactly the ADR-059 class — owner/lead territory, recorded here as
   **required decision N1**, not taken by this audit.
3. The dated-extract pin failed as a reproducibility anchor. For the dissertation's
   reproducibility chapter this is a *finding*: external dated artifacts need local retention
   (as the ADR already required for the raw member — whose retention died with the session
   workspace) or checksummed third-party archives.

## Recovery plan (halted after step 1; steps 2–6 await decision N1)

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

## Demand-survivor measurement — with a provenance finding

The truncated survivor yielded **3,550,666 parsed vehicles** with route edge counts of
median 134 / p90 261 / p99 363 / max 488 and departs spanning 0–17,999.99 s. Two conclusions,
kept separate:

1. **Provenance is not established.** The corrected alpha.7 demand holds 746,440 vehicles;
   a 3.55M-vehicle prefix means this file is almost certainly the *discredited
   parallel-session artifact* (the 10.4×-inflated construction), not the corrected demand.
   No receipt sits beside it. Its stats must never be attributed to the alpha.7 candidate.
2. **The route-length signal is still informative about the generation policy**: routes of
   median 134 edges (p99 363) through an urban subnetwork are long cross-network paths,
   consistent with the recorded gridlock hypothesis — evidence about the *pool policy* that
   both demand constructions shared, reported as exactly that and nothing more.

## Lesson recorded

Products of session-scoped workspaces that later phases depend on (network, index, pool,
match rows) must either be regenerable from committed pins — which everything above is — or
be moved to a durable ignored location like the giant demand artifacts were. Regenerability
held; convenience did not.
