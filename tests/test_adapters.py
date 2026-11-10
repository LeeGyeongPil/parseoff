from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from parseoff import runner
from parseoff.adapters import get_adapter
from parseoff.adapters.custom import parse_spec
from parseoff.findings import build_findings
from parseoff.model import RunReport, Skipped, Thresholds
from parseoff.runner import UsageError, select_parsers


def _names(specs) -> list[str]:
    return [s.name for s in specs]


def test_optional_parsers_skipped_or_normalized(
    monkeypatch: pytest.MonkeyPatch, sample_dir: Path
) -> None:
    """AC-6: missing optional parsers are skipped with a hint; fake modules are normalised."""
    pdf = str(sample_dir / "report-table.pdf")

    # 1) nothing optional installed -> skipped with install hints, run continues
    monkeypatch.setattr(runner, "is_installed", lambda name: name in {"pypdf", "pdfplumber", "pdfminer"})
    specs, skipped = select_parsers(None, [])
    assert _names(specs) == ["pypdf", "pdfplumber", "pdfminer"]
    reasons = {s.name: s.reason for s in skipped}
    assert "uv sync --extra markitdown" in reasons["markitdown"]
    assert "uv pip install pymupdf4llm" in reasons["pymupdf4llm"]
    assert "opt-in" in reasons["docling"]

    # 2) everything installed -> docling still does NOT run unless named in --parsers
    monkeypatch.setattr(runner, "is_installed", lambda name: True)
    specs, skipped = select_parsers(None, [])
    assert "docling" not in _names(specs) and [s.name for s in skipped] == ["docling"]
    specs, _ = select_parsers(["pypdf", "docling"], [])
    assert _names(specs) == ["pypdf", "docling"]

    # 3) fake markitdown: one conversion per page, so the result has one string per page
    seen_pages: list[int] = []

    class FakeMarkItDown:
        def __init__(self, enable_plugins: bool = True) -> None:
            assert enable_plugins is False  # plugins would run third-party code

        def convert(self, path: str):
            from pypdf import PdfReader

            reader = PdfReader(path)
            seen_pages.append(len(reader.pages))
            return types.SimpleNamespace(text_content=f"# md\n{reader.pages[0].extract_text()}")

    monkeypatch.setitem(sys.modules, "markitdown", types.SimpleNamespace(MarkItDown=FakeMarkItDown))
    md = get_adapter("markitdown")(pdf, [1, 3])
    assert len(md) == 2 and seen_pages == [1, 1]
    assert "Quarterly Report" in md[0] and "Quarterly Report" not in md[1]

    # 4) fake pymupdf4llm: page_chunks=True dicts are turned into plain strings
    def to_markdown(path: str, pages: list[int], page_chunks: bool):
        assert page_chunks is True
        return [{"text": f"# page {p + 1}\n"} for p in pages]

    monkeypatch.setitem(sys.modules, "pymupdf4llm", types.SimpleNamespace(to_markdown=to_markdown))
    assert get_adapter("pymupdf4llm")(pdf, [2, 3]) == ["# page 2", "# page 3"]

    monkeypatch.setitem(
        sys.modules, "pymupdf4llm", types.SimpleNamespace(to_markdown=lambda *a, **k: [{"text": "x"}])
    )
    with pytest.raises(RuntimeError, match="1 page chunk"):
        get_adapter("pymupdf4llm")(pdf, [1, 2])

    # 5) the AGPL parser carries a LICENSE_COPYLEFT finding whenever it ran
    report = RunReport(docs=[], parsers=["pypdf", "pymupdf4llm"], skipped=[Skipped("docling", "opt-in only")],
                       thresholds=Thresholds())
    codes = {(f.code, f.parser) for f in build_findings(report)}
    assert ("LICENSE_COPYLEFT", "pymupdf4llm") in codes
    assert ("HEAVY_INSTALL", "pymupdf4llm") in codes
    assert ("LICENSE_COPYLEFT", "pypdf") not in codes
    assert ("SKIPPED", "docling") in codes


def test_docling_adapter_with_fake_module(monkeypatch: pytest.MonkeyPatch, sample_dir: Path) -> None:
    class FakeDocument:
        def export_to_markdown(self, page_no: int) -> str:
            return f"## docling page {page_no}\n"

    class FakeConverter:
        def convert(self, path: str):
            return types.SimpleNamespace(document=FakeDocument())

    fake = types.SimpleNamespace(DocumentConverter=FakeConverter)
    monkeypatch.setitem(sys.modules, "docling", types.SimpleNamespace())
    monkeypatch.setitem(sys.modules, "docling.document_converter", fake)
    assert get_adapter("docling")(str(sample_dir / "two-column.pdf"), [1, 2]) == [
        "## docling page 1",
        "## docling page 2",
    ]


def test_builtin_adapters_reject_pages_out_of_range(sample_dir: Path) -> None:
    for name in ("pypdf", "pdfplumber", "pdfminer"):
        with pytest.raises(ValueError, match="out of range"):
            get_adapter(name)(str(sample_dir / "two-column.pdf"), [3])


def test_unknown_parser_and_custom_spec_errors() -> None:
    with pytest.raises(UsageError, match="unknown parser"):
        select_parsers(["nope"], [])
    with pytest.raises(ValueError, match="NAME=module:function"):
        parse_spec("just-a-name")
    with pytest.raises(ValueError, match="taken by a built-in"):
        parse_spec("pypdf=mod:fn")
    with pytest.raises(ValueError, match="invalid custom parser name"):
        parse_spec("bad name=mod:fn")
    assert parse_spec("mine=pkg.sub:to_pages").function == "to_pages"


def test_install_hints_work_for_clone_uv_install() -> None:
    """Install hints must be commands that work in a clone + uv setup (parseoff is not on PyPI)."""
    from parseoff.registry import REGISTRY  # noqa: PLC0415

    hints = {n: i.install_hint for n, i in REGISTRY.items() if i.install_hint}
    assert hints["markitdown"].startswith("uv sync --extra markitdown")
    assert hints["docling"].startswith("uv sync --extra docling")
    assert hints["pymupdf4llm"] == "uv pip install pymupdf4llm; AGPL-3.0, check its terms"
    for hint in hints.values():
        assert 'pip install "parseoff[' not in hint
        assert not hint.startswith("pip install")


def test_optional_adapter_errors_use_working_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    from parseoff.adapters import optional

    real_import = importlib.import_module

    def fake_import(name, *a, **k):
        if name.split(".")[0] in {"markitdown", "pymupdf4llm", "docling"}:
            raise ImportError(name)
        return real_import(name, *a, **k)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    msgs = []
    for fn in (optional.markitdown_convert, optional.pymupdf4llm_convert, optional.docling_convert):
        with pytest.raises(RuntimeError) as err:
            fn("x.pdf", [1])
        msgs.append(str(err.value))
    assert all('pip install "parseoff[' not in m for m in msgs)
    assert "uv pip install pymupdf4llm" in msgs[1] and "AGPL-3.0" in msgs[1]


def test_readme_install_commands_match() -> None:
    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
    assert 'pip install "parseoff[' not in readme
    row = next(ln for ln in readme.splitlines() if ln.startswith("| pymupdf4llm"))
    assert "`uv pip install pymupdf4llm`" in row
