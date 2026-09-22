"""In-memory negative probes; never alter manuscript or research inputs."""
import json
from pathlib import Path
from validate_exemplar_alignment import checks

HERE = Path(__file__).resolve().parents[1]
tex = (HERE/'TrafficTwin_Dissertation.tex').read_text()
assert all(checks(HERE).values())
probes = [
 ('glossary',r'\section*{Glossary}',r'\section*{Glossary removed}','exemplar_glossary_present'),
 ('copyright','The author of this thesis','The author of this dissertation','exemplar_copyright_i_to_iv_verbatim'),
 ('environment',r'\label{tab:environment}',r'\label{tab:removed}','exemplar_environment_table_present'),
 ('access',r'\appendixsection{app:H}{Artefact access and verification}',r'\appendixsection{app:H}{Removed}','exemplar_access_appendix_present'),
 ('spaced_path',r'\texttt{traffictwin integration tos}',r'\path{traffictwin integration tos}','exemplar_no_path_with_spaces'),
 ('access_tag',r'\bibitem{ref1}',r'Source. \bibitem{ref1}','exemplar_no_bibliography_access_tags'),
 ('provenance','one demand-scaled Manchester network','one calibrated Manchester network','exemplar_no_calibrated_network_or_simulation'),
]
results=[]
for name,old,new,key in probes:
 assert old in tex
 mutated=tex.replace(old,new,1)
 outcome=checks(HERE,mutated)
 results.append({'probe':name,'specific_guard':key,'rejected':outcome[key] is False,'ledger_rejected':outcome['exemplar_only_recorded_tex_operations'] is False})
record={'method':'In-memory text mutations against final LaTeX; no files or scientific inputs mutated. Each named semantic guard and the operation ledger must reject the change.','passed':all(x['rejected'] and x['ledger_rejected'] for x in results),'probes':results,'research_workloads_launched':0}
(HERE/'evidence/EXEMPLAR_MUTATION_CHECKS_2026-09-16.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
raise SystemExit(0 if record['passed'] else 1)
