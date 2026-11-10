"""Parser adapters.

An adapter is a function ``convert(pdf_path: str, pages: list[int]) -> list[str]`` that returns one
Markdown/plain-text string per requested page (``pages`` are 1-based). Adapters import their parser
lazily so that a missing optional parser never breaks the others.
"""

from __future__ import annotations

from collections.abc import Callable

from .builtin import pdfminer_convert, pdfplumber_convert, pypdf_convert
from .optional import docling_convert, markitdown_convert, pymupdf4llm_convert

Adapter = Callable[[str, list[int]], list[str]]

ADAPTERS: dict[str, Adapter] = {
    "pypdf": pypdf_convert,
    "pdfplumber": pdfplumber_convert,
    "pdfminer": pdfminer_convert,
    "markitdown": markitdown_convert,
    "pymupdf4llm": pymupdf4llm_convert,
    "docling": docling_convert,
}


def get_adapter(name: str) -> Adapter:
    try:
        return ADAPTERS[name]
    except KeyError:
        known = ", ".join(sorted(ADAPTERS))
        raise ValueError(f"unknown parser {name!r}; known parsers: {known}") from None
