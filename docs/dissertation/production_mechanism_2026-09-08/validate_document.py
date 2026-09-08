"""Check draft counts, links, numbered objects and source-backed result tables."""
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
BASELINE = '04f3b6a95c7bc06c80ed95b54762f12861bba183'
ARCHIVE = REPO/'docs/evaluation/vec_followup_2026-09-07'
draft = ROOT/'TrafficTwin_Dissertation.md'
text = draft.read_text()
tokens = MarkdownIt('commonmark').enable('table').parse(text)

def plain(t):
    return ''.join(c.content if c.type in ('text','code_inline') else ' ' if c.type in
                   ('softbreak','hardbreak') else '' for c in t.children or [])

parts = {}; section = None
for i,t in enumerate(tokens):
    if t.type=='heading_open' and t.tag=='h2':
        section = tokens[i+1].content
        if section=='References' or section.startswith('Appendix'): section=None
        elif section: parts[section]=0
    if section and t.type=='inline' and not t.content.startswith(('*Table','*Figure')):
        if not any(c.type=='image' for c in t.children or []): parts[section]+=len(plain(t).split())
    elif section and t.type=='fence': parts[section]+=len(t.content.split())
total=sum(parts.values())
assert 7000 <= total <= 9000, total
assert set(parts)=={'Abstract','1. Introduction','2. Methodology','3. Evaluation and Reflection','4. Conclusion'}
assert not re.search(r'^#{1,3} .*Background',text,re.M)

links=0; internal=0; images=0
for doc in ROOT.rglob('*.md'):
    content=doc.read_text()
    anchors=set(re.findall(r'<a id="([^"]+)"',content))
    doc_tokens=MarkdownIt('commonmark').enable('table').parse(content)
    hrefs=[c.attrGet('href') or c.attrGet('src') for t in doc_tokens for c in t.children or []
           if c.type in ('link_open','image')]
    for href in hrefs:
        if href.startswith('#'):
            assert href[1:] in anchors, (doc.name,href)
            internal+=1
        elif not href.startswith(('http','mailto:')):
            target=(doc.parent/href.split('#')[0]).resolve()
            assert target.exists(),(doc.name,href)
            links+=1
    images+=len(re.findall(r'!\[',content))
for name in ('Figure','Table'):
    captions=[int(n) for n in re.findall(r'^\*'+name+r' (\d+)\.',text,re.M)]
    assert captions==list(range(1,6 if name=='Figure' else 11)), (name,captions)
    mentions={int(n) for n in re.findall(r'(?<!\*)'+name+r' (\d+)',text)}
    assert mentions <= set(captions)
assert set(re.findall(r'\[\[(\d+)\]\]\(#ref-',text))==set(map(str,range(1,14)))
assert set(re.findall(r'id="ref-(\d+)"',text))==set(map(str,range(1,14)))
assert set(re.findall(r'id="source-s(\d+)"',text))==set(map(str,range(15)))

def rows(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def table(n):
    block=text.split(f'*Table {n}.',1)[1].split('\n\n',2)[1]
    return [[x.strip() for x in line.strip().strip('|').split('|')] for line in block.splitlines()[2:]]
def fnum(x):return float(x.replace('−','-').replace('+',''))

# Every numeric data cell in the two primary per-draw tables and interval table.
checked_cells=0
incident=rows(ARCHIVE/'historical_e0_e2d/experiments/E2d/data/e2d_paired_results.csv')
for actual,source in zip(table(4),incident,strict=True):
    expected=[int(source['fleet_seed'])]+[float(source[k])*100 for k in (
        'ingress_dla_offered_attainment','common_target_dla_offered_attainment',
        'per_task_dla_offered_attainment','per_task_minus_ingress')]
    for a,e in zip(actual,expected,strict=True):
        assert abs(fnum(a)-e)<=.000501,(a,e)
        checked_cells+=1
morning=rows(ARCHIVE/'generalisation-replication-2026-09-07/runs.csv')
# Explicit column names are read from this archived schema, not inferred from labels.
seedkey='fleet_seed'
armkey='arm'
attkey='attainment_pct'
for actual in table(5):
    seed=int(actual[0]); grouped={r[armkey]:r for r in morning if int(r[seedkey])==seed}
    vals=[float(grouped[k][attkey]) for k in ('ingress','common_target','per_task')]
    expected=[seed]+vals+[vals[2]-vals[0]]
    for a,e in zip(actual,expected,strict=True):
        assert abs(fnum(a)-e)<=.000501,(a,e)
        checked_cells+=1
intervals=rows(ARCHIVE/'generalisation-replication-2026-09-07/paired_intervals.csv')
for actual,source in zip(table(6),intervals,strict=True):
    observed=[fnum(actual[1])]+[fnum(n) for c in actual[2:] for n in re.findall(r'[+−-]?\d+\.\d+',c)]
    expected=[float(source[k]) for k in ('mean_pp','ci95_low_pp','ci95_high_pp','family95_low_pp','family95_high_pp')]
    for a,e in zip(observed,expected,strict=True):
        assert abs(a-e)<=.000501,(a,e)
        checked_cells+=1


# Reuse authenticated paired outcomes; these are saved-output arithmetic checks.
oldroot=REPO/'docs/dissertation/gap_closure_2026-09-08'
vr=oldroot/'verification/results'; ar=ROOT/'analysis/results'
assert re.findall(r'^\*Table (B\d+)\.',text,re.M)==['B1','B2']
assert text.count('unquantified')>=3
trans=json.loads((vr/'OUTCOME_TRANSITIONS.json').read_text())['pairs'];assert len(trans)==23
primary=[r for r in trans if 'replication' in r['group'] and '_ingress/' in r['A'] and '_per_task/' in r['B']]
for actual,r in zip(table('B2'),primary,strict=True):
 expected=[r['seed']]+[r[k] for k in ['failure_to_success','success_to_failure','success_both','failure_both','net_successes']]
 assert [int(v.replace(',','')) for v in actual]==expected
 checked_cells+=len(expected)
account=json.loads((ar/'OUTCOME_ACCOUNTING.json').read_text())
keys=['gain_gate','gain_admitted_miss','loss_terminal','loss_admitted_miss','net']
for actual,r in zip(table(7),account['rows']+[account['totals']],strict=True):
 expected=([r['seed']] if 'seed' in r else [])+[r[k] for k in keys]
 vals=actual if 'seed' in r else actual[1:]
 assert [int(v.replace(',','')) for v in vals]==expected
 assert r['gains']-r['losses']==r['net']
 assert r['gain_gate']+r['gain_admitted_miss']==r['gains']
 assert r['loss_terminal']+r['loss_admitted_miss']==r['losses']
 checked_cells+=len(expected)
for r in account['rows']:
 src=next(x for x in primary if x['seed']==r['seed'])
 assert r['gains']==src['failure_to_success'] and r['losses']==src['success_to_failure'] and r['net']==src['net_successes']
assert account['totals']['gains']==284821 and account['totals']['losses']==12842 and account['totals']['net']==271979
for k in account['totals']: assert sum(r[k] for r in account['rows'])==account['totals'][k]
assert 'Loss: non-admitted' in text
adverse=rows(ar/'ADVERSE_PRODUCTION.csv')
for actual,r in zip(table(8),adverse,strict=True):
 expected=[f"{r['substep']}.{r['candidate']}",str(int(float(r['deadline']))),f"{float(r['service']):.3f}"]
 for arm in ['B','C']:
  assert r[f'{arm}_admitted']=='True'
  expected.extend([f"{r[f'{arm}_target']} / {float(r[f'{arm}_before']):.3f}",f"{float(r[f'{arm}_completion']):.3f} "+('met' if r[f'{arm}_met']=='True' else 'miss')])
 assert [x.replace('**','') for x in actual]==expected,(actual,expected)
 checked_cells+=len(expected)
assert sum(r['B_met']=='True' for r in adverse)==8 and sum(r['C_met']=='True' for r in adverse)==7
old=(oldroot/'TrafficTwin_Dissertation.md').read_text()
assert text.split('## References')[1].split('## Appendix A')[0]==old.split('## References')[1].split('## Appendix A')[0]

# Authenticate unchanged inputs and prior outputs, never substitute for raw-array audit.
bound=json.loads((ROOT/'analysis/SOURCE_BINDINGS.json').read_text())
for b in bound:
 data=subprocess.check_output(['git','show',b['commit']+':'+b['path']],cwd=REPO)
 assert hashlib.sha256(data).hexdigest()==b['sha256']
 assert (REPO/b['path']).read_bytes()==data
summary=json.loads((ar/'EVIDENCE_SUMMARY.json').read_text())
assert summary['additional_inputs']==sum(summary['stages'].values())==719
assert summary['budget']==800 and summary['additional_inputs']<=summary['budget']<=1000
assert summary['prior_raw_audits_repeated']==summary['prior_task_joins_repeated']==summary['full_simulations']==0
assert summary['full_dimension_adverse_cases']==0 and summary['padding_alternating_masks']==4
assert not summary['zero_entry_common_target_fourth_changes']
diag=json.loads((ar/'DIAGNOSTICS.json').read_text())
assert len(diag['results'])==diag['additional_inputs']==671
for prefix,counts in diag['counts'].items():
 rr=[x for x in diag['results'] if x['input']['id'].startswith(prefix)]
 assert len(rr)==counts['inputs']
 assert all(x['exact']['fixed_by']<=x['exact']['bound'] for x in rr)
 assert sum(x['production_fourth_changes'] for x in rr)==counts['float_fourth_changes']
assert diag['counts']['coupled_']['float_fourth_changes']==0
assert diag['counts']['coupled_']['float_vs_causal_masks']==0
assert diag['counts']['near_']['float_fourth_changes']==1
assert sum(x['different'] for x in summary['completion_boundary_recalculation'])==1

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert diag['script_sha256']==sha(ROOT/'analysis/diagnostics.py')
assert diag['protocol_sha256']==sha(ROOT/'analysis/PROTOCOL.md')
assert diag['production_source_sha256']==sha(oldroot/'verification/sources/production/eval_sumo_stage1_mc.py')
follow=(ROOT/'analysis/FOLLOWUP_PROTOCOL.md').read_bytes()
protocol_prefixes={hashlib.sha256(follow[:i]).hexdigest() for i in range(len(follow)+1) if i==len(follow) or follow[i:i+1]==b'\n'}
# Appended declarations bind to the exact earlier text prefix used for that phase.
for name,key in [('NUMERICAL_FOLLOWUP','protocol_sha256'),('DIMENSION_CHECK','followup_protocol_sha256'),('PADDING_CHECK','followup_protocol_sha256'),('COMMON_TARGET_INPUT','followup_protocol_sha256')]:
 rec=json.loads((ar/(name+'.json')).read_text())
 assert rec[key] in protocol_prefixes,(name,rec[key])
for name,script in [('ADVERSE_PRODUCTION','adverse_production.py'),('PADDING_CHECK','padding_check.py'),('COMMON_TARGET_INPUT','common_target_fixture.py')]:
 rec=json.loads((ar/(name+'.json')).read_text());assert rec['script_sha256']==sha(ROOT/'analysis'/script)
assert sha(ROOT/'analysis/MATHEMATICS.md')=='0e709917cd575bdd472b3a22ff9f051975fd90f4ae3021c62014a7014aae7444'

# Check every baseline Git-tracked blob remains unchanged, including scientific archives.
DRAFT_BASE='1b6a8555c27901ec95ad8b123c413453ecdb5620'
tracked=subprocess.check_output(['git','ls-tree','-rz',DRAFT_BASE],cwd=REPO).split(b'\0')
verified=0
for entry in tracked:
    if not entry:continue
    meta,path=entry.split(b'\t',1); mode,kind,expected=meta.split(); p=REPO/path.decode()
    if kind!=b'blob':continue
    data=p.readlink().as_posix().encode() if mode==b'120000' else p.read_bytes()
    actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest().encode()
    assert actual==expected, str(p)
    verified+=1
from pypdf import PdfReader
pdf=ROOT/'TrafficTwin_Dissertation.pdf'; reader=PdfReader(pdf)
texts=[p.extract_text() for p in reader.pages]
assert not any('\u25a1' in t or '\ufffd' in t for t in texts)
pdf_links={'internal':0,'external_or_companion':0}
for page in reader.pages:
    for ref in page.get('/Annots',[]):
        obj=ref.get_object()
        if obj.get('/Subtype')!='/Link':continue
        if '/Dest' in obj:
            assert len(obj['/Dest'])>=1
            pdf_links['internal']+=1
        elif '/A' in obj:pdf_links['external_or_companion']+=1
# Check outline destinations against headings actually extracted on their pages.
outline=[]
def inspect(items):
    for item in items:
        if isinstance(item,list):inspect(item);continue
        page=reader.get_destination_page_number(item)
        title=item.title
        normal=lambda v:re.sub(r'[^a-z0-9]','',v.lower())
        assert normal(title) in normal(texts[page]),(title,page+1)
        outline.append({'title':title,'page':page+1})
inspect(reader.outline)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
visual=ROOT/'VISUAL_REVIEW.json'
v=json.loads(visual.read_text()) if visual.exists() else {'status':'pending'}
visual_current=v.get('pdf_sha256')==sha(pdf) and v.get('status')=='passed'
assert visual_current, 'Every-page visual review is absent or belongs to a different PDF'
assert v['pages']==len(reader.pages)
assert [c['page'] for c in v['checks']]==list(range(1,len(reader.pages)+1))
assert all(c['result']=='clean' for c in v['checks'])

report={
 'status':'current_document_source_arithmetic_integrity_and_visual_checks_passed',
 'date':'2026-09-08','branch':'docs/dissertation-production-mechanism-2026-09-08',
 'draft_baseline':DRAFT_BASE,'scientific_evidence_baseline':BASELINE,
 'manuscript_sha256':sha(draft),'pdf_sha256':sha(pdf),'proof_sha256':sha(ROOT/'analysis/MATHEMATICS.md'),
 'word_count':{'total':total,'sections':parts,'rule':'Same conservative rule as previous revision: whitespace-delimited rendered Markdown from Abstract through Conclusion including headings, table cells and algorithm blocks; excludes cover, contents, captions, figures, references and appendices. URLs and markup excluded.'},
 'references':13,'evidence_entries':15,'figure_captions':5,'body_table_captions':10,'appendix_tables':2,
 'numeric_or_status_table_cells_checked':checked_cells,'companion_links_checked':links,'internal_markdown_links_checked':internal,
 'baseline_tracked_blobs_verified':verified,'source_and_previous_output_bindings_verified':len(bound),'historical_scientific_artifacts_unchanged':True,
 'pdf':{'pages':len(reader.pages),'links':pdf_links,'outline_heading_agreement':outline,'current_every_page_visual_review':visual_current},
 'additional_small_inputs':summary['additional_inputs'],'declared_maximum':summary['budget'],
 'checks_distinguished':{
  'source_inspection':'Frozen environment constants, simultaneous helper prefix/mask/label operations and causal reservations inspected. Seven unchanged source/prior-result files rebound to base Git objects.',
  'compact_data_arithmetic':'Current tables4–8 and B2 compared with archived summaries and authenticated transitions/diagnostic CSV; saved input ledger and protocol bindings checked. Existing interval values retained, no new statistical tests.',
  'raw_record_reanalysis':'None in this task. Previous 19-run September audit and23joins reused, not repeated. Historical E0/E1/E2 task checks remain not assessable; recovery excluded.',
  'standalone_algorithm_tests':'719 explicit-input diagnostics including exact rational reference, unchanged production helpers, reductions and negative parameter transfers. Traces are instrumented mirrors checked against final helper fields. See analysis results; no full-model reachability/frequency claim.',
  'mathematical_analysis':'Exact-model unique fixed point/causal equivalence and min(n,2d−1) bound under explicit assumptions. Queue-clearing deduction conditional on stated gate, service and timing.',
  'file_integrity':'Every base Git-tracked blob verified unchanged; new artifact hashes recorded. A checksum is not a backup.',
  'rendering':'Fresh ReportLab PDF, Poppler page images and primary-agent inspection of every delivered page, bound to PDF hash. No old visual status reused.',
  'separate_ai_critique':'One separate reviewer assessed714-input manuscript/proof without desired score. One focused response; final5inputs and final layout checked by primary agent. Reviewed input hashes in REVIEW.md; not a human peer review.',
  'full_simulation_runs':'None; no actor, SUMO, retraining, campaign or proposed full-evaluator prefix execution.',
  'human_author_supervisor_approval':'Not received. Personal contribution, independent checks and assessment-specific AI-use permission remain author decisions.'},
 'docx':{'created':False,'scope':'Not requested in the current targeted task; no Word export or layout check claimed.'},
 'artifacts_sha256':{str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*') if p.is_file() and p.name not in ['VALIDATION.json','VISUAL_REVIEW.json','SHA256SUMS'] and '__pycache__' not in p.parts},
 'scope_limits':['No historical recovery or raw filesystem searches','No frozen evaluator/results modified','No push, merge, upload, submission or author approval']}
(ROOT/'VALIDATION.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','word_count','numeric_or_status_table_cells_checked','baseline_tracked_blobs_verified']},indent=2))
