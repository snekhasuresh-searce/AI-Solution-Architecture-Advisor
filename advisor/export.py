"""Export a recommendation (Markdown from report.py) to DOCX and PDF.

The report uses a small, fixed Markdown subset - headings, paragraphs, bullets,
pipe tables, block quotes, rules and **bold** / *italic* / `code` - so it is
parsed here directly instead of pulling in a full Markdown engine.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path


# ----------------------------------------------------------------- parsing
@dataclass
class Block:
    kind: str  # heading | para | bullets | table | quote | rule
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
def to_docx(markdown: str) -> bytes:
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.shared import Inches, Pt, RGBColor

    doc = Document()
    for section in doc.sections:
        section.left_margin = section.right_margin = Inches(0.7)
        section.top_margin = section.bottom_margin = Inches(0.7)
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    doc.core_properties.title = title_of(markdown)

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
            add_runs(doc.add_heading(level=min(block.level, 4) if block.level > 1 else 0), block.text)
        elif block.kind == "para":
            add_runs(doc.add_paragraph(), block.text)
        elif block.kind == "bullets":
            for item in block.items:
                add_runs(doc.add_paragraph(style="List Bullet"), item)
        elif block.kind == "quote":
            add_runs(doc.add_paragraph(style="Intense Quote"), block.text)
        elif block.kind == "rule":
            p = doc.add_paragraph()
            p.add_run("_" * 60).font.color.rgb = RGBColor(0xBB, 0xBB, 0xBB)
        elif block.kind == "table":
            width = max(len(r) for r in block.rows)
            table = doc.add_table(rows=0, cols=width)
            table.style = "Light Grid Accent 1"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            for r, row in enumerate(block.rows):
                cells = table.add_row().cells
                for c in range(width):
                    para = cells[c].paragraphs[0]
                    add_runs(para, row[c] if c < len(row) else "", size=Pt(9), bold=r == 0)
            doc.add_paragraph()

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


def to_pdf(markdown: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer,
                                    Table, TableStyle)

    regular, bold, uni = _fonts()
    ink, muted, accent, line = (colors.HexColor(c) for c in ("#1f2328", "#59636e", "#1f5fbf", "#d0d7de"))
    base = ParagraphStyle("base", fontName=regular, fontSize=10, leading=14, textColor=ink, alignment=TA_LEFT)
    heading = ParagraphStyle("heading", parent=base, keepWithNext=1)  # never strand a heading at a page end
    styles = {
        1: ParagraphStyle("h1", parent=heading, fontName=bold, fontSize=20, leading=25, spaceAfter=8),
        2: ParagraphStyle("h2", parent=heading, fontName=bold, fontSize=14, leading=18, textColor=accent,
                          spaceBefore=12, spaceAfter=6),
        3: ParagraphStyle("h3", parent=heading, fontName=bold, fontSize=11.5, leading=15, spaceBefore=8, spaceAfter=4),
    }
    para = ParagraphStyle("p", parent=base, spaceAfter=6)
    quote = ParagraphStyle("q", parent=base, textColor=muted, leftIndent=10, borderPadding=(4, 6, 4, 6),
                           backColor=colors.HexColor("#f6f8fa"), spaceAfter=6)
    cell = ParagraphStyle("cell", parent=base, fontSize=8, leading=10.5)
    head = ParagraphStyle("head", parent=cell, fontName=bold)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title=title_of(markdown))
    story = []
    for block in parse(markdown):
        if block.kind == "heading":
            story.append(Paragraph(_markup(block.text, uni), styles.get(block.level, styles[3])))
        elif block.kind == "para":
            story.append(Paragraph(_markup(block.text, uni), para))
        elif block.kind == "quote":
            story.append(Paragraph(_markup(block.text, uni), quote))
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
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf1fb")),
                ("GRID", (0, 0), (-1, -1), 0.5, line),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story += [table, Spacer(1, 8)]

    def footer(canvas, _doc) -> None:
        canvas.saveState()
        canvas.setFont(regular, 8)
        canvas.setFillColor(muted)
        canvas.drawString(16 * mm, 9 * mm, "AI Solution Architecture Advisor")
        canvas.drawRightString(A4[0] - 16 * mm, 9 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


EXPORTERS = {
    "docx": (to_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "pdf": (to_pdf, "application/pdf"),
}
