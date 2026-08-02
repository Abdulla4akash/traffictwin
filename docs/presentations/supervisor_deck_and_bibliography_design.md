# Design — supervisor checkpoint deck and bibliography completion

**Status: IMPLEMENTED AND ARTIFACT-VERIFIED IN PHASE 180.** This design authorises communication
and reference artifacts only. It does not supply a supervisor decision, publication status,
ethics approval or scientific evidence.

## 1. Communication job

By the end, the project supervisor should be able to understand TrafficTwin as an auditable
what-if loop, see the one protocol-confirmed project result in its correct boundary, and decide
which scientific/human gates deserve attention next. The central takeaway is that the platform's
differentiator is not another simulation dashboard: it binds observation, scenario, execution,
measurement and claim state so a favourable aggregate cannot outrun its evidence.

The deck is a four-slide supervisor checkpoint, not a defence, product pitch or approval record.
Visible copy is audience-facing. Detailed provenance sits in `[Sources]` speaker-note blocks and a
companion source audit.

## 2. Narrative and visual route

No reference deck or visual direction was supplied, so the Presentations workflow routes to the
Codex Grid layout library. The deck retains its white canvas, black hierarchy, light-grey structure
and restrained blue evidence accent. Adjacent slides use different silhouettes.

1. **Minimal cover — layout 01.** `TrafficTwin` and a single proposition: a verifiable what-if
   loop for traffic and edge-computing research.
2. **Process — layout 17.** The loop reads observation → canonical twin → bounded what-if →
   evidence/decision, with a feedback line to the next observation. The two analytical lenses are
   explicit: mobility/traffic truth and VEC policy/QoS truth. LLM drafting is visually outside the
   evidence path.
3. **Evidence — layout 21.** A native two-column chart shows the held-out mean latency at capacity
   2.5 versus 0.75; the interpretation rail states −8,310.9 ms, five paired seeds, flat deadline
   attainment, zero action mismatches in the audited pilot pairs, and the tail/population meaning.
   This is protocol-confirmed within the signed project design, not real-Manchester causality.
4. **Decision close — layout 10.** Status separates implemented instrument, bounded evidence,
   planned portfolio/benchmark direction and external decisions. The supervisor-facing questions
   are Gate-D scientific contracts, the next confirmatory subgroup/actor design, and whether an
   ethics-gated usability study proceeds.

Minimum typography is 50 pt on the cover title, 35 pt on slide titles, 24 pt on callout headers and
16 pt on body copy. The deck uses no decorative stock imagery, UI-like card grid or colour-only
semantics. All PowerPoint objects remain editable.

## 3. Evidence and citation contract

Three source classes stay separate:

- **Literature evidence:** primary papers, standards and official provider records verified through
  DOI metadata plus publisher/official pages. It supports context and method only.
- **Project measurements:** signed experiment reports, immutable evidence JSON and current status
  records. They control every TrafficTwin-specific number and standing.
- **LLM drafting:** disclosed drafting assistance only. It is never a citation, measurement,
  approval, decision or evidence source.

Every slide has a `[Sources]` block in speaker notes. The evidence slide cites the exact project
records and the external literature that motivates tail-aware interpretation and protocol
discipline. The status slide cites current repository truth and unsigned decision forms. The
companion source audit lists claim, source class, exact repository path or DOI and the permitted
interpretation.

## 4. Bibliography completion contract

The existing 17-item bibliography is expanded to exactly 100 distinct references. The set covers:

- digital-twin definitions and transport implementations;
- microscopic traffic simulation, calibration and map matching;
- edge/VEC architectures and offloading optimisation;
- reinforcement learning and cooperative MARL;
- statistical protocol, reproducibility, provenance and reporting;
- explainability, attribution and claim-validity boundaries; and
- the three mandatory private producer records plus official BODS/SUMO sources.

Each matrix group records reference numbers, supported claim, explicit transfer limit, metadata
authority and verification date. DOI-bearing items must resolve through DOI/Crossref/DataCite and
retain the publisher-returned title/year. Official non-DOI sources must use stable first-party
URLs. Private producer records remain visibly private and are not described as independently
verified publications. The manuscript may cite grouped sources, but the bibliography never
upgrades a project measurement or fills a missing calibration citation.

## 5. Implementation and verification

The editable source is an ES module using `@oai/artifact-tool`; the final editable artifact is a
PPTX and the visually verified rendition is a four-page PDF. Temporary renders, layout JSON and
contact sheets stay outside the repository. Verification must prove:

- four slides and four `[Sources]` note blocks;
- no overflow, unresolved placeholder or unintended overlap;
- readable full-size renders and coherent deck-level flow;
- exact evidence numbers and forbidden-claim language;
- 100 unique numbered manuscript references and 100 unique BibTeX entries;
- complete citation coverage for every reference number;
- DOI/official-location presence and literature/project/LLM separation; and
- clean lint, test, lock and staged-diff gates.

Residual human work remains explicit: University reference-manager/style export, private-source
format choice, final template/word-count convention, supervisor interpretation, ethics outcome and
any publication decision.
