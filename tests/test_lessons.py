"""The three lessons the demo is built to show, checked on real parser output."""

from __future__ import annotations


def _doc(summary: dict, doc_id: str) -> dict:
    return next(d for d in summary["documents"] if d["id"] == doc_id)


def _findings(summary: dict, code: str, **where) -> list[dict]:
    return [f for f in summary["findings"] if f["code"] == code and all(f.get(k) == v for k, v in where.items())]


def test_table_structure_kept_only_by_pdfplumber(demo_summary: dict) -> None:
    """AC-3: high coverage everywhere, but only pdfplumber keeps the table; headers repeat."""
    doc = _doc(demo_summary, "report-table.pdf")
    page1 = {name: info["pages"][0] for name, info in doc["parsers"].items()}
    assert page1["pdfplumber"]["tables"] >= 1
    assert page1["pypdf"]["tables"] == 0
    assert page1["pdfminer"]["tables"] == 0
    assert all(p["coverage"] >= 0.9 for p in page1.values())  # coverage alone misses the loss
    assert _findings(demo_summary, "NO_STRUCTURE", doc="report-table.pdf", parser="pypdf")
    assert _findings(demo_summary, "BOILERPLATE", doc="report-table.pdf")


def test_two_column_page_flags_low_agreement(demo_summary: dict) -> None:
    """AC-4: the two-column page splits the parsers; the single-column page does not."""
    agreement = _doc(demo_summary, "two-column.pdf")["agreement"]
    page1 = [pair["pages"]["1"] for pair in agreement.values()]
    page2 = [pair["pages"]["2"] for pair in agreement.values()]
    assert min(page1) < 0.6
    assert min(page2) >= 0.9
    assert _findings(demo_summary, "LOW_AGREEMENT", doc="two-column.pdf", page=1)
    assert not _findings(demo_summary, "LOW_AGREEMENT", doc="two-column.pdf", page=2)


def test_image_only_page_flags_empty_text_layer(demo_summary: dict) -> None:
    """AC-5: no text layer is a finding about the page, not a parser error, and coverage is null."""
    doc = _doc(demo_summary, "scanned-like.pdf")
    assert doc["text_layer_chars"][1] == 0
    for info in doc["parsers"].values():
        assert info["status"] == "ok"
        assert info["pages"][1]["coverage"] is None
        assert info["pages"][1]["chars"] == 0
    empty = _findings(demo_summary, "EMPTY_TEXT_LAYER")
    assert len(empty) == 1 and empty[0]["level"] == "FAIL"
    assert empty[0]["doc"] == "scanned-like.pdf" and empty[0]["page"] == 2
    assert not _findings(demo_summary, "LOW_COVERAGE")
