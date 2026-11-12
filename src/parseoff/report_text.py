"""summary.json and summary.md. No timestamps, no absolute paths, sorted keys: diff-friendly."""

from __future__ import annotations

import json

from . import __version__
from .findings import message_for, skip_reason
from .i18n import DEFAULT_LANG, t
from .model import RunReport
from .registry import REGISTRY, SURVEY_NOTE, installed_version, size_text, survey_note

NOTICE = "This output contains text from your documents. parseoff sends nothing over the network."
DEMO_NOTICE = "Practice (mock) mode: synthetic sample PDFs, but the parsers are real."


def _r(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _pair(pair: tuple[str, str]) -> str:
    return f"{pair[0]} | {pair[1]}"


def build_summary(report: RunReport) -> dict:
    parsers = []
    for name in report.parsers:
        info = REGISTRY.get(name)
        parsers.append({
            "name": name, "status": "ran",
            "version": installed_version(name) if info else "custom",
            "license": info.license if info else "unknown (custom)",
            "install_size_surveyed": info.size_text if info else None,
        })
    parsers += [{"name": s.name, "status": "skipped", "reason": s.reason} for s in report.skipped]

    docs = []
    for doc in report.docs:
        entry: dict = {
            "id": doc.doc_id, "sha256": doc.sha256, "total_pages": doc.total_pages,
            "analyzed_pages": doc.pages, "text_layer_chars": doc.layer_chars,
        }
        if doc.open_error:
            entry["error"] = doc.open_error
        per_parser = {}
        for name, out in doc.outputs.items():
            item: dict = {"status": out.status, "version": out.version, "seconds": round(out.seconds, 3)}
            if out.error:
                item["error"] = out.error
            pm = doc.metrics.parsers.get(name) if doc.metrics else None
            if pm:
                item.update({
                    "mean_coverage": _r(pm.mean_coverage),
                    "boilerplate_ratio": _r(pm.boilerplate_ratio),
                    "pages": [
                        {"page": p, "chars": m.chars, "tokens_est": m.tokens_est,
                         "coverage": _r(m.coverage), "tables": m.tables, "headings": m.headings}
                        for p, m in zip(doc.pages, pm.pages)
                    ],
                })
            per_parser[name] = item
        entry["parsers"] = per_parser
        if doc.metrics:
            entry["agreement"] = {
                _pair(pair): {
                    "mean": _r(mean),
                    "pages": {str(p): _r(doc.metrics.agreement[p][pair]) for p in doc.pages},
                }
                for pair, mean in doc.metrics.mean_agreement.items()
            }
        docs.append(entry)

    return {
        "parseoff_version": __version__,
        "mode": "demo" if report.demo else "run",
        "notes": {"tokens_est": "characters / 4, an estimate", "install_size": SURVEY_NOTE},
        "thresholds": {"min_coverage": report.thresholds.min_coverage, "min_agreement": report.thresholds.min_agreement},
        "counts": report.counts(),
        "parsers": parsers,
        "documents": docs,
        "findings": [
            {"code": f.code, "level": f.level, "doc": f.doc, "page": f.page, "parser": f.parser, "message": f.message}
            for f in report.findings
        ],
    }


def summary_json(report: RunReport) -> str:
    return json.dumps(build_summary(report), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _md(value: object) -> str:
    """One-line, pipe-safe text for a Markdown table cell."""
    return " ".join(str(value).split()).replace("|", "\\|")


def _cell(value: float | None, pct: bool = False) -> str:
    if value is None:
        return "-"
    return f"{value:.0%}" if pct else f"{value:.2f}"


def summary_markdown(report: RunReport, lang: str = DEFAULT_LANG) -> str:
    """summary.md in the screen language. Numbers, parser names and finding codes never change."""
    c = report.counts()
    lines = [f"# {t('md.title', lang)}", ""]
    lines.append(f"> {t('notice.demo' if report.demo else 'notice', lang)}")
    lines += ["", f"FAIL {c['FAIL']}, WARN {c['WARN']}, INFO {c['INFO']}", "", f"## {t('md.parsers', lang)}", ""]
    heads = [t("tbl.parser", lang), t("tbl.version", lang), t("tbl.license", lang), t("md.size_head", lang), t("tbl.status", lang)]
    lines += ["| " + " | ".join(heads) + " |", "|---|---|---|---|---|"]
    skipped = {s.name: s for s in report.skipped}
    for p in build_summary(report)["parsers"]:
        if p["status"] == "ran":
            status = t("md.ran", lang)
        else:
            status = t("md.skipped", lang, reason=skip_reason(skipped[p["name"]], lang))
        info = REGISTRY.get(p["name"])
        license_ = p.get("license", "-") if info or p["status"] != "ran" else t("license.custom", lang)
        size = (size_text(p["name"], lang) if info and p["status"] == "ran" else None) or "-"
        lines.append(f"| {_md(p['name'])} | {p.get('version') or '-'} | {_md(license_)} | {_md(size)} | {_md(status)} |")
    lines += ["", f"## {t('md.documents', lang)}", ""]
    heads = [t(f"tbl.{k}", lang) for k in ("document", "parser", "status", "seconds", "coverage", "tables", "headings", "tokens")]
    lines += ["| " + " | ".join(heads) + " |", "|---|---|---|---|---|---|---|---|"]
    for doc in report.docs:
        for name, out in doc.outputs.items():
            pm = doc.metrics.parsers.get(name) if doc.metrics else None
            tables = sum(m.tables for m in pm.pages) if pm else "-"
            heads_n = sum(m.headings for m in pm.pages) if pm else "-"
            toks = sum(m.tokens_est for m in pm.pages) if pm else "-"
            cov = _cell(pm.mean_coverage, pct=True) if pm else "-"
            lines.append(f"| {_md(doc.doc_id)} | {_md(name)} | {out.status} | {out.seconds:.2f} | {cov} | {tables} | {heads_n} | {toks} |")
    lines += ["", f"## {t('md.findings', lang)}", ""]
    if not report.findings:
        lines.append(t("md.no_findings", lang))
    for f in report.findings:
        where = " ".join(x for x in (f.doc, f"p{f.page}" if f.page else None, f.parser) if x)
        lines.append(f"- **{f.level}** `{f.code}` {_md(where)}: {_md(message_for(f, lang))}")
    lines += ["", t("md.foot", lang, survey=survey_note(lang)), ""]
    return "\n".join(lines)
