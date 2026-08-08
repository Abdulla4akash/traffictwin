# Evaluation Materials

These files prepare a possible expert/researcher evaluation of TrafficTwin. They are drafts for
supervisor and ethics review. Their presence does not mean that ethics approval has been obtained
or that participant sessions have occurred.

Contents:

- `ethics_application_draft.md` — protocol summary and risk controls;
- `participant_task_script.md` — consistent task-based session;
- `survey.md` — short post-session questionnaire;
- `interview_guide.md` — alternative semi-structured interview guide;
- `consent_and_privacy.md` — draft information, consent, withdrawal, and data-handling text;
- `anonymised_result_schema.json` — machine-readable schema excluding direct identifiers.

Use either the survey or the interview after supervisor direction. Do not recruit participants or
collect data until the applicable University process confirms that work may begin.

`mock_results.json` is an explicitly labelled synthetic software fixture for testing the
descriptive analysis pipeline. It is not collected participant data. Analyse it with:

```bash
traffictwin participant-evaluation analyse-mock docs/evaluation/mock_results.json
```

`batch_ingestion_benchmark.md` is separate software-performance/equivalence evidence for v0.5
`ING-04`; it is not participant evaluation and makes no city-scale throughput claim.

`streaming_ingestion_benchmark.md` is separate generated-fixture parser working-set/runtime and
equivalence evidence for v0.5 `ING-05`. Its `tracemalloc` values are not full process RSS and it
makes no Randy/VEC or city-scale claim.

The [E0 corrected-evaluator validity gate](e0/README.md) records the predeclared bounded smoke,
deterministic conservation checks, repeat comparison and readiness boundary for the Randy/VEC
research stream. It is not a controller comparison.

The [E1 waiting-room semantics evidence](e1/README.md) records the bounded 0.75x, 2.5x and 40x
legacy-versus-physical seed-0 pilot, its non-conserving legacy evidence boundary, and a
code-generated descriptive three-cap comparison. It is not a replicated E1 cap sweep and does not
begin the E2 placement comparison.

The E1 directory also contains a cumulative E0-to-E1 research record covering the hypotheses,
experimental design, authorization and decision sequence, observations, results, interpretation,
validity threats, reproducibility index and remaining gates.
