# ADR-019: Evidence-Gated Operational Fairness Metrics

Status: accepted

## Context

TrafficTwin v0.5 `MET-04` promotes the existing vehicle-tier completion grouping and Jain
capacity-normalised RSU load index into a documented fairness family. The canonical model contains
operational vehicle tiers and RSU infrastructure identifiers, but it contains no protected or
demographic attributes. Missing tier rows, tier changes within a metric scope, missing capacity,
and thin groups can make a disparity value misleading even when a formula is computable.

The existing implementation admitted any non-empty group and silently ignored missing group
evidence. It also calculated the RSU Jain index from any subset with positive capacity. That did
not meet the v0.5 requirement for explicit coverage and minimum support.

## Decision

- Define strict `OperationalFairnessPolicy` v1.0 with a stable fingerprint.
- Treat `vehicle_state.tier` only as an operational compute/resource tier. Never infer or label a
  protected, demographic, socioeconomic, or personal attribute.
- Admit one task into a vehicle-tier group only when exact `task.vehicle_id` joins to a non-empty
  tier that is stable for that vehicle throughout the metric scope.
- Admit one RSU load observation only when canonical `active_tasks` is non-negative and canonical
  `capacity` is positive. Group by exact canonical `rsu_id` and calculate `active_tasks / capacity`.
- Require, for every fairness output:
  - at least two operational groups;
  - at least two eligible observations in every observed group;
  - complete in-scope coverage (`1.0`).
- Do not drop an under-supported group to make a metric available. Return one of
  `GROUP_COVERAGE_INSUFFICIENT`, `INSUFFICIENT_GROUP_COUNT`, or
  `INSUFFICIENT_GROUP_SUPPORT`.
- Compute and preserve these grouped/scalar outputs:
  - completion rate by stable vehicle tier;
  - maximum vehicle-tier completion-rate gap;
  - Jain index over vehicle-tier completion rates;
  - mean capacity-normalised load by RSU;
  - maximum per-RSU mean-load gap;
  - Jain index over per-RSU mean loads.
- Define maximum gap as `max(group mean) - min(group mean)`.
- Define Jain index as `(sum(x)^2) / (n * sum(x^2))`. When every admitted group mean is zero,
  return unavailable because the expression is `0/0`; do not replace it with zero or one.
- Attach policy fingerprint/version, exact group-set fingerprint, group semantics, support counts,
  eligible/population counts, and coverage to every output.
- Compare scalar fairness metrics only when policy and group-set fingerprints match. Grouped object
  values remain non-scalar and are not converted into a fabricated arithmetic delta.
- Apply the same rules to whole-run and fixed-window scopes. Windowed vehicle-tier joins and RSU
  support use only independently in-window canonical evidence.

## Consequences

- `task.completion.rate_by_vehicle_tier` and
  `infra.load_balance.jain_capacity_normalised` become stricter without changing their keys.
- The four new fairness definitions increased the window-applicable catalogue from 50 to 54;
  ADR-020 later extends the current total to 60.
- Existing generic fixtures without vehicle tiers or capacity/active-task evidence remain
  explicitly unavailable. Generated synthetic bundles provide labelled software-fixture evidence.
- Current public SUMO and TOS summary contracts keep the family unavailable. Source RSU pressure,
  padded slots, or aggregate class summaries are not relabelled as compatible canonical groups.
- A zero maximum gap or high Jain index does not establish good performance, equal task outcomes,
  causal fairness, protected-attribute fairness, or external validity.
- R7 remains separately unimplemented. `MET-04` supplies metrics but does not choose a diagnostic
  threshold or a declarative rule grammar.

## Acceptance Evidence

- Unit tests pin policy/fingerprint behavior, exact grouped values, gaps, Jain indices, support,
  coverage, conflicting tiers, missing loads, insufficient groups, singleton groups, zero-group
  behavior, comparison compatibility, windows, and complete row ledgers.
- A reviewed golden projection pins the complete generated-synthetic family.
- CLI, report, aggregation, comparison, capability, SUMO/TOS boundary, generated-reference,
  Streamlit Fairness Evidence, lint, typing, package-build, and full-suite gates cover public
  surfaces.

## Alternatives Considered

- Infer missing tier from seed proportions or vehicle capability: rejected because group identity
  must come from accepted row evidence.
- Treat tier as a protected attribute: rejected because the canonical field describes an
  operational compute/resource category only.
- Admit singleton groups: rejected because one observation does not provide the minimum repeated
  support required by this policy.
- Use an 80% coverage threshold: rejected for v1.0 because the cutoff would be an unevidenced
  tolerance and could conceal the omitted group most relevant to a disparity claim.
- Drop incomplete groups before computing Jain or gap: rejected because selection would change the
  fairness question silently.
- Treat all-zero Jain as perfect equality: rejected because the formula is undefined and equal
  failure is not evidence of good outcomes.
