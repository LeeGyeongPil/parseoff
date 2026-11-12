"""English / Korean screen language: message tables, language choice and the switch itself."""

from __future__ import annotations

import argparse
import re
import string
import subprocess
import sys
from pathlib import Path

import pytest

from parseoff import cli, i18n
from parseoff.doctor import render_doctor
from parseoff.findings import message_for
from parseoff.i18n import MESSAGES, resolve_lang, t
from parseoff.registry import REGISTRY, SURVEY_NOTE
from parseoff.report_text import DEMO_NOTICE, NOTICE
from parseoff.runner import UsageError

# a fixed particle right after a placeholder (closing quote/bracket/space allowed) is wrong Korean
# for some values: the particle depends on the last sound of the value
PLACEHOLDER = r"(?:\}|%\([A-Za-z_]+\)[sdrif]|%[sdrif])"
PARTICLE_AFTER_VALUE = re.compile(PLACEHOLDER + r"[\"'”’)\]」』>` ]*[이가을를은는와과도로]")


def _fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


# --- message tables ----------------------------------------------------------------------------


def test_both_languages_have_exactly_the_same_keys() -> None:
    assert set(MESSAGES["en"]) == set(MESSAGES["ko"])
    assert set(MESSAGES) == set(i18n.LANGS)


def test_placeholders_match_between_languages() -> None:
    for key, en in MESSAGES["en"].items():
        assert _fields(en) == _fields(MESSAGES["ko"][key]), key
        assert en.count("%s") == MESSAGES["ko"][key].count("%s"), key


def test_korean_never_puts_a_fixed_particle_after_a_value() -> None:
    bad = {k: v for k, v in MESSAGES["ko"].items() if PARTICLE_AFTER_VALUE.search(v)}
    assert not bad, bad


def test_particle_check_catches_wrong_sentences() -> None:
    """The regex itself must flag the patterns the rule forbids (and accept the allowed ones)."""
    for wrong in ("{n} 가 많습니다", '"{x}" 를 열 수 없습니다', "{a}은 같습니다", "({x}) 도 있습니다", "{p}과 {q}",
                  "%(option)s 는 %(matches)s 와", "%s 를 열 수 없음", "'%(v)r' 이", "%d가"):
        assert PARTICLE_AFTER_VALUE.search(wrong), wrong
    for right in ("{n}개 있습니다", "{x}쪽", "{best} 에서는 {count}개", "{x}. 구조가", "{seconds:g}초 만에", "{coverage:.0%}만",
                 "%(type)s 값이 올바르지", "다음 인자가 필요합니다: %s", "(후보: %(matches)s)"):
        assert not PARTICLE_AFTER_VALUE.search(right), right


def test_english_table_matches_the_values_kept_elsewhere() -> None:
    """The English screen text must equal the facts parseoff always had (registry, notices)."""
    assert t("notice") == NOTICE
    assert t("notice.demo") == DEMO_NOTICE
    assert t("survey") == SURVEY_NOTE
    for name, info in REGISTRY.items():
        assert t(f"note.{name}") == info.note
    assert t("size.pdfminer") == REGISTRY["pdfminer"].size_text
    assert t("size.docling") == REGISTRY["docling"].size_text
    assert t("hint.pymupdf4llm") == REGISTRY["pymupdf4llm"].install_hint


# --- choosing the language ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cli_value", "env", "expected"),
    [
        ("ko", {"PARSEOFF_LANG": "en", "LANG": "en_US.UTF-8"}, "ko"),  # --lang wins
        ("en", {"PARSEOFF_LANG": "ko", "LANG": "ko_KR.UTF-8"}, "en"),
        (None, {"PARSEOFF_LANG": "ko", "LANG": "en_US.UTF-8"}, "ko"),  # PARSEOFF_LANG next
        (None, {"PARSEOFF_LANG": "en", "LANG": "ko_KR.UTF-8"}, "en"),
        (None, {"LC_ALL": "ko_KR.UTF-8", "LANG": "en_US.UTF-8"}, "ko"),  # then LC_ALL > LC_MESSAGES > LANG
        (None, {"LC_ALL": "en_US.UTF-8", "LC_MESSAGES": "ko_KR.UTF-8"}, "en"),
        (None, {"LC_MESSAGES": "ko_KR.UTF-8", "LANG": "en_US.UTF-8"}, "ko"),
        (None, {"LC_ALL": "", "LANG": "ko_KR.eucKR"}, "ko"),  # empty values are skipped
        (None, {"LANG": "ja_JP.UTF-8"}, "en"),  # not Korean -> English
        (None, {"LANG": "C"}, "en"),
        (None, {}, "en"),
        ("fr", {"LANG": "ko_KR.UTF-8"}, "ko"),  # an invalid --lang is not a language
    ],
)
def test_language_priority(cli_value: str | None, env: dict[str, str], expected: str) -> None:
    assert resolve_lang(cli_value, env) == expected


def test_read_lang_option_finds_both_spellings() -> None:
    assert cli.read_lang_option(["run", "x", "--lang", "ko"]) == "ko"
    assert cli.read_lang_option(["--lang=ko", "doctor"]) == "ko"
    assert cli.read_lang_option(["doctor"]) is None
    assert cli.read_lang_option(["doctor", "--lang"]) is None
    assert cli.read_lang_option(["run", "--", "--lang", "ko"]) is None


def test_environment_switches_the_screen(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("LANG", "ko_KR.UTF-8")
    assert cli.main(["doctor"]) == 0
    assert "설치됨" in capsys.readouterr().out
    monkeypatch.setenv("PARSEOFF_LANG", "en")
    assert cli.main(["doctor"]) == 0
    assert "installed" in capsys.readouterr().out
    assert cli.main(["--lang", "ko", "doctor"]) == 0
    assert "설치됨" in capsys.readouterr().out


# --- the Korean screen -------------------------------------------------------------------------


def _parse_exit(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    with pytest.raises(SystemExit) as info:
        cli.main(argv)
    return int(info.value.code or 0), capsys.readouterr().err + ""


def test_korean_help_has_no_english_fixed_sentences(capsys: pytest.CaptureFixture[str]) -> None:
    for argv in (["--lang", "ko", "--help"], ["run", "--lang", "ko", "-h"], ["demo", "-h", "--lang", "ko"],
                 ["doctor", "--lang=ko", "--help"]):
        with pytest.raises(SystemExit) as info:
            cli.main(argv)
        assert info.value.code == 0
        out = capsys.readouterr().out
        assert "사용법:" in out and "옵션" in out and "이 도움말을 보여 주고 끝냅니다" in out
        for english in ("usage:", "options:", "show this help message", "positional arguments"):
            assert english not in out
    with pytest.raises(SystemExit):
        cli.main(["run", "--lang", "ko", "-h"])
    assert "LOW_COVERAGE 기준값" in capsys.readouterr().out


def test_english_help_is_still_english(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.main(["run", "--help"])
    out = capsys.readouterr().out
    assert "usage:" in out and "LOW_COVERAGE threshold" in out and "show this help message and exit" in out


def test_argument_errors_are_korean_and_exit_code_stays_2(capsys: pytest.CaptureFixture[str]) -> None:
    cases = {
        ("run", "x", "--min-coverage", "3"): "범위를 벗어났습니다",
        ("run", "x", "--min-coverage", "abc"): "0과 1 사이의 숫자가 아닙니다",
        ("run", "x", "--timeout", "0"): "0보다 커야 합니다",
        ("run", "x", "--timeout", "abc"): "숫자가 아닙니다",
        ("run", "x", "--custom", "bad"): "--custom 값이 올바르지 않습니다",
        ("run", "x", "--custom", "pypdf=m:f"): "내장 파서가 쓰고 있는 이름",
        ("run",): "다음 인자가 필요합니다",
        ("nosuchcommand",): "선택할 수 없는 값입니다",
        ("run", "x", "--bogus"): "알 수 없는 인자입니다",
        (): "다음 인자가 필요합니다",
    }
    for argv, expected in cases.items():
        code, err = _parse_exit([*argv, "--lang", "ko"] if "--lang" not in argv else list(argv), capsys)
        assert code == 2, argv
        assert expected in err, (argv, err)
        assert "error:" not in err and "usage:" not in err, err


def test_invalid_lang_value_is_reported_in_the_environment_language(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PARSEOFF_LANG", "ko")
    code, err = _parse_exit(["doctor", "--lang", "fr"], capsys)
    assert code == 2 and "선택할 수 없는 값입니다" in err and "'fr'" in err


def test_english_argument_errors_are_unchanged(capsys: pytest.CaptureFixture[str]) -> None:
    code, err = _parse_exit(["run", "x", "--min-coverage", "3"], capsys)
    assert code == 2 and "is out of range: use a value between 0 and 1" in err and "error:" in err
    code, err = _parse_exit(["run", "x", "--custom", "bad"], capsys)
    assert "invalid --custom value 'bad': expected NAME=module:function" in err


def test_usage_errors_are_korean_with_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "nothing"
    assert cli.main(["run", str(missing), "--lang", "ko"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("오류: ") and "해당 파일이나 폴더가 없습니다" in err and str(missing) in err
    assert cli.main(["run", str(missing)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: ") and "no such file or folder" in err
    assert cli.main(["run", str(tmp_path), "--lang", "ko"]) == 2
    assert "PDF 파일이 없습니다" in capsys.readouterr().err
    assert cli.main(["run", str(tmp_path), "--parsers", "nope", "--lang", "ko"]) == 2
    assert cli.main(["demo", "--max-pages", "0", "--out", str(tmp_path / "o"), "--lang", "ko"]) == 2
    assert "--max-pages 는 1 이상이어야 합니다" in capsys.readouterr().err
    assert cli.main(["demo", "--max-pages", "0", "--out", str(tmp_path / "o")]) == 2
    assert "error: --max-pages must be 1 or greater" in capsys.readouterr().err


def test_usage_error_keeps_code_and_params() -> None:
    err = UsageError("usage.unknown_parsers", unknown="x", known="a, b")
    assert err.key == "usage.unknown_parsers" and err.params == {"unknown": "x", "known": "a, b"}
    assert str(err) == "unknown parser(s): x. Known parsers: a, b"
    assert "x" in err.text("ko") and "알 수 없는 파서" in err.text("ko")


def test_argparse_patch_is_undone_after_a_run(capsys: pytest.CaptureFixture[str]) -> None:
    before = argparse._  # type: ignore[attr-defined]
    cli.main(["doctor", "--lang", "ko"])
    capsys.readouterr()
    assert argparse._ is before  # type: ignore[attr-defined]
    with pytest.raises(SystemExit):
        cli.main(["doctor", "--lang", "ko", "--bogus"])
    capsys.readouterr()
    assert argparse._ is before  # type: ignore[attr-defined]


def test_doctor_korean_has_no_english_labels(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["doctor", "--lang", "ko"]) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    for word in ("설치됨", "라이선스", "디스크 사용", "비고", "조사한 값이며"):
        assert word in out
    for english in ("installed", "licence", "on disk", "notes", "survey values", "WARNING", "install:"):
        assert english not in out, english
    for name in REGISTRY:  # parser names stay and rows keep their order
        assert any(ln.startswith(name) for ln in lines)
    assert render_doctor("en") == render_doctor()


def test_doctor_columns_line_up_with_korean_text() -> None:
    import unicodedata

    def width(text: str) -> int:
        return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)

    lines = render_doctor("ko").splitlines()[:7]
    licences = ["라이선스", "BSD-3-Clause", "MIT", "MIT", "MIT", "AGPL-3.0 or commercial", "MIT"]
    # the licence column starts at the same display column on every row
    starts = {width(ln[: ln.index(lic)]) for ln, lic in zip(lines, licences)}
    assert len(starts) == 1, starts


def test_demo_korean_screen_and_reports(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "ko"
    assert cli.main(["demo", "--out", str(out), "--lang", "ko"]) == 0
    text = capsys.readouterr().out
    for needle in ("연습 모드", "문서 3개", "파서: pypdf, pdfplumber, pdfminer", "종료 코드 0", "리포트:", "건너뜀 docling"):
        assert needle in text, needle
    for english in ("documents,", "skipped ", "report:", "practice mode", "exit 0"):
        assert english not in text, english
    index = (out / "report" / "index.html").read_text(encoding="utf-8")
    assert index.startswith('<!doctype html>\n<html lang="ko">')
    assert "연습(목) 모드" in index and "발견 사항" in index
    doc_page = (out / "report" / "doc-two-column.html").read_text(encoding="utf-8")
    assert '<html lang="ko">' in doc_page and "개요로 돌아가기" in doc_page and "1쪽" in doc_page
    md = (out / "summary.md").read_text(encoding="utf-8")
    assert md.startswith("# parseoff 요약") and "## 발견 사항" in md and "연습(목) 모드" in md
    for english in ("## Findings", "## Parsers", "| document |"):
        assert english not in md


def test_strict_line_is_korean(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["demo", "--out", str(tmp_path / "o"), "--strict", "--no-render", "--lang", "ko"]) == 1
    assert "종료 코드 1" in capsys.readouterr().out


def test_cached_marker_is_translated(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "o"
    assert cli.main(["demo", "--out", str(out), "--no-render"]) == 0
    capsys.readouterr()
    assert cli.main(["demo", "--out", str(out), "--no-render", "--lang", "ko"]) == 0
    text = capsys.readouterr().out
    assert "(캐시)" in text and "(cached)" not in text


# --- what must NOT change with the language ----------------------------------------------------


def test_summary_json_is_byte_identical_in_every_language(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "same"
    codes = []
    blobs = []
    for lang in ("en", "ko", "en"):
        codes.append(cli.main(["demo", "--out", str(out), "--lang", lang]))
        blobs.append((out / "summary.json").read_bytes())
    capsys.readouterr()
    assert codes == [0, 0, 0]
    assert blobs[0] == blobs[1] == blobs[2]
    text = blobs[0].decode("utf-8")
    assert "text layer" in text  # finding messages in summary.json stay English


def test_exit_codes_do_not_depend_on_language(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for lang in ("en", "ko"):
        assert cli.main(["demo", "--out", str(tmp_path / lang), "--strict", "--no-render", "--lang", lang]) == 1
        assert cli.main(["demo", "--out", str(tmp_path / lang), "--no-render", "--lang", lang]) == 0
    capsys.readouterr()


def test_version_output_is_not_translated(capsys: pytest.CaptureFixture[str]) -> None:
    outputs = []
    for argv in (["--version"], ["--lang", "ko", "--version"]):
        with pytest.raises(SystemExit) as info:
            cli.main(argv)
        assert info.value.code == 0
        outputs.append(capsys.readouterr().out)
    assert outputs[0] == outputs[1] and re.fullmatch(r"parseoff \d+\.\d+\.\d+\n", outputs[0])


def test_findings_keep_english_message_and_translate_on_screen(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from parseoff.model import Finding
    from parseoff.runner import RunOptions, run_pipeline

    pdfs = tmp_path / "samples"
    from parseoff.samples import create_samples

    create_samples(pdfs)
    report = run_pipeline(RunOptions(pdfs, tmp_path / "o", render=False))
    capsys.readouterr()
    assert report.findings
    for f in report.findings:
        assert message_for(f, "en") == f.message
        ko = message_for(f, "ko")
        assert "{" not in ko and "}" not in ko, ko
        if f.key:
            assert ko != f.message, f.code
    codes = {f.code for f in report.findings}
    assert {"EMPTY_TEXT_LAYER", "SKIPPED"} <= codes
    # a finding without a key (text produced by a parser) is shown as it is
    raw = Finding("PARSER_ERROR", "FAIL", "boom from a library")
    assert message_for(raw, "ko") == "boom from a library"


def test_every_finding_template_renders_in_both_languages() -> None:
    from parseoff.findings import _render

    samples = {
        "finding.cannot_open": {"error": "ValueError: x"},
        "finding.empty_layer": {},
        "finding.low_coverage": {"coverage": 0.25, "threshold": 0.8},
        "finding.low_agreement": {"a": "pypdf", "b": "pdfminer", "value": 0.31, "threshold": 0.6},
        "finding.boilerplate": {"example": "Page 1", "share": "pypdf 20%"},
        "finding.copyleft": {"license": "AGPL-3.0"},
        "finding.weights": {},
        "finding.model_download": {"found": False},
        "finding.heavy": {"name": "markitdown"},
        "finding.no_item": {"parts": [("tables", "pdfplumber", 2), ("headings", "pdfminer", 1)]},
        "skip.opt_in": {"name": "docling"},
        "skip.not_installed": {"name": "markitdown"},
        "err.timeout": {"seconds": 5.0},
        "err.worker_exit": {"code": 3},
    }
    for key, params in samples.items():
        for lang in ("en", "ko"):
            text = _render(key, params, lang)
            assert text and "{" not in text, (key, lang, text)
        assert _render(key, params, "ko") != _render(key, params, "en"), key
    assert _render("finding.no_item", samples["finding.no_item"], "en") == (
        "no tables (but pdfplumber found 2) and no headings (but pdfminer found 1): structure may be flattened"
    )


def test_custom_error_in_korean_keeps_the_fix(capsys: pytest.CaptureFixture[str]) -> None:
    code, err = _parse_exit(["run", "x", "--custom", "9bad=m:f", "--lang", "ko"], capsys)
    assert code == 2 and "영문자, 숫자" in err
    code, err = _parse_exit(["run", "x", "--custom", "mine=bad-module:f", "--lang", "ko"], capsys)
    assert code == 2 and "module.path:function_name" in err


def test_terminal_that_cannot_show_korean_does_not_crash(tmp_path: Path) -> None:
    """ASCII-only output encoding: the Korean line degrades to '?' instead of a traceback."""
    env = {"PATH": "/usr/bin:/bin", "PYTHONIOENCODING": "ascii", "PARSEOFF_LANG": "ko", "PYTHONPATH": str(Path(cli.__file__).parent.parent)}
    done = subprocess.run([sys.executable, "-m", "parseoff.cli", "run", str(tmp_path / "none")],
                          capture_output=True, env=env, check=False)
    assert done.returncode == 2
    assert b"Traceback" not in done.stderr and b"?" in done.stderr
