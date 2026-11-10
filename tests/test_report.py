from __future__ import annotations

import os
import re
from pathlib import Path

from parseoff import cli


def test_report_is_self_contained_and_escaped(one_pdf: Path, tmp_path: Path) -> None:
    """AC-8: parser output is escaped, nothing external is referenced, no paths or clock times leak."""
    out = tmp_path / "out"
    code = cli.main([
        "run", str(one_pdf), "--out", str(out), "--parsers", "pypdf", "--timeout", "10",
        "--custom", "evil=fake_parsers:script", "--custom", "leak=fake_parsers:leaky",
    ])
    assert code == 0

    html_files = sorted((out / "report").glob("*.html"))
    assert [p.name for p in html_files] == ["doc-two-column.html", "index.html"]
    page = (out / "report" / "doc-two-column.html").read_text(encoding="utf-8")
    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;" in page
    assert "&lt;b&gt;bold&lt;/b&gt;" in page
    assert (out / "report" / "img" / "two-column-p1.png").is_file()

    for html_file in html_files:
        text = html_file.read_text(encoding="utf-8")
        assert "<script" not in text.lower()
        assert not re.search(r"""(?:src|href)\s*=\s*["']?(?:[a-z]+:)?//""", text, re.I)
        assert not re.search(r"""url\(\s*["']?https?:""", text, re.I)

    forbidden = [str(tmp_path), str(tmp_path.resolve()), os.getcwd(), str(Path.home())]
    outputs = [p for p in out.rglob("*") if p.is_file() and p.suffix in {".html", ".json", ".md"}]
    assert len(outputs) >= 7  # index, doc page, summary x2, 3 raw results
    for path in outputs:
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in text, f"{needle} leaked into {path.name}"
        assert not re.search(r"\b\d{2}:\d{2}:\d{2}\b", text), f"clock time in {path.name}"
    # the scrubbed error still says what happened, with a placeholder instead of the real path
    assert "cannot read <input>/two-column.pdf" in (out / "summary.json").read_text(encoding="utf-8")


def test_summary_is_stable_between_runs(one_pdf: Path, tmp_path: Path) -> None:
    """Same input twice -> identical summary.md and summary.json (cache keeps timings the same)."""
    out = tmp_path / "out"
    args = ["run", str(one_pdf), "--out", str(out), "--parsers", "pypdf,pdfplumber", "--no-render"]
    assert cli.main(args) == 0
    first = [(out / n).read_text(encoding="utf-8") for n in ("summary.json", "summary.md")]
    assert cli.main(args) == 0
    assert first == [(out / n).read_text(encoding="utf-8") for n in ("summary.json", "summary.md")]
