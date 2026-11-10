"""Helpers shared by the adapters."""

from __future__ import annotations


def check_pages(pages: list[int], total: int) -> None:
    """Raise a helpful error if a requested page is outside the document."""
    bad = [p for p in pages if p < 1 or p > total]
    if bad:
        raise ValueError(f"page(s) {bad} out of range: the PDF has {total} page(s) (pages are 1-based)")
