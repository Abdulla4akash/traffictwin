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
            assert target.exists() or (target == ROOT/'VALIDATION.json'),(doc.name,href)
            links+=1
    images+=len(re.findall(r'!\[',content))
for name in ('Figure','Table'):
    captions=[int(n) for n in re.findall(r'^\*'+name+r' (\d+)\.',text,re.M)]
    assert captions==list(range(1,6 if name=='Figure' else 13)), (name,captions)
    mentions={int(n) for n in re.findall(r'(?<!\*)'+name+r' (\d+)',text)}
    assert mentions <= set(captions)
assert set(re.findall(r'\[\[(\d+)\]\]\(#ref-',text))==set(map(str,range(1,15)))
assert set(re.findall(r'id="ref-(\d+)"',text))==set(map(str,range(1,15)))
assert set(re.findall(r'id="source-s(\d+)"',text))==set(map(str,range(16)))

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
vr=oldroot/'verification/results'; ar=ROOT.parent/'production_mechanism_2026-09-08/analysis/results'
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
for actual,r in zip(table(9),adverse,strict=True):
 expected=[f"{r['substep']}.{r['candidate']}",str(int(float(r['deadline']))),f"{float(r['service']):.3f}"]
 for arm in ['B','C']:
  assert r[f'{arm}_admitted']=='True'
  expected.extend([f"{r[f'{arm}_target']} / {float(r[f'{arm}_before']):.3f}",f"{float(r[f'{arm}_completion']):.3f} "+('met' if r[f'{arm}_met']=='True' else 'miss')])
 assert [x.replace('**','') for x in actual]==expected,(actual,expected)
 checked_cells+=len(expected)
assert sum(r['B_met']=='True' for r in adverse)==8 and sum(r['C_met']=='True' for r in adverse)==7
old=(ROOT.parent/'production_mechanism_2026-09-08/TrafficTwin_Dissertation.md').read_text()
assert text.split('## References')[1].split('<a id="ref-14">')[0].strip()==old.split('## References')[1].split('## Appendix A')[0].strip()

# New table cells are derived from authenticated September aggregation and saved timings.
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
newar=ROOT/'analysis/results'
types=load(newar/'TASK_TYPES.json');paired=types['paired']
assert types['script_sha256']==sha(ROOT/'analysis/task_types.py')
assert len(types['bindings'])==8 and len(types['rows'])==24 and len(paired)==12
assert types['task_joins_rerun']==0 and types['inferential_tests']==0
for actual,typ in zip(table(8),[1,2,3],strict=True):
    rr=[r for r in paired if r['type']==typ]
    assert actual[0]==f"{typ} / {100 if typ!=2 else 500} ms"
    expected=[rr[0]['offered']]+[r['net_successes'] for r in rr]
    assert [int(v.replace(',','').replace('+','')) for v in actual[1:]]==expected
    checked_cells+=len(expected)
assert len(table('D1'))==len(types['rows'])
for actual in table('D1'):
    seed,typ=map(int,actual[0].split('/'));arm='ingress' if actual[1]=='I' else 'per_task'
    r=next(r for r in types['rows'] if r['seed']==seed and r['type']==typ and r['arm']==arm)
    expected=[f"{r['seed']}/{r['type']}", 'I' if r['arm']=='ingress' else 'P']
    expected += [f"{r[k]:,}" for k in ['offered','successes']]
    expected += [f"{r['attainment_pct']:.3f}"]
    expected += [f"{r[k]:,}" for k in ['admitted','gate_rejected','admitted_misses']]
    assert actual==expected,(actual,expected)
    checked_cells+=len(expected)
assert [sum(r['net_successes'] for r in paired if r['type']==t) for t in [1,2,3]]==[79581,145,192253]
b=load(newar/'BENCHMARK.json')
assert b['protocol_sha256']==sha(ROOT/'analysis/PROTOCOL.md')
for path,digest in b['sources'].items():assert sha(ROOT/path)==digest
for actual,policy in zip(table(10),['ingress_dla','dla','per_task_dla','causal_round_robin'],strict=True):
    def rec(n,fixture):return next(r for r in b['rows'] if r['N']==n and r['fixture']==fixture and r['policy']==policy)
    expected=['/'.join(f"{rec(n,f)['median_ms']:.3f}" for f in ['sparse','busy']) for n in [215,2488]]
    expected += ['/'.join(f"{rec(n,'busy')['p95_ms']:.3f}" for n in [215,2488])]
    expected += ['/'.join(f"{rec(n,'busy')['memory_analysis_bytes']['temp_size_in_bytes']/1024:.1f}" for n in [215,2488])]
    assert actual[1:]==expected,(actual,expected)
    checked_cells+=8
assert min(r['compilation_s'] for r in b['rows'])>=.0575 and max(r['compilation_s'] for r in b['rows'])<.2675
assert 'At each nonempty destination' in text
assert 'imposed stress' in text and 'fixed-action replay' in text
assert 'Algorithm 1:' in text and 'Algorithm 2:' in text and '**Proposition 1' in text
assert re.findall(r'^\*Table ([A-Z]\d+)\.',text,re.M)==['B1','B2','D1']

bound=load(ROOT/'analysis/SOURCE_BINDINGS.json')
for r in bound:assert sha(REPO/r['path'])==r['sha256'],r['path']
compact=load(newar/'compact/COMPACT_CHECKS.json')
relocation=load(newar/'RELOCATION_CHECK.json')
assert compact['status']==relocation['status']=='passed'
assert compact['benchmark_calls_checked']==1600
for name in ['COMPARATOR_TESTS','COMPATIBILITY_TESTS']:
    d=load(newar/(name+'.json'));assert d['status']=='passed' and d['full_evaluations']==0
    for path,digest in d['source_sha256'].items():assert sha(ROOT/'experimental'/path)==digest
seal=load(ROOT/'confirmation/SEALED.json')
assert not seal['execute_new_confirmation']
for path,digest in seal['sources'].items():assert sha(REPO/path)==digest
assert compact['seal_sha256']==sha(ROOT/'confirmation/SEALED.json')
for name in ['RUNNER_TESTS','DRY_RUN']:
    d=load(ROOT/'confirmation'/(name+'.json'));assert d['seal_sha256']==sha(ROOT/'confirmation/SEALED.json')
assert load(ROOT/'confirmation/DRY_RUN.json')['full_evaluations_launched']==0

# All pre-existing Git blobs, including archives and manuscripts, remain untouched.
DRAFT_BASE='ee6a4b151d92329f9c26e3f344d87b70b84fc31e'
tracked=subprocess.check_output(['git','ls-tree','-rz',DRAFT_BASE],cwd=REPO).split(b'\0');verified=0
for entry in tracked:
    if not entry:continue
    meta,path=entry.split(b'\t',1);mode,kind,expected=meta.split();p=REPO/path.decode()
    if kind!=b'blob':continue
    data=p.readlink().as_posix().encode() if mode==b'120000' else p.read_bytes()
    assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest().encode()==expected,str(p)
    verified+=1

from pypdf import PdfReader
pdf=ROOT/'TrafficTwin_Dissertation.pdf';reader=PdfReader(pdf);texts=[p.extract_text() for p in reader.pages]
assert not any('\u25a1' in t or '\ufffd' in t for t in texts)
pdf_links={'internal':0,'external_or_companion':0};page_refs={p.indirect_reference.idnum for p in reader.pages}
for page in reader.pages:
    for ref in page.get('/Annots',[]):
        obj=ref.get_object()
        if obj.get('/Subtype')!='/Link':continue
        if '/Dest' in obj:
            assert obj['/Dest'][0].idnum in page_refs
            pdf_links['internal']+=1
        elif '/A' in obj:pdf_links['external_or_companion']+=1
outline=[]
def inspect(items):
    for item in items:
        if isinstance(item,list):inspect(item);continue
        page=reader.get_destination_page_number(item);title=item.title
        normal=lambda v:re.sub(r'[^a-z0-9]','',v.lower())
        assert normal(title) in normal(texts[page]),(title,page+1)
        outline.append({'title':title,'page':page+1})
inspect(reader.outline)
v=load(ROOT/'VISUAL_REVIEW.json')
assert v['pdf_sha256']==sha(pdf) and v['status']=='passed'
assert v['pages']==len(reader.pages)
assert [c['page'] for c in v['checks']]==list(range(1,len(reader.pages)+1))
assert all(c['result']=='clean' for c in v['checks'])
assert 'Not assessable from available records' in text and 'unquantified off-mask exception' in text

report={
 'status':'current_document_source_arithmetic_integrity_and_visual_checks_passed',
 'date':'2026-09-08','branch':'docs/dissertation-empirical-extension-2026-09-08',
 'draft_baseline':DRAFT_BASE,'scientific_evidence_baseline':BASELINE,
 'manuscript_sha256':sha(draft),'pdf_sha256':sha(pdf),
 'word_count':{'total':total,'sections':parts,'rule':'Whitespace-delimited rendered Markdown from Abstract through Conclusion, including headings, table cells and algorithm blocks; excludes cover, contents, captions, figures, references and appendices. Same conservative count rule as the preceding package.'},
 'assessment_basis':{'original_supplied_rubric':'MSc_Report_and_Video_Rubric (2).pdf, five pages inspected','rubric_sha256':'c88175e344c8aa0cfd5eba6164a8b5941670c7cc5bb69e89213c6c019bcd8c0f','repository_transcription':'docs/dissertation/comp66060_rubric_readiness_2026-08-19.md','word_requirement':[7000,9000],'video_minutes':[6,8]},
 'references':14,'evidence_entries':16,'figure_captions':5,'body_table_captions':12,'appendix_tables':3,
 'numeric_or_status_table_cells_checked':checked_cells,'companion_links_checked':links,'internal_markdown_links_checked':internal,
 'baseline_tracked_blobs_verified':verified,'source_and_output_bindings_verified':len(bound),
 'historical_scientific_artifacts_unchanged':True,
 'pdf':{'pages':len(reader.pages),'links':pdf_links,'outline_heading_agreement':outline,'current_every_page_visual_review':True},
 'confirmation':{'switch':False,'full_evaluations':0,'planned_cells':32,'planned_joint_blocks':8,'seal_sha256':sha(ROOT/'confirmation/SEALED.json'),'full_instrumented_evaluator_qualification':'unrun; kernel and runner checks are not end-to-end qualification'},
 'checks_distinguished':{
  'source_inspection':'Frozen placement, service, scorer, random-key, state feedback and queue conventions; new comparator generation/entry route inspected. Old files unchanged.',
  'compact_data_arithmetic':'Tables4–10, B2 and D1 compared with saved source records; type totals reconcile and 1600 saved timing durations regenerate summaries. No new traffic-inference tests.',
  'raw_record_reanalysis':'Exactly eight authenticated September primary-morning ingress/per-task files, one at a time, aggregated by three task types. The old19-run audit and23joins were reused and not repeated. Historical E0/E1/E2 task-level checks remain not assessable.',
  'standalone_algorithm_tests':'Six declared round-robin hand/reference cases, pointer/pass/capacity/radio/work checks, one-RSU equality and28unchanged-route checks. No old proof or719-input suite rerun.',
  'scheduler_benchmark':'Sixteen fixture/dimension/policy configurations, five warmups and100synchronised steady-state calls each; compiled frozen helpers and new cyclic implementation. No actor/evaluator timing, transfer timing or peak-RSS measurement.',
  'mathematical_analysis':'Prior exact-model proposition and numerical investigation reused. Nonempty-destination assumption and negative-transfer scope clarified after separate critique.',
  'runner_dry_run':'32configurations, source/runtime/input identities and storage checked; launch disabled; failure/control-binding tests passed. No full evaluator process launched.',
  'relocation':'Compact verifier passed from a clean temporary checkout and separate empty working directory; no private arrays, actor or trace copied.',
  'file_integrity':'Every baseline tracked blob checked unchanged. New artifact hashes bind outputs; hashes and a local copy are not backups.',
  'rendering':'Fresh document-only ReportLab build, Poppler rasterisation and primary-agent inspection of all current pages; receipt bound to final PDF hash.',
  'separate_ai_critique':'One separate AI reviewer assessed the revised manuscript/rubric and new evidence without a desired score. Five supported objections addressed once; post-fix validation is primary-agent self-check, not a second independent review.',
  'full_simulation_runs':'Zero. No actor inference, SUMO run, retraining, historical recovery, full-evaluator prefix or campaign.',
  'human_author_supervisor_approval':'Not received; personal contribution, independent understanding/checks and assessment-specific AI authority remain unresolved author inputs.'},
 'docx':{'created':False,'reason':'Not requested by the current task; no new Word file or layout check claimed.'},
 'video':{'storyboard':True,'duration':'7:20','recorded':False},
 'artifacts_sha256':{str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*') if p.is_file() and p.name not in ['VALIDATION.json','SHA256SUMS'] and '__pycache__' not in p.parts},
 'scope_limits':['No historical recovery/search','No frozen evaluator or result edits','No push, merge, upload, paid compute, cluster job or submission']}
(ROOT/'VALIDATION.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','word_count','numeric_or_status_table_cells_checked','baseline_tracked_blobs_verified']},indent=2))
