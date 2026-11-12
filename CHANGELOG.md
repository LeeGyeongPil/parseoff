# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-11-13

### Added
- English and Korean screen language. Pick it with `--lang en|ko` (accepted before or after the command), the `PARSEOFF_LANG` environment variable, or the locale (`LC_ALL`, `LC_MESSAGES`, `LANG`, first one that is set); anything that does not start with `ko` means English.
- Translated: `--help` of every command (including argparse's own `usage:`, `options` and error sentences), argument errors, usage errors, the progress and summary lines of `run` and `demo`, the `doctor` table, the HTML report (`<html lang>` follows the chosen language) and `summary.md`.
- `src/parseoff/i18n.py` holds both message tables; tests check that both languages have the same keys and placeholders, that Korean sentences never put a fixed particle after a value, and that switching the language really changes the output.

### Unchanged
- `summary.json` is byte-identical in every language (finding messages stay English), as are finding codes, levels, parser names, exit codes, `--version` and the public Python functions (new `lang` arguments default to English).
- Scripts that compare terminal output or `summary.md` as text can see Korean when the environment locale is Korean: read `summary.json` for machine use, or set `PARSEOFF_LANG=en`.

### Known limitations
- Text that comes from a parser or a PDF library (parser error text, `cannot open` causes, skip reasons of custom code, stderr) stays in its original language.

## [0.1.1] - 2026-11-11

### Fixed
- Install hints for optional parsers now work in a cloned checkout: `uv sync --extra markitdown`, `uv sync --extra docling` and `uv pip install pymupdf4llm` replace the `pip install "parseoff[...]"` and `pip install pymupdf4llm` hints, which failed because parseoff is not on PyPI and the project venv has no pip. Changed in `parseoff doctor`, the `skipped ...` lines, README tables and screenshots.

### Changed
- README: note that syncing extras one at a time removes the earlier ones, and a looser test duration (10-20 s).

### Known limitations
- `parseoff doctor` still shows the install hint on rows of parsers that are already installed.
- `parseoff doctor` reports pymupdf4llm as 0.0 MB on disk (only the thin wrapper package is measured, not pymupdf).
- The demo screenshot `03-demo.png` shows `(cached)` next to parsers because it was captured on a second run; a first run does not show it.

## [0.1.0] - 2026-11-10

### Added
- `parseoff doctor`: installed parsers, real versions, licences, surveyed install sizes and warnings.
- `parseoff run`: run every installed parser on a PDF file or folder, one subprocess per document and parser with a timeout, cached by file hash, parser and version.
- Built-in parsers: pypdf, pdfplumber (tables as GFM), pdfminer.six. Optional, detected when installed: markitdown, pymupdf4llm (AGPL-3.0, never an extra), docling (experimental, opt-in).
- `--custom NAME=module:function` to put your own parser in the same report.
- Metrics without ground truth: coverage against the PDF text layer, pairwise word-order agreement, table and heading counts, repeated header/footer lines, estimated tokens.
- Findings (FAIL / WARN / INFO) and `--strict` exit code for CI.
- Static HTML report with page images next to every parser's output, `summary.json` and `summary.md`.
- `parseoff demo`: three deterministic synthetic PDFs (table, two columns, image-only page) with real parsers.
