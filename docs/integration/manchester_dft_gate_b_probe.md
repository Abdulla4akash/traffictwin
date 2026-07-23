# DfT minimal real-source Gate-B probe (`MAN-02`)

Status: **accepted minimal probe with scoped blockers; `MAN-01` and `MAN-02` remain `planned`**

On 23 July 2026, the controlled DfT acquisition service fetched the three minimal anonymous,
Manchester-scoped cases fixed by the Gate-A plan: raw-count row `43177`, count-point row `6046`,
and AADF row `9219`. The machine record is
[`manchester_dft_gate_b_probe_20260723.json`](evidence/manchester_dft_gate_b_probe_20260723.json).

## Execution boundary

The probe ran from branch `codex/traffictwin-v0.7` at recorded Git head
`c2160999c6c66ab3b871b2ebd0ef6645a1ee6952`, with hashes for every relevant dirty implementation
file recorded in the machine evidence. It created a new temporary isolated v0.7 workspace and used
only `DftAcquisitionRequest` → `BoundedHttpClient` → MAN-01 quarantine → MAN-02 parser → atomic
accepted promotion. Requests were anonymous, fixed to local-authority ID `85`, bounded to one row
and at most two pages, and labelled real (`synthetic=false`) and `redistributable_raw` under the
audited OGL decision.

After promotion, `load_accepted_dft_report` independently re-opened each accepted snapshot,
verified its workspace, receipt, manifest, request, policy, hashes, inventory, publication/evidence
class, and reran the parser without a network call.

The later-session catalogue then discovered all three snapshots by ID, classified exactly one of
each DfT dataset, and replayed them without an acquisition object or network access.

The accepted raw-count receipt then drove the exact survey-filter/view service, while the accepted
count-point receipt drove MAN-07 spatial admission and the DfT MAN-08 layer builder. These were
offline downstream replays of the same real snapshots, not additional source requests.

## Result

| Product | Filter ID | Raw member | Parser | Accepted replay |
|---|---:|---:|---|---|
| Raw counts | 43177 | 1,550 bytes | accepted, 1/1 row | exact fingerprint match |
| Count points | 6046 | 1,184 bytes | accepted, 1/1 row | exact fingerprint match |
| AADF | 9219 | 1,634 bytes | accepted, 1/1 row | exact fingerprint match |

All three response row objects and their field sets were identical to the already retained official
fixtures. The raw response hashes differ because the controlled requests include the mandatory
`filter[local_authority_id]=85` in pagination URLs; the stored row data did not change. Exact raw,
parser-report, and snapshot-receipt fingerprints are in the machine record.

The real raw-count view selected one present `all_motor_vehicles` value while retaining
`time_basis="local_clock_hour"` and keeping UTC unavailable. The real count point was spatially
admitted into an available attributed reference layer with zero exclusions. The deterministic view
and layer-summary fingerprints are recorded in the machine evidence.

## What this proves

- The current allowlisted transport reaches all three audited anonymous endpoints.
- The real response envelopes and row schemas pass the current strict parsers.
- Quarantine precedes parsing and each admitted result is promoted immutably.
- Accepted local bytes reproduce the original parser fingerprints and counts offline.
- The bounded local catalogue discovers and reopens all three products without ephemeral receipts.
- The three retained minimal fixture rows still match the source rows semantically.
- The accepted real raw-count row reaches the source-specific survey-view boundary without UTC
  promotion, and the accepted real count point reaches an available spatial reference layer.

## What this does not prove

- It is not a full Manchester bulk synchronisation or load/performance acceptance.
- It does not establish a timezone for DfT survey-hour labels (`GA-DFT-1`).
- It does not establish a source rate-limit policy or SLA (`GA-DFT-2`, `GA-DFT-3`).
- The temporary accepted workspace is not checked in and is not a public-hosting artifact.
- It does not accept the common `MAN-01` service, the MAN-08 UI, calibration, or SUMO demand use.

Accordingly, this closes the missing **minimal real-response execution evidence** for the three DfT
parser surfaces, while capability truth remains `planned` pending the complete integrating gate.
