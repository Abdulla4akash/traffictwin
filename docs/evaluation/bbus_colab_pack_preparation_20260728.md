# B-BUS Paired Private-Colab Packs — Ready, Upload Pending

**Outcome: two separately bound private Colab packs were constructed and verified.** The
corridor and whole-fleet Sparse-64 arms have different ZIPs, bindings and experiment IDs;
neither can inherit the other's infrastructure status. No GPU training or held-out policy
evaluation has run.

- Corridor ZIP: 2,187,939 bytes / sha256 `8aa1b554…`
- Sparse-64 ZIP: 28,147,413 bytes / sha256 `04e8f5db…`
- Private pack manifest: sha256 `eaae62ce…`
- Machine record:
  [Colab-pack preparation evidence](../integration/evidence/bbus_colab_pack_preparation_20260728.json)

Each ZIP passed CRC testing, extraction into a clean directory and the bundled runner's full
verification. Its 14-member allowlist contains the two derived trace NPZs, exact permitted
producer code, a compatibility-only JAX alias patch, the arm's protocol, the owner receipt,
requirements, runner and binding. Occupancy CSVs, session tokens, raw BODS material, raw
identifiers, salts, producer data and checkpoints are absent.

The common runtime design is frozen before execution: Model-C 17-input MAPPO; seeds 30--34;
64 vector environments; rollout length 50; 5,000,000 requested / 4,998,400 effective steps;
dawn training at baseline 2.5 capacity per slot; then one full peak evaluation of each frozen
actor at 2.5 and 0.75 under common task keys. A Colab GPU is mandatory and its identity is
recorded; CPU fallback is refused.

The owner's signed-in Colab was configured to G4 High RAM and connected. The first browser
file handoff was blocked before transmission because Chrome had not enabled file-URL access
for the ChatGPT extension. Therefore `colab_upload_performed`, `gpu_training_performed` and
`checkpoint_returned` remain false. The verified local ZIPs are unchanged. Resume requires
only that local Chrome permission; it does not require re-derivation, a protocol change or a
new experiment decision.

