"""Ground-truth-free metrics: coverage vs the PDF text layer, pairwise agreement, structure counts."""

from __future__ import annotations

import difflib
import itertools
import math
import re
import unicodedata
from collections import Counter

from .model import DocMetrics, PageMetrics, ParserMetrics

# SequenceMatcher is quadratic in the worst case; very long pages are compared on a prefix.
MAX_AGREEMENT_WORDS = 3000
BOILERPLATE_MIN_PAGES = 3
BOILERPLATE_MIN_RATIO = 0.02

_WORD = re.compile(r"\w+", re.UNICODE)
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+\S")


def words(text: str) -> list[str]:
    """NFKC-normalised, case-folded word list. Markdown punctuation (| # * -) is dropped."""
    return _WORD.findall(unicodedata.normalize("NFKC", text).casefold())


def coverage(reference: str, output: str) -> float | None:
    """Share of the text layer's words (multiset) found in the parser output, or None if empty."""
    ref = Counter(words(reference))
    total = sum(ref.values())
    if total == 0:
        return None
    got = Counter(words(output))
    hit = sum(min(count, got[word]) for word, count in ref.items())
    return hit / total


def agreement(a: str, b: str) -> float | None:
    """Word-order similarity in [0, 1] (difflib ratio); None if both are empty."""
    wa, wb = words(a)[:MAX_AGREEMENT_WORDS], words(b)[:MAX_AGREEMENT_WORDS]
    if not wa and not wb:
        return None
    if not wa or not wb:
        return 0.0
    return difflib.SequenceMatcher(None, wa, wb, autojunk=False).ratio()


def count_tables(markdown: str) -> int:
    """Number of GFM tables: runs of `|` lines that contain a `| --- | --- |` separator row."""
    tables, in_table, has_sep = 0, False, False
    for line in markdown.splitlines() + [""]:
        if line.lstrip().startswith("|"):
            in_table = True
            has_sep = has_sep or bool(_TABLE_SEPARATOR.match(line))
        else:
            if in_table and has_sep:
                tables += 1
            in_table, has_sep = False, False
    return tables


def count_headings(markdown: str) -> int:
    return sum(1 for line in markdown.splitlines() if _HEADING.match(line))


def estimate_tokens(text: str) -> int:
    """Rough token estimate (characters / 4). Always an estimate, never a tokenizer result."""
    return math.ceil(len(text) / 4)


def _normalise_line(line: str) -> str:
    line = unicodedata.normalize("NFKC", line).casefold()
    line = re.sub(r"\d+", "#", line)
    return re.sub(r"\s+", " ", line).strip()


def repeated_line_ratio(pages: list[str]) -> tuple[float, str]:
    """Share of lines that repeat on many pages (running headers/footers, page numbers).

    Digits are normalised so "Page 1 of 3" and "Page 2 of 3" count as the same line.
    Returns (ratio, an example of a repeated line, or "").
    """
    if len(pages) < BOILERPLATE_MIN_PAGES:
        return 0.0, ""
    per_page: list[list[str]] = []
    for page in pages:
        lines = [_normalise_line(ln) for ln in page.splitlines()]
        per_page.append([ln for ln in lines if len(ln) >= 4 and not _TABLE_SEPARATOR.match(ln)])
    presence: Counter[str] = Counter()
    for lines in per_page:
        presence.update(set(lines))
    need = max(BOILERPLATE_MIN_PAGES, math.ceil(len(pages) / 2))
    repeated = {ln for ln, n in presence.items() if n >= need}
    total = sum(len(lines) for lines in per_page)
    if total == 0 or not repeated:
        return 0.0, ""
    hits = sum(1 for lines in per_page for ln in lines if ln in repeated)
    example = max(sorted(repeated), key=lambda ln: presence[ln])
    return hits / total, example


def compute_doc_metrics(
    pages: list[int], layer_texts: list[str], outputs: dict[str, list[str]]
) -> DocMetrics:
    """Metrics for one document. `outputs` maps parser -> page texts aligned with `pages`."""
    parsers: dict[str, ParserMetrics] = {}
    for name, texts in outputs.items():
        page_metrics = [
            PageMetrics(
                chars=len(text),
                tokens_est=estimate_tokens(text),
                coverage=coverage(layer, text),
                tables=count_tables(text),
                headings=count_headings(text),
            )
            for layer, text in zip(layer_texts, texts)
        ]
        covs = [m.coverage for m in page_metrics if m.coverage is not None]
        ratio, example = repeated_line_ratio(texts)
        parsers[name] = ParserMetrics(
            pages=page_metrics,
            mean_coverage=sum(covs) / len(covs) if covs else None,
            boilerplate_ratio=ratio,
            boilerplate_example=example,
        )

    per_page: dict[int, dict[tuple[str, str], float | None]] = {}
    sums: dict[tuple[str, str], list[float]] = {}
    for idx, page in enumerate(pages):
        per_page[page] = {}
        for a, b in itertools.combinations(outputs, 2):
            value = agreement(outputs[a][idx], outputs[b][idx])
            per_page[page][(a, b)] = value
            if value is not None:
                sums.setdefault((a, b), []).append(value)
    mean = {
        pair: (sum(sums[pair]) / len(sums[pair]) if pair in sums else None)
        for pair in itertools.combinations(outputs, 2)
    }
    return DocMetrics(parsers=parsers, agreement=per_page, mean_agreement=mean)
