# Supervisor and Viva Pack

TrafficTwin can build a checksummed private review pack from the inspected TOS package:

```bash
traffictwin integration tos supervisor-pack TOS_DATA_PATH \
  --variation ukfleettrain_mappo \
  --output supervisor-pack
```

## Contents

- deterministic Markdown and HTML research reports;
- interactive aggregate results atlas;
- evaluation matrix and common-seed paired comparison JSON;
- reproducibility audit;
- machine-readable integration-readiness report;
- dissertation evaluation plan;
- viva notes grounded in inspected artifacts;
- private screenshot checklist;
- manifest and SHA-256 checksum file.

The manifest classifies the output as `private_research_material`. Generating a pack does not grant
permission to publish it. It contains imported simulation summaries, not live Manchester data,
real-world validation, or proven causal explanations.

The Streamlit `TOS Training & Audit` page provides the same pack as a deliberate ZIP download.
It is generated only after the user presses the export button and is not written into the source
package.

## Integrity Check

From inside the pack directory:

```bash
shasum -a 256 -c checksums.sha256
```

The checksum file covers every substantive artifact and the pack manifest. The checksum file does
not checksum itself.

## Publication Boundary

The private pack and local atlas may be used for supervisor review subject to project permissions.
Public TOS atlas staging is a separate command and refuses to run without the explicit
`--confirm-publication-permission` attestation. TrafficTwin cannot determine whether permission has
actually been granted.

## Related Documents

- [TOS Results Workbench](integration/tos_results_workbench.md)
- [Integration readiness gates](integration/readiness_gates.md)
- [Dissertation evaluation plan](dissertation_evaluation_plan.md)
- [Release guide](release_guide.md)
