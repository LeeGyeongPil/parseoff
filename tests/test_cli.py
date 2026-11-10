from __future__ import annotations

from pathlib import Path

import pytest

from parseoff import cli


def test_doctor_lists_every_known_parser(capsys: pytest.CaptureFixture[str]) -> None:
    """AC-7: doctor shows installed state, version, licence, surveyed size and warnings."""
    assert cli.main(["doctor"]) == 0
    lines = capsys.readouterr().out.splitlines()

    def row(name: str) -> str:
        return next(ln for ln in lines if ln.startswith(name))

    assert "7.0.0" in row("pypdf")
    assert "AGPL-3.0" in row("pymupdf4llm")
    assert "model download" in row("docling")
    assert "147 MB" in row("markitdown")
    for name in ("pypdf", "pdfplumber", "pdfminer", "markitdown", "pymupdf4llm", "docling"):
        row(name)
    assert any("surveyed 2026-11-10" in ln for ln in lines)


def test_demo_writes_all_outputs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """AC-1: one command, three documents, three reports, exit 0 even with FAIL findings."""
    out = tmp_path / "demo-out"
    assert cli.main(["demo", "--out", str(out)]) == 0
    text = capsys.readouterr().out
    for needle in ("3 documents", "pypdf", "pdfplumber", "pdfminer", "FAIL", "exit 0", "practice mode"):
        assert needle in text
    assert (out / "report" / "index.html").is_file()
    assert (out / "summary.json").is_file() and (out / "summary.md").is_file()
    assert len(list((out / "samples").glob("*.pdf"))) == 3
    assert "Practice (mock) mode" in (out / "report" / "index.html").read_text(encoding="utf-8")


def test_demo_strict_fails_on_the_scan_finding(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["demo", "--out", str(tmp_path / "o"), "--strict", "--no-render"]) == 1
    assert "exit 1" in capsys.readouterr().out


def test_missing_custom_module_shows_cause_in_terminal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The console shows the first line of a parser error, not only summary.md."""
    out = tmp_path / "demo-out"
    assert cli.main(["demo", "--out", str(out)]) == 0
    capsys.readouterr()
    code = cli.main(["run", str(out / "samples"), "--out", str(tmp_path / "o"), "--parsers", "pypdf",
                     "--custom", "mine=nosuch_mod_xyz:f", "--no-render"])
    assert code == 0
    assert "cannot import module 'nosuch_mod_xyz'" in capsys.readouterr().out
