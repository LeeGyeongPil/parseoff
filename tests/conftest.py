from __future__ import annotations

import json
from pathlib import Path

import pytest

from parseoff import cli
from parseoff.samples import create_samples


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
