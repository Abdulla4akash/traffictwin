"""Render the complete Markdown draft; never imports or executes the evaluator."""
from __future__ import annotations

import re
from html import escape
from pathlib import Path
from urllib.parse import quote

from markdown_it import MarkdownIt
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle, Preformatted,
)
from reportlab.platypus.tableofcontents import TableOfContents
from svglib.svglib import svg2rlg

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
BASELINE = '04f3b6a95c7bc06c80ed95b54762f12861bba183'
FONT_ROOT = Path('/System/Library/Fonts/Supplemental')
for name, filename in (
    ('TimesDraft', 'Times New Roman.ttf'),
    ('TimesDraft-Bold', 'Times New Roman Bold.ttf'),
    ('TimesDraft-Italic', 'Times New Roman Italic.ttf'),
    ('TimesDraft-BoldItalic', 'Times New Roman Bold Italic.ttf'),
    ('ArialDraft', 'Arial.ttf'),
    ('ArialDraft-Bold', 'Arial Bold.ttf'),
):
    pdfmetrics.registerFont(TTFont(name, str(FONT_ROOT / filename)))
pdfmetrics.registerFontFamily('TimesDraft', normal='TimesDraft', bold='TimesDraft-Bold',
                             italic='TimesDraft-Italic', boldItalic='TimesDraft-BoldItalic')
pdfmetrics.registerFontFamily('ArialDraft', normal='ArialDraft', bold='ArialDraft-Bold',
                             italic='ArialDraft', boldItalic='ArialDraft-Bold')

PAGE_W, PAGE_H = A4
MARGIN = 62
WIDTH = PAGE_W - 2 * MARGIN
INK = colors.HexColor('#182b3a')
MUTED = colors.HexColor('#52616b')
STYLES = getSampleStyleSheet()
STYLES.add(ParagraphStyle('BodyDraft', fontName='TimesDraft', fontSize=11.5, leading=15,
                         spaceAfter=7, alignment=TA_LEFT, allowWidows=0, allowOrphans=0))
STYLES.add(ParagraphStyle('ChapterDraft', fontName='ArialDraft-Bold', fontSize=17, leading=21,
                         spaceBefore=12, spaceAfter=13, textColor=INK, keepWithNext=True))
STYLES.add(ParagraphStyle('SectionDraft', fontName='ArialDraft-Bold', fontSize=12, leading=16,
                         spaceBefore=13, spaceAfter=7, textColor=INK, keepWithNext=True))
STYLES.add(ParagraphStyle('CaptionDraft', fontName='TimesDraft-Italic', fontSize=9.5, leading=12,
                         spaceBefore=4, spaceAfter=10, textColor=MUTED))
STYLES.add(ParagraphStyle('TableDraft', fontName='ArialDraft', fontSize=9, leading=12,
                         spaceBefore=0, spaceAfter=0))
STYLES.add(ParagraphStyle('TableHeadDraft', parent=STYLES['TableDraft'], fontName='ArialDraft-Bold'))
STYLES.add(ParagraphStyle('ReferenceDraft', parent=STYLES['BodyDraft'], fontSize=10, leading=13,
                         spaceAfter=9, wordWrap='LTR'))
STYLES.add(ParagraphStyle('CoverDraft', fontName='ArialDraft-Bold', fontSize=25, leading=32,
                         spaceAfter=26, textColor=INK, alignment=TA_CENTER))
STYLES.add(ParagraphStyle('MetaDraft', fontName='ArialDraft', fontSize=11, leading=17,
                         spaceAfter=10, textColor=MUTED, alignment=TA_CENTER))
STYLES.add(ParagraphStyle('CodeDraft', fontName='Courier', fontSize=8.1, leading=11,
                         spaceBefore=7, spaceAfter=12))
STYLES.add(ParagraphStyle('TOCDraft', fontName='TimesDraft', fontSize=10.5, leading=12,
                         leftIndent=0, firstLineIndent=0, spaceBefore=3, spaceAfter=0))
STYLES.add(ParagraphStyle('TOCSubDraft', parent=STYLES['TOCDraft'], fontSize=9.5,
                         leading=11, leftIndent=16, spaceBefore=0, spaceAfter=0))

def slug(text):
    return re.sub(r'[^a-z0-9 -]', '', text.lower()).replace(' ', '-')

def url_for(href):
    if href.startswith(('#', 'http')):
        return href
    p = (ROOT / href.split('#')[0]).resolve()
    if p.is_relative_to(REPO):
        relative = p.relative_to(REPO).as_posix()
        revision = 'main' if p.is_relative_to(ROOT) else BASELINE
        return f'https://github.com/Abdulla4akash/traffictwin/blob/{revision}/{quote(relative)}'
    return href

def inline(children):
    out = []
    for t in children or []:
        if t.type == 'text':
            out.append(escape(t.content).replace('—', '-').replace('–', '-'))
        elif t.type in ('softbreak', 'hardbreak'):
            out.append(' ' if t.type == 'softbreak' else '<br/>')
        elif t.type == 'strong_open': out.append('<b>')
        elif t.type == 'strong_close': out.append('</b>')
        elif t.type == 'em_open': out.append('<i>')
        elif t.type == 'em_close': out.append('</i>')
        elif t.type == 'code_inline':
            out.append('<font name="Courier" size="8.5">' + escape(t.content) + '</font>')
        elif t.type == 'link_open':
            out.append('<a color="#244967" href="' + escape(url_for(t.attrGet('href')), quote=True) + '">')
        elif t.type == 'link_close': out.append('</a>')
        elif t.type == 'html_inline':
            m = re.search(r'id="([^"]+)"', t.content)
            if m: out.append(f'<a name="{m.group(1)}"/>')
    return ''.join(out)

class DraftDoc(BaseDocTemplate):
    def __init__(self, filename):
        super().__init__(str(filename), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=60, bottomMargin=55, title='TrafficTwin: Auditable Infrastructure Scheduling',
                         author='S M Abdulla Al Mamun')
        self.addPageTemplates(PageTemplate(id='main', frames=[Frame(MARGIN,55,WIDTH,PAGE_H-115,
                                 leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],
                                 onPage=self.furniture))
    def furniture(self, canvas, doc):
        if doc.page > 1:
            canvas.saveState()
            canvas.setFont('ArialDraft', 8)
            canvas.setFillColor(MUTED)
            canvas.drawString(MARGIN, PAGE_H-34, 'TRAFFICTWIN  |  COMPLETE DISSERTATION DRAFT')
            canvas.drawRightString(PAGE_W-MARGIN, 30, str(doc.page))
            canvas.restoreState()
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and hasattr(flowable, '_toc_level'):
            text = flowable.getPlainText()
            key = slug(text)
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, flowable._toc_level, False)
            self.notify('TOCEntry', (flowable._toc_level, text, self.page, key))

def build():
    text = (ROOT/'TrafficTwin_Dissertation.md').read_text()
    tokens = MarkdownIt('commonmark').enable('table').parse(text)
    story = []
    i = 0
    backmatter = False
    cover = True
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == 'heading_open':
            title = tokens[i+1].content
            level = int(tok.tag[1])
            if level == 1:
                story += [Spacer(1,94), Paragraph(escape(title), STYLES['CoverDraft'])]
            else:
                if title == 'Abstract':
                    cover = False
                    story.append(PageBreak())
                    story.append(Paragraph('Contents', STYLES['ChapterDraft']))
                    toc = TableOfContents()
                    toc.levelStyles = [STYLES['TOCDraft'], STYLES['TOCSubDraft']]
                    story.extend([toc, PageBreak()])
                elif level == 2:
                    story.append(PageBreak())
                if title == 'References' or title.startswith('Appendix'):
                    backmatter = True
                p = Paragraph(escape(title), STYLES['ChapterDraft' if level==2 else 'SectionDraft'])
                p._toc_level = 0 if level==2 else 1
                story.append(p)
            i += 3
            continue
        if tok.type == 'html_block':
            m = re.search(r'id="([^"]+)"', tok.content)
            if m: story.append(Paragraph(f'<a name="{m.group(1)}"/>', STYLES['ReferenceDraft']))
            i += 1
            continue
        if tok.type == 'paragraph_open':
            content = tokens[i+1]
            imgs = [t for t in content.children or [] if t.type=='image']
            if imgs:
                src = (ROOT/imgs[0].attrGet('src')).resolve()
                if src.suffix=='.svg':
                    img = svg2rlg(str(src))
                    scale = WIDTH / img.width
                    img.scale(scale,scale)
                    img.width *= scale
                    img.height *= scale
                else:
                    with PILImage.open(src) as im: w,h=im.size
                    scale = min(WIDTH/w, 280/h)
                    img = Image(str(src), width=w*scale, height=h*scale)
                group = [Spacer(1,5),img]
                if i+4 < len(tokens) and tokens[i+3].type=='paragraph_open' and tokens[i+4].content.startswith('*Figure'):
                    group.append(Paragraph(inline(tokens[i+4].children), STYLES['CaptionDraft']))
                    i += 3
                story.append(KeepTogether(group))
            else:
                iscaption = content.content.startswith(('*Table', '*Figure'))
                style = 'MetaDraft' if cover else 'CaptionDraft' if iscaption else 'ReferenceDraft' if backmatter else 'BodyDraft'
                p = Paragraph(inline(content.children), STYLES[style])
                if iscaption and content.content.startswith('*Table'):
                    p.keepWithNext = True
                story.append(p)
            i += 3
            continue
        if tok.type == 'table_open':
            rows=[]; row=[]; in_header=False
            i += 1
            while tokens[i].type!='table_close':
                tt=tokens[i]
                if tt.type=='thead_open': in_header=True
                elif tt.type=='thead_close': in_header=False
                elif tt.type=='tr_open': row=[]
                elif tt.type=='inline': row.append(Paragraph(inline(tt.children),STYLES['TableHeadDraft' if in_header else 'TableDraft']))
                elif tt.type=='tr_close': rows.append(row)
                i+=1
            cols=len(rows[0])
            widths = [WIDTH*.32,WIDTH*.34,WIDTH*.34] if cols==3 else [WIDTH*.30,WIDTH*.12,WIDTH*.28,WIDTH*.30] if cols==4 else [WIDTH*.16,WIDTH*.18,WIDTH*.21,WIDTH*.18,WIDTH*.27]
            table=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf1f4')),
                ('LINEABOVE',(0,0),(-1,0),.7,INK),('LINEBELOW',(0,0),(-1,0),.5,INK),
                ('LINEBELOW',(0,-1),(-1,-1),.7,INK),
                ('LINEBELOW',(0,1),(-1,-2),.25,colors.HexColor('#cdd5db')),
                ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
                ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ]))
            story.extend([table,Spacer(1,12)])
            i += 1
            continue
        if tok.type == 'fence':
            story.append(Preformatted(tok.content.rstrip(), STYLES['CodeDraft']))
        i += 1
    output=ROOT/'TrafficTwin_Dissertation.pdf'
    DraftDoc(output).multiBuild(story)
    print(output)

if __name__=='__main__': build()
