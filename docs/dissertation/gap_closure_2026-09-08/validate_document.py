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
for doc in ROOT.glob('*.md'):
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
    assert captions==list(range(1,6 if name=='Figure' else 9)), (name,captions)
    mentions={int(n) for n in re.findall(r'(?<!\*)'+name+r' (\d+)',text)}
    assert mentions <= set(captions)
assert set(re.findall(r'\[\[(\d+)\]\]\(#ref-',text))==set(map(str,range(1,14)))
assert set(re.findall(r'id="ref-(\d+)"',text))==set(map(str,range(1,14)))
assert set(re.findall(r'id="source-s(\d+)"',text))==set(map(str,range(14)))

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

# Current new evidence; distinguish finite observations from historical missingness.
assert re.findall(r'^\*Table (B\d+)\.',text,re.M)==['B1','B2']
assert '## Appendix B. Audit coverage and diagnostic boundaries' in text
assert text.count('unquantified')>=3
vr=ROOT/'verification/results'
raw=json.loads((vr/'RAW_AUDIT.json').read_text())['runs'];assert len(raw)==19
assert all(all(r['checks'].values()) and r['false_success_discrepancies']==0 and r['rejected_finite_nonpenalty_latency']==0 for r in raw)
inv=json.loads((vr/'INVENTORY_CHECK.json').read_text());assert inv['verified']==87 and inv['bytes_verified']==1762464782
trans=json.loads((vr/'OUTCOME_TRANSITIONS.json').read_text())['pairs'];assert len(trans)==23
primary=[r for r in trans if 'replication' in r['group'] and '_ingress/' in r['A'] and '_per_task/' in r['B']]
for actual,r in zip(table('B2'),primary,strict=True):
 expected=[r['seed']]+[r[k] for k in ['failure_to_success','success_to_failure','success_both','failure_both','net_successes']]
 assert [int(v.replace(',','')) for v in actual]==expected
 checked_cells+=len(expected)
for k,v in [('failure_to_success',284821),('success_to_failure',12842),('net_successes',271979)]:assert sum(r[k] for r in primary)==v and f'{v:,}' in text
kern=json.loads((vr/'KERNEL_RESULTS.json').read_text());assert kern['primary_cases']==440 and kern['minimisation_trials']==10 and kern['fourth_changes_cases']==1
assert sum(any(s['A']['fourth_changes'] for s in r['steps']) for r in kern['results'] if r['input']['id'].startswith('grid_'))==0
assert kern['contrasts']['B_C']['success_increase_cases']==69 and kern['contrasts']['B_C']['success_decrease_cases']==16
prod=json.loads((vr/'PRODUCTION_AGREEMENT.json').read_text());assert prod['status']=='passed' and prod['substeps_compared']==1305
hist=json.loads((vr/'HISTORICAL_COVERAGE.json').read_text());assert all(r['false_success_discrepancies']=='not assessable from available records' for r in hist['runs'])
assert json.loads((vr/'RELOCATION_CHECK.json').read_text())['status']=='passed'
# Scholarly identities remain exactly as previously verified; Table1 terminology is corrected.
old=(REPO/'docs/dissertation/substantive_revision_2026-09-07/TrafficTwin_Dissertation.md').read_text()
assert text.split('## References')[1].split('## Appendix A')[0]==old.split('## References')[1].split('## Appendix A')[0]
# Every compact copy is also checked against its stated Git object, not just a self-generated checksum.
bound=json.loads((ROOT/'verification/SOURCE_BINDINGS.json').read_text())
for b in bound:
 source_repo=REPO if b['repository']=='Abdulla4akash/traffictwin' else Path('/Users/akashx/Downloads/diss_mat/vec_env-full')
 data=subprocess.check_output(['git','show',b['commit']+':'+b['source']],cwd=source_repo)
 assert hashlib.sha256(data).hexdigest()==b['sha256']
 assert (ROOT/'verification'/b['file']).read_bytes()==data

# Check every baseline Git-tracked blob remains unchanged, including scientific archives.
DRAFT_BASE='227c95e8e3e6b949eacb2b92c6e32c0ffdcd8133'
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
 'status':'document_source_arithmetic_integrity_and_current_visual_checks_passed',
 'draft_baseline':DRAFT_BASE,'scientific_evidence_baseline':BASELINE,
 'manuscript_sha256':sha(draft),'pdf_sha256':sha(pdf),
 'word_count':{'total':total,'sections':parts,'rule':'Whitespace-delimited rendered Markdown text from Abstract through Conclusion, including headings, table cells and algorithm blocks; excludes cover, contents, captions, figures, references and appendix. URLs and markup excluded. Same conservative rule as baseline draft.'},
 'references':13,'evidence_entries':14,'figure_captions':5,'table_captions':8,'appendix_tables':2,
 'numeric_primary_table_cells':checked_cells,'companion_links_checked':links,'internal_markdown_links_checked':internal,
 'baseline_tracked_blobs_verified':verified,'compact_sources_bound_to_git':len(bound),'historical_scientific_artifacts_unchanged':True,
 'pdf':{'pages':len(reader.pages),'links':pdf_links,'outline_heading_agreement':outline,'current_every_page_visual_review':visual_current},
 'checks_distinguished':{'arithmetic':'Executed relocatable compact_arithmetic.py and revised-table checks; original t and Bonferroni formulas recalculated from summaries. See verification/results/ARITHMETIC.json. Not fresh historical task validation.','source':'Inspected exact historical/follow-up scoring/energy/queue paths, source hashes, ownership and stream contracts. Existing primary synthesis retained; one targeted waiting-time-definition recheck. See CLAIM_SOURCE_MAP.md and REFERENCE_CHECK.md.','file_integrity':'All baseline tracked blobs compared to Git object identities.','rendering':'Fresh ReportLab build, Poppler rendering and visual record tied to this PDF hash.','raw_data_reanalysis':'Executed authenticated 19-run September audit and all 23 within-study/same-seed paired transitions; historical E0/E1/E2 arrays unavailable, checks not assessable. See verification/results/RAW_AUDIT.json and OUTCOME_TRANSITIONS.json.','separate_ai_critique':'One separate context-isolated AI reviewer assessed manuscript/evidence without a desired score; supported objections addressed once. See REVIEW.md.', 'standalone_algorithm_tests':'440 predeclared cases + 10 deletion trials; unchanged production A/C helper agreement on 1,305 substeps. Explicit synthetic arrays; no actor/full evaluator or physics validation.', 'full_simulation_runs':'None executed. Optional full-evaluator tie-break prefixes remain unrun.', 'human_author_supervisor_approval':'Not received; attribution and assessment-specific AI permission unresolved.','independent_scientific_review':'Not claimed. The AI critique is neither human peer review nor experimental replication.'},
 'docx':{'created':False,'attempt':'Current tool/skill discovery, specific runtime/tool lookup and Codex Document Control session listing performed. No managed dependency loader/runtime exposed; runtime variables absent; no connected document session; no LibreOffice or Word application at checked paths. Managed DOCX authoring could not start. Pandoc alone does not meet the skill runtime contract.','skill_requirement':'Documents SKILL.md: Use Codex workspace dependencies for docx artifact work; do not use system runtimes/global/repo-local installs.'},
 'artifacts_sha256':{str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*') if p.is_file() and p.name not in ['VALIDATION.json','VISUAL_REVIEW.json','SHA256SUMS'] and '__pycache__' not in p.parts},
 'scope_limits':['No full simulations, historical evaluator/result changes, retraining, benchmark campaign or full-evaluator tie-break execution; standalone synthetic diagnostics explicitly authorised','No push, merge, upload, publication or submission','No author approval or unaided authorship inferred'],
}
(ROOT/'VALIDATION.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','word_count','numeric_primary_table_cells','baseline_tracked_blobs_verified']},indent=2))
