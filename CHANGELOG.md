# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
