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
            assert target==(ROOT/'VALIDATION.json') or target.exists(),(doc.name,href)
            links+=1
    images+=len(re.findall(r'!\[',content))
for name in ('Figure','Table'):
    captions=[int(n) for n in re.findall(r'^\*'+name+r' (\d+)\.',text,re.M)]
    assert captions==list(range(1,6)), (name,captions)
    mentions={int(n) for n in re.findall(r'(?<!\*)'+name+r' (\d+)',text)}
    assert mentions <= set(captions)
assert set(re.findall(r'\[\[(\d+)\]\]\(#ref-',text))==set(map(str,range(1,9)))
assert set(re.findall(r'id="ref-(\d+)"',text))==set(map(str,range(1,9)))
assert set(re.findall(r'id="source-s(\d+)"',text))==set(map(str,range(12)))

def rows(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def table(n):
    block=text.split(f'*Table {n}.',1)[1].split('\n\n',2)[1]
    return [[x.strip() for x in line.strip().strip('|').split('|')] for line in block.splitlines()[2:]]
def fnum(x):return float(x.replace('−','-').replace('+',''))

# Every numeric data cell in the two primary per-draw tables and interval table.
checked_cells=0
incident=rows(ARCHIVE/'historical_e0_e2d/experiments/E2d/data/e2d_paired_results.csv')
for actual,source in zip(table(3),incident,strict=True):
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
for actual in table(4):
    seed=int(actual[0]); grouped={r[armkey]:r for r in morning if int(r[seedkey])==seed}
    vals=[float(grouped[k][attkey]) for k in ('ingress','common_target','per_task')]
    expected=[seed]+vals+[vals[2]-vals[0]]
    for a,e in zip(actual,expected,strict=True):
        assert abs(fnum(a)-e)<=.000501,(a,e)
        checked_cells+=1
intervals=rows(ARCHIVE/'generalisation-replication-2026-09-07/paired_intervals.csv')
for actual,source in zip(table(5),intervals,strict=True):
    observed=[fnum(actual[1])]+[fnum(n) for c in actual[2:] for n in re.findall(r'[+−-]?\d+\.\d+',c)]
    expected=[float(source[k]) for k in ('mean_pp','ci95_low_pp','ci95_high_pp','family95_low_pp','family95_high_pp')]
    for a,e in zip(observed,expected,strict=True):
        assert abs(a-e)<=.000501,(a,e)
        checked_cells+=1

# All tracked changes outside the new manuscript package must be discovery links only.
changed=subprocess.check_output(['git','diff',BASELINE,'--name-only'],cwd=REPO,text=True).splitlines()
permitted={'docs/index.md'}
assert all(p in permitted or p.startswith('docs/dissertation/complete_draft_2026-09-07/') for p in changed),changed
historical=REPO/'docs/dissertation_manuscript_20260801.md'
original=subprocess.check_output(['git','show',f'{BASELINE}:docs/dissertation_manuscript_20260801.md'],cwd=REPO)
assert original==historical.read_bytes()
report={
 'status':'passed','evidence_baseline':BASELINE,
 'draft_sha256':hashlib.sha256(draft.read_bytes()).hexdigest(),
 'word_count':{'total':total,'sections':parts,'rule':'Whitespace-delimited rendered text from Abstract through Conclusion; includes headings, table cells and algorithm; excludes cover, contents, captions, images, references and appendix; link URLs and Markdown syntax are not words.'},
 'references':8,'evidence_source_entries':12,'figure_captions':5,'table_captions':5,
 'internal_links_checked':internal,'relative_links_checked':links,'images_checked':images,
 'primary_table_numeric_cells_checked':checked_cells,
 'historical_manuscript_unchanged':True,'tracked_changes_outside_package':[
     p for p in changed if not p.startswith('docs/dissertation/complete_draft_2026-09-07/')],
 'scope':'Draft structure, word count, local links, numbered cross-references, archived CSV-to-table arithmetic, preservation. No simulations, evaluator execution, raw-array reanalysis or complete figure regeneration.'
}
(ROOT/'VALIDATION.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
