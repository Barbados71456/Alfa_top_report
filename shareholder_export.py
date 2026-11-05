"""Download the exact month and YTD commentary visible in Svod1."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.shared import Cm, Pt, RGBColor
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate


TITLE = 'Итоги для акционеров'
FORMATS = {'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
           'pdf': 'application/pdf'}
FONTS = Path(__file__).parent / 'assets' / 'fonts'


def blocks(snapshot, edits):
    yield 'Title', TITLE
    yield 'Period', ' · '.join(('Альфа', snapshot['period'], snapshot['allocation']))
    if snapshot['partial']:
        yield 'Note', 'Месяц ещё идёт. Факт на текущую дату сравнивается с полным месяцем прогноза и прошлого года.'
    for i, card in enumerate(snapshot['cards']):
        if i and card.get('sections'):
            yield 'PageBreak', ''
        yield 'Heading', f"{card['title']} · {card['label']}"
        yield 'Headline', card['headline']
        for item in card['comparisons']:
            detail = edits.get(item['id'], item['detail'])
            yield 'Text', ' '.join(filter(None, (item['finding'], item.get('bridge'), detail, item.get('investment'))))
        for section in card.get('sections', []):
            yield 'Subheading', section['title']
            yield 'Text', section['intro']
            for para in section['paragraphs']:
                yield 'Text', (para['label'] + '. ' if para['label'] else '') + para['text']
        if card['gaps']:
            yield 'Note', 'Месяцы без данных. ' + '. '.join(f'{name} — {months}' for name, months in card['gaps']) + '.'


def word(parts):
    document = Document()
    document.core_properties.title = TITLE
    document.core_properties.author = 'Альфа'
    page = document.sections[0]
    page.page_width, page.page_height = Cm(21), Cm(29.7)
    page.left_margin = page.right_margin = Cm(1.6)
    page.top_margin = page.bottom_margin = Cm(1.5)
    styles = {'Title': ('Title', 23, True, '181818', 4),
              'Period': ('Report period', 11, False, '546572', 12),
              'Heading': ('Heading 1', 16, True, '244E59', 5),
              'Subheading': ('Heading 2', 12, True, '244E59', 4),
              'Headline': ('Report headline', 12, True, '18272C', 5),
              'Text': ('Normal', 10, False, '18272C', 4),
              'Note': ('Report note', 10, False, '546572', 6)}
    for role, (name, size, bold, color, space) in styles.items():
        style = document.styles[name] if name in document.styles else document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        style.font.name, style.font.size = 'Arial', Pt(size)
        style.font.bold, style.font.color.rgb = bold, RGBColor.from_string(color)
        fmt = style.paragraph_format
        fmt.space_before = Pt(9 if role == 'Heading' else 0)
        fmt.space_after, fmt.line_spacing = Pt(space), 1.04
        fmt.keep_with_next = role in ('Heading', 'Subheading', 'Title')
    for role, text in parts:
        if role == 'PageBreak':
            document.add_page_break()
            continue
        p = document.add_paragraph(text, style=styles[role][0])
        if role == 'Title':
            # The default Word Title style carries a decorative bottom border.
            from docx.oxml.ns import qn
            props = p.style.element.get_or_add_pPr()
            border = props.find(qn('w:pBdr'))
            if border is not None:
                props.remove(border)
    output = BytesIO()
    document.save(output)
    return output


def pdf(parts):
    for name, file in [('AlfaSans', 'DejaVuSans.ttf'), ('AlfaSansBold', 'DejaVuSans-Bold.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(FONTS / file)))
    styles = {'Title': (21, 25, True, '#181818', 0, 3), 'Period': (10, 13, False, '#546572', 0, 6),
              'Heading': (15, 18, True, '#244E59', 5, 4), 'Subheading': (12, 15, True, '#244E59', 5, 3),
              'Headline': (11, 14, True, '#18272C', 0, 4),
              'Text': (9.8, 12, False, '#18272C', 0, 3), 'Note': (9, 11.5, False, '#546572', 0, 3)}
    paragraphs = []
    for role, text in parts:
        if role == 'PageBreak':
            paragraphs.append(PageBreak())
            continue
        size, leading, bold, color, before, after = styles[role]
        style = ParagraphStyle(role, fontName='AlfaSansBold' if bold else 'AlfaSans', fontSize=size,
                               leading=leading, textColor=HexColor(color), alignment=TA_LEFT,
                               spaceBefore=before, spaceAfter=after, keepWithNext=role in ('Title', 'Heading', 'Subheading'))
        paragraphs.append(Paragraph(escape(text), style))
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, title=TITLE, author='Альфа',
                            leftMargin=16*mm, rightMargin=16*mm, topMargin=15*mm, bottomMargin=15*mm)
    doc.build(paragraphs)
    return output


def render(kind, snapshot, edits):
    parts = blocks(snapshot, edits)
    output = pdf(parts) if kind == 'pdf' else word(parts)
    output.seek(0)
    return output
