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
assert set(re.findall(r'id="source-s(\d+)"',text))==set(map(str,range(13)))

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

# Check every baseline Git-tracked blob remains unchanged, including scientific archives.
DRAFT_BASE='f91436af2b8f506b400d815947b3a87bda8cd3fd'
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
 'references':13,'evidence_entries':13,'figure_captions':5,'table_captions':8,
 'numeric_primary_table_cells':checked_cells,'companion_links_checked':links,'internal_markdown_links_checked':internal,
 'baseline_tracked_blobs_verified':verified,'historical_scientific_artifacts_unchanged':True,
 'pdf':{'pages':len(reader.pages),'links':pdf_links,'outline_heading_agreement':outline,'current_every_page_visual_review':visual_current},
 'checks_distinguished':{'arithmetic':'Executed check_arithmetic.py and CSV-to-manuscript checks; original t and Bonferroni formulas recalculated. See ARITHMETIC.json.','source':'Read frozen algorithms, latency/accounting, ownership history, manifests, primary methods. See CLAIM_SOURCE_MAP.md and REFERENCE_CHECK.md.','file_integrity':'All baseline tracked blobs compared to Git object identities.','rendering':'Fresh ReportLab build, Poppler rendering and visual record tied to this PDF hash.','raw_data_reanalysis':'Not performed. Archived scientific validation/audit receipts inspected, not rerun.','separate_ai_critique':'Context-isolated reviewer assessed all five requested criteria without a target score, followed by one focused response check. See REVIEW.md.','independent_scientific_review':'Not claimed. The AI critique is neither human peer review nor experimental replication.'},
 'docx':{'created':False,'attempt':'Current tool/skill discovery and local capability check. No workspace dependency loader/runtime exposed; RUNTIME_NODE/PYTHON/BIN_DIR absent; no LibreOffice/soffice in PATH or Applications. Managed DOCX export could not be started. Pandoc is present but does not supply the document skill required managed runtime or visual renderer.','skill_requirement':'Documents SKILL.md: Use Codex workspace dependencies for docx artifact work; do not use system runtimes/global/repo-local installs.'},
 'artifacts_sha256':{str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*') if p.is_file() and p.name not in ['VALIDATION.json','VISUAL_REVIEW.json','SHA256SUMS'] and '__pycache__' not in p.parts},
 'scope_limits':['No new simulations, evaluator changes, retraining, benchmark or tie-break execution','No push, merge, upload, publication or submission','No author approval or unaided authorship inferred'],
}
(ROOT/'VALIDATION.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','word_count','numeric_primary_table_cells','baseline_tracked_blobs_verified']},indent=2))
