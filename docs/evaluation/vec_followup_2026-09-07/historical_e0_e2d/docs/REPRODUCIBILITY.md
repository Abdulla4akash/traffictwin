# Reproducibility

## What is reproducible here

This public repository supports independent checking of the reported arithmetic, figure generation, design progression, frozen identities and evidence-publication decisions. It does not bundle the private simulator, third-party source, trace, actor checkpoint or large raw arrays.

### Recompute statistics

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python analysis/verify_statistics.py
```

The verifier reads committed CSVs, recomputes E1, E2c and E2d means/SD/SE/Student-t intervals, checks the E2b factorial arithmetic and verifies the direction reversal.

### Regenerate figures

```bash
python analysis/generate_figures.py
```

Generated files are deterministic for the pinned numeric inputs and plotting code. Minor raster-byte differences may occur across matplotlib/font backends; the numeric source remains the CSV data.

## Evidence hierarchy

1. Frozen private raw outputs and their SHA-256 ledgers.
2. Frozen private machine-readable comparison/validation records.
3. Byte-identical public copies of records that passed the public-source scan.
4. Clearly named public-sanitized derivatives where original records exposed private local paths.
5. Compact CSV extracts and explanatory prose generated from those records.

The original private hash and the public derivative hash are never conflated. See [Provenance](PROVENANCE.md).

## Raw evidence

Large `.npz` task and step arrays were intentionally omitted from Git to avoid publishing hundreds of megabytes, private local path structure and source-adjacent artifacts. Frozen evidence-index and root-ledger identities remain documented. If full raw publication is later approved, suitable channels include Zenodo, a versioned GitHub Release, an institutional archive or Git LFS with an explicit data-use/licensing review.

## Scientific identity checks

The experiments froze source commits, manifests, evaluator/module hashes, actor and trace hashes, seeds, backend/package versions, queue semantics and commands. Validators checked terminal accounting, path consistency, V2I work, vehicle work, finite values and no silent loss. E2c/E2d matched task, actor-action and fleet identities within each seed.

## No execution from this repository

The public analysis scripts operate only on compact committed result tables. They do not import or invoke the TrafficTwin evaluator and cannot launch a scientific trace run.
