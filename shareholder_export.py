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
from reportlab.platypus import Paragraph, SimpleDocTemplate


TITLE = 'Итоги для акционеров'
FORMATS = {'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
           'pdf': 'application/pdf'}
FONTS = Path(__file__).parent / 'assets' / 'fonts'


def blocks(snapshot, edits):
    yield 'Title', TITLE
    yield 'Period', ' · '.join(('Альфа', snapshot['period'], snapshot['allocation']))
    if snapshot['partial']:
        yield 'Note', 'Месяц ещё идёт. Факт на текущую дату сравнивается с полным месяцем прогноза и прошлого года.'
    for card in snapshot['cards']:
        yield 'Heading', f"{card['title']} · {card['label']}"
        yield 'Headline', card['headline']
        for item in card['comparisons']:
            detail = edits.get(item['id'], item['detail'])
            yield 'Text', ' '.join(filter(None, (item['finding'], detail)))
        if card['gaps']:
            yield 'Note', 'Месяцы без данных. ' + '. '.join(f'{name} — {months}' for name, months in card['gaps']) + '.'


def word(parts):
    document = Document()
    document.core_properties.title = TITLE
    document.core_properties.author = 'Альфа'
    page = document.sections[0]
    page.page_width, page.page_height = Cm(21), Cm(29.7)
    page.left_margin = page.right_margin = Cm(2)
    page.top_margin = page.bottom_margin = Cm(1.8)
    styles = {'Title': ('Title', 23, True, '181818', 4),
              'Period': ('Report period', 11, False, '546572', 12),
              'Heading': ('Heading 1', 16, True, '244E59', 5),
              'Headline': ('Report headline', 12, True, '18272C', 5),
              'Text': ('Normal', 11, False, '18272C', 6),
              'Note': ('Report note', 10, False, '546572', 6)}
    for role, (name, size, bold, color, space) in styles.items():
        style = document.styles[name] if name in document.styles else document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        style.font.name, style.font.size = 'Arial', Pt(size)
        style.font.bold, style.font.color.rgb = bold, RGBColor.from_string(color)
        fmt = style.paragraph_format
        fmt.space_before = Pt(9 if role == 'Heading' else 0)
        fmt.space_after, fmt.line_spacing = Pt(space), 1.15
        fmt.keep_with_next = role in ('Heading', 'Title')
    for role, text in parts:
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
    styles = {'Title': (22, 28, True, '#181818', 0, 4), 'Period': (10, 14, False, '#546572', 0, 11),
              'Heading': (15, 20, True, '#244E59', 9, 5), 'Headline': (11, 16, True, '#18272C', 0, 5),
              'Text': (10.5, 15, False, '#18272C', 0, 6), 'Note': (9, 13, False, '#546572', 0, 6)}
    paragraphs = []
    for role, text in parts:
        size, leading, bold, color, before, after = styles[role]
        style = ParagraphStyle(role, fontName='AlfaSansBold' if bold else 'AlfaSans', fontSize=size,
                               leading=leading, textColor=HexColor(color), alignment=TA_LEFT,
                               spaceBefore=before, spaceAfter=after, keepWithNext=role in ('Title', 'Heading'))
        paragraphs.append(Paragraph(escape(text), style))
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, title=TITLE, author='Альфа',
                            leftMargin=19*mm, rightMargin=19*mm, topMargin=17*mm, bottomMargin=17*mm)
    doc.build(paragraphs)
    return output


def render(kind, snapshot, edits):
    parts = blocks(snapshot, edits)
    output = pdf(parts) if kind == 'pdf' else word(parts)
    output.seek(0)
    return output
