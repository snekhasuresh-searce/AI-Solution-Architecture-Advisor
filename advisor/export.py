"""Export a recommendation (Markdown from report.py) to DOCX and PDF.

The report uses a small, fixed Markdown subset - headings, paragraphs, bullets,
pipe tables, block quotes, rules and **bold** / *italic* / `code` - so it is
parsed here directly instead of pulling in a full Markdown engine. An image
line (`![alt](src)`) marks where the architecture diagram goes; it is drawn
from the run's architecture JSON (vector in PDF, PNG in DOCX) on its own
landscape page.
"""

from __future__ import annotations

import io
import re
from datetime import date
from dataclasses import dataclass, field
from pathlib import Path


# ------------------------------------------------------------------ branding
LOGO = Path(__file__).parent / "assets" / "searce_logo.png"
NAVY, ACCENT, BAND, RULE = "1F2A44", "1F5FBF", "F3F6FB", "D0D7DE"


def _logo_aspect() -> float:
    """Width / height of the logo, read from the PNG header (no imaging library needed)."""
    import struct

    with LOGO.open("rb") as f:
        head = f.read(24)
    w, h = struct.unpack(">II", head[16:24])
    return w / h


# ----------------------------------------------------------------- parsing
@dataclass
class Block:
    kind: str  # heading | para | bullets | table | quote | rule | image
    text: str = ""
    level: int = 0
    items: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)  # first row is the header


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse(markdown: str) -> list[Block]:
    blocks: list[Block] = []
    para: list[str] = []

    def flush() -> None:
        if para:
            # A trailing double space is a Markdown line break.
            blocks.append(Block("para", text="\n".join(p.rstrip() for p in para)))
            para.clear()

    for raw in markdown.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if m := re.match(r"^(#{1,6})\s+(.*)$", stripped):
            flush()
            blocks.append(Block("heading", text=m.group(2), level=len(m.group(1))))
        elif m := re.fullmatch(r"!\[([^\]]*)\]\([^)]*\)", stripped):
            flush()
            blocks.append(Block("image", text=m.group(1)))
        elif re.fullmatch(r"-{3,}|\*{3,}", stripped):
            flush()
            blocks.append(Block("rule"))
        elif stripped.startswith("|"):
            flush()
            if re.fullmatch(r"\|?(\s*:?-{3,}:?\s*\|)+\s*:?-*:?\s*\|?", stripped):
                continue  # header separator
            if blocks and blocks[-1].kind == "table":
                blocks[-1].rows.append(_cells(stripped))
            else:
                blocks.append(Block("table", rows=[_cells(stripped)]))
        elif m := re.match(r"^[-*]\s+(.*)$", stripped):
            flush()
            if blocks and blocks[-1].kind == "bullets":
                blocks[-1].items.append(m.group(1))
            else:
                blocks.append(Block("bullets", items=[m.group(1)]))
        elif stripped.startswith(">"):
            flush()
            blocks.append(Block("quote", text=stripped.lstrip("> ").strip()))
        else:
            para.append(line)
    flush()
    return blocks


# Bold, code, then italics; underscores only at word edges so snake_case survives.
_INLINE = re.compile(
    r"\*\*(?P<b>.+?)\*\*"
    r"|`(?P<c>[^`]+)`"
    r"|(?<![\w*])\*(?P<i1>[^*\s](?:[^*]*?[^*\s])?)\*(?![\w*])"
    r"|(?<![\w])_(?P<i2>[^_\s](?:[^_]*?[^_\s])?)_(?![\w])"
)


def inline_runs(text: str) -> list[tuple[str, str]]:
    """Split text into (style, text) runs, style in {'', 'b', 'i', 'c'}."""
    runs: list[tuple[str, str]] = []
    pos = 0
    for m in _INLINE.finditer(text):
        if m.start() > pos:
            runs.append(("", text[pos:m.start()]))
        if m.group("b") is not None:
            runs.append(("b", m.group("b")))
        elif m.group("c") is not None:
            runs.append(("c", m.group("c")))
        else:
            runs.append(("i", m.group("i1") or m.group("i2")))
        pos = m.end()
    if pos < len(text):
        runs.append(("", text[pos:]))
    return runs


def title_of(markdown: str) -> str:
    m = re.search(r"^#\s+(.+)$", markdown, re.M)
    return m.group(1).strip() if m else "Solution recommendation"


# -------------------------------------------------------------------- DOCX
def to_docx(markdown: str, architecture: dict | None = None) -> bytes:
    from docx import Document
    from docx.enum.section import WD_ORIENT, WD_SECTION
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.shared import Inches, Pt, RGBColor

    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    doc = Document()
    for section in doc.sections:
        section.left_margin = section.right_margin = Inches(0.8)
        section.top_margin, section.bottom_margin = Inches(0.9), Inches(0.8)
        section.header_distance = section.footer_distance = Inches(0.35)
    styles = doc.styles
    styles["Normal"].font.name = "Calibri"
    styles["Normal"].font.size = Pt(10.5)
    styles["Normal"].paragraph_format.space_after = Pt(6)
    styles["Normal"].paragraph_format.line_spacing = 1.1
    for name, size, color, before in (("Title", 24, NAVY, 0), ("Heading 1", 16, ACCENT, 16),
                                      ("Heading 2", 13, ACCENT, 12), ("Heading 3", 11.5, NAVY, 10),
                                      ("Heading 4", 10.5, NAVY, 8)):
        st = styles[name]
        st.font.name, st.font.size, st.font.bold = "Calibri", Pt(size), True
        st.font.color.rgb = RGBColor.from_string(color)
        st.paragraph_format.space_before, st.paragraph_format.space_after = Pt(before), Pt(6)
        st.paragraph_format.keep_with_next = True
        rpr = st.element.get_or_add_rPr()  # theme fonts would otherwise override the font name
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is not None:
            for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
                fonts.attrib.pop(qn(attr), None)
    doc.core_properties.title = title_of(markdown)
    doc.core_properties.author = "Searce"

    def border(paragraph, edge: str, color: str = RULE, size: str = "6") -> None:
        ppr = paragraph._p.get_or_add_pPr()
        bdr = OxmlElement("w:pBdr")
        side = OxmlElement(f"w:{edge}")
        for k, v in (("val", "single"), ("sz", size), ("space", "4"), ("color", color)):
            side.set(qn(f"w:{k}"), v)
        bdr.append(side)
        ppr.append(bdr)

    def field_run(paragraph, code: str) -> None:
        run = paragraph.add_run()
        run.font.size, run.font.color.rgb = Pt(8.5), RGBColor(0x59, 0x63, 0x6E)
        for kind, text in (("begin", None), (None, code), ("end", None)):
            if kind:
                el = OxmlElement("w:fldChar")
                el.set(qn("w:fldCharType"), kind)
            else:
                el = OxmlElement("w:instrText")
                el.set(qn("xml:space"), "preserve")
                el.text = text
            run._r.append(el)

    def brand_section(section) -> None:
        """Logo + product name in the header, document title and page number in the footer."""
        width = section.page_width - section.left_margin - section.right_margin
        head = section.header.paragraphs[0]
        head.text = ""
        head.paragraph_format.tab_stops.add_tab_stop(width, WD_TAB_ALIGNMENT.RIGHT)
        height = Inches(0.42)
        head.add_run().add_picture(str(LOGO), height=height)
        border(head, "bottom")
        foot = section.footer.paragraphs[0]
        foot.text = ""
        foot.paragraph_format.tab_stops.add_tab_stop(width, WD_TAB_ALIGNMENT.RIGHT)
        border(foot, "top", ACCENT, "36")  # thick blue bar
        foot.paragraph_format.space_after = Pt(0)
        grey = RGBColor(0x59, 0x63, 0x6E)
        r = foot.add_run(f"{title_of(markdown)}\t{date.today():%d-%b-%Y}")
        r.font.size, r.font.color.rgb = Pt(9), grey
        second = section.footer.add_paragraph()
        second.paragraph_format.tab_stops.add_tab_stop(width, WD_TAB_ALIGNMENT.RIGHT)
        r = second.add_run("Confidential\tPage ")
        r.font.size, r.font.color.rgb = Pt(9), grey
        field_run(second, "PAGE")
        r = second.add_run(" of ")
        r.font.size, r.font.color.rgb = Pt(9), grey
        field_run(second, "NUMPAGES")

    def shade(cell, fill: str) -> None:
        tcpr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        for k, v in (("val", "clear"), ("color", "auto"), ("fill", fill)):
            shd.set(qn(f"w:{k}"), v)
        tcpr.append(shd)

    def style_table(table, widths_in: float) -> None:
        tblpr = table._tbl.tblPr
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            el = OxmlElement(f"w:{edge}")
            for k, v in (("val", "single"), ("sz", "4"), ("space", "0"), ("color", RULE)):
                el.set(qn(f"w:{k}"), v)
            borders.append(el)
        tblpr.append(borders)
        margins = OxmlElement("w:tblCellMar")
        for edge, w in (("top", 60), ("left", 100), ("bottom", 60), ("right", 100)):
            el = OxmlElement(f"w:{edge}")
            el.set(qn("w:w"), str(w))
            el.set(qn("w:type"), "dxa")
            margins.append(el)
        tblpr.append(margins)
        table.autofit = False

    brand_section(doc.sections[0])

    def add_runs(paragraph, text: str, size: Pt | None = None, bold: bool = False) -> None:
        for i, line in enumerate(text.split("\n")):
            if i:
                paragraph.add_run().add_break()
            for style, chunk in inline_runs(line):
                run = paragraph.add_run(chunk)
                run.bold = bold or style == "b"
                run.italic = style == "i"
                if style == "c":
                    run.font.name = "Consolas"
                if size:
                    run.font.size = size

    for block in parse(markdown):
        if block.kind == "heading":
            heading = doc.add_heading(level=min(block.level, 4) if block.level > 1 else 0)
            add_runs(heading, block.text)
            if block.level == 1:
                border(heading, "bottom", ACCENT)
        elif block.kind == "para":
            add_runs(doc.add_paragraph(), block.text)
        elif block.kind == "bullets":
            for item in block.items:
                add_runs(doc.add_paragraph(style="List Bullet"), item)
        elif block.kind == "quote":
            add_runs(doc.add_paragraph(style="Intense Quote"), block.text)
        elif block.kind == "image":
            if not architecture:
                add_runs(doc.add_paragraph(), f"[{block.text}: not available for this run]")
                continue
            from .diagram import to_png

            # The diagram gets its own landscape section, then portrait resumes.
            portrait = doc.sections[-1]
            land = doc.add_section(WD_SECTION.NEW_PAGE)
            land.orientation = WD_ORIENT.LANDSCAPE
            land.page_width, land.page_height = portrait.page_height, portrait.page_width
            add_runs(doc.add_paragraph(), block.text, bold=True)
            usable = land.page_width - land.left_margin - land.right_margin
            doc.add_picture(io.BytesIO(to_png(architecture)), width=usable)
            back = doc.add_section(WD_SECTION.NEW_PAGE)
            back.orientation = WD_ORIENT.PORTRAIT
            back.page_width, back.page_height = portrait.page_width, portrait.page_height
        elif block.kind == "rule":
            p = doc.add_paragraph()
            p.add_run("_" * 60).font.color.rgb = RGBColor(0xBB, 0xBB, 0xBB)
        elif block.kind == "table":
            width = max(len(r) for r in block.rows)
            table = doc.add_table(rows=0, cols=width)
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            sec = doc.sections[-1]
            usable = sec.page_width - sec.left_margin - sec.right_margin
            style_table(table, usable)
            lengths = [max(min(len(r[c]) if c < len(r) else 0, 80) for r in block.rows) + 6 for c in range(width)]
            for r, row in enumerate(block.rows):
                tr = table.add_row()
                trpr = tr._tr.get_or_add_trPr()
                trpr.append(OxmlElement("w:cantSplit"))
                if r == 0:
                    trpr.append(OxmlElement("w:tblHeader"))  # repeat header on each page
                for c in range(width):
                    cell = tr.cells[c]
                    cell.width = int(usable * lengths[c] / sum(lengths))
                    para = cell.paragraphs[0]
                    para.paragraph_format.space_after = Pt(0)
                    add_runs(para, row[c] if c < len(row) else "", size=Pt(9), bold=r == 0)
                    if r == 0:
                        shade(cell, NAVY)
                        for run in para.runs:
                            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                    elif r % 2 == 0:
                        shade(cell, BAND)
            spacer = doc.add_paragraph()
            spacer.paragraph_format.space_after = Pt(4)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# --------------------------------------------------------------------- PDF
# Fonts with wide Unicode coverage (arrows, dashes, accents); first found wins.
_FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
]
_ASCII = {"→": "->", "←": "<-", "≤": "<=", "≥": ">=", "✓": "v", "✔": "v", "✗": "x", "≈": "~",
          "█": "#", "░": "."}
_font_cache: tuple[str, str, bool] | None = None


def _fonts() -> tuple[str, str, bool]:
    """(regular, bold, unicode) font names for reportlab."""
    global _font_cache
    if _font_cache:
        return _font_cache
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    _font_cache = ("Helvetica", "Helvetica-Bold", False)
    for regular, bold in _FONT_CANDIDATES:
        if Path(regular).exists() and Path(bold).exists():
            try:
                pdfmetrics.registerFont(TTFont("Report", regular))
                pdfmetrics.registerFont(TTFont("Report-Bold", bold))
            except Exception:  # noqa: BLE001 - unreadable font file, try the next one
                continue
            for b, i, name in ((0, 0, "Report"), (1, 0, "Report-Bold"), (0, 1, "Report"), (1, 1, "Report-Bold")):
                addMapping("Report", b, i, name)
            _font_cache = ("Report", "Report-Bold", True)
            break
    return _font_cache


def _markup(text: str, unicode_font: bool) -> str:
    """Inline Markdown -> reportlab paragraph markup (escaped)."""
    from xml.sax.saxutils import escape

    if not unicode_font:
        for k, v in _ASCII.items():
            text = text.replace(k, v)
    out = []
    for i, line in enumerate(text.split("\n")):
        if i:
            out.append("<br/>")
        for style, chunk in inline_runs(line):
            chunk = escape(chunk)
            out.append({"b": f"<b>{chunk}</b>", "i": f"<i>{chunk}</i>",
                        "c": f'<font face="Courier">{chunk}</font>'}.get(style, chunk))
    return "".join(out)


def _col_widths(rows: list[list[str]], total: float, char_w: float = 5.0) -> list[float]:
    """Share the width by text length; each column is at least as wide as its
    longest word, so words never break mid-way."""
    n = max(len(r) for r in rows)
    col = [[r[c] if c < len(r) else "" for r in rows] for c in range(n)]
    lengths = [max(min(len(t), 120) for t in texts) + 8 for texts in col]
    floors = [max((len(w) for t in texts for w in t.split()), default=1) * char_w + 8 for texts in col]
    widths = [total * x / sum(lengths) for x in lengths]
    for _ in range(n):  # lift narrow columns to their floor, take the space from the others
        short = [i for i in range(n) if widths[i] < floors[i]]
        if not short:
            break
        need = sum(floors[i] - widths[i] for i in short)
        rest = [i for i in range(n) if i not in short]
        spare = sum(widths[i] for i in rest)
        for i in short:
            widths[i] = floors[i]
        for i in rest:
            widths[i] -= need * widths[i] / spare if spare else 0
    return widths


def to_pdf(markdown: str, architecture: dict | None = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, ListFlowable, ListItem, NextPageTemplate,
                                    PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle)

    regular, bold, uni = _fonts()
    ink, muted, accent, line = (colors.HexColor(c) for c in ("#1f2328", "#59636e", "#1f5fbf", "#d0d7de"))
    base = ParagraphStyle("base", fontName=regular, fontSize=10, leading=14, textColor=ink, alignment=TA_LEFT)
    heading = ParagraphStyle("heading", parent=base, keepWithNext=1)  # never strand a heading at a page end
    styles = {
        1: ParagraphStyle("h1", parent=heading, fontName=bold, fontSize=22, leading=27, spaceAfter=10,
                          textColor=colors.HexColor("#" + NAVY)),
        2: ParagraphStyle("h2", parent=heading, fontName=bold, fontSize=14, leading=18, textColor=accent,
                          spaceBefore=12, spaceAfter=6),
        3: ParagraphStyle("h3", parent=heading, fontName=bold, fontSize=11.5, leading=15, spaceBefore=8, spaceAfter=4,
                          textColor=colors.HexColor("#" + NAVY)),
    }
    para = ParagraphStyle("p", parent=base, spaceAfter=6)
    quote = ParagraphStyle("q", parent=base, textColor=muted, leftIndent=10, borderPadding=(4, 6, 4, 6),
                           backColor=colors.HexColor("#f6f8fa"), spaceAfter=6)
    cell = ParagraphStyle("cell", parent=base, fontSize=8, leading=10.5)
    head = ParagraphStyle("head", parent=cell, fontName=bold, textColor=colors.white)

    margin = 16 * mm
    top = 26 * mm  # room for the logo header
    bottom = 22 * mm
    title = title_of(markdown)
    logo_h = 11 * mm

    def page_frame(canvas, _doc) -> None:
        w, h = canvas._pagesize
        canvas.saveState()
        canvas.drawImage(str(LOGO), margin, h - 8 * mm - logo_h, width=logo_h * _logo_aspect(), height=logo_h,
                         mask="auto")
        canvas.setStrokeColor(line)
        canvas.setLineWidth(0.6)
        canvas.line(margin, h - 8 * mm - logo_h - 3 * mm, w - margin, h - 8 * mm - logo_h - 3 * mm)
        canvas.setFillColor(accent)  # thick blue bar above the footer text
        canvas.rect(margin, 17 * mm, w - 2 * margin, 1.6 * mm, stroke=0, fill=1)
        canvas.setFillColor(muted)
        canvas.setFont(regular, 8.5)
        canvas.drawString(margin, 11.5 * mm, title[:90])
        canvas.drawRightString(w - margin, 11.5 * mm, f"{date.today():%d-%b-%Y}")
        canvas.drawString(margin, 6.5 * mm, "Confidential")
        canvas.drawRightString(w - margin, 6.5 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    footer = page_frame
    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=margin, rightMargin=margin, topMargin=top,
                          bottomMargin=bottom, title=title, author="Searce")
    land = landscape(A4)
    doc.addPageTemplates([
        PageTemplate("portrait", [Frame(margin, bottom, A4[0] - 2 * margin, A4[1] - top - bottom, id="p")],
                     onPage=footer, pagesize=A4),
        PageTemplate("landscape", [Frame(margin, bottom, land[0] - 2 * margin, land[1] - top - bottom, id="l")],
                     onPage=footer, pagesize=land),
    ])
    story = []
    for block in parse(markdown):
        if block.kind == "heading":
            story.append(Paragraph(_markup(block.text, uni), styles.get(block.level, styles[3])))
        elif block.kind == "para":
            story.append(Paragraph(_markup(block.text, uni), para))
        elif block.kind == "quote":
            story.append(Paragraph(_markup(block.text, uni), quote))
        elif block.kind == "image":
            if not architecture:
                story.append(Paragraph(_markup(f"[{block.text}: not available for this run]", uni), quote))
                continue
            from .diagram import to_drawing

            box_w, box_h = land[0] - 2 * margin - 12, land[1] - top - bottom - 40
            story += [NextPageTemplate("landscape"), PageBreak(),
                      Paragraph(_markup(block.text, uni), styles[3]),
                      to_drawing(architecture, box_w, box_h),
                      NextPageTemplate("portrait"), PageBreak()]
        elif block.kind == "rule":
            story.append(HRFlowable(width="100%", color=line, spaceBefore=6, spaceAfter=6))
        elif block.kind == "bullets":
            story.append(ListFlowable(
                [ListItem(Paragraph(_markup(i, uni), para), leftIndent=12) for i in block.items],
                bulletType="bullet", start="•", leftIndent=12, bulletFontName=regular))
        elif block.kind == "table":
            width = max(len(r) for r in block.rows)
            rows = [[Paragraph(_markup(r[c] if c < len(r) else "", uni), head if i == 0 else cell)
                     for c in range(width)] for i, r in enumerate(block.rows)]
            table = Table(rows, colWidths=_col_widths(block.rows, doc.width), repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#" + NAVY)),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#" + BAND)]),
                ("BOX", (0, 0), (-1, -1), 0.6, line),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, line),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story += [table, Spacer(1, 8)]

    while story and isinstance(story[-1], Spacer):  # a trailing spacer can spill onto a blank page
        story.pop()
    doc.build(story)
    return buf.getvalue()


EXPORTERS = {
    "docx": (to_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "pdf": (to_pdf, "application/pdf"),
}
