# Cross-regime capacity-response figure provenance

Status: **exploratory, owner_approved_candidate, descriptive non-causal**. This is
not supervisor approval, external validation, a causal claim, or a universal
capacity threshold.

## Projection source

| Field | Value |
|---|---|
| Projection record | `vec_cross_regime_capacity_projection_20260728.json` |
| Projection SHA-256 | `dbda22fab8ba3826728c2ad9cd4fe9473a996ee5ad80dd8a389632356b43fede` |
| Projection ID | `vec-cross-regime-capacity-response-20260728` |
| Trace-audit SHA-256 | `20704a05c7db0bbbf92e7f8c51ae0b72560fa91acbea2968d3531a1fe8c1b659` |
| Metric | `task.latency.mean_ms` |
| Standard contrast | `cap-0.75` minus `cap-2.5` |
| Pairing unit | fleet seed within campaign |

## Campaign-analysis bindings

| Experiment | Analysis SHA-256 | Design fingerprint |
|---|---|---|
| `vec-capacity-grid-we` | `b6464fde837e7f6e0933eb5b68027690daf9ae2d6fb3b02e9757bef2cc5984c0` | `b4da3a5ba9b4dd100c3dd041b7bc7a19e35da2b4e8b673fa4733c0203a308312` |
| `vec-capacity-grid-wd-pm` | `338e0951ae43f6ec01a16c072fe24afe96aa69de6d81d941daed5bc35bf04494` | `635a2cbefd94b75773fcb608d71f4c0c8a2cbc3df447934980655fe75bdf8df5` |
| `vec-capacity-grid-ev` | `06b148ace10eab4603f68079f4eaa5c81c8c1164d57e2dd7fca7fc53e61dac9e` | `efa83a78c8518861cde62191c2a8c6975b5e616c6770f309496c955883a8245b` |
| `vec-capacity-grid-wd-am` | `3ebda792418ed804389f1dd9e35acdca90b64675292ce76ce51ed149924dee06` | `2844fde2c38ec22664357865c528006a1cbad62f3ddb659fbd20a38c920f8df6` |
| `vec-capacity-squeeze-pilot` | `7507639a41ad8b287e5a6f4103ba3739a323adf5382a772d29e13849e9421ac9` | `de474e038523e5e79e2d167364f312dc7c2ea273e610f2d26ec1cf253f41bb90` |
| `vec-capacity-deep-ev` | `415e7c9c5c167cbd76f811eb603800c66141cb433504711b97743fa4adb05699` | `727745441c5e43c1cb95ea76b337716629cf528319b534e756bc9c140192109d` |

The campaign-analysis paths are private, gitignored workspace paths. Their exact
hashes and the complete numeric projection are preserved in the committed JSON;
the generator never opens those paths.

## Published files

| File | SHA-256 | Bytes |
|---|---|---|
| `capacity_cross_regime_response.svg` | `d95b76c43ade83822da2668987c2ef5ca21a7b8f47472a6a62e1e14fa7188051` | 6693 |
| `capacity_cross_regime_response.tex` | `8ab4f730af14a72329e566e8206dcde2197e6e2d99a5fd7f76407bb9090c35ea` | 985 |

## Derivation and reading boundary

- Each plotted response is the arithmetic mean of the three recorded paired
  per-seed differences, variation minus baseline. No cross-regime pooling or
  inferential test is performed.
- `maxN` is the audited trace-array width, not the number of vehicles active at
  every second. The aligned panels show an association with saturation; they do
  not identify a universal threshold.
- The four normal regimes are exactly invariant under the standard squeeze in
  every recorded metric. The 2,488-slot collapse hour has a −6,715.239 ms mean
  paired latency response. The separately magnified event-night response first
  becomes non-zero at cap-0.1 (−0.024 ms).
- All traces cover the Etihad/Co-op Live event district, not Manchester city-wide.
- The policy's offloading decisions remain invariant; decision invariance and
  outcome sensitivity are separate observations.

## Regenerating

```bash
uv run python scripts/generate_cross_regime_capacity_figure.py \
  docs/integration/evidence/vec_cross_regime_capacity_projection_20260728.json \
  --overwrite
```

Unchanged input rewrites byte-identical SVG, TeX, and provenance files.
