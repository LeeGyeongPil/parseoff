"""Adapters for parsers that are NOT part of parseoff's own dependencies.

Nothing from these packages is bundled; each adapter imports its parser inside the function and
only runs when the user installed it. An import failure is reported as a clear error message.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from ._common import check_pages


def _require(module: str, hint: str):
    import importlib

    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise RuntimeError(f"{module} is not installed ({hint})") from exc


def markitdown_convert(pdf_path: str, pages: list[int]) -> list[str]:
    """markitdown only returns one string per file, so each page is split out and converted alone."""
    mod = _require("markitdown", 'uv sync --extra markitdown (or pip install "parseoff[markitdown]")')
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(pdf_path)
    check_pages(pages, len(reader.pages))
    converter = mod.MarkItDown(enable_plugins=False)
    out: list[str] = []
    with tempfile.TemporaryDirectory(prefix="parseoff-") as tmp:
        for number in pages:
            writer = PdfWriter()
            writer.add_page(reader.pages[number - 1])
            single = Path(tmp) / f"page-{number}.pdf"
            with single.open("wb") as fh:
                writer.write(fh)
            out.append((converter.convert(str(single)).text_content or "").strip())
    return out


def pymupdf4llm_convert(pdf_path: str, pages: list[int]) -> list[str]:
    """pymupdf4llm (AGPL-3.0, user-installed). `page_chunks=True` returns one dict per page."""
    mod = _require("pymupdf4llm", "pip install pymupdf4llm - AGPL-3.0, check the licence terms")
    chunks = mod.to_markdown(pdf_path, pages=[p - 1 for p in pages], page_chunks=True)
    if len(chunks) != len(pages):
        raise RuntimeError(f"pymupdf4llm returned {len(chunks)} page chunk(s) for {len(pages)} page(s)")
    return [str(chunk.get("text", "")).strip() for chunk in chunks]


def docling_convert(pdf_path: str, pages: list[int]) -> list[str]:
    """docling (experimental, opt-in). Downloads models on first run unless they are present."""
    mod = _require("docling.document_converter", 'uv sync --extra docling (or pip install "parseoff[docling]")')
    converter = mod.DocumentConverter()
    document = converter.convert(pdf_path).document
    return [document.export_to_markdown(page_no=p).strip() for p in pages]
