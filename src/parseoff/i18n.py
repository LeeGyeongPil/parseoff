"""Screen language: one message table per language, plus the rule that picks the language.

Language order: ``--lang en|ko`` > ``PARSEOFF_LANG`` > ``LC_ALL`` / ``LC_MESSAGES`` / ``LANG``
(the first one that is set and not empty). A value that starts with ``ko`` means Korean, anything
else means English.

Only text meant for people is translated. ``summary.json``, finding codes, levels, parser names,
exit codes and the text that parsers or PDF libraries produce stay as they are.
Korean sentences never put a fixed particle (i/ga/eul/reul ...) after a value, because the right
particle depends on the value: the value goes at the end of the sentence or is followed by a unit.
"""

from __future__ import annotations

import argparse
import contextlib
import os
from collections.abc import Iterator, Mapping

LANGS = ("en", "ko")
DEFAULT_LANG = "en"
ENV_VAR = "PARSEOFF_LANG"

_EN: dict[str, str] = {
    # --- command line: help ------------------------------------------------------------------
    "cli.description": "Compare PDF parsers side by side on your own documents.",
    "cli.help.lang": "screen language: en or ko (default: PARSEOFF_LANG, then LC_ALL / LC_MESSAGES / LANG)",
    "cli.help.version": "show the version and exit",
    "cli.help.doctor": "show installed parsers, versions, licences and warnings",
    "cli.help.run": "compare parsers on a PDF file or a folder of PDFs",
    "cli.help.demo": "generate 3 practice PDFs and compare the default parsers on them",
    "cli.help.input": "a .pdf file or a folder (searched recursively)",
    "cli.help.out_run": "output folder (default parseoff-out)",
    "cli.help.out_demo": "output folder (default demo-out)",
    "cli.help.parsers": "comma separated parsers to run (default: every installed one except docling)",
    "cli.help.max_pages": "analyse only the first N pages of each PDF",
    "cli.help.timeout": "per parser and document (default 120)",
    "cli.help.custom": "add your own parser function (repeatable)",
    "cli.help.min_coverage": "LOW_COVERAGE threshold (default 0.8)",
    "cli.help.min_agreement": "LOW_AGREEMENT threshold (default 0.6)",
    "cli.help.strict": "exit 1 if any FAIL finding exists (for CI)",
    "cli.help.fresh": "ignore cached parser results",
    "cli.help.no_render": "do not write page images",
    # --- command line: errors and progress ----------------------------------------------------
    "cli.error_prefix": "error: ",
    "arg.not_fraction": "{text!r} is not a number between 0 and 1",
    "arg.out_of_range": "{text} is out of range: use a value between 0 and 1",
    "arg.not_number": "{text!r} is not a number",
    "arg.not_positive": "{text} must be greater than 0",
    "err.max_pages": "--max-pages must be 1 or greater",
    "demo.banner": "parseoff demo - practice mode: 3 synthetic PDFs, real parsers",
    "run.summary": "{count} documents, parsers: {parsers}",
    "run.none": "(none)",
    "run.skipped": "skipped {name}: {reason}",
    "run.counts": "FAIL {fail}, WARN {warn}, INFO {info} - exit {code}{hint}",
    "run.strict_hint": " (use --strict to fail)",
    "run.report": "report: {path}",
    # --- custom parser option ----------------------------------------------------------------
    "custom.bad_value": "invalid --custom value {text!r}: expected NAME=module:function "
                        "(for example: --custom mine=mypkg.parse:to_pages)",
    "custom.bad_name": "invalid custom parser name {name!r}: use letters, digits, - or _ (max 32)",
    "custom.taken": "custom parser name {name!r} is taken by a built-in parser; pick another name",
    "custom.bad_target": "invalid --custom target {target!r}: expected module.path:function_name",
    # --- runner ------------------------------------------------------------------------------
    "usage.no_such": "{path}: no such file or folder. Pass a PDF file or a folder that contains PDFs.",
    "usage.not_pdf": "{path}: not a .pdf file. Pass a PDF file or a folder that contains PDFs.",
    "usage.no_pdfs": "{path}: no PDF files found. Pass a folder that contains .pdf files.",
    "usage.unknown_parsers": "unknown parser(s): {unknown}. Known parsers: {known}",
    "skip.opt_in": "opt-in only: add {name} to --parsers (model download on first run)",
    "skip.not_installed": "not installed ({hint})",
    "skip.install_first": "install it first",
    "err.timeout": "timed out after {seconds:g}s (raise --timeout or use --max-pages)",
    "err.worker_exit": "worker exited with code {code} without a result",
    "progress.cannot_open": "  {doc}: cannot open ({error})",
    "progress.images_skipped": "  {doc}: page images skipped ({error})",
    "progress.parser": "  {doc}: {parser} {status} {seconds:.2f}s{cached}",
    "progress.cached": " (cached)",
    # --- doctor ------------------------------------------------------------------------------
    "doctor.h.parser": "parser",
    "doctor.h.installed": "installed",
    "doctor.h.version": "version",
    "doctor.h.license": "license",
    "doctor.h.size": "install size*",
    "doctor.h.disk": "on disk",
    "doctor.h.notes": "notes",
    "doctor.yes": "yes",
    "doctor.no": "no",
    "doctor.copyleft": "WARNING copyleft licence",
    "doctor.model_download": "WARNING model download on first run (local models: {found}); opt-in via --parsers",
    "doctor.found": "found",
    "doctor.not_found": "not found",
    "doctor.install": "install: {hint}",
    "doctor.foot1": "* install size: {survey} (docling not measured). Versions and 'on disk' are read from your environment.",
    "doctor.foot2": "Licence and size columns are survey values, not legal advice: verify before you ship.",
    # --- registry facts shown on screen --------------------------------------------------------
    "survey": "surveyed 2026-11-10, macOS arm64, Python 3.12, isolated install",
    "size.pdfminer": "part of pdfplumber",
    "size.docling": "not measured (large, torch)",
    "license.custom": "unknown (custom)",
    "hint.pymupdf4llm": "uv pip install pymupdf4llm; AGPL-3.0, check its terms",
    "note.pypdf": "pure Python; text in content-stream order, no structure",
    "note.pdfplumber": "text by position + tables as GFM (includes pypdfium2, pdfminer.six)",
    "note.pdfminer": "layout-box text; markitdown's PDF path is pdfminer text extraction",
    "note.markitdown": "most of the size is onnxruntime; page-split (one conversion per page)",
    "note.pymupdf4llm": "detected only if you installed it; not an extra of parseoff",
    "note.docling": "experimental",
    # --- findings ----------------------------------------------------------------------------
    "finding.cannot_open": "cannot open the PDF: {error}",
    "finding.empty_layer": "page has no text layer (scan or image only): OCR is needed, text parsers return nothing",
    "finding.low_coverage": "only {coverage:.0%} of the text-layer words appear (threshold {threshold:.0%})",
    "finding.low_agreement": "{a} and {b} agree on only {value:.2f} of the word order "
                             "(threshold {threshold:.2f}): look at this page yourself",
    "finding.boilerplate": "lines repeat on many pages (e.g. \"{example}\"; share of lines: {share}): "
                           "headers/footers will pollute RAG chunks",
    "finding.copyleft": "{license}: copyleft licence, check it fits how you ship your software",
    "finding.weights": "model weights have commercial-use limits",
    "finding.model_download": "downloads models on first run unless present ({state}); "
                              "set DOCLING_ARTIFACTS_PATH for offline use",
    "finding.models_found": "models found locally",
    "finding.models_missing": "models NOT found locally",
    "finding.heavy": "install size about {size} (surveyed, may differ on your system)",
    "finding.no_item": "no {label} (but {best} found {count})",
    "finding.and": " and ",
    "finding.flattened": "{items}: structure may be flattened",
    "label.tables": "tables",
    "label.headings": "headings",
    # --- HTML report and summary.md ------------------------------------------------------------
    "notice": "This output contains text from your documents. parseoff sends nothing over the network.",
    "notice.demo": "Practice (mock) mode: synthetic sample PDFs, but the parsers are real.",
    "tbl.parser": "parser",
    "tbl.version": "version",
    "tbl.license": "license",
    "tbl.status": "status",
    "tbl.document": "document",
    "tbl.seconds": "seconds",
    "tbl.coverage": "mean coverage",
    "tbl.tables": "tables",
    "tbl.headings": "headings",
    "tbl.tokens": "est. tokens",
    "html.title": "parseoff report",
    "html.parsers": "Parsers",
    "html.size_head": "install size ({survey})",
    "html.ran": "ran",
    "html.skipped": "skipped: {reason}",
    "html.docs": "Documents x parsers",
    "html.cannot_open_row": "cannot open: {error}",
    "html.tokens_note": "Token counts are estimates (characters / 4).",
    "html.agreement": "Agreement between parsers (mean word-order similarity)",
    "html.findings": "Findings",
    "html.no_findings": "No findings.",
    "html.back": "back to overview",
    "html.cannot_open": "Cannot open this PDF: {error}",
    "html.docinfo": "sha256 {sha}..., {total} page(s), {analysed} analysed",
    "html.no_stderr": "(no stderr)",
    "html.page": "Page {page}",
    "html.page_alt": "page {page}",
    "html.layer": "text layer: {chars} chars",
    "html.agreement_row": "agreement: {pairs}",
    "html.original": "original",
    "html.page_metrics": "chars {chars}, coverage {coverage}, tables {tables}, headings {headings}",
    "where.page": " page {page}",
    "md.title": "parseoff summary",
    "md.parsers": "Parsers",
    "md.size_head": "install size (surveyed)",
    "md.ran": "ran",
    "md.skipped": "skipped - {reason}",
    "md.documents": "Documents",
    "md.findings": "Findings",
    "md.no_findings": "No findings.",
    "md.foot": "Token counts are estimates (characters / 4). Install sizes: {survey}.",
}

_KO: dict[str, str] = {
    "cli.description": "내 문서로 PDF 파서를 나란히 비교합니다.",
    "cli.help.lang": "화면 언어: en 또는 ko (기본값: PARSEOFF_LANG, 그다음 LC_ALL / LC_MESSAGES / LANG)",
    "cli.help.version": "버전을 보여 주고 끝냅니다",
    "cli.help.doctor": "설치된 파서와 버전, 라이선스, 경고를 보여 줍니다",
    "cli.help.run": "PDF 파일 또는 PDF 폴더에서 파서를 비교합니다",
    "cli.help.demo": "연습용 PDF 3개를 만들고 기본 파서로 비교합니다",
    "cli.help.input": ".pdf 파일 또는 폴더 (하위 폴더까지 찾습니다)",
    "cli.help.out_run": "출력 폴더 (기본값 parseoff-out)",
    "cli.help.out_demo": "출력 폴더 (기본값 demo-out)",
    "cli.help.parsers": "실행할 파서를 쉼표로 구분해 지정합니다 (기본값: docling 을 뺀 설치된 모든 파서)",
    "cli.help.max_pages": "각 PDF 의 앞쪽 N쪽만 분석합니다",
    "cli.help.timeout": "파서·문서마다 적용되는 제한 시간(초) (기본값 120)",
    "cli.help.custom": "직접 만든 파서 함수를 추가합니다 (여러 번 지정 가능)",
    "cli.help.min_coverage": "LOW_COVERAGE 기준값 (기본값 0.8)",
    "cli.help.min_agreement": "LOW_AGREEMENT 기준값 (기본값 0.6)",
    "cli.help.strict": "FAIL 결과가 하나라도 있으면 종료 코드 1 로 끝냅니다 (CI 용)",
    "cli.help.fresh": "저장된 파서 결과를 무시합니다",
    "cli.help.no_render": "쪽 이미지를 만들지 않습니다",
    "cli.error_prefix": "오류: ",
    "arg.not_fraction": "0과 1 사이의 숫자가 아닙니다: {text!r}",
    "arg.out_of_range": "범위를 벗어났습니다. 0과 1 사이의 값을 쓰십시오: {text}",
    "arg.not_number": "숫자가 아닙니다: {text!r}",
    "arg.not_positive": "0보다 커야 합니다: {text}",
    "err.max_pages": "--max-pages 는 1 이상이어야 합니다",
    "demo.banner": "parseoff demo - 연습 모드: 합성 PDF 3개, 실제 파서",
    "run.summary": "문서 {count}개, 파서: {parsers}",
    "run.none": "(없음)",
    "run.skipped": "건너뜀 {name}: {reason}",
    "run.counts": "FAIL {fail}, WARN {warn}, INFO {info} - 종료 코드 {code}{hint}",
    "run.strict_hint": " (실패로 처리하려면 --strict 사용)",
    "run.report": "리포트: {path}",
    "custom.bad_value": "--custom 값이 올바르지 않습니다. NAME=module:function 형식으로 쓰십시오 "
                        "(예: --custom mine=mypkg.parse:to_pages): {text!r}",
    "custom.bad_name": "사용자 파서 이름이 올바르지 않습니다. 영문자, 숫자, - 또는 _ 만 쓰십시오 (최대 32자): {name!r}",
    "custom.taken": "내장 파서가 쓰고 있는 이름이라 사용자 파서 이름으로 쓸 수 없습니다. 다른 이름을 고르십시오: {name!r}",
    "custom.bad_target": "--custom 대상이 올바르지 않습니다. module.path:function_name 형식으로 쓰십시오: {target!r}",
    "usage.no_such": "해당 파일이나 폴더가 없습니다. PDF 파일 또는 PDF 가 들어 있는 폴더를 지정하십시오: {path}",
    "usage.not_pdf": ".pdf 파일이 아닙니다. PDF 파일 또는 PDF 가 들어 있는 폴더를 지정하십시오: {path}",
    "usage.no_pdfs": "PDF 파일이 없습니다. .pdf 파일이 들어 있는 폴더를 지정하십시오: {path}",
    "usage.unknown_parsers": "알 수 없는 파서가 있습니다. 사용 가능한 파서: {known} / 입력한 값: {unknown}",
    "skip.opt_in": "직접 지정할 때만 실행합니다 (처음 실행할 때 모델을 내려받습니다). --parsers 에 추가할 이름: {name}",
    "skip.not_installed": "설치되지 않음 ({hint})",
    "skip.install_first": "먼저 설치하십시오",
    "err.timeout": "{seconds:g}초 만에 시간 초과 (--timeout 을 늘리거나 --max-pages 를 쓰십시오)",
    "err.worker_exit": "작업 프로세스가 결과 없이 종료되었습니다. 종료 코드: {code}",
    "progress.cannot_open": "  {doc}: 열 수 없음 ({error})",
    "progress.images_skipped": "  {doc}: 쪽 이미지를 건너뜀 ({error})",
    "progress.parser": "  {doc}: {parser} {status} {seconds:.2f}초{cached}",
    "progress.cached": " (캐시)",
    "doctor.h.parser": "파서",
    "doctor.h.installed": "설치됨",
    "doctor.h.version": "버전",
    "doctor.h.license": "라이선스",
    "doctor.h.size": "설치 크기*",
    "doctor.h.disk": "디스크 사용",
    "doctor.h.notes": "비고",
    "doctor.yes": "예",
    "doctor.no": "아니오",
    "doctor.copyleft": "경고: 카피레프트 라이선스",
    "doctor.model_download": "경고: 처음 실행할 때 모델을 내려받습니다 (로컬 모델: {found}). --parsers 로 직접 지정할 때만 실행",
    "doctor.found": "있음",
    "doctor.not_found": "없음",
    "doctor.install": "설치: {hint}",
    "doctor.foot1": "* 설치 크기: {survey} (docling 은 측정하지 않았습니다). 버전과 '디스크 사용'은 현재 환경에서 읽은 값입니다.",
    "doctor.foot2": "라이선스와 크기 열은 조사한 값이며 법률 자문이 아닙니다. 배포 전에 직접 확인하십시오.",
    "survey": "2026-11-10 조사, macOS arm64, Python 3.12, 격리 설치",
    "size.pdfminer": "pdfplumber 에 포함",
    "size.docling": "측정하지 않음 (용량이 큼, torch)",
    "license.custom": "알 수 없음 (사용자 파서)",
    "hint.pymupdf4llm": "uv pip install pymupdf4llm; AGPL-3.0 이므로 조건을 확인하십시오",
    "note.pypdf": "순수 Python. 콘텐츠 스트림 순서대로 텍스트를 뽑고 구조는 없음",
    "note.pdfplumber": "위치 기준 텍스트 + GFM 표 (pypdfium2, pdfminer.six 포함)",
    "note.pdfminer": "레이아웃 상자 단위 텍스트. markitdown 의 PDF 경로는 pdfminer 텍스트 추출",
    "note.markitdown": "용량 대부분은 onnxruntime. 쪽 단위로 변환 (쪽마다 한 번)",
    "note.pymupdf4llm": "직접 설치했을 때만 감지. parseoff 의 extra 가 아님",
    "note.docling": "실험적",
    "finding.cannot_open": "PDF 를 열 수 없습니다: {error}",
    "finding.empty_layer": "이 쪽에는 텍스트 레이어가 없습니다 (스캔 또는 이미지뿐). OCR 이 필요하며 텍스트 파서는 아무것도 반환하지 않습니다",
    "finding.low_coverage": "텍스트 레이어 단어 중 {coverage:.0%}만 나타납니다 (기준 {threshold:.0%})",
    "finding.low_agreement": "파서 사이의 단어 순서 일치도가 낮습니다: {a} / {b}, 일치도 {value:.2f} (기준 {threshold:.2f}). 이 쪽을 직접 확인하십시오",
    "finding.boilerplate": "여러 쪽에 같은 줄이 반복됩니다 (예: \"{example}\", 줄 비율: {share}). "
                           "머리글·바닥글이 RAG 청크를 오염시킵니다",
    "finding.copyleft": "카피레프트 라이선스입니다. 소프트웨어 배포 방식에 맞는지 확인하십시오: {license}",
    "finding.weights": "모델 가중치에 상업적 사용 제한이 있습니다",
    "finding.model_download": "모델이 없으면 처음 실행할 때 내려받습니다 ({state}). "
                              "오프라인에서는 DOCLING_ARTIFACTS_PATH 를 지정하십시오",
    "finding.models_found": "로컬에 모델 있음",
    "finding.models_missing": "로컬에 모델 없음",
    "finding.heavy": "설치 크기 약 {size} (조사 값이며 환경에 따라 다를 수 있음)",
    "finding.no_item": "{label} 없음 ({best} 에서는 {count}개 찾음)",
    "finding.and": ", ",
    "finding.flattened": "{items}. 구조가 평탄화되었을 수 있습니다",
    "label.tables": "표",
    "label.headings": "제목",
    "notice": "이 출력에는 문서에서 가져온 텍스트가 들어 있습니다. parseoff 는 네트워크로 아무것도 보내지 않습니다.",
    "notice.demo": "연습(목) 모드: 샘플 PDF 는 합성이지만 파서는 실제입니다.",
    "tbl.parser": "파서",
    "tbl.version": "버전",
    "tbl.license": "라이선스",
    "tbl.status": "상태",
    "tbl.document": "문서",
    "tbl.seconds": "초",
    "tbl.coverage": "평균 커버리지",
    "tbl.tables": "표",
    "tbl.headings": "제목",
    "tbl.tokens": "추정 토큰",
    "html.title": "parseoff 리포트",
    "html.parsers": "파서",
    "html.size_head": "설치 크기 ({survey})",
    "html.ran": "실행됨",
    "html.skipped": "건너뜀: {reason}",
    "html.docs": "문서 x 파서",
    "html.cannot_open_row": "열 수 없음: {error}",
    "html.tokens_note": "토큰 수는 추정값입니다 (글자 수 / 4).",
    "html.agreement": "파서 간 일치도 (단어 순서 유사도 평균)",
    "html.findings": "발견 사항",
    "html.no_findings": "발견 사항이 없습니다.",
    "html.back": "개요로 돌아가기",
    "html.cannot_open": "이 PDF 를 열 수 없습니다: {error}",
    "html.docinfo": "sha256 {sha}..., 전체 {total}쪽, 분석 {analysed}쪽",
    "html.no_stderr": "(stderr 없음)",
    "html.page": "{page}쪽",
    "html.page_alt": "{page}쪽",
    "html.layer": "텍스트 레이어: {chars}자",
    "html.agreement_row": "일치도: {pairs}",
    "html.original": "원본",
    "html.page_metrics": "글자 {chars}, 커버리지 {coverage}, 표 {tables}, 제목 {headings}",
    "where.page": " {page}쪽",
    "md.title": "parseoff 요약",
    "md.parsers": "파서",
    "md.size_head": "설치 크기 (조사 값)",
    "md.ran": "실행됨",
    "md.skipped": "건너뜀 - {reason}",
    "md.documents": "문서",
    "md.findings": "발견 사항",
    "md.no_findings": "발견 사항이 없습니다.",
    "md.foot": "토큰 수는 추정값입니다 (글자 수 / 4). 설치 크기: {survey}.",
}

# argparse prints these fixed sentences itself (Python's gettext catalogue has no Korean entry for
# parseoff's tone), so they are mapped here by their English text.
_ARGPARSE_KO: dict[str, str] = {
    "usage: ": "사용법: ",
    "positional arguments": "위치 인자",
    "options": "옵션",
    "subcommands": "하위 명령",
    "show this help message and exit": "이 도움말을 보여 주고 끝냅니다",
    "show program's version number and exit": "버전을 보여 주고 끝냅니다",
    "%(prog)s: error: %(message)s\n": "%(prog)s: 오류: %(message)s\n",
    "the following arguments are required: %s": "다음 인자가 필요합니다: %s",
    "unrecognized arguments: %s": "알 수 없는 인자입니다: %s",
    "invalid choice: %(value)r (choose from %(choices)s)": "선택할 수 없는 값입니다: %(value)r (선택지: %(choices)s)",
    "unknown parser %(parser_name)r (choices: %(choices)s)": "알 수 없는 명령입니다: %(parser_name)r (선택지: %(choices)s)",
    "argument %(argument_name)s: %(message)s": "인자 %(argument_name)s: %(message)s",
    "expected one argument": "값이 하나 필요합니다",
    "expected at least one argument": "값이 하나 이상 필요합니다",
    "expected at most one argument": "값은 최대 하나만 쓸 수 있습니다",
    "invalid %(type)s value: %(value)r": "%(type)s 값이 올바르지 않습니다: %(value)r",
    "ambiguous option: %(option)s could match %(matches)s": "모호한 옵션입니다: %(option)s (후보: %(matches)s)",
    "ignored explicit argument %r": "값을 받지 않는 옵션에 값이 지정되었습니다: %r",
    "not allowed with argument %s": "다음 인자와 함께 쓸 수 없습니다: %s",
    "one of the arguments %s is required": "다음 인자 중 하나가 필요합니다: %s",
    "unexpected option string: %s": "예상하지 못한 옵션입니다: %s",
}

MESSAGES: dict[str, dict[str, str]] = {
    "en": {**_EN, **{f"argparse:{k}": k for k in _ARGPARSE_KO}},
    "ko": {**_KO, **{f"argparse:{k}": v for k, v in _ARGPARSE_KO.items()}},
}


def normalize(value: str | None) -> str | None:
    """Map a raw value (``ko``, ``ko_KR.UTF-8``, ``en_US`` ...) to ``ko``/``en``; None if empty."""
    if value is None or not value.strip():
        return None
    return "ko" if value.strip().lower().startswith("ko") else "en"


def resolve_lang(cli_value: str | None = None, env: Mapping[str, str] | None = None) -> str:
    """Pick the screen language: --lang, then PARSEOFF_LANG, then the first set locale variable."""
    env = os.environ if env is None else env
    if cli_value in LANGS:
        return str(cli_value)
    for name in (ENV_VAR, "LC_ALL", "LC_MESSAGES", "LANG"):
        found = normalize(env.get(name))
        if found:
            return found
    return DEFAULT_LANG


def t(key: str, lang: str = DEFAULT_LANG, **params: object) -> str:
    """Look up a message and fill its placeholders. Unknown language -> English."""
    table = MESSAGES.get(lang, MESSAGES[DEFAULT_LANG])
    text = table.get(key)
    if text is None:
        text = MESSAGES[DEFAULT_LANG][key]
    return text.format(**params) if params else text


@contextlib.contextmanager
def argparse_language(lang: str) -> Iterator[None]:
    """Make argparse's own fixed sentences (usage:, options, error ...) use `lang` while active."""
    if lang == DEFAULT_LANG:
        yield
        return
    table = MESSAGES[lang]
    original = argparse._  # type: ignore[attr-defined]

    def translate(msgid: str) -> str:
        return table.get(f"argparse:{msgid}", original(msgid))

    argparse._ = translate  # type: ignore[attr-defined]
    try:
        yield
    finally:
        argparse._ = original  # type: ignore[attr-defined]


class LocalizedError(Exception):
    """An error that keeps its message key and parameters so it can be shown in any language.

    ``str(error)`` is always English; call ``error.text(lang)`` for the screen language.
    """

    def __init__(self, key: str, **params: object) -> None:
        self.key = key
        self.params = params
        super().__init__(t(key, DEFAULT_LANG, **params))

    def text(self, lang: str = DEFAULT_LANG) -> str:
        return t(self.key, lang, **self.params)
