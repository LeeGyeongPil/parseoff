"""Smallest possible custom parser for `parseoff run --custom`.

It must accept (pdf_path, page_numbers) and return one string per requested page.
"""
from pypdf import PdfReader


def to_pages(pdf_path: str, page_numbers: list[int]) -> list[str]:
    reader = PdfReader(pdf_path)
    return [(reader.pages[n - 1].extract_text() or "").upper() for n in page_numbers]
