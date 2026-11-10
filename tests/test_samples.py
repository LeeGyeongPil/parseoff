from __future__ import annotations

import hashlib
import socket
from pathlib import Path

import pytest
from pypdf import PdfReader

from parseoff.samples import PAGE_COUNTS, SAMPLE_NAMES, create_samples


def _digests(folder: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob("*.pdf"))}


def test_samples_are_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-2: byte-identical output, correct page counts, and no network use while generating."""

    def no_network(*_a, **_k):
        raise AssertionError("sample generation must not open sockets")

    monkeypatch.setattr(socket, "socket", no_network)
    first = create_samples(tmp_path / "a")
    second = create_samples(tmp_path / "b")
    assert [p.name for p in first] == sorted(SAMPLE_NAMES)
    assert _digests(tmp_path / "a") == _digests(tmp_path / "b")
    for path in second:
        assert len(PdfReader(path).pages) == PAGE_COUNTS[path.name]
    assert PAGE_COUNTS == {"report-table.pdf": 3, "two-column.pdf": 2, "scanned-like.pdf": 2}


def test_scanned_like_second_page_has_no_text(sample_dir: Path) -> None:
    reader = PdfReader(sample_dir / "scanned-like.pdf")
    assert reader.pages[0].extract_text().strip()
    assert reader.pages[1].extract_text().strip() == ""
