"""Turn metrics, parser status and registry facts into a flat list of findings.

Levels: FAIL = something is broken or unusable, WARN = look at it before choosing, INFO = good to know.
Rules (code -> level):
  FAIL  PARSER_ERROR, TIMEOUT, EMPTY_TEXT_LAYER, LOW_COVERAGE
  WARN  LOW_AGREEMENT, BOILERPLATE, LICENSE_COPYLEFT, LICENSE_WEIGHTS, MODEL_DOWNLOAD, HEAVY_INSTALL
  INFO  NO_STRUCTURE, SKIPPED
"""

from __future__ import annotations

from .metrics import BOILERPLATE_MIN_RATIO
from .model import FAIL, INFO, LEVELS, WARN, DocReport, Finding, RunReport
from .registry import HEAVY_INSTALL_MB, REGISTRY, docling_models_present


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
            donors = {n: t[idx] for n, t in totals.items() if n != name and t[idx] > 0}
            if totals[name][idx] == 0 and donors:
                best = max(sorted(donors), key=lambda n: donors[n])
                missing.append(f"no {label} (but {best} found {donors[best]})")
        if missing:
            out.append(Finding(
                "NO_STRUCTURE", INFO, " and ".join(missing) + ": structure may be flattened",
                doc.doc_id, None, name,
            ))
    return out


def build_findings(report: RunReport) -> list[Finding]:
    th = report.thresholds
    found: list[Finding] = []

    for doc in report.docs:
        if doc.open_error:
            found.append(Finding("PARSER_ERROR", FAIL, f"cannot open the PDF: {doc.open_error}", doc.doc_id))
            continue
        for page, chars in zip(doc.pages, doc.layer_chars):
            if chars == 0:
                found.append(Finding(
                    "EMPTY_TEXT_LAYER", FAIL,
                    "page has no text layer (scan or image only): OCR is needed, text parsers return nothing",
                    doc.doc_id, page,
                ))
        for name, out in doc.outputs.items():
            if out.status == "timeout":
                found.append(Finding("TIMEOUT", FAIL, out.error, doc.doc_id, None, name))
            elif out.status == "error":
                found.append(Finding("PARSER_ERROR", FAIL, out.error, doc.doc_id, None, name))
        if not doc.metrics:
            continue
        for name, pm in doc.metrics.parsers.items():
            for page, m in zip(doc.pages, pm.pages):
                if m.coverage is not None and m.coverage < th.min_coverage:
                    found.append(Finding(
                        "LOW_COVERAGE", FAIL,
                        f"only {m.coverage:.0%} of the text-layer words appear (threshold {th.min_coverage:.0%})",
                        doc.doc_id, page, name,
                    ))
        for page, pairs in doc.metrics.agreement.items():
            values = {pair: v for pair, v in pairs.items() if v is not None}
            if values:
                pair = min(sorted(values), key=lambda p: values[p])
                if values[pair] < th.min_agreement:
                    found.append(Finding(
                        "LOW_AGREEMENT", WARN,
                        f"{pair[0]} and {pair[1]} agree on only {values[pair]:.2f} of the word order "
                        f"(threshold {th.min_agreement:.2f}): look at this page yourself",
                        doc.doc_id, page,
                    ))
        repeated = {
            n: pm for n, pm in doc.metrics.parsers.items() if pm.boilerplate_ratio >= BOILERPLATE_MIN_RATIO
        }
        if repeated:
            top = max(sorted(repeated), key=lambda n: repeated[n].boilerplate_ratio)
            share = ", ".join(f"{n} {pm.boilerplate_ratio:.0%}" for n, pm in sorted(repeated.items()))
            found.append(Finding(
                "BOILERPLATE", WARN,
                f"lines repeat on many pages (e.g. \"{repeated[top].boilerplate_example}\"; share of lines: {share}): "
                "headers/footers will pollute RAG chunks",
                doc.doc_id,
            ))
        found += _structure_findings(doc)

    for name in report.parsers:
        info = REGISTRY.get(name)
        if info is None:  # custom parser: nothing is known about it
            continue
        if info.copyleft:
            found.append(Finding(
                "LICENSE_COPYLEFT", WARN,
                f"{info.license}: copyleft licence, check it fits how you ship your software", parser=name,
            ))
        if info.weights_restricted:
            found.append(Finding("LICENSE_WEIGHTS", WARN, "model weights have commercial-use limits", parser=name))
        if info.model_download:
            state = "models found locally" if docling_models_present() else "models NOT found locally"
            found.append(Finding(
                "MODEL_DOWNLOAD", WARN,
                f"downloads models on first run unless present ({state}); set DOCLING_ARTIFACTS_PATH for offline use",
                parser=name,
            ))
        if info.size_mb is not None and info.size_mb >= HEAVY_INSTALL_MB:
            found.append(Finding(
                "HEAVY_INSTALL", WARN, f"install size about {info.size_text} (surveyed, may differ on your system)",
                parser=name,
            ))
    for skip in report.skipped:
        found.append(Finding("SKIPPED", INFO, skip.reason, parser=skip.name))

    rank = {lvl: i for i, lvl in enumerate(LEVELS)}
    return sorted(found, key=lambda f: (rank[f.level], f.code, f.doc or "", f.page or 0, f.parser or "", f.message))
