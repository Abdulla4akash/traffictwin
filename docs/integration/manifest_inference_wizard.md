# Manifest Inference Wizard

TrafficTwin implements v0.5 capability `ING-02` as a deterministic, confirmation-gated assistant
for existing CSV bundle inputs. It suggests file kinds, canonical column mappings, and units only
where the header provides unit evidence. The draft cannot be validated, canonicalised, imported,
or analysed.

The workflow is:

```text
unchanged CSV directory
    -> bounded deterministic inference
    -> non-executable draft
    -> user accepts or edits mappings/units
    -> source fingerprint recheck
    -> confirmed CanonicalisationManifest
    -> apply to complete metadata template
    -> ordinary manifest.yaml
    -> normal bundle validation
```

## Supported Scope

The wizard targets the existing generic CSV kinds:

| File kind | Required canonical fields |
|---|---|
| `tasks` | `task_id`, `vehicle_id`, `task_class`, `arrival_time`, `deadline_ms`, `decision`, `completed` |
| `infra_state` | `timestamp`, `rsu_id` |
| `vehicle_state` | `timestamp`, `vehicle_id` |
| `traffic_obs` | `timestamp`, `sensor_id` |
| `trips` | `trip_id`, `departure_time` |
| `incidents` | `incident_id`, `timestamp`, `incident_type` |

It does not infer bundle/run metadata, environment versions, policies, checkpoints, random seeds,
licences, source permission, or `seed.yaml` content. Those remain explicit metadata supplied by the
user or producer.

## Deterministic Evidence

Field candidates use ordered evidence:

1. exact canonical header after case/separator normalisation;
2. a documented source alias;
3. a distinctive bounded value vocabulary.

Value-only matching is deliberately limited to task class (`T1`, `T2`, `T3`), task decision
(`local`, `v2i`, `v2v`), and supported boolean-completion values. Generic numeric, time, identifier,
location, energy, and capacity meanings are never inferred from value range.

Inference reads at most:

- 32 CSV files;
- 128 columns per file;
- 100 rows per file;
- 256 characters from each sampled value.

Complete CSV bytes are still hashed. The deterministic score orders mapping evidence and is not a
probability. A tied top file kind remains `ambiguous`; no kind is selected.

## Units

A unit is suggested only from a supported header suffix or word, for example:

- `DeadlineMs` → `ms`;
- `ArrivalTimeSeconds` → `s`;
- `MeanSpeedKmh` → `km/h`;
- `EnergyJoules` → `J`.

If a mapped canonical field requires a unit and the header does not evidence one, confirmation is
blocked until the user selects a supported unit. Numeric magnitude is not unit evidence.

## CLI Workflow

Inspect the complete machine-readable algorithm boundary:

```bash
traffictwin manifest contract --format json
```

Create a draft:

```bash
traffictwin manifest infer raw-csv-directory \
  --format yaml --output mapping-draft.yaml
```

Inspect `mapping-draft.yaml`. It always contains:

```yaml
confirmation_required: true
analysis_ready: false
```

Accept every unambiguous suggestion explicitly:

```bash
traffictwin manifest confirm mapping-draft.yaml raw-csv-directory \
  --accept-suggestions \
  --confirmed-by "analyst-role" \
  --output canonicalisation.yaml
```

Edit ambiguity, fields, exclusions, or units during confirmation:

```bash
traffictwin manifest confirm mapping-draft.yaml raw-csv-directory \
  --confirmed-by "analyst-role" \
  --kind entity.csv=traffic_obs \
  --map entity.csv:sensor_id=DetectorCode \
  --unmap entity.csv:location \
  --unit entity.csv:timestamp=s \
  --exclude unrelated.csv \
  --output canonicalisation.yaml
```

`--kind` uses `FILE=KIND`; `--map` and `--unit` use `FILE:FIELD=VALUE`; `--unmap` uses
`FILE:FIELD`. The confirmation command rejects a changed source fingerprint, duplicate mappings,
missing required fields, unsupported units, and unresolved ambiguity.

Inspect the confirmed file fragment:

```bash
traffictwin manifest files canonicalisation.yaml --format yaml
```

Apply confirmed mappings to a complete bundle metadata template:

```bash
traffictwin manifest apply canonicalisation.yaml manifest-template.yaml \
  --output manifest.yaml
```

The template must already declare valid bundle, run, environment, and provenance metadata. Place
the generated `manifest.yaml` beside the unchanged CSV files and required `seed.yaml`, then use the
ordinary validation path:

```bash
traffictwin bundle validate path/to/bundle
```

The `apply` step records inference version, source/draft/confirmation fingerprints, confirmation
state, and the `confirmed_by` label inside `manifest.yaml`.

## Streamlit Workflow

Open **Manifest Inference Wizard** and:

1. select a CSV directory;
2. inspect immutable fingerprints, evidence methods, limits, and ambiguity findings;
3. include/exclude each file and select its file kind;
4. review or edit every column and required unit;
5. enter a non-sensitive analyst/role label and acknowledge the review;
6. download `canonicalisation.yaml`, the file fragment, and—when a complete template is
   supplied—the final `manifest.yaml`.

The UI does not write into the source directory, import a run, or calculate metrics.

## Synthetic Acceptance Fixtures

- `tests/fixtures/manifest_inference/value_patterns` exercises header aliases, distinctive value
  patterns, explicit unit suffixes, confirmation, and bundle validation.
- `tests/fixtures/manifest_inference/ambiguous` is intentionally compatible with infrastructure,
  vehicle-state, and traffic-observation required fields. It has no automatic selection.

These fixtures are synthetic software-test data, not external schema validation or real traffic
evidence.

## Security And Integrity

- Source CSV files are never rewritten.
- Complete hashes bind the draft and confirmation to exact source bytes.
- Confirmation re-runs inference and rejects a changed source set or content.
- Symlinks/escaping paths, duplicate or empty headers, invalid CSV/encoding, and configured bounds
  are rejected.
- Drafts and generated artifacts contain relative file paths, not local absolute source paths.
- No source value samples are emitted in the draft.

The decision rationale is recorded in
[ADR-012](../decisions/ADR-012-confirmation-gated-manifest-inference.md).
