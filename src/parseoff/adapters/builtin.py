"""Adapters for the parsers installed together with parseoff: pypdf, pdfplumber, pdfminer.six."""

from __future__ import annotations

from ._common import check_pages


def pypdf_convert(pdf_path: str, pages: list[int]) -> list[str]:
    """Plain text in content-stream order (pypdf's default). No structure is reconstructed."""
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    check_pages(pages, len(reader.pages))
    return [(reader.pages[p - 1].extract_text() or "").strip() for p in pages]


def _gfm_table(rows: list[list[str | None]]) -> str:
    """Render extracted table rows as a GitHub-flavoured Markdown table (first row = header)."""

    def cell(value: str | None) -> str:
        return " ".join((value or "").split()).replace("|", "\\|")

    clean = [[cell(c) for c in row] for row in rows if row]
    width = max(len(r) for r in clean)
    clean = [r + [""] * (width - len(r)) for r in clean]
    lines = ["| " + " | ".join(clean[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in clean[1:]]
    return "\n".join(lines)


def pdfplumber_convert(pdf_path: str, pages: list[int]) -> list[str]:
    """Text by position, with detected tables rendered as GFM tables at their vertical position.

    Characters inside a table are removed from the running text so cell values appear once.
    """
    import pdfplumber

    out: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        check_pages(pages, len(pdf.pages))
        for number in pages:
            page = pdf.pages[number - 1]
            tables = page.find_tables()
            boxes = [t.bbox for t in tables]

            def outside(obj: dict, boxes=boxes) -> bool:
                if obj.get("object_type") != "char":
                    return True
                cx, cy = (obj["x0"] + obj["x1"]) / 2, (obj["top"] + obj["bottom"]) / 2
                return not any(x0 <= cx <= x1 and top <= cy <= bottom for x0, top, x1, bottom in boxes)

            body = page.filter(outside) if boxes else page
            blocks = [(ln["top"], ln["text"]) for ln in body.extract_text_lines(return_chars=False)]
            blocks += [(t.bbox[1], _gfm_table(t.extract())) for t in tables if t.extract()]
            out.append("\n".join(text for _, text in sorted(blocks, key=lambda b: b[0])))
    return out


def pdfminer_convert(pdf_path: str, pages: list[int]) -> list[str]:
    """Layout-box text from pdfminer.six (the engine behind markitdown's PDF path)."""
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTTextContainer
    from pypdf import PdfReader

    check_pages(pages, len(PdfReader(pdf_path).pages))
    by_page: dict[int, str] = {}
    for number, layout in zip(sorted(set(pages)), extract_pages(pdf_path, page_numbers=[p - 1 for p in sorted(set(pages))])):
        boxes = [el.get_text().strip() for el in layout if isinstance(el, LTTextContainer)]
        by_page[number] = "\n\n".join(b for b in boxes if b)
    return [by_page.get(p, "") for p in pages]
