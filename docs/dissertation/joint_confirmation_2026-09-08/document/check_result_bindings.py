"""Check manuscript table values against completed compact data and old tables."""
from pathlib import Path
import json,re,hashlib
from markdown_it import MarkdownIt
P=Path(__file__).resolve().parent.parent
load=lambda p:json.loads(p.read_text())
m=load(P/'document/SOURCE_MAP.json');tables={x['number']:x['rows'] for x in m['tables']}
analysis=load(P/'evidence/ANALYSIS.json');cells=load(P/'evidence/CELL_RESULTS.json')
num=lambda s:float(s.replace(',','').replace('−','-'))
counts=0
for row,contrast in zip(tables['13'][1:],analysis['primary']):
 expected={'per_task_dla minus ingress_dla':'Per-task − ingress','dla minus ingress_dla':'Common-target − ingress','per_task_dla minus causal_round_robin':'Per-task − round-robin'}[contrast['contrast']]
 assert row[0]==expected
 values=[num(row[1])]+[num(x) for x in row[2].strip('[]').split(', ')]
 for value,key in zip(values,['mean_pp','family95_low_pp','family95_high_pp']):assert abs(value-contrast[key])<=.0005;counts+=1
codes={'I':'ingress_dla','D':'dla','P':'per_task_dla','R':'causal_round_robin'}
assert len(tables['E1'])==33
for row in tables['E1'][1:]:
 block,code=row[0].split('/');cell=next(c for c in cells if c['block']==int(block) and c['arm']==codes[code])
 for value,key in zip(row[1:],['offered','admitted','successes','attainment_pct','gate_rejected','admitted_misses']):
  if key=='attainment_pct':assert abs(num(value)-cell[key])<=.0005
  else:assert num(value)==cell[key]
  counts+=1
assert len(tables['E2'])==9
for row in tables['E2'][1:]:
 b=int(row[0])
 for value,c in zip(row[1:],analysis['primary']):assert abs(num(value)-c['effects_pp'][b])<=.0005;counts+=1
# The previous manuscript's table cells are preserved, except the added cyclic row.
old=P.parent/'latex_markdown_2026-09-08/TrafficTwin_Dissertation.md'
tokens=MarkdownIt('commonmark').enable('table').parse(old.read_text());old_tables={};pending=None;rows=None
for t in tokens:
 if t.type=='inline':
  cap=re.fullmatch(r'\*Table ([A-E]?\d+)\. .*\*',t.content,re.S)
  if cap:pending=cap[1]
 if t.type=='table_open':assert pending;rows=[]
 elif t.type=='tr_open':row=[]
 elif t.type=='inline' and rows is not None:row.append(t.content)
 elif t.type=='tr_close':rows.append(row)
 elif t.type=='table_close':old_tables[pending]=rows;pending=None;rows=None
for name,rows in old_tables.items():
 current=tables[name]
 if name=='3':assert current[:-1]==rows,name
 elif name=='11':assert current[:-1]==rows[:-1] and current[-1][:-1]==rows[-1][:-1],name
 elif name=='12':assert current[:3]==rows[:3] and current[4:]==rows[4:],name
 else:assert current==rows,name
out=dict(status='passed',new_numeric_values_checked=counts,old_tables_preserved=len(old_tables),allowed_table_change='Table 3 adds cyclic mode; Table 11 updates AI attribution; Table 12 updates sampling scope. Other historical table cells unchanged',rounding_tolerance_pp=.0005,meaning='Presentation rounding only; no scientific validation tolerance changed',manuscript_sha256=hashlib.sha256((P/'TrafficTwin_Dissertation.md').read_bytes()).hexdigest(),analysis_sha256=hashlib.sha256((P/'evidence/ANALYSIS.json').read_bytes()).hexdigest())
(P/'document/RESULT_BINDINGS.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
