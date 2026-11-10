"""Deterministic synthetic PDFs used by `parseoff demo`.

They are practice documents written for this tool (original English sentences, no real data).
Each one reproduces one well-known parser pitfall, so the demo shows real parsers misbehaving
on purpose-built input rather than replaying fake output:

* report-table.pdf  - a grid table plus a running header/footer on every page.
* two-column.pdf    - two text columns whose right column is drawn first in the content stream.
* scanned-like.pdf  - a text page followed by a page that holds only shapes and a raster image.

reportlab's `invariant=1` fixes creation dates and document ids, so the bytes are reproducible.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

SAMPLE_NAMES = ("report-table.pdf", "two-column.pdf", "scanned-like.pdf")
PAGE_COUNTS = {"report-table.pdf": 3, "two-column.pdf": 2, "scanned-like.pdf": 2}

_W, _H = A4
_LEFT = 56
_BODY = "Helvetica"

_PARAGRAPH = (
    "This practice document was written for the parseoff demo. It contains plain English "
    "sentences so that every parser has something to read, and a few structures that "
    "parsers handle differently from one another."
)
_NOTES = (
    "Section notes follow here. Parsers that read the content stream in drawing order, "
    "parsers that sort text by position and parsers that build layout boxes can disagree "
    "about the order of the same words."
)


def _canvas(path: Path) -> Canvas:
    # invariant=1 -> no timestamps or random ids in the file, so the bytes are reproducible
    return Canvas(str(path), pagesize=A4, invariant=1, pageCompression=0)


def _lines(c: Canvas, x: float, y: float, text: str, width: int = 88, size: int = 10) -> float:
    """Draw wrapped text from (x, y) downwards; return the next free y."""
    c.setFont(_BODY, size)
    for line in textwrap.wrap(text, width=width):
        c.drawString(x, y, line)
        y -= size + 4
    return y


def _frame(c: Canvas, page: int, total: int) -> None:
    """Running header and page-number footer, identical on every page (boilerplate lesson)."""
    c.setFont(_BODY, 9)
    c.drawString(_LEFT, _H - 36, "ACME Handbook - draft")
    c.drawString(_LEFT, 30, f"Page {page} of {total}")


def _report_table(path: Path) -> None:
    c = _canvas(path)
    total = 3
    # page 1: title, headings, paragraph, a 3 x 4 grid table
    _frame(c, 1, total)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(_LEFT, _H - 90, "Quarterly Report")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(_LEFT, _H - 125, "1. Overview")
    y = _lines(c, _LEFT, _H - 145, _PARAGRAPH)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(_LEFT, y - 16, "2. Numbers")
    rows = [
        ["Region", "Q1", "Q2"],
        ["North", "120", "135"],
        ["South", "98", "101"],
        ["East", "77", "90"],
    ]
    col_w, row_h, top = 110, 24, y - 40
    c.setLineWidth(0.8)
    for r, row in enumerate(rows):
        for k, cell in enumerate(row):
            x = _LEFT + k * col_w
            c.rect(x, top - (r + 1) * row_h, col_w, row_h)  # grid lines -> a ruled table
            c.setFont(_BODY, 10)
            c.drawString(x + 8, top - (r + 1) * row_h + 8, cell)
    c.showPage()
    # pages 2 and 3: a heading and a paragraph each
    for page, heading in ((2, "3. Method"), (3, "4. Notes")):
        _frame(c, page, total)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(_LEFT, _H - 90, heading)
        _lines(c, _LEFT, _H - 112, _NOTES if page == 3 else _PARAGRAPH + " " + _NOTES)
        c.showPage()
    c.save()


_WORDS = (
    "river stone lantern copper meadow signal harbor velvet orchid timber anchor ember "
    "falcon quartz willow marble thistle cobalt saffron juniper pebble zephyr mosaic"
).split()


def _column_line(tag: str, i: int) -> str:
    # three distinct words per line so reordering is visible to a word-order comparison
    w = [_WORDS[(i * 3 + k) % len(_WORDS)] for k in range(3)]
    return f"{tag}{i:02d} {w[0]} {w[1]} {w[2]}"


def _two_column(path: Path) -> None:
    c = _canvas(path)
    left_x, right_x, top, step = _LEFT, 320, _H - 100, 18
    c.setFont("Helvetica-Bold", 14)
    # page 1: two columns; the RIGHT column is drawn first, so stream order is R01..R12, L01..L12
    for tag, x in (("R", right_x), ("L", left_x)):
        c.setFont(_BODY, 10)
        for i in range(1, 13):
            c.drawString(x, top - (i - 1) * step, _column_line(tag, i))
    c.showPage()
    # page 2: an ordinary single column, where every parser should agree
    c.setFont("Helvetica-Bold", 14)
    c.drawString(_LEFT, _H - 90, "Single column page")
    _lines(c, _LEFT, _H - 112, (_PARAGRAPH + " " + _NOTES) * 2)
    c.showPage()
    c.save()


def _scanned_like(path: Path) -> None:
    c = _canvas(path)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(_LEFT, _H - 90, "Scanned appendix")
    _lines(c, _LEFT, _H - 112, "This first page has a real text layer. " + _PARAGRAPH)
    c.showPage()
    # page 2: no text at all - a raster image of a "scan" and some shapes
    img = Image.new("L", (160, 220), 255)
    pix = img.load()
    assert pix is not None
    for yy in range(220):
        for xx in range(160):
            if (yy // 20) % 2 == 0 and 12 < xx < 148:  # horizontal "text bars"
                pix[xx, yy] = 40 if (xx // 6 + yy // 4) % 3 else 140
    c.drawImage(ImageReader(img), _LEFT, _H - 330, width=320, height=440)
    c.rect(_LEFT - 8, _H - 340, 340, 460)
    c.showPage()
    c.save()


def create_samples(out_dir: Path) -> list[Path]:
    """Write the three sample PDFs into `out_dir` and return their paths (sorted by name)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    builders = {
        "report-table.pdf": _report_table,
        "two-column.pdf": _two_column,
        "scanned-like.pdf": _scanned_like,
    }
    paths = []
    for name in SAMPLE_NAMES:
        path = out_dir / name
        builders[name](path)
        paths.append(path)
    return sorted(paths)
