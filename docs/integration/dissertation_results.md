# Dissertation experiment results in TrafficTwin

## Latest follow-ups — 15 September 2026

The page now defaults to **Latest follow-ups · 15 September 2026**. Select
**Experiment** to inspect native two-choice placement, half-speed servers, or
the second actor. Resource Strategy Explorer also has an **Open latest
experimental results** button in the grouped navigation app.

The display reads a packaged copy of the completed study: 72 new runs and 32
reused historical controls, using the same eight previously examined paired
blocks. Two-choice comparisons label their reused controls; the half-speed
gap-change contrast retains its paired original-speed reference and exposes
those 16 reference rows separately. The second actor uses normal server speed.

**Paired comparisons** shows the original saved effects and Bonferroni 95%
intervals across all ten follow-up comparisons (df=7). **Runs & blocks** shows
the original equal-weight means, per-block attainment and offered/admitted/
deadline-success counts. Filtering never changes the saved inference.
**Evidence & downloads** offers all original compact tables, the report, audit
and evidence ZIP. Queue statistics and additional lifecycle counts are outside
this basic display; it does not run experiments or import arbitrary new studies.

`scripts/build_followup_results_packet.py` copies exact bytes from repository
commit `fe8c8d9e4f725665508e47e61dc6e3286d005450`; the historical execution source
is separately identified as `5cbe568c9260c432f3e3ae42b45dcfba7f1a8dbe`. The loader
checks packaged fingerprints, audit bindings, block identities, offered-task
denominators and comparison arithmetic. It does not reopen raw arrays or rerun
the historical task-level audit. Missing or changed evidence hides results.

## Original confirmation — 8 September 2026

TrafficTwin's **Results → Experimental Results** page displays the completed
joint-randomness confirmation study from 8 September 2026. The bundled evidence
contains the actual 32 simulation cells, eight paired blocks and four policies
reported in the dissertation. It is labelled **Workflow demonstration**.

Open `/experimental-results` in the normal Streamlit app. **Bundle Import &
Validation** also links to this page. Select **Original confirmation · 8 September
2026** to use the existing **Dissertation study** source, which
loads a compact packet included with the application; no simulator, external
data service, or original machine path is needed.

## What the page shows

- Three original paired contrasts with their simultaneous 95% confidence
  intervals, preserving equal weighting of the eight blocks.
- Deadline attainment for each policy and block, with offered, admitted,
  successful, gate-rejected and missed-deadline counts.
- The original protocol seal, 32 cell validation receipts and summaries,
  block controls, compact tables, analysis and file fingerprints.
- Downloads of the evidence ZIP, both original CSV files, selected historical
  receipts and a new import-check receipt.

The filter on **Runs & blocks** changes the table only. It does not recompute
the sealed analysis or its sample size. Deadline attainment uses all offered
tasks as its denominator. Tasks are not independent statistical replicates.
The intervals use the original three-contrast Bonferroni family and Student's
t distribution with seven degrees of freedom.

## Importing a copy

1. Choose **Evidence & downloads → Download study evidence ZIP**.
2. On another installation, expand **Import study evidence**, select **Upload
   evidence ZIP**, and choose that file.
3. Alternatively, extract the packet yourself and select **Local evidence
   folder**, pointing to its root containing `evidence/` and `confirmation/`.

This is a bounded adapter for the exact frozen study. It does not accept an
arbitrary CSV or infer a new experiment's schema. Missing or changed required
files are refused. Caller-supplied hashes cannot authorize replacement results.
ZIP entries are read in memory with size and path checks; the importer does
not extract or execute supplied files. Directory inputs remain read-only.

The older run-bundle importer retains its own manifest and per-run contract.
Aggregated dissertation tables use this dedicated study adapter, so they do
not silently become raw task records or operational Manchester observations.

## Evidence standing

The import check authenticates compact files against trusted fingerprints and
checks result arithmetic and receipt bindings. The displayed task-level
validation status comes from the historical receipts. Loading this page does
not repeat raw-array checks, independently validate the simulator, launch a
research workload, or broaden any experiment's scientific authorization.

The morning trace and frozen actor limit the study's scope. Earlier studies
remain separate and are not pooled with these eight joint-randomness blocks.
The view does not imply that TrafficTwin originally executed these experiments.

## Figure 7

Use a capture of **Paired comparisons** as the dissertation workflow image.
Suggested caption:

> TrafficTwin workflow demonstration using the completed joint-randomness
> confirmation study: 32 runs across eight paired blocks and four policies.
> The page presents imported paired effects, their simultaneous 95% intervals,
> and checks linking the compact results to the original validation receipts.
> This illustrates evidence inspection; it does not establish independent
> scientific validation or original execution through the platform.

The source evidence in `docs/dissertation/joint_confirmation_2026-09-08/`
remains unchanged. The packaged ZIP and trusted manifest are generated by
`scripts/build_dissertation_results_packet.py` from that tracked source.
