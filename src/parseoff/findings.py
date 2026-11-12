"""Turn metrics, parser status and registry facts into a flat list of findings.

Levels: FAIL = something is broken or unusable, WARN = look at it before choosing, INFO = good to know.
Rules (code -> level):
  FAIL  PARSER_ERROR, TIMEOUT, EMPTY_TEXT_LAYER, LOW_COVERAGE
  WARN  LOW_AGREEMENT, BOILERPLATE, LICENSE_COPYLEFT, LICENSE_WEIGHTS, MODEL_DOWNLOAD, HEAVY_INSTALL
  INFO  NO_STRUCTURE, SKIPPED

Every finding keeps an English ``message`` (this is what summary.json stores, so it never depends on
the screen language) plus a message ``key`` and ``params``. ``message_for(finding, lang)`` builds the
same sentence in the screen language for the terminal, HTML report and summary.md.
"""

from __future__ import annotations

from .i18n import DEFAULT_LANG, t
from .metrics import BOILERPLATE_MIN_RATIO
from .model import FAIL, INFO, LEVELS, WARN, DocReport, Finding, RunReport, Skipped
from .registry import HEAVY_INSTALL_MB, REGISTRY, docling_models_present, install_hint, size_text


def _render(key: str, params: dict, lang: str) -> str:
    """Build one finding sentence. Language independent params, language dependent words."""
    if key == "finding.no_item" and "parts" in params:  # NO_STRUCTURE: one or two parts
        items = t("finding.and", lang).join(
            t("finding.no_item", lang, label=t(f"label.{label}", lang), best=best, count=count)
            for label, best, count in params["parts"]
        )
        return t("finding.flattened", lang, items=items)
    if key == "finding.model_download":
        state = t("finding.models_found" if params["found"] else "finding.models_missing", lang)
        return t(key, lang, state=state)
    if key == "skip.not_installed":
        hint = install_hint(params["name"], lang) or t("skip.install_first", lang)
        return t(key, lang, hint=hint)
    if key == "finding.heavy":
        return t(key, lang, size=size_text(params["name"], lang))
    return t(key, lang, **params)


def message_for(finding: Finding, lang: str = DEFAULT_LANG) -> str:
    """The finding's message in `lang`. Messages without a key (text from a parser) stay as they are."""
    if lang == DEFAULT_LANG or not finding.key:
        return finding.message
    return _render(finding.key, finding.params, lang)


def skip_reason(skip: Skipped, lang: str = DEFAULT_LANG) -> str:
    """Why a parser was skipped, in `lang` (the English text is `skip.reason`)."""
    if lang == DEFAULT_LANG or not skip.key:
        return skip.reason
    return _render(skip.key, skip.params, lang)


def _make(code: str, level: str, key: str, params: dict, doc: str | None = None,
          page: int | None = None, parser: str | None = None) -> Finding:
    return Finding(code, level, _render(key, params, DEFAULT_LANG), doc, page, parser, key, params)


def _structure_findings(doc: DocReport) -> list[Finding]:
    """NO_STRUCTURE: a parser found no tables/headings although another parser did."""
    out: list[Finding] = []
    if not doc.metrics:
        return out
    totals = {
        name: (sum(p.tables for p in pm.pages), sum(p.headings for p in pm.pages))
        for name, pm in doc.metrics.parsers.items()
    }
    for name in totals:
        missing = []
        for idx, label in ((0, "tables"), (1, "headings")):
            donors = {n: t_[idx] for n, t_ in totals.items() if n != name and t_[idx] > 0}
            if totals[name][idx] == 0 and donors:
                best = max(sorted(donors), key=lambda n: donors[n])
                missing.append((label, best, donors[best]))
        if missing:
            out.append(_make("NO_STRUCTURE", INFO, "finding.no_item", {"parts": missing}, doc.doc_id, None, name))
    return out


def build_findings(report: RunReport) -> list[Finding]:
    th = report.thresholds
    found: list[Finding] = []

    for doc in report.docs:
        if doc.open_error:
            found.append(_make("PARSER_ERROR", FAIL, "finding.cannot_open", {"error": doc.open_error}, doc.doc_id))
            continue
        for page, chars in zip(doc.pages, doc.layer_chars):
            if chars == 0:
                found.append(_make("EMPTY_TEXT_LAYER", FAIL, "finding.empty_layer", {}, doc.doc_id, page))
        for name, out in doc.outputs.items():
            if out.status in ("timeout", "error"):
                code = "TIMEOUT" if out.status == "timeout" else "PARSER_ERROR"
                # the text comes from the parser or from parseoff itself; only our own is translatable
                found.append(Finding(code, FAIL, out.error, doc.doc_id, None, name, out.error_key, dict(out.error_params)))
        if not doc.metrics:
            continue
        for name, pm in doc.metrics.parsers.items():
            for page, m in zip(doc.pages, pm.pages):
                if m.coverage is not None and m.coverage < th.min_coverage:
                    found.append(_make(
                        "LOW_COVERAGE", FAIL, "finding.low_coverage",
                        {"coverage": m.coverage, "threshold": th.min_coverage}, doc.doc_id, page, name,
                    ))
        for page, pairs in doc.metrics.agreement.items():
            values = {pair: v for pair, v in pairs.items() if v is not None}
            if values:
                pair = min(sorted(values), key=lambda p: values[p])
                if values[pair] < th.min_agreement:
                    found.append(_make(
                        "LOW_AGREEMENT", WARN, "finding.low_agreement",
                        {"a": pair[0], "b": pair[1], "value": values[pair], "threshold": th.min_agreement},
                        doc.doc_id, page,
                    ))
        repeated = {
            n: pm for n, pm in doc.metrics.parsers.items() if pm.boilerplate_ratio >= BOILERPLATE_MIN_RATIO
        }
        if repeated:
            top = max(sorted(repeated), key=lambda n: repeated[n].boilerplate_ratio)
            share = ", ".join(f"{n} {pm.boilerplate_ratio:.0%}" for n, pm in sorted(repeated.items()))
            found.append(_make(
                "BOILERPLATE", WARN, "finding.boilerplate",
                {"example": repeated[top].boilerplate_example, "share": share}, doc.doc_id,
            ))
        found += _structure_findings(doc)

    for name in report.parsers:
        info = REGISTRY.get(name)
        if info is None:  # custom parser: nothing is known about it
            continue
        if info.copyleft:
            found.append(_make("LICENSE_COPYLEFT", WARN, "finding.copyleft", {"license": info.license}, parser=name))
        if info.weights_restricted:
            found.append(_make("LICENSE_WEIGHTS", WARN, "finding.weights", {}, parser=name))
        if info.model_download:
            found.append(_make(
                "MODEL_DOWNLOAD", WARN, "finding.model_download", {"found": docling_models_present()}, parser=name,
            ))
        if info.size_mb is not None and info.size_mb >= HEAVY_INSTALL_MB:
            found.append(_make("HEAVY_INSTALL", WARN, "finding.heavy", {"name": name}, parser=name))
    for skip in report.skipped:
        found.append(Finding("SKIPPED", INFO, skip.reason, None, None, skip.name, skip.key, dict(skip.params)))

    rank = {lvl: i for i, lvl in enumerate(LEVELS)}
    return sorted(found, key=lambda f: (rank[f.level], f.code, f.doc or "", f.page or 0, f.parser or "", f.message))
