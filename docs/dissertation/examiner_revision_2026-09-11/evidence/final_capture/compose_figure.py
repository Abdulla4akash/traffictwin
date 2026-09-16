"""Compose real captured panels without changing or synthesising interface contents."""
from pathlib import Path
import json,hashlib
from PIL import Image,ImageDraw,ImageFont
import fitz
r=Path(__file__).parent
# CSS-pixel bounds within the 1440x3000 capture, sampled at device scale 2.
# Panel a retains page heading, source directory, inspection action, counters and provenance.
# Panel b retains the heatmap plus full paired-comparison table.
# Panel c retains the study identity, block counters, contrast chart and complete interval table.
bounds={'a':(372,72,1370,604),'b':(372,420,1370,1383),'c':(372,72,1370,1195)}
imgs={}
for k,box in bounds.items():
 im=Image.open(r/'shots'/f'{k}_tall.png');imgs[k]=im.crop(tuple(v*2 for v in box))
# Landscape composition: a full-width top band, b and c below at equal scale.
scale=1
margin=35;gap=40;label_h=52
panelw=imgs['b'].width
# a is kept at same scale as lower panels and occupies top-left; its white right half holds legend text.
width=2*panelw+3*margin
height=imgs['a'].height+label_h+imgs['c'].height+label_h+3*margin
canvas=Image.new('RGB',(width,height),'white');d=ImageDraw.Draw(canvas)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf',34)
small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',29)
x=margin;y=margin
d.text((x,y),'(a) TOS Data Import',font=font,fill='#16313a');canvas.paste(imgs['a'],(x,y+label_h))
# Editorial legend outside screenshots, explicitly descriptive rather than fake UI.
for j,line in enumerate(['External package: Paper 2B / R. P. Putra','Panels (a)–(b): imported simulation evidence','Panel (c): sealed dissertation confirmation','Original interface captures; no simulated UI']):
 d.text((panelw+2*margin,170+65*j),line,font=small,fill='#334155')
y+=label_h+imgs['a'].height+margin
for k,title,x in [('b','(b) External deadline-success matrix and comparison',margin),('c','(c) Sealed eight-block dissertation contrasts',panelw+2*margin)]:
 d.text((x,y),title,font=font,fill='#16313a');canvas.paste(imgs[k],(x,y+label_h))
canvas.save(r/'traffictwin_platform_real_data.png',dpi=(300,300))
# A standalone PDF preserves raster exactly at 300 dpi.
doc=fitz.open();page=doc.new_page(width=width*72/300,height=height*72/300);page.insert_image(page.rect,filename=str(r/'traffictwin_platform_real_data.png'))
doc.set_metadata({'title':'TrafficTwin with real data','author':'S M Abdulla Al Mamun'});doc.save(r/'traffictwin_platform_real_data.pdf',deflate=True)
preview=canvas.copy();preview.thumbnail((1800,1800));preview.save(r/'figure_preview.png')
receipt={'source_branch':'feature/dissertation-results-2026-09-15','source_commit':'17d6b21c7228910a911d66879a1c6e11ae445eb2','all_three_panels_captured':True,'viewport_css':[1440,3000],'device_scale_factor':2,'embed':True,'crop_bounds_css':bounds,'dpi':300,'research_workloads_launched':0,'browser_errors':json.loads((r/'browser_errors.json').read_text()),'package_fingerprint':json.loads((r/'TOS_ADAPTER_VALIDATION.json').read_text())['package_fingerprint'],'composition_note':'Authentic screenshot crops with panel labels and explanatory legend outside screenshots; no UI content synthesised. All panels served from the pinned bridge worktree via explicit PYTHONPATH.','files':{str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [r/'capture_final.py',r/'compose_figure.py',r/'traffictwin_platform_real_data.png',r/'traffictwin_platform_real_data.pdf',r/'TOS_ADAPTER_VALIDATION.json',*[r/'shots'/f'{k}_tall.png' for k in bounds]]}}
(r/'FINAL_PLATFORM_CAPTURE_2026-09-16.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(width,height)
