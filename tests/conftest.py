from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from parseoff import cli
from parseoff.samples import create_samples

# Tests expect the English screen: clear every variable that could pick Korean. This runs at import
# time so session fixtures are covered too; the autouse fixture below repeats it for each test.
LANG_VARS = ("PARSEOFF_LANG", "LC_ALL", "LC_MESSAGES", "LANG")
for _name in LANG_VARS:
    os.environ.pop(_name, None)


@pytest.fixture(autouse=True)
def _english_screen(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in LANG_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(scope="session")
def sample_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The three synthetic PDFs, created once per test session."""
    folder = tmp_path_factory.mktemp("samples")
    create_samples(folder)
    return folder


@pytest.fixture(scope="session")
def demo_summary(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """summary.json of one real `parseoff demo` run (real parsers on the synthetic PDFs)."""
    out = tmp_path_factory.mktemp("demo") / "out"
    assert cli.main(["demo", "--out", str(out)]) == 0
    return json.loads((out / "summary.json").read_text(encoding="utf-8"))


@pytest.fixture
def one_pdf(sample_dir: Path, tmp_path: Path) -> Path:
    """A folder holding a single PDF, for tests that run many pipelines."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "two-column.pdf").write_bytes((sample_dir / "two-column.pdf").read_bytes())
    return folder
