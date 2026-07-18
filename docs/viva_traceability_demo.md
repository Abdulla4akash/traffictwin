# Viva Traceability Demo

This demo shows how TrafficTwin traces a displayed result back through deterministic evidence. It
does not require Randy, SUMO, Manchester feeds, external services, or live data.

## Setup

```bash
source .venv/bin/activate
traffictwin bundle validate tests/fixtures/bundles/baseline_valid
traffictwin bundle validate tests/fixtures/bundles/variation_valid
streamlit run src/traffictwin/ui/app.py
```

## Demonstration Script

1. Open `Home / Project Status`.
   - State that the current system is import-first and synthetic/imported only.
   - Point out that direct launch and live data remain unsupported.

2. Open `Run Overview`.
   - Use the baseline fixture.
   - Show `task.completion.rate`.
   - Say that the number comes from the deterministic metric engine, not from the UI.

3. Open `Provenance Explorer`.
   - Select `Metric`.
   - Select `task.completion.rate`.
   - Show:
     - metric result;
     - metric definition;
     - canonical `tasks` table;
     - source rows from `tasks.csv`;
     - manifest, run, seed, environment, and fingerprint.

4. Open `Source file row`.
   - Select `tasks.csv`, row `2`.
   - Show the raw row and its canonical `TaskRecord`.
   - Explain that the preview is read-only and bundle-relative.

5. Switch to the variation fixture.
   - Select `Metric`.
   - Select `infra.utilisation.p95`.
   - Show the `infra_state.csv` source-row lineage and the aggregate-metric limitation.

6. Select `trip.duration.p95_s`.
   - Show that journey-time evidence comes from imported synthetic `trips.csv`.
   - Avoid calling this a real Manchester prediction.

7. Select `Diagnostic rule`.
   - Select `R2`.
   - Show the rule result, cited evidence keys, metric results, threshold configuration, alternatives,
     missing evidence, and unavailable links.
   - State that hypotheses are candidate explanations, not proven causes.

8. Download trace JSON and Markdown.
   - JSON is the machine-readable audit artifact.
   - Markdown is suitable for a viva appendix or supervisor review.

## CLI Fallback

If Streamlit is unavailable, run:

```bash
traffictwin provenance metric tests/fixtures/bundles/baseline_valid task.completion.rate
traffictwin provenance source tests/fixtures/bundles/baseline_valid tasks.csv 2
traffictwin provenance export tests/fixtures/bundles/baseline_valid \
  --root-type metric \
  --root-id task.completion.rate \
  --format markdown
```

## Key Points To Say

- Provenance supports auditability and reproducibility.
- It traces software derivation, not real-world causality.
- Aggregate metric traces show eligible input rows and exact counts, not per-row causal weights.
- EvidencePack-only diagnostic fixtures cannot recover source rows unless the bundle is available.
- Future Randy/SUMO adapters only need to preserve canonical source provenance for the explorer to
  work.

## Related Documents

- [Provenance Explorer](provenance_explorer.md)
- [Provenance model](provenance_model.md)
- [Demo script](demo_script.md)
- [Viva guide](viva_guide.md)
