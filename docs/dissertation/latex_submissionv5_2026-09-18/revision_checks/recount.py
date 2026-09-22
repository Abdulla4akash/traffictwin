"""Reproduce the automated count; run with Python 3 and markdown-it-py.

The pinned source-map count supplies original equation/pseudocode tokenisation.
Changed TeX blocks are projected using the retained project convention. Unlike
that older validator, this wrapper ALSO counts all table-body changes, including
headers (once) and the new divider text; captions and repeated headers are out.
No source, manuscript or historical receipt is modified. This is an automated
token estimate, not an institutional or manual count.
"""
from pathlib import Path
import json, re, sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'counting'))
import validate_prose_pass as c
c.HERE=HERE/'counting'
c.baseline=lambda *args,**kwargs: (c.HERE/'TrafficTwin_Dissertation.tex').read_text()
tex=(HERE.parent/'TrafficTwin_Dissertation.tex').read_text()
old=c.blocks(c.baseline()); new=c.blocks(tex)
r=c.word_counts(tex)
def table_visible(value):
    if not value.strip(): return ''  # Removed table contributes zero words.
    value=value.split(r'\toprule',1)[1]
    if r'\endfoot' in value:
        head=value.split(r'\midrule',1)[0]
        value=head+' '+value.split(r'\endfoot',1)[1]
    value=re.split(r'\\end\{(?:xltabular|tabularx|tabular)\}',value)[0]
    value=re.sub(r'\\multicolumn\{\d+\}\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}\{(.*?)\}(?=\\\\)',r'\1',value)
    value=re.sub(r'\\(?:toprule|midrule|bottomrule|endfirsthead|endhead|endfoot)\b',' ',value)
    value=value.replace(r'\\',' ').replace('&',' ')
    value=c.projection(value)
    value=re.sub(r'\\(?:textit|textbf|emph)\{([^{}]*)\}',r'\1',value)
    return value
r['table_body_deltas']=[]
for n,(kind,before) in old.items():
    if n>=206 or kind!='table':continue
    after=new[n][1]
    if after==before:continue
    a=len(re.findall(c.TOKEN,table_visible(before)))
    b=len(re.findall(c.TOKEN,table_visible(after)))
    r['table_body_deltas'].append({'block':n,'before':a,'after':b,'delta':b-a})
r['after']['strict']+=sum(d['delta'] for d in r['table_body_deltas'])
r['abstract_words']=sum(c.count([{'id':n,'kind':new[n][0],'source':c.projection(new[n][1])}])['strict'] for n in (3,4,5,6))
r['method']='Automated project token count: pinned cf8b514 source-map baseline plus checked TeX-projection deltas for prose, equations, pseudocode and table bodies; study map included. Abstract, main headings, table bodies and pseudocode included. Captions, references, appendices and other front matter excluded. Repeated continuation headers excluded. TOKEN = '+c.TOKEN
r['limitations']='This is not a manual count or a statement of additional institutional exclusions. Mathematical and hyphenated tokens depend on the documented source-projection convention; layout and figure labels are not narrative text. Requires markdown-it-py.'
print(json.dumps(r,indent=2))
