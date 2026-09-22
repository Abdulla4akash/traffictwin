# Week 4 → Week 5 Progress — Owner Checkpoint (28 July 2026)

**Status: owner-facing checkpoint, not a supervisor-endorsed record.** Every research
statement below keeps its recorded ceiling. `owner_approved_candidate` is not external
validation, supervisor approval, a causal claim, or permission to publish third-party
material. No communication, signature, branch fast-forward, or owner decision is recorded
by this document.

**Post-snapshot correction:** N1 was withdrawn on 28 July; the provider file did not mutate and
the network was rebuilt to its original canonical identity. References to an N1 re-pin below are
retained only as the queue state before that correction.

## 1. What changed since the Week-4 checklist

| Workstream | Week-5 position | Remaining boundary |
|---|---|---|
| Capacity programme | Complete: exploratory pilot, signed held-out confirmation, five-regime sweep, B0 prediction test, keyed-action and observability probes, and deep-squeeze onset | One actor family and one audited district; held-out seeds `{10–14}` are spent; no external validation |
| Real bus evidence | Night, dawn, and rush-hour sessions processed offline into aggregate cadence/progression records | No bus experiment has run; B1 needs G1–G5 decisions, map matching, trace viability, and an explicit speed-outlier rule |
| GPU training track | B-CAP, B-REWARD, B-MASK, and B-DOMAIN full archives preserved locally; B-BUS/IPPO remain engineering smokes | All outputs are private, non-admitted diagnostics; B-DOMAIN is not literal trace B4 |
| Dissertation evidence | Consolidated experiments register and a deterministic cross-regime figure now exist | Prose chapters and the citable literature spine remain to be written |
| MAN-05 parser gap | Both preserved rush-hour refusals diagnosed to the same cross-operator raw-reference collision shape | Accepted parser amendment remains lead-owned; diagnosis does not authorise the fix |
| Owner/external track | Ethics, Sandra, Randy, CSF, official-branch review, and scientific signings are decision-ready | The owner must personally send, sign, or trigger each item |

## 2. Capacity result now available for the dissertation

The capacity programme has a coherent bounded result:

- On the 2,488-slot modelled collapse hour, the signed held-out protocol confirmed a
  **−8,310.9 ms** mean paired latency difference for cap-0.75 minus cap-2.5, with bootstrap
  interval **[−9,097.5, −7,524.3] ms** and all five reserved seeds in the declared direction.
- Deadline success remained flat-to-rising descriptively. The hypothesised degradation
  cliff did not appear.
- The policy selected identical per-vehicle actions across capacity arms: zero mismatches
  in 8,956,800 keyed actions over nine comparisons. The vehicle-side observation is
  capacity-invariant while the RSU-side state changes, locating the structural observation
  gap without adopting an XAI research frame.
- The B0 baseline-actor prediction held: a second actor was also exactly capacity-invariant.
- All four normal regimes (`we`, `wd_pm`, `ev`, `wd_am`; maxN 139/163/175/215) were exactly
  inert under the standard squeeze. Only the 2,488-slot collapse hour responded.
- On the 175-slot event night, cap-0.5 and cap-0.25 remained exactly inert; cap-0.1 produced
  the first non-zero outcome change. This brackets a saturation-governed mechanism but does
  not establish a universal slot-count threshold.

The deterministic [cross-regime figure](dissertation_appendices/figures/cross_regime/provenance.md)
binds those projections to six campaign-analysis hashes and the generated trace audit.
It performs no cross-regime pooling or inferential test.

## 3. B1's measured bus inputs — processing complete, experiment not started

Post-hoc processing used only the durable private quarantines: no acquisition, API key,
network request, or attendance step occurred.

| Session | Verified snapshots | Seen | Active support | Median / p90 cadence | Maximum implied speed |
|---|---:|---:|---:|---:|---:|
| Night | 15 promoted | 872 | **41** | 68 / 75 s | 28.4 m/s |
| Dawn | 52 promoted | 1,676 | **1,162** | 67 / 76 s | 38.0 m/s |
| Peak | 52 verified quarantines (51 promoted) | 1,677 | **1,433** | 66 / 75 s | 64.7 m/s |

Dawn is already 81.1% of peak active support; peak is 35.0× night and 23.3% above dawn.
The long sessions exposed that bare `VehicleRef` values are reused across operators. The
session token is therefore corrected to v1.1:
`HMAC(session_salt, OperatorRef || NUL || VehicleRef)`, with v1.0 aggregate-read
compatibility retained. Raw references and salts do not leave the private processing
boundary.

The 64.7 m/s peak maximum is corrected, not a token-merging artefact. The recorded
recommendation is to keep the proposed 32 m/s plausibility ceiling and drop+count violating
segments rather than raise the threshold after seeing the data. That recommendation is
**not** an owner decision. Buses remain buses and are never relabelled as general traffic.

## 4. Parser refusal diagnosis

Offline replay of both preserved rush-hour `PARSE_REJECTED` snapshots returns
`CONFLICTING_ACTIVITY`. In each snapshot, one raw-reference/time group contains two
activities from different operators; no conflict remains when that group is operator-scoped.
The rejected bytes and identities remain preserved, and the accepted MAN-05 parser was not
changed in the post-hoc slice.

The evidence supports a narrow lead review of conflict grouping by
`(OperatorRef, VehicleRef, recorded_at)`. It does not support weakening other duplicate or
conflict refusals, deleting the quarantines, or changing the accepted parser without the
lead's explicit ownership record.

## 5. GPU campaign preservation

- B-MASK completed 10/10 jobs, 49,984,000 effective steps, 10,240,000 recorded diagnostic
  decisions, and zero infeasible selections in masked-deployment cells. Archive SHA-256:
  `cf18bedf2dcb833a6bce072bfa24f23734c3e49f94212d54eb135520deb80dce`.
- B-DOMAIN completed 15/15 jobs, 74,976,000 effective steps, and 11,520,000 recorded
  diagnostic decisions. Archive SHA-256:
  `0d17154ebfed2d33be3e63485fceabbd6a7d6d5f399569bf94c83aa0a7e119b6`.

Both exact ZIPs are preserved in gitignored `data/gpu-track/`, pass ZIP integrity checks,
contain private checkpoint/raw diagnostic material, and are not Git evidence bytes. Neither
archive admits an actor or authorises a scientific result. B-DOMAIN is a data-free procedural
precursor and explicitly `literal_trace_b4: false`.

## 6. Verification state

The completed bus slice has 49 focused tests passing, focused Ruff and strict mypy clean,
and exact evidence-to-private-artifact hashes for 3/3 session views. The cross-regime figure
has six focused tests passing, focused Ruff/format and strict mypy clean, valid SVG XML, a
visual inspection, and exact agreement with all source-analysis hashes, maxN values, and
paired differences.

The stale dissertation appendix was mechanically regenerated after ADR-066 (the only delta
was its missing row and count 65→66). The resulting full unit suite is current and green:
**2,923 passed in 128.16 s**.

The broader tree is still not represented as globally clean:

- repository-wide Ruff reports five pre-existing findings in notebook subprocess calls and
  `scripts/ev_timing_probe.py`; and
- repository-wide strict mypy reports 71 pre-existing findings in unclaimed GPU/script files.

Those broad findings are separate from the focused slices above and must not be silently
folded into their acceptance claims.

## 7. Owner decision and send queue

| Priority | Owner action | Prepared input | Agent boundary |
|---:|---|---|---|
| 1 | **Review and submit ethics application** | Seven proposed values in `docs/evaluation/ethics_application_draft.md`; participant window remains proposed | Agent does not submit or recruit |
| 2 | Send Sandra progress email and obtain her scope verdict | Current draft in `docs/owner_action_pack_20260727.md` | No supervisor view is inferred before reply |
| 3 | Send Randy permission/provenance email | Current draft in the same action pack | Written code/data/publication conditions remain external |
| 4 | Send CSF3 request | Current draft in the same action pack; student ID still required | Agent does not send or authenticate |
| 5 | Trigger Codex review and official-branch fast-forward | `CODEX_INTEGRATION_HANDOFF.md`; exact ancestry is fast-forwardable | `main` remains untouched; agent does not trigger without owner instruction |
| 6 | Decide B1 G1–G5, including speed-outlier handling | Measured proposals in the B1 draft and three-session record | No bus trace or experiment before signing and viability |
| 7 | Complete crossover/stadium designs, then sign or decline | Both are still explicitly `NOT SIGNABLE YET` | Agent cannot fill owner choices |
| 8 | Decide demand E1–E5 and network/data N1/R1 re-pins | Existing predeclarations and decision records | No re-pin or demand execution is implied |

The fastest external critical-path move remains the ethics submission. The highest-value
technical owner choice is B1's outlier rule and G1–G5 disposition. Sandra's reply may change
the programme scope; when it arrives, it supersedes assumptions in this checkpoint.
