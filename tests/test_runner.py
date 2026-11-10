from __future__ import annotations

import json
from pathlib import Path

import pytest

from parseoff import cli, runner

BASE = ["--max-pages", "1", "--timeout", "5", "--no-render"]


def _summary(out: Path) -> dict:
    return json.loads((out / "summary.json").read_text(encoding="utf-8"))


def _codes(summary: dict) -> set[tuple[str, str | None]]:
    return {(f["code"], f["parser"]) for f in summary["findings"]}


def test_timeout_error_isolated_strict_and_cache(
    one_pdf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-9: a hang and an exception are recorded, the rest still works, strict gates, cache reuses."""
    out = tmp_path / "out"
    args = ["run", str(one_pdf), "--out", str(out), "--parsers", "pypdf", *BASE,
            "--custom", "good=fake_parsers:ok", "--custom", "bad=fake_parsers:boom",
            "--custom", "hang=fake_parsers:slow"]
    assert cli.main(args) == 0  # findings never fail the run unless --strict
    summary = _summary(out)
    codes = _codes(summary)
    assert ("TIMEOUT", "hang") in codes and ("PARSER_ERROR", "bad") in codes
    parsers = summary["documents"][0]["parsers"]
    assert parsers["pypdf"]["status"] == "ok" and parsers["good"]["status"] == "ok"
    assert parsers["hang"]["status"] == "timeout" and parsers["bad"]["status"] == "error"
    assert "always fails" in parsers["bad"]["error"]
    assert cli.main([*args, "--strict"]) == 1

    # cache: pypdf is reused (no worker launched), custom parsers always run again
    launches: list[list[str]] = []
    real = runner._launch
    monkeypatch.setattr(runner, "_launch", lambda cmd, t, env: (launches.append(cmd), real(cmd, t, env))[1])
    args2 = ["run", str(one_pdf), "--out", str(tmp_path / "out2"), "--parsers", "pypdf", *BASE,
             "--custom", "good=fake_parsers:ok"]
    assert cli.main(args2) == 0
    assert len(launches) == 2  # fresh output folder: pypdf + good
    launches.clear()
    assert cli.main(args2) == 0
    assert len(launches) == 1 and "good=fake_parsers:ok" in launches[0]  # pypdf served from raw/
    launches.clear()
    assert cli.main([*args2, "--fresh"]) == 0
    assert len(launches) == 2  # --fresh ignores the cache


def test_cache_is_invalidated_when_the_document_changes(one_pdf: Path, tmp_path: Path, sample_dir: Path) -> None:
    out = tmp_path / "out"
    args = ["run", str(one_pdf), "--out", str(out), "--parsers", "pypdf", *BASE]
    assert cli.main(args) == 0
    first = _summary(out)["documents"][0]["sha256"]
    (one_pdf / "two-column.pdf").write_bytes((sample_dir / "report-table.pdf").read_bytes())
    assert cli.main(args) == 0
    second = _summary(out)["documents"][0]
    assert second["sha256"] != first
    assert second["parsers"]["pypdf"]["pages"][0]["chars"] > 0


def test_unreadable_pdf_is_a_finding_not_a_crash(tmp_path: Path, sample_dir: Path) -> None:
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "broken.pdf").write_bytes(b"this is not a pdf")
    (folder / "fine.pdf").write_bytes((sample_dir / "two-column.pdf").read_bytes())
    out = tmp_path / "out"
    args = ["run", str(folder), "--out", str(out), "--parsers", "pypdf", *BASE]
    assert cli.main(args) == 0
    summary = _summary(out)
    broken = [f for f in summary["findings"] if f["doc"] == "broken.pdf"]
    assert broken and broken[0]["code"] == "PARSER_ERROR"
    assert any(d["id"] == "fine.pdf" and d["parsers"]["pypdf"]["status"] == "ok" for d in summary["documents"])
    assert cli.main([*args, "--strict"]) == 1


def test_usage_errors_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["run", str(tmp_path / "missing"), "--out", str(tmp_path / "o")]) == 2
    assert "no such file or folder" in capsys.readouterr().err
    (tmp_path / "empty").mkdir()
    assert cli.main(["run", str(tmp_path / "empty"), "--out", str(tmp_path / "o")]) == 2
    assert "no PDF files found" in capsys.readouterr().err
    assert cli.main(["run", str(tmp_path / "empty"), "--max-pages", "0"]) == 2
    with pytest.raises(SystemExit) as exc:
        cli.main(["run", str(tmp_path), "--min-coverage", "1.5"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        cli.main(["run", str(tmp_path), "--custom", "oops"])
    assert exc.value.code == 2


def test_unknown_parser_name_exit_2(one_pdf: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["run", str(one_pdf), "--out", str(tmp_path / "o"), "--parsers", "nope"]) == 2
    assert "unknown parser" in capsys.readouterr().err


def test_slugs_are_unique_and_safe() -> None:
    slugs = runner.make_slugs(["a/b c.pdf", "a_b_c.pdf", "x.PDF", "x.pdf"])
    assert slugs == ["a_b_c", "a_b_c-2", "x", "x-2"]
    assert all(s.replace("-", "").replace("_", "").isalnum() for s in slugs)
