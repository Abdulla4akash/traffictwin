# ADR-060: Controlled OSM PBF Decode Boundary (`osmium-tool`)

- Status: accepted (lead-approved dependency decision, 25 July 2026)
- Date: 2026-07-25
- Capability: `MAN-09` network-binding component only; extends [ADR-059](ADR-059-greater-manchester-baseline-network.md)

## Context

ADR-059 pins the Greater Manchester baseline extract to the dated Geofabrik file
`greater-manchester-260724.osm.pbf`. Building the network from it then hit a measured, hard
blocker rather than an assumed one.

`netconvert` 1.27.1, as built in the reviewed environment, reads OSM **XML** only. Handed the
pinned `.osm.pbf` it exits 1 with `Error: invalid byte '' at position 2 of a 2-byte sequence` —
it is trying to parse the binary container as XML. The reviewed build's feature list
(`Proj GUI FMT Intl SWIG Parquet Eigen GDAL GL2PS JuPedSim`) contains no PBF reader. No decoder
of any kind (`osmium`, `osmconvert`, `osmosis`, `pyosmium`) was installed. The builder therefore
refused with the typed diagnostic `OSM_PBF_DECODE_UNAVAILABLE`, and the only network that could be
built was a small city-centre probe acquired as XML directly from the OSM API.

That probe covers Manchester city centre and the University area. It is **not** the Greater
Manchester baseline and must not be relabelled as one.

Closing the gap required a decode step, which is a dependency decision, not an implementation
detail — so it went to the lead rather than being chosen locally.

## Decision

1. **`osmium-tool` is the approved PBF-to-OSM-XML decoder**, on the same footing as SUMO: an
   optional, audited **external runtime that is executed, never linked and never imported**. It is
   deliberately not added to the Python dependencies, and no Python binding (`pyosmium`) is used,
   so no GPL-licensed code enters the scientific code path.

   Recorded identity: `osmium-tool` 1.19.1 with `libosmium` 2.23.1, GPL-3.0-or-later, installed via
   Homebrew. The executable's SHA-256 and its resolved path are recorded in local evidence only;
   the path never reaches persisted or public evidence.

2. **The decode is a format conversion and nothing else.** The argument vector is frozen:

   ```
   cat --output-format osm --output <output> --no-progress <input>
   ```

   There is no mechanism for a caller to add, remove, or reorder any element of it. The vector
   contains no `--bbox`, no `--polygon`, no `tags-filter`, and no `extract` subcommand, and a test
   asserts their absence. A filter or clip applied during decode would be a scientific decision
   hidden inside a conversion step; the receipt states `conversion_only`, `content_filtered: false`,
   `bounding_box_clipped: false`, `simplified: false`, and `road_classes_selected: false` so a
   reader does not have to take that on trust.

3. **The pinned source expectation is the default, not an option.** A decode without the pinned
   identity refuses with `UNPINNED_SOURCE_REFUSED`. The opt-out exists only for clearly-labelled
   synthetic fixtures and forces `synthetic: true` into the receipt, which in turn makes
   `source_identity_verified: false` legible rather than silent. A receipt claiming real evidence
   without a verified pinned source is rejected by the model itself.

4. **Every decode is confined and receipted.** The destination must resolve inside the declared
   workspace or the decode refuses with `WORKSPACE_ESCAPE_REFUSED`; traversal is refused rather
   than followed. The workspace is identified in evidence by a digest-derived label
   (`<name>:<16 hex>`), never by its absolute path.

   The receipt records both input and output digests, the tool identity, the frozen argument
   vector's fingerprint, the observed structure of the decoded document, the licence and
   attribution, any refusal codes, and a seal over its own complete payload. The seal is computed
   in two passes so it covers defaulted fields as well; a receipt that was never sealed, or that
   was edited after the fact, is rejected on load. This makes the decode replayable and checkable
   **offline**, with neither the provider nor the decoder present.

5. **The decoded output is validated structurally before it is used.** The root element must be
   `osm` (`DECODED_WRONG_XML_ROOT`) and the document must actually contain nodes, ways, or
   relations (`DECODED_OSM_XML_EMPTY`). A bounded prefix is read rather than parsing a
   gigabyte-scale document.

6. **The decoder remains optional.** When `osmium` is absent the application continues to fail
   closed with the actionable typed diagnostic `OSM_PBF_DECODE_UNAVAILABLE` naming the missing
   step. Tests requiring the real decoder skip rather than fake a decode, so the suite stays
   runnable offline. A major-version change refuses with a version-drift error rather than being
   silently accepted.

## Consequences

**What this unblocked.** The full Greater Manchester network now builds and validates: 2.11M edges,
468k junctions, 2.55M connections, UTM 30N, about 1.25 GB. Its measured extent contains the whole
Manchester local-authority filter with zero shortfall, so it classifies as a baseline candidate;
the earlier city-centre build classifies from the same measurement as `sub_area_probe_only` and
keeps that label without anyone having to remember to apply it.

**What it did not change.** `MAN-09` remains `planned` and Gate D remains `foundation_only`. This
ADR delivers a decode step inside Gate-D step 1. It is not calibration, not validation against
observations, not map matching, not a comparison, and not VEC execution. Network coverage is also
not observation coverage: DfT observations remain Manchester local authority only, and the rest of
Greater Manchester stays **unavailable** — never zero traffic — regardless of the network now
covering it.

**Licensing.** `osmium-tool` is GPL-3.0-or-later and is executed as a separate process, never
linked or imported, which is the same boundary already used for SUMO. The decoded OSM data remains
ODbL 1.0 with attribution `© OpenStreetMap contributors, ODbL 1.0`, carried through the receipt.

**Cost.** One more optional external runtime to install and record. Rejected alternatives:
`pyosmium` (would import GPL code into the scientific path), `osmconvert` and `osmosis` (not
approved, and no better on the licensing or determinism questions), and re-acquiring Greater
Manchester as XML from the OSM API (the API refuses extracts of that size, which is why the pinned
PBF exists in the first place).
