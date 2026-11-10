"""PDF text-layer baseline and page images via pypdfium2 (BSD-3 / Apache-2.0)."""

from __future__ import annotations

from pathlib import Path


def page_count(pdf_path: Path) -> int:
    """Number of pages; raises an exception with a readable message if the PDF cannot be opened."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        return len(pdf)
    finally:
        pdf.close()


def layer_texts(pdf_path: Path, pages: list[int]) -> list[str]:
    """Text layer per requested page. An empty string means the page has no extractable text."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        out = []
        for number in pages:
            textpage = pdf[number - 1].get_textpage()
            out.append(textpage.get_text_range())
            textpage.close()
        return out
    finally:
        pdf.close()


def render_pages(pdf_path: Path, pages: list[int], out_dir: Path, prefix: str, scale: float = 1.0) -> None:
    """Write ``<prefix>-p<N>.png`` for each page (low resolution on purpose: reports stay small)."""
    import pypdfium2 as pdfium

    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        for number in pages:
            image = pdf[number - 1].render(scale=scale).to_pil()
            image.save(out_dir / f"{prefix}-p{number}.png")
    finally:
        pdf.close()
