"""Recompose only the hash-bound original captures; never launch or recapture UI."""
from pathlib import Path
import hashlib
import json
import os
import tempfile
from PIL import Image, ImageDraw, ImageFont
import fitz

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]
ASSETS = PACKAGE / 'assets'
PDF_OUTPUT = Path(os.environ.get('TRAFFICTWIN_FIGURE_PDF_DIR', tempfile.gettempdir())) / 'traffictwin-exemplar-figure-pdfs'
PDF_OUTPUT.mkdir(parents=True, exist_ok=True)
local_pdfs = []
original = json.loads((HERE / 'ORIGINAL_CAPTURE_RECEIPT.json').read_text())
previous = json.loads((PACKAGE / 'evidence/FINAL_PLATFORM_CAPTURE_2026-09-16.json').read_text())
# These fixed digests are from the ded54bd capture receipt.
SHOTS = {
 'a': 'bbea52d66a8241d8b7eb197fc1494662d9e896379715682de991540061280a14',
 'b': '8a835ff1bbf1e734cb827f4e0cb98a4f868fafa56be8f6db18a61796da18dab6',
 'c': '8e0fed0e1cdc592ba70825763ef78a8fe478629a9458a9b895fc9ecf46c3d908',
}
def sha(p):
 return hashlib.sha256(p.read_bytes()).hexdigest()
for k,h in SHOTS.items():
 assert sha(HERE/'shots'/f'{k}_tall.png') == h
bounds = {'a': (372,72,1370,604), 'b': (372,420,1370,1383), 'c': (372,72,1370,1195)}
imgs = {k:Image.open(HERE/'shots'/f'{k}_tall.png').crop(tuple(v*2 for v in box)) for k,box in bounds.items()}
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf',32)
labels={'a':'(a) TOS Data Import', 'b':'(b) External deadline-success matrix and comparison', 'c':'(c) Sealed eight-block dissertation contrasts'}
def paste(canvas,k,im,x,y):
 ImageDraw.Draw(canvas).text((x,y),labels[k],font=font,fill='#16313a')
 canvas.paste(im,(x,y+42))
def save(canvas,name):
 png=ASSETS/(name+'.png');pdf=PDF_OUTPUT/(name+'.pdf')
 canvas.save(png,dpi=(300,300))
 doc=fitz.open();page=doc.new_page(width=canvas.width*72/300,height=canvas.height*72/300)
 page.insert_image(page.rect,filename=str(png));doc.set_metadata({'title':'TrafficTwin with real data','author':'S M Abdulla Al Mamun'})
 if pdf.exists():pdf.unlink()
 doc.save(pdf,deflate=True);doc.close()
 local_pdfs.append({'filename':pdf.name,'local_path':str(pdf),'sha256':sha(pdf),'delivered_or_committed':False})
 return [png]
# Requested legend-free composite: (a) now spans the full width.
w=imgs['a'].width*2+20
afull=imgs['a'].resize((w,imgs['a'].height*2+11),Image.Resampling.LANCZOS)
canvas=Image.new('RGB',(w,afull.height+imgs['c'].height+104),'white')
paste(canvas,'a',afull,0,0); y=afull.height+62
paste(canvas,'b',imgs['b'],0,y);paste(canvas,'c',imgs['c'],imgs['b'].width+20,y)
files=save(canvas,'traffictwin_platform_real_data')
# At manuscript scale the single composite is below the requested type size.
# Figure 7a keeps directory/actions/counters/provenance; only its introductory
# heading/banner is cropped. No screenshot pixels are rewritten.
split_bounds_a=(372,285,1370,604)
a=Image.open(HERE/'shots/a_tall.png').crop(tuple(v*2 for v in split_bounds_a))
ab=Image.new('RGB',(imgs['b'].width,a.height+imgs['b'].height+104),'white')
paste(ab,'a',a,0,0);paste(ab,'b',imgs['b'],0,a.height+62)
files+=save(ab,'traffictwin_platform_7a')
c=Image.new('RGB',(imgs['c'].width,imgs['c'].height+42),'white');paste(c,'c',imgs['c'],0,0)
files+=save(c,'traffictwin_platform_7b')
previous.update({'crop_bounds_css':bounds,'split_figure_7a_a_crop_css':split_bounds_a,'figure_split':True,
 'composition_note':'Legend-free full-width (a) composite retained as a build input. Manuscript uses Figure 7a (a,b) and Figure 7b (c); panel a introductory heading/banner cropped only in 7a to retain legible directory, actions, counters and provenance. Original screenshots unchanged; no recapture or synthesised UI.',
 'research_workloads_launched':0})
previous['local_only_pdf_assets']=local_pdfs
previous['manuscript_uses']='PNG split assets; all regenerated PDFs are local-only. The tracked legacy full-composite PDF is preserved, unused by the current TeX.'
previous['files']={str(p.relative_to(PACKAGE)):sha(p) for p in [HERE/'capture_final.py',HERE/'compose_figure.py',HERE/'TOS_ADAPTER_VALIDATION.json',*[HERE/'shots'/f'{k}_tall.png' for k in SHOTS],*files]}
(PACKAGE/'evidence/FINAL_PLATFORM_CAPTURE_2026-09-16.json').write_text(json.dumps(previous,indent=2)+'\n')
print('PNG composites written; regenerated PDFs kept outside the repository/delivery; all three screenshot hashes unchanged.')
