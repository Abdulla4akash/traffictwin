# Demo Script

This demo uses synthetic fixtures only.

## Fixture Paths

- Baseline: `tests/fixtures/bundles/baseline_valid`
- Variation: `tests/fixtures/bundles/variation_valid`
- Partial evidence example: `tests/fixtures/bundles/partial_valid`

## Steps And Expected States

1. Open Home / Project Status.
   - Current phase is Phase 4 UI prototype.
   - Capability manifest shows direct launch as Unsupported.
   - Notice states that direct simulator launch, live data, and diagnostic rules are not implemented.

2. Open Scenario Studio.
   - Seed fields render.
   - Unknown environment controls are disabled.
   - Run button is disabled with direct-launch unavailable text.
   - YAML preview validates and can be downloaded.

3. Open Bundle Import & Validation.
   - Enter `tests/fixtures/bundles/baseline_valid`.
   - Validation status is Accepted.
   - Manifest, declared files, findings, and evidence availability are visible.

4. Import the baseline bundle.
   - Registry import reports created or idempotent.
   - Metrics and evidence-pack JSON are stored in the registry.

5. Repeat validation/import for `tests/fixtures/bundles/variation_valid`.
   - Validation status is Accepted.

6. Open Run Overview.
   - KPI cards show synthetic baseline metrics.
   - Completion rate is available.
   - Metric availability summary includes unavailable optional metrics.

7. Open Operations View.
   - `HISTORICAL REPLAY` badge is visible.
   - Replay clock has first/current/final timestamps.
   - Traffic, infrastructure, and task timelines render.

8. Open Infrastructure & Congestion.
   - Queue and utilisation time series render.
   - Saturation threshold notice reads `Demo threshold: 0.90`.
   - Capacity-normalised load balance is unavailable unless capacity evidence exists.

9. Open What-if Compare.
   - Baseline and variation fixture paths are selected.
   - Compatibility shows same experiment and same random seed.
   - Changed parameters include demand multiplier, workload birth-rate multiplier, failed RSUs, and RSU capacity mode.
   - Variation has lower task completion and longer trip duration.

10. Open Journey-Time Lens.
    - Trip metrics are available for the synthetic fixtures.
    - Trip duration chart renders.
    - Labels avoid real Manchester prediction claims.

11. Open Evidence & Diagnostic Readiness.
    - Evidence availability and validation status are visible.
    - EvidencePack ID and fingerprint are visible.
    - Required notice states that R1-R3 are planned for Phase 5 and inactive.
    - No causal recommendation or diagnosis appears.
