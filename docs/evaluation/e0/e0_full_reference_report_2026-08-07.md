# E0 full corrected strongest-link reference

Date: 2026-08-07

Decision: **PASS for one full 3,600-step corrected strongest-link reference**

Next-stage boundary: no E1 or controller comparison was started.

The authoritative machine records are the
[predeclared full-reference manifest](e0_full_reference_manifest_v1.json) and
[deterministic full-reference validation](e0_full_reference_validation_v1.json). Their SHA-256
identities are:

- manifest: `eae09f31bd049b70f99930507873b0efb84a7a7cbeab2a37adb7b3a0bae6b12f`;
- validation: `3970b89e371a05cae6f5baa8142c98587b302d0c5a467601d50aa021e1368bfa`.

## Scope and provenance

This was the next step authorised after the bounded E0 smoke passed. It used the same scientific
configuration and changed only the execution length from 10 to 3,600 steps:

- vec_env commit `0f01f4d2082d3e8b735e74a873095ab8eeba37cc`;
- tos-data commit `a75bbdb1a956f828ee0e9b97b33506bd32d31b85`;
- evaluator SHA-256 `260b90ff400cb5048ae4e74fb6c407d197fbfc80d91d7b7edf0c65640b5bd669`;
- frozen 17-dimensional Paper-2A actor SHA-256
  `93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208`;
- Manchester incident trace SHA-256
  `e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056`;
- evaluator seed 0, fleet seed 0 and `uk2030` fleet preset;
- sequential substep accounting, conserved vehicle queues and physical RSU rejection;
- strongest-link/default placement with load balancing off;
- fixed 1x RSU service and scaling off;
- provisional fleet-scaled admission ceiling of 6,220 tasks per RSU.

The command and environment variables are recorded exactly in the manifest. The evaluator ran for
`5870.3` seconds and exited with status 0 after writing its aggregate, per-step and per-task outputs.

## Observed reference

| Ledger item | Observed |
|---|---:|
| Offered tasks | 13,076,234 |
| Admitted tasks | 11,661,973 |
| Simulated deadline-met outcomes | 8,939,165 |
| Admitted but deadline-missed outcomes | 2,722,808 |
| RSU-cap rejections | 834,120 |
| Local vehicle-queue rejections | 34,124 |
| V2V helper-queue rejections | 545,879 |
| V2I-unavailable outcomes | 138 |
| DLA-gate and V2V-unavailable outcomes | 0 |
| Offered-denominator deadline attainment | 0.6836192285944103 |
| Admitted-denominator deadline attainment | 0.7665225258196019 |

These values are the corrected strongest-link reference under this provisional configuration. They
are not a load-balancing comparison, a reproduction of Randy's reported `0.6943`, or evidence of
native physical completion/result return.

## Conservation verdict

All 32 deterministic checks passed:

- task conservation:
  `13,076,234 = 11,661,973 + 834,120 + 34,124 + 545,879 + 138`;
- V2I work conservation in milliseconds:
  `42,670,748 = 29,263,840 + 13,406,908`;
- vehicle work conservation in milliseconds:
  `281,346,752 = 270,951,552 + 10,395,200`;
- active task records and per-step arrivals equal offered tasks;
- per-step deadline outcomes, task flags and outcome code 1 reconcile to 8,939,165;
- per-task outcome codes 3 through 8 equal every aggregate terminal-reason counter;
- offered and admitted outcome/latency denominators were recomputed independently;
- no NaN, infinity, negative count/work/latency, impossible completion fraction, missing terminal
  outcome or silent task loss was found.

The full run exercised the physical RSU-cap rejection and V2I-unavailable paths that were zero in
the ten-step smoke. The DLA gate was correctly inactive because load balancing was off.

## Output identities

Raw output locator: `local-output:e0_outputs/e0-full-corrected-reference-v1/run_1`.

| Artifact | Size (bytes) | SHA-256 |
|---|---:|---|
| `summary.json` | 1,854 | `1ed26e6c8a4411b9a4e27dacf4d9381c8f8430a37c434f93b36f1150d8c661e1` |
| `per_step.npz` | 20,091,650 | `0be8726efa956d6d6e60b289fb3a6b587beb4dde7616fc235462bfb997d0e6d1` |
| `per_task.npz` | 84,380,786 | `c30acc1e6685db268a31daeda2c8020df2968487efecd420e729a16d3b3b2d57` |
| `stdout_stderr.log` | 2,675 | `46539ecf9e219e09c180b952737cd915eb0efa784b4674233317c99f5edd0bd5` |

The raw artifacts remain outside Git. The local run checksum manifest has SHA-256
`3596554ca3c0dddab9bc352881b6c320035af427b2cfa183843f500794bbdb0c`; the root checksum manifest
has SHA-256 `688baf8155afb848487a3b1393066e36f01e20560bd178ede03d55f4bbc3fec4`.

One full run was authorised and executed. No second full repeat was requested because the bounded
predecessor smoke had already demonstrated exact scientific-summary and array stability across two
identical runs.

## Remaining limitations

1. The 6,220-task ceiling is the evaluator's provisional 2.5x training-parity ratio. It is not an
   approved physical waiting-room size and not compute power.
2. `uk2030` remains a provisional evidence-anchored fleet choice pending the complete historical
   run contract.
3. The incident trace has no `enter` channel. The run therefore reports
   `engine_version=v2_post_nrsus_fix` and retains mask-only reset semantics.
4. Trace provenance names SUMO 1.27.0 while the installed local binary is 1.27.1. The evaluator
   replayed the NPZ and did not invoke SUMO.
5. Deadline attainment remains a simulated evaluator outcome, not confirmed physical task
   completion or result return.
6. GitHub Actions remains externally blocked by the repository-owner billing/spending-limit state;
   the jobs receive no runner and execute no steps.

The corrected strongest-link reference is now available for a later, explicitly predeclared E1
comparison. This result does not itself authorise or answer E1.
