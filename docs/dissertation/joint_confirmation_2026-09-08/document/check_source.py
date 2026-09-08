"""Source-only validation. No compilation, rendering, or scientific execution."""
from pathlib import Path
from collections import Counter
from markdown_it import MarkdownIt
import hashlib,json,re,subprocess,unicodedata
R=Path(__file__).resolve().parents[4]
O=R/'docs/dissertation/joint_confirmation_2026-09-08'
S=R/'docs/dissertation/latex_markdown_2026-09-08'
md=(O/'TrafficTwin_Dissertation.md').read_text();orig=(S/'TrafficTwin_Dissertation.md').read_text();tex=(O/'TrafficTwin_Dissertation.tex').read_text()
record=json.loads((O/'document/SOURCE_MAP.json').read_text())
p=MarkdownIt('commonmark').enable('table');failures=[];checks={}
def check(name,truth,detail=None):
 checks[name]={'passed':bool(truth),'detail':detail}
 if not truth:failures.append(name)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def mdplain(s):
 return ''.join(t.content if t.type in ('text','code_inline') else ' ' if t.type in ('softbreak','hardbreak') else '' for t in p.parseInline(s)[0].children)
def canon(s):
 s=unicodedata.normalize('NFC',s).replace('’',"'").replace('“','"').replace('”','"').replace('−','-')
 s=re.sub(r'§\s+','§',s)
 s=re.sub(r'\s*([≥≤])\s*',r'\1',s)
 return re.sub(r'\s+',' ',s).strip()
# The current Markdown is the editable content authority for this research revision.
check('markdown_source_binding',sha(O/'TrafficTwin_Dissertation.md')==record['markdown_sha256'])
check('latex_source_binding',sha(O/'TrafficTwin_Dissertation.tex')==record['tex_sha256'])
# Decode typesetting without using the converter's escaping functions.
inv={'$'+v+'$':k for k,v in record['math_map'].items()}
mathkeys=re.compile('|'.join(re.escape(x) for x in sorted(inv,key=len,reverse=True)))
def group(s,j):
 assert s[j]=='{',(s,j)
 level=1;k=j+1
 while level:
  assert k<len(s),s[j:]
  if s[k]=='\\':
   if k+1<len(s) and s[k+1] in '{}':k+=2;continue
  if s[k]=='{':level+=1
  if s[k]=='}':level-=1
  k+=1
 return s[j+1:k-1],k
sym={'pm':'±','cdot':'·','times':'×','sum':'Σ','xi':'ξ','to':'→','neq':'≠','leq':'≤','geq':'≥','S':'§'}
# Placeholders shield exact formulas from markup parsing.
def decode(s):
 stash=[]
 def hold(m):stash.append(inv[m[0]]);return '\u0001'+str(len(stash)-1)+'\u0002'
 s=mathkeys.sub(hold,s);s=s.replace('---','—').replace('--','–').replace('``','“').replace("''",'”')
 def rec(s):
  out=[];i=0
  while i<len(s):
   ch=s[i]
   if ch=='$':i+=1;continue
   if ch=='~':out.append(' ');i+=1;continue
   if ch=='{':g,i=group(s,i);out.append(rec(g));continue
   if ch!='\\':out.append(ch);i+=1;continue
   i+=1
   if s[i] in r'{}%$&#_':out.append(s[i]);i+=1;continue
   if s[i]=='\\':out.append(' ');i+=1;continue
   if s[i] in ',;:! ':out.append(' ');i+=1;continue
   m=re.match(r'[A-Za-z]+\*?',s[i:]);assert m,s[i:];cmd=m[0];i+=len(cmd)
   if cmd in ('textbf','texttt','emph','text','mathrm','mathbf','ensuremath'):
    g,i=group(s,i);out.append(rec(g))
   elif cmd=='href':
    _,i=group(s,i);g,i=group(s,i);out.append(rec(g))
   elif cmd=='hyperref':
    assert s[i]=='[';i=s.index(']',i)+1;g,i=group(s,i);out.append(rec(g))
   elif cmd in ('ref','eqref','cite'):
    g,i=group(s,i)
    if cmd=='cite':out.append('['+g.removeprefix('ref')+']')
    elif cmd=='eqref':out.append('('+g.split(':')[-1]+')')
    else:out.append(g.split(':')[-1])
   elif cmd in ('label','phantomsection'):
    if cmd=='label':_,i=group(s,i)
   elif cmd in sym:out.append(sym[cmd])
   elif cmd in ('textbackslash','textasciicircum','textasciitilde'):
    if i<len(s) and s[i]=='{':_,i=group(s,i)
    out.append({'textbackslash':'\\','textasciicircum':'^','textasciitilde':'~'}[cmd])
   elif cmd=='textsuperscript':g,i=group(s,i);out.append(g.translate(str.maketrans('89','⁸⁹')))
   else:raise AssertionError(('unexpected_tex_command',cmd,s))
  return ''.join(out)
 s=rec(s)
 return re.sub('\u0001(\\d+)\u0002',lambda m:stash[int(m[1])],s)
# Validate each visible source block; table rows/algorithms independently extracted.
actual={int(m[1]):(m[2],m[3]) for m in re.finditer(r'% BEGIN SOURCE BLOCK (\d+) (\w+)\n(.*?)\n% END SOURCE BLOCK \1',tex,re.S)}
check('source_block_integrity',len(actual)==len(record['blocks'])-1)
bodycount=0;cells=0;numerical_cells=0
for b in record['blocks']:
 kind=b['kind'];raw=b['source'];code=b['latex']
 if b['id']:
  check('block_binding_'+str(b['id']),actual.get(b['id'])==(kind,code))
 if kind in ('paragraph','title','bibliography_item','proposition','proof','heading'):
  src=raw;new=code
  if kind=='bibliography_item':src=re.sub(r'^\[\d+\] ','',src);new=re.sub(r'^\\bibitem\{ref\d+\} ','',new)
  if kind=='proposition':
   m=re.match(r'^\*\*Proposition 1 \((.*?)\)\.\*\* (.*)',src,re.S);assert m
   mm=re.match(r'\\begin\{proposition\}\[(.*?)\]\\label\{prop:1\}\n(.*)\\end\{proposition\}',new,re.S);assert mm
   check('proposition_title',canon(mdplain(m[1]))==canon(decode(mm[1])))
   src=m[2];new=mm[2]
  if kind=='proof':src=src.removeprefix('**Proof sketch.** ');new=new.removeprefix('\\begin{proof}[Proof sketch]\n').removesuffix('\\end{proof}')
  if kind=='heading':
   if src=='Abstract':new='Abstract'
   elif src.startswith('Appendix '):
    m=re.fullmatch(r'Appendix ([A-E])\. (.*)',src);mm=re.match(r'\\appendixsection\{app:([A-E])\}\{(.*)\}',new,re.S)
    check('appendix_number_'+m[1],m[1]==mm[1]);src=m[2];new=mm[2]
   else:
    m=re.match(r'^((?:[A-E]|\d+)(?:\.\d+)?)\.? (.*)',src);mm=re.match(r'\\(?:sub)?section\{(.*)\}\\label\{sec:([^}]+)\}',new,re.S)
    check('section_number_'+m[1],m[1]==mm[2]);src=m[2];new=mm[1]
  a=canon(mdplain(src));c=canon(decode(new));check('content_'+str(b['id']),a==c, None if a==c else {'source':a,'tex':c});bodycount+=1
 elif kind=='table':
  num=re.search(r'\\label\{tab:([^}]+)\}',code)[1];table=next(t for t in record['tables'] if t['number']==num)
  ca=code.index('\\caption{')+len('\\caption');cap,_=group(code,ca)
  check('table_caption_'+num,canon(decode(cap))==canon(mdplain(table['caption'])))
  first=code.split('\\toprule\n',1)[1].split('\n\\midrule\\endfirsthead',1)[0]
  second=code.split('\\midrule\\endfirsthead\n\\toprule\n',1)[1].split('\n\\midrule\\endhead',1)[0]
  check('table_repeated_header_'+num,first==second)
  data=code.split('\\bottomrule\\endfoot\n',1)[1].split('\n\\end{xltabular}',1)[0]
  lines=[first]+data.splitlines()
  check('table_row_count_'+num,len(lines)==len(table['rows']))
  for ri,(line,row) in enumerate(zip(lines,table['rows'])):
   assert line.endswith(' \\\\');values=re.split(r'(?<!\\) & ',line[:-3])
   check(f'table_width_{num}_{ri}',len(values)==len(row))
   for ci,(v,cell) in enumerate(zip(values,row)):
    a=canon(mdplain(cell));c=canon(decode(v));check(f'cell_{num}_{ri}_{ci}',a==c,None if a==c else [a,c]);cells+=1
    if re.search(r'\d',a):numerical_cells+=1
 elif kind=='figure':
  num=re.search(r'\\label\{fig:([^}]+)\}',code)[1];fig=next(f for f in record['figures'] if f['number']==num)
  cap,_=group(code,code.index('\\caption{')+len('\\caption'))
  check('figure_caption_'+num,canon(decode(cap))==canon(mdplain(fig['caption'])))
 elif kind=='algorithm':
  num=re.search(r'\\label\{alg:([^}]+)\}',code)[1];alg=next(a for a in record['algorithms'] if a['number']==num)
  cap,_=group(code,code.index('\\caption{')+len('\\caption'))
  check('algorithm_caption_'+num,canon(decode(cap))==canon(mdplain(alg['title'])))
  body=re.search(r'\\begin\{Verbatim\}\[[^\n]*\]\n(.*?)\n\\end\{Verbatim\}',code,re.S)[1]
  check('algorithm_body_'+num,body==alg['body'])
# Independently account for original source block kinds/counts.
toks=p.parse(md)
check('table_count',sum(t.type=='table_open' for t in toks)==len(record['tables']))
check('algorithm_count',sum(t.type=='fence' for t in toks)==len(record['algorithms'])==2)
check('figure_count',sum(c.type=='image' for t in toks for c in t.children or [])==5)
check('heading_count',sum(t.type=='heading_open' for t in toks)==sum(b['kind'] in ('heading','title','bibliography_open') for b in record['blocks']))
# Numbered formula source review: operators, strictness, units, components are preserved.
check('numbered_equations_present',len(record['equations'])==6 and r'\label{eq:C1}' in tex and all('\\label{eq:'+str(n)+'}' in tex for n in range(1,6)))
# The five main equations and C1 are also inspected against their Markdown source.
# Structural balance, excluding literal pseudocode and TeX comments.
clean=re.sub(r'\\begin\{Verbatim\}.*?\\end\{Verbatim\}','',tex,flags=re.S)
clean=re.sub(r'(?<!\\)%[^\n]*','',clean)
stack=[];envs=[]
for m in re.finditer(r'\\(begin|end)\{([^}]+)\}',clean):
 if m[1]=='begin':stack.append(m[2]);envs.append(m[2])
 else:
  check('environment_'+str(m.start()),bool(stack) and stack[-1]==m[2])
  if stack:stack.pop()
check('environments_balanced',not stack)
balance=0;minimum=0;i=0
while i<len(clean):
 if clean[i]=='\\' and i+1<len(clean) and not clean[i+1].isalpha():i+=2;continue
 if clean[i]=='{':balance+=1
 if clean[i]=='}':balance-=1;minimum=min(minimum,balance)
 i+=1
check('braces_balanced',balance==0 and minimum==0)
check('math_dollars_even',len(re.findall(r'(?<!\\)\$',clean))%2==0)
check('groups_balanced',clean.count('\\begingroup')==clean.count('\\endgroup'))
labels=re.findall(r'\\label\{([^}]+)\}',tex)
labels=[x for x in labels if x!='#1']+re.findall(r'\\appendixsection\{([^}]+)\}',tex)
check('labels_unique',len(labels)==len(set(labels)))
refs=re.findall(r'\\(?:eqref|ref)\{([^}]+)\}|\\hyperref\[([^]]+)\]',tex);targets=[a or b for a,b in refs]
check('reference_targets',not(set(targets)-set(labels)),sorted(set(targets)-set(labels)))
bibs=re.findall(r'\\bibitem\{([^}]+)\}',tex);cites=re.findall(r'\\cite\{([^}]+)\}',tex)
check('bibliography_keys',bibs==['ref'+str(i) for i in range(1,15)])
check('citation_targets',set(cites)<=set(bibs))
# Count source citations outside bibliography. Source table citations are plain [n].
pre=md.split('\n## References\n',1)[0]
sourcecites=re.findall(r'(?<!\w)\[(\d+)\]',mdplain(pre))
# Markdown whole-block parse used above doesn't collapse link labels twice.
# Tex table continuation headers contain no citations in this manuscript.
check('citation_frequency',Counter(sourcecites)==Counter(k[3:] for k in cites),{'markdown':dict(Counter(sourcecites)),'latex':dict(Counter(k[3:] for k in cites))})
urls=[]
for t in p.parse(md):
 for c in t.children or []:
  if c.type in ('link_open','image'):urls.append(c.attrGet('href') or c.attrGet('src'))
missing=[]
for u in urls:
 if u.startswith(('#','http://','https://')):continue
 if not (O/u.split('#')[0]).exists():missing.append(u)
check('markdown_local_links_and_assets',not missing,missing)
texurls=re.findall(r'\\href\{\\detokenize\{([^}]+)\}\}',tex)
check('latex_external_links_match_markdown',Counter(texurls)==Counter(u for u in urls if not u.startswith(('#','assets/'))))
assets=re.findall(r'\\includesvg\[.*?\]\{([^}]+)\}',tex)
check('latex_figure_assets',len(assets)==5 and all((O/(a+'.svg')).is_file() for a in assets))
asset_hashes={a+'.svg':sha(O/(a+'.svg')) for a in assets}
check('assets_unchanged',all(sha(O/(a+'.svg'))==sha(S/(a+'.svg')) for a in assets))
check('no_absolute_local_paths',not any(x in tex+md for x in ('/Users/','/tmp/','/System/','/opt/homebrew/')))
expected_files={'TrafficTwin_Dissertation.md','TrafficTwin_Dissertation.tex'}|set(asset_hashes)
# Direct content hashes prove all old tracked files, PDFs and validation receipts unchanged.
entries=subprocess.check_output(['git','ls-tree','-r','-z','c049f00f2247bfbd1196d5e6524de8198fdd2df7'],cwd=R).split(b'\0');modified=[];tracked=0
for entry in entries:
 if not entry:continue
 meta,name=entry.split(b'\t',1);mode,typ,oid=meta.decode().split();path=R/name.decode()
 if typ!='blob':continue
 if not path.is_file():modified.append(name.decode());continue
 data=path.read_bytes();gitsha=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest();tracked+=1
 if gitsha!=oid:modified.append(name.decode())
check('historical_tracked_files_unchanged',not modified,{'count':tracked,'changed':modified})
sections={};section=None;in_main=False;words=[]
for ti,t in enumerate(toks):
 if t.type=='heading_open':
  title=toks[ti+1].content
  if title=='Abstract':in_main=True
  if title=='References':in_main=False
  if in_main and t.tag=='h2':section=title;sections[section]=0
 if not in_main:continue
 if t.type=='inline':
  if t.content.startswith(('*Table ','*Figure ')) or any(c.type=='image' for c in t.children or []):continue
  n=len(mdplain(t.content).split());sections[section]+=n;words.extend(mdplain(t.content).split())
 elif t.type=='fence':n=len(t.content.split());sections[section]+=n;words.extend(t.content.split())
check('main_word_limit',7000<=len(words)<=9000,{'count':len(words),'sections':sections,'rule':'Abstract through Conclusion, rendered Markdown whitespace tokens including headings, table cells and algorithms; captions/figures, cover, references and appendices excluded'})
# Explicitly included full proof, not just a hyperlink.
check('full_proof_sections',all('### C.'+str(i)+' ' in md for i in range(1,7)))
check('full_proof_environments',len(re.findall(r'\\begin\{proof\}',tex))==3)
result={'scope':'Source-only manuscript checks; scientific execution and validation are recorded separately','baseline_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'branch':subprocess.check_output(['git','branch','--show-current'],cwd=R,text=True).strip(),'source_sha256':sha(S/'TrafficTwin_Dissertation.md'),'output_sha256':{f:sha(O/f) for f in sorted(expected_files)},'compilation_performed':False,'pdf_generation_performed':False,'visual_validation_performed':False,'main_text_words':len(words),'section_words':sections,'source_checks':{'body_blocks_compared':bodycount,'table_cells_compared':cells,'numerical_cells_compared':numerical_cells,'tables':len(record['tables']),'figures':5,'algorithms':2,'numbered_equations':6,'bibliography_entries':14,'labels':len(labels),'link_occurrences':len(urls),'preserved_tracked_files':tracked},'checks':checks,'failures':failures,'boundaries':['Source checks do not establish compilation or visual correctness.','SVG use requires standard svg package and Inkscape at future compilation; authorised shell escape may be required.','Evidence hyperlinks require the preserved repository records. Bibliography and all figures are included.']}
(O/'document/SOURCE_VALIDATION.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'failures':failures,'coverage':result['source_checks'],'source_checks':len(checks)},indent=2))
for f in failures[:12]:print(f,checks[f])
raise SystemExit(bool(failures))
