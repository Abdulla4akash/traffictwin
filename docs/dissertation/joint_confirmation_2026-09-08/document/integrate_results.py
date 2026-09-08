"""Integrate completed sealed results into the current manuscript; no simulation.
The predeclared analysis supplies every primary estimate and interval.
"""
from pathlib import Path
import json
import statistics
P=Path(__file__).resolve().parent.parent
load=lambda n:json.loads((P/'evidence'/n).read_text())
a=load('ANALYSIS.json');cells=load('CELL_RESULTS.json');blocks=load('BLOCK_CONTROLS.json');timing=load('TIMING.json')
assert a['status']=='completed_primary_confirmation' and len(cells)==32 and len(blocks)==8
q=a['primary'];pi,di,pr=q
names={'ingress_dla':'Ingress','dla':'Common-target','per_task_dla':'Per-task','causal_round_robin':'Round-robin'}
f=lambda x:f'{x:+.3f}'.replace('-','−')
ci=lambda x:'['+f(x['family95_low_pp'])+', '+f(x['family95_high_pp'])+']'
reversal=pi['family95_low_pp']>0 and di['family95_high_pp']<0
rr='better' if pr['family95_low_pp']>0 else 'worse' if pr['family95_high_pp']<0 else 'inconclusive'
comparisons=[x for b in blocks for x in b['policy_controls'] if x['arm']!='ingress_dla']
assert len(comparisons)==24
matches={field:sum(x[field+'_identical'] for x in comparisons) for field in ['veh_observations','veh_actor_logits','veh_action']}
actions=sum(x['changed_vehicle_seconds'] for x in comparisons)
if matches=={'veh_observations':24,'veh_actor_logits':24,'veh_action':24}:
 control='All 24 non-reference arm/block comparisons matched observations, logits and actions exactly, despite allowing feedback. This extends the original observed fixed-action finding to these streams; frozen weights alone still do not guarantee future equality.'
else:
 control=f"Exact observation/logit/action equality held in {matches['veh_observations']}/{matches['veh_actor_logits']}/{matches['veh_action']} of 24 arm/block comparisons. There were {actions:,} changed vehicle-second actions summed over non-reference arms. Legitimate feedback was retained; the estimate concerns the total scheduling intervention, not forced fixed-action replay."
rows=['| Contrast | Mean difference, pp | Simultaneous 95% interval, pp |','|---|---:|---|']
for x,label in zip(q,['Per-task − ingress','Common-target − ingress','Per-task − round-robin']):rows.append(f"| {label} | {f(x['mean_pp'])} | {ci(x)} |")
if rr=='better':
 rrtext='Workload-aware targeting outperformed cyclic spreading in this study. Its additional deadline benefit accompanies the higher scheduler-only cost relative to round-robin in Table 10.'
elif rr=='worse':
 rrtext='Cyclic spreading outperformed workload-aware targeting in this study. Round-robin also had lower scheduler-only cost on the separate fixtures (Table 10); per-task least workload is therefore not the preferred arm on both measured dimensions.'
else:
 rrtext='The workload-aware versus cyclic contrast is statistically inconclusive, not evidence of equivalence. The lower round-robin scheduler cost in Table 10 therefore accompanies an unresolved deadline-attainment difference.'
status='The declared reversal criterion holds' if reversal else 'The declared reversal criterion does not hold'
new='''### 3.7 Joint-randomness confirmation and the cyclic comparator

All 32 full morning cells and eight block-control receipts passed after bounded qualification; no attempt failed or was retried. Fleet/evaluator pairs (100,200) through (107,207), controls, rotating arm order and analysis were sealed before full outcomes. Block 0 remains included; the original sample and pilots are not pooled [[S16]](#source-s16).

Evaluator seed varies observation descriptors, arrivals, operational types/sizes, fading and service wobble; fleet seed varies tier, EV status and initial SoC. All four arms shared the required exogenous arrays exactly within each block. '''+control+'''

*Table 13. New morning confirmation, eight paired joint-seed blocks with equal weighting. Two-sided Bonferroni simultaneous 95% Student-t intervals cover the three predeclared contrasts; positive differences favour the first arm.*

'''+ '\n'.join(rows)+f'''

{status}, evaluated using both directional requirements within the same simultaneous family. The mean per-task difference corresponds to {pi['mean_pp']*100:+.1f} successes per 10,000 offered tasks relative to ingress. {rrtext}

The critical value is {a['critical_value']:.6f}, recomputed with seven degrees of freedom. Independent joint blocks and approximately normal paired effects remain assumptions; eight blocks cannot strongly diagnose tails. Joint randomness extends the original fleet-conditional result within this morning scenario. It does not identify a unique mechanism decomposition or generalise across geography, actor training, physical timing or distributed information. Full counts, control diagnostics and elapsed times are in Appendix E.

'''
path=P/'TrafficTwin_Dissertation.md';s=path.read_text()
start=s.index('### 3.7 A sealed extension, not new confirmation evidence');end=s.index('## 4. Conclusion',start);s=s[:start]+new+s[end:]
old='This does not establish a round-robin deadline advantage: no full comparison has run.'
assert old in s;s=s.replace(old,"The new deadline comparison is reported separately in §3.7; the benchmark itself measures execution cost.")
old="The new host benchmark quantifies lower scheduler cost for causal scans on these fixtures and an additional reduction for cyclic targeting. Its companion comparator and sealed joint-randomness protocol make the next uncertainty explicit: whether workload awareness earns a deadline benefit over spreading when evaluator randomness also varies. That campaign remains unrun. Physical timing, generalisation, personal contribution, assessment-specific AI use and examiner access require their own evidence or author decisions; kernel speed and verification cannot substitute for them."
assert old in s
ending=f"The separate eight-block joint-randomness study yields per-task–ingress {f(pi['mean_pp'])}, common-target–ingress {f(di['mean_pp'])} and per-task–round-robin {f(pr['mean_pp'])} points. {status}. "+({'better':'Workload awareness adds a supported deadline benefit over cyclic spreading, with higher scheduler cost on the separate CPU fixtures.','worse':'Cyclic spreading has a supported deadline advantage over per-task workload awareness and lower scheduler cost on the separate CPU fixtures.','inconclusive':'The workload-aware versus cyclic deadline difference remains inconclusive; cyclic selection costs less on the separate CPU fixtures.'}[rr])+" Physical timing, wider generalisation, historical scoring uncertainty, personal contribution, assessment-specific AI use and examiner access remain distinct limitations or author decisions."
s=s.replace(old,ending)
# Full block counts are descriptive; only eight paired effects enter inference.
append='\n\nThe completed full matrix has 32 valid cells, eight valid block receipts and no failed attempts. The following tables retain every cell and block. I = ingress, D = common-target, P = per-task and R = round-robin; fleet/evaluator seeds are 100+b and 200+b for block b. Other terminal categories are retained in CELL_RESULTS.csv and each validation receipt.\n\n*Table E1. Full new-study counts. Offered populations match within blocks; attainment is offered-task percent. Gate rejection and admitted misses are disjoint.*\n\n| Block / arm | Offered | Admitted | Successes | Attainment | Gate rejected | Admitted misses |\n|---|---:|---:|---:|---:|---:|---:|\n'
order=list(names);codes={'ingress_dla':'I','dla':'D','per_task_dla':'P','causal_round_robin':'R'}
for b in range(8):
 for arm in order:
  x=next(x for x in cells if x['block']==b and x['arm']==arm)
  append+=f"| {b}/{codes[arm]} | {x['offered']:,} | {x['admitted']:,} | {x['successes']:,} | {x['attainment_pct']:.3f} | {x['gate_rejected']:,} | {x['admitted_misses']:,} |\n"
append+='\n*Table E2. All eight paired effects, percentage points. These blocks, not tasks or RSUs, are the new replications.*\n\n| Block | Per-task − ingress | Common-target − ingress | Per-task − round-robin |\n|---|---:|---:|---:|\n'
for b in range(8):append+=f"| {b} | {f(pi['effects_pp'][b])} | {f(di['effects_pp'][b])} | {f(pr['effects_pp'][b])} |\n"
append+='\n'+control+' The [block receipts](evidence/BLOCK_CONTROLS.json) retain each arm comparison, maximum absolute differences and changed-action counts. The [cell records](evidence/CELL_RESULTS.json) and [paired effects](evidence/PAIRED_EFFECTS.csv) preserve unrounded values. No task-level significance tests or new type subgroup analysis were added.\n'
maxr=max(x['max_service_conservation_error_ms'] for x in cells);maxv=max(x['max_vehicle_service_conservation_error_ms'] for x in cells)
append+=f"\nAll 32 records passed final-admission/score/category/penalty, assignment and queue checks under the sealed contract. Maximum reconstructed per-queue-second service discrepancy was {maxr:.9f} ms for RSUs and {maxv:.9f} ms for vehicle queues. This finite result does not certify every possible path or repair the historical off scorer.\n"
append+=f"\nFull evaluator processes took {timing['full_simulation_process_s']:.2f} seconds in total; cell validation took {timing['cell_validation_s']:.2f} seconds, block validation {timing['block_validation_s']:.2f} seconds, and sealed analysis with completion/hash checks {timing['analysis_with_completion_checks_s']:.2f} seconds. Qualification processes separately took {timing['qualification_simulation_process_s']:.2f} seconds. [Timing records](evidence/TIMING.json) and per-cell logs retain the exact boundaries. The first-block estimate used runtime only.\n"
append+='\nThe [raw inventory](evidence/RAW_INVENTORY.json) binds the locally retained task/step arrays and supporting files. The [portable verifier](document/verify_results.py) regenerates central tables from compact evidence and accepts an optional explicit raw root for integrity checking. Compact arithmetic is not repeated task-level validation; hashes are not a backup. Approved off-machine storage and examiner access remain unresolved.\n'
s+=append
# Add direct new evidence links to S16 after completion exists.
s=s.replace('This new study is separate from the original four-draw sample, pilot and retrospective analyses.', '[Completed primary analysis](evidence/ANALYSIS.json), [all cell counts](evidence/CELL_RESULTS.csv), [block controls](evidence/BLOCK_CONTROLS.json) and [raw inventory](evidence/RAW_INVENTORY.json) bind the new results. This study is separate from the original four-draw sample, pilot and retrospective analyses.')
# Abstract last, after all body findings have been determined.
abstract=f'''Infrastructure scheduling can reverse a vehicular computing comparison under frozen policy weights. TrafficTwin studies strongest-link ingress, common-target least-workload and causal per-task placement. A new, separately sealed morning study completes 32 evaluations across eight joint fleet/evaluator-seed blocks. Per-task minus ingress is {f(pi['mean_pp'])} percentage points, common-target minus ingress {f(di['mean_pp'])}, and per-task minus causal round-robin {f(pr['mean_pp'])}; simultaneous 95% intervals are {ci(pi)}, {ci(di)} and {ci(pr)}, respectively. '''+({'better':'Workload awareness improves deadline attainment over cyclic spreading in this comparison.','worse':'Simple cyclic spreading outperforms per-task workload awareness in this comparison.','inconclusive':'The workload-aware versus cyclic difference is inconclusive, not equivalent.'}[rr])+'''

The earlier four-draw morning replication, excluding its inspected pilot, remains separate from the new joint-randomness sample. Retrospective analysis distinguishes shared destinations, immediate reservations and admission reconciliation. In the exact studied model, two deadline values guarantee that three simultaneous replacements equal causal fixed-target admission; service/timing constraints explain queue clearing and recurring destinations. Constructed float32 boundaries qualify executable equivalence without establishing historical prevalence.

Retained morning accounting locates 284,821 gains and 12,842 losses, with almost all net gains in the two distinct 100 ms task types. These are descriptive transitions, not individual-decision causal effects. Separate compiled CPU fixtures show lower scheduler cost for causal per-task scans than three-pass reconciliation and a further reduction for cyclic targeting.

The contribution is an inspectable implementation study, not a new learned controller. Joint randomness broadens evidence within one morning trace, while global service-work knowledge, aggregate timing and one actor restrict generalisation. Historical capacity statistics remain inconclusive and separately qualified by an unquantified scoring-mask exception whose original task records are unavailable.

'''
start=s.index('## Abstract\n\n')+len('## Abstract\n\n');end=s.index('## 1. Introduction',start);s=s[:start]+abstract+s[end:]
path.write_text(s)
(P/'document/INTEGRATION.json').write_text(json.dumps(dict(reversal_criterion=reversal,per_task_vs_round_robin=rr,policy_matching=matches,action_changes_summed_over_arms=actions,completed_cells=32,completed_blocks=8),indent=2)+'\n')
print(json.dumps(dict(reversal=reversal,round_robin_contrast=rr,policy_matching=matches),indent=2))
