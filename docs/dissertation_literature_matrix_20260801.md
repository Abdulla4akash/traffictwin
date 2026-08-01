# Dissertation literature and claim matrix

**Prepared:** 1 August 2026
**Purpose:** source audit for `dissertation_manuscript_20260801.md`
**Status:** submission-support draft; bibliographic details must still pass the University's
required reference-manager/export check before final submission.

This matrix records what each source can support and, just as importantly, what it cannot.
TrafficTwin's experiment records remain the authority for project-specific numbers. Literature
is never used to upgrade an exploratory or descriptive project result into a confirmatory one.

## A. Research context and method

| Source | Claim it supports here | Limit carried into the dissertation |
|---|---|---|
| Satyanarayanan (2017), *The Emergence of Edge Computing* | Edge computing places computation nearer data sources/users to reduce dependence on distant cloud infrastructure and enable latency-sensitive applications. | A general edge-computing position paper; it does not validate this VEC simulator, policy or metric. |
| Shi et al. (2016), *Edge Computing: Vision and Challenges* | Edge systems distribute computation between devices, edge nodes and cloud resources and introduce resource-management challenges. | Broad IoT framing, not evidence that offloading improves every workload or vehicle. |
| Mach and Becvar (2017), *Mobile Edge Computing: A Survey on Architecture and Computation Offloading* | Computation offloading couples communication, computation and scheduling decisions; latency and energy are common objectives. | A survey of MEC, not a benchmark for the producer's environment or Manchester trace. |
| Mao et al. (2017), *A Survey on Mobile Edge Computing: The Communication Perspective* | Radio and computation resources are jointly relevant to mobile offloading performance. | Does not establish the semantics of TrafficTwin's source-defined deadlines or capacity control. |
| Schulman et al. (2017), *Proximal Policy Optimization Algorithms* | PPO optimises a clipped/surrogate policy objective using repeated minibatch updates and is a foundation for the audited actor family. | The dissertation evaluates a supplied checkpoint; it neither retrains PPO nor compares PPO generally with other RL algorithms. |
| Yu et al. (2022), *The Surprising Effectiveness of PPO in Cooperative Multi-Agent Games* | MAPPO can be a strong cooperative-MARL baseline and implementation/hyperparameter details materially affect performance. | Results on standard MARL testbeds do not transfer automatically to VEC; the present actor study is environment- and checkpoint-specific. |
| Tang and Wong (2022), *Deep Reinforcement Learning for Task Offloading in Mobile Edge Computing Systems* | Explicitly models uncertain edge-load dynamics, queues, delay-sensitive tasks and decentralised offloading, showing why load observation can matter. | Different algorithm/environment; it motivates the audit question but cannot validate TrafficTwin's result or show that adding load to this actor would help. |
| Karimi, Chen and Akbari (2022), *Task offloading in vehicular edge computing networks via deep reinforcement learning* | Treats dynamic VEC offloading/resource allocation and evaluates response time/acceptance, grounding the VEC-specific optimisation context. | A different MEC/cloud design and experiment; its reported gains do not transfer to the supplied checkpoint. |
| Gorsane et al. (2022), *Towards a Standardised Performance Evaluation Protocol for Cooperative MARL* | MARL comparisons require transparent protocols, multiple runs and reproducible evaluation; inconsistent practice can exaggerate apparent progress. | It motivates this workflow but does not prescribe this dissertation's exact sample size or confer external validation. |
| Dean and Barroso (2013), *The Tail at Scale* | A small high-latency population can dominate aggregate service behaviour; means should be decomposed alongside distributional tails. | Warehouse-scale service results are conceptual context, not direct evidence for RSU queues. |
| Nosek et al. (2018), *The preregistration revolution* | Separating pre-specified prediction tests from post-hoc discovery improves interpretability. | The repository uses signed, hash-bound protocols rather than claiming registration with an external registry. |
| Pineau et al. (2021), *Improving Reproducibility in Machine Learning Research* | Code, data/provenance, checklists and executable workflows improve the ability to scrutinise ML findings. | Reproducibility is necessary but does not prove truth, causality or external validity. |

## B. Source and simulator provenance

| Source | Claim it supports here | Limit carried into the dissertation |
|---|---|---|
| Alvarez Lopez et al. (2018), *Microscopic Traffic Simulation using SUMO* | SUMO is the microscopic road-traffic simulator used to generate the producer traces. | A simulation is not an observation of physical road traffic. The `inc` finding concerns one modelled Etihad/Co-op Live district collapse hour, not city-wide Manchester. |
| Department for Transport (2020), BODS SIRI-VM technical guidance | BODS vehicle-monitoring feeds contain current public-transport vehicle locations and related journey information in SIRI-VM. | Positions are bus observations, not general traffic and not measurements of VEC tasks, RSUs or network QoS. |
| Putra, R. P., *Intelligent Task Offloading: Current State Limitations and Proposed Potential Solutions* (private Year-1 report) | Documents the producer environment, the task-offloading research context and prior concerns about distribution shift/reward alignment. | Private research material; it is cited but not reproduced or committed. It is not independent validation of TrafficTwin's findings. |
| Putra environment repository, commit `068b4ea33e640f206ce6a7d04f3d6fae2ac831f4` | Pins the evaluated `v2_post_nrsus_fix` implementation and supplied checkpoint boundary. | Permission covers use with citation; repository contents are not republished. Source inspection supports implementation facts, not causal performance claims. |
| Putra trace repository, commit `f6c67acbed3360dba3a0d5c8d1fd557caa99ecff` | Pins the five trace artifacts and producer provenance used by the experiments. | Demand-calibration bibliographic detail remains incomplete; the dissertation does not make a calibration-quality claim. |

## C. Project claims and their controlling evidence

| Dissertation claim | Evidence class | Controlling repository record | Permitted wording |
|---|---|---|---|
| Tightening capacity from 2.5 to 0.75 reduced mean latency by 8,310.9 ms while deadline attainment remained flat in five held-out seeds. | Protocol-confirmed within the signed project design | `evaluation/capacity_confirmatory_results_20260728.md` and signed protocol/report | “confirmed in the held-out experiment”; never “externally validated” or “causal in real Manchester”. |
| Actions were exactly invariant across pilot arm comparisons. | Audited post-hoc probe over admitted artifacts | `integration/evidence/vec_pilot_keyed_action_comparison_20260728.json` | “0 mismatches in 8,956,800 compared actions”; not proof of invariance outside those artifacts. |
| The mean improvement was concentrated in an already-failed, always-offloading population. | Post-hoc mechanism analysis | `evaluation/latency_tail_analysis_20260728.md`; `evaluation/offload_partition_analysis_20260729.md` | “mechanism consistent with the observed artifacts”; subgroup construction and interpretation remain post-hoc. |
| The inverse-capacity ceiling law predicted 27/27 new checks within ±5%. | Predeclared exploratory prediction | `evaluation/ceiling_law_prediction_results_20260729.md` | “the predeclared exploratory prediction held”; it is not a universal law of VEC. |
| The trained actor remained better than baseline, but latency slopes differed. | Predeclared exploratory robustness test | `evaluation/actor_crossover_results_20260730.md` | “no crossover; slope-invariance prediction refuted”; actor/preset mismatch prevents algorithm-family claims. |
| Density/onset scaling matched only four of six exact checks. | Predeclared exploratory falsification test | `evaluation/onset_scaling_prediction_results_20260730.md` | “prediction refuted under the frozen exact rule”; tiny numerical deviations are disclosed. |
| Sparse-64 bus runs yielded approximately 50.1% mean completion at cap 0.75. | Execution-deviated descriptive output | `evaluation/bbus_sparse64_clean_rerun_results_20260730.md` | “descriptive corroboration only”; outside VEC-06, synthetic compute/infrastructure, not admitted and not confirmatory. |

## D. Reference-list candidates

Alvarez Lopez, P., Behrisch, M., Bieker-Walz, L., Erdmann, J., Flötteröd, Y.-P., Hilbrich,
R., Lücken, L., Rummel, J., Wagner, P. and Wießner, E. (2018) ‘Microscopic Traffic Simulation
using SUMO’, *2018 21st International Conference on Intelligent Transportation Systems (ITSC)*,
pp. 2575–2582. https://doi.org/10.1109/ITSC.2018.8569938.

Dean, J. and Barroso, L. A. (2013) ‘The Tail at Scale’, *Communications of the ACM*, 56,
pp. 74–80.

Department for Transport (2020) *Technical guidance: publishing location data using the Bus Open
Data Service (SIRI-VM)*. Available at:
https://www.gov.uk/government/publications/technical-guidance-publishing-location-data-using-the-bus-open-data-service-siri-vm.

Gorsane, R., Mahjoub, O., de Kock, R. J., Dubb, R., Singh, S. and Pretorius, A. (2022)
‘Towards a Standardised Performance Evaluation Protocol for Cooperative MARL’, *Advances in
Neural Information Processing Systems*, 35. https://doi.org/10.52202/068431-0398.

Karimi, E., Chen, Y. and Akbari, B. (2022) ‘Task offloading in vehicular edge computing networks
via deep reinforcement learning’, *Computer Communications*, 189, pp. 193–204.
https://doi.org/10.1016/j.comcom.2022.04.006.

Mach, P. and Becvar, Z. (2017) ‘Mobile Edge Computing: A Survey on Architecture and Computation
Offloading’, *IEEE Communications Surveys & Tutorials*, 19, pp. 1628–1656.
https://doi.org/10.1109/COMST.2017.2682318.

Mao, Y., You, C., Zhang, J., Huang, K. and Letaief, K. B. (2017) ‘A Survey on Mobile Edge
Computing: The Communication Perspective’, *IEEE Communications Surveys & Tutorials*, 19(4),
pp. 2322–2358. https://doi.org/10.1109/COMST.2017.2745201.

Nosek, B. A., Ebersole, C. R., DeHaven, A. C. and Mellor, D. T. (2018) ‘The preregistration
revolution’, *Proceedings of the National Academy of Sciences*, 115(11), pp. 2600–2606.
https://doi.org/10.1073/pnas.1708274114.

Pineau, J., Vincent-Lamarre, P., Sinha, K., Larivière, V., Beygelzimer, A., d'Alché-Buc, F.,
Fox, E. and Larochelle, H. (2021) ‘Improving Reproducibility in Machine Learning Research’,
*Journal of Machine Learning Research*, 22(164), pp. 1–20.

Putra, R. P. (n.d.) *Intelligent Task Offloading: Current State Limitations and Proposed
Potential Solutions*. Year-1 PhD report, University of Manchester. Supervisor: Sandra Sampaio;
co-supervisor: Rizos Sakellariou. Private research material.

Putra, R. P. (2026a) *VEC environment*, repository commit
`068b4ea33e640f206ce6a7d04f3d6fae2ac831f4`, University of Manchester GitLab.

Putra, R. P. (2026b) *TOS trace data*, repository commit
`f6c67acbed3360dba3a0d5c8d1fd557caa99ecff`, University of Manchester GitLab.

Satyanarayanan, M. (2017) ‘The Emergence of Edge Computing’, *Computer*, 50(1), pp. 30–39.
https://doi.org/10.1109/MC.2017.9.

Schulman, J., Wolski, F., Dhariwal, P., Radford, A. and Klimov, O. (2017) ‘Proximal Policy
Optimization Algorithms’, arXiv:1707.06347. https://doi.org/10.48550/arXiv.1707.06347.

Shi, W., Cao, J., Zhang, Q., Li, Y. and Xu, L. (2016) ‘Edge Computing: Vision and Challenges’,
*IEEE Internet of Things Journal*, 3(5), pp. 637–646.
https://doi.org/10.1109/JIOT.2016.2579198.

Tang, M. and Wong, V. W. S. (2022) ‘Deep Reinforcement Learning for Task Offloading in Mobile
Edge Computing Systems’, *IEEE Transactions on Mobile Computing*, 21(6), pp. 1985–1997.
https://doi.org/10.1109/TMC.2020.3036871.

Yu, C., Velu, A., Vinitsky, E., Gao, J., Wang, Y., Bayen, A. and Wu, Y. (2022) ‘The
Surprising Effectiveness of PPO in Cooperative Multi-Agent Games’, *Advances in Neural
Information Processing Systems*, 35. https://doi.org/10.52202/068431-1787.

## Submission check still requiring a person

- Import these entries into the required University reference workflow and verify the selected
  IEEE numeric style, access dates and capitalisation.
- Confirm the Year-1 report's year and the Lourenço calibration reference with the producer; until
  then the manuscript deliberately avoids a calibration-quality claim.
- Confirm whether private GitLab URLs should appear as plain repository identifiers or as
  non-clickable private references in the submitted bibliography.
- Preserve the producer's full citation set wherever a figure, table or video frame reports
  producer-derived capacity results.
