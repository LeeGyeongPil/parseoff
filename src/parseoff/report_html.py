"""Static HTML report: index.html plus one doc-<slug>.html per PDF.

Self-contained: inline CSS, no scripts, no external resources. Every piece of text that comes from a
document or a parser goes through html.escape. Page images are relative links to img/*.png.
The screen language is fixed when the report is written (``<html lang>`` follows it).
"""

from __future__ import annotations

from html import escape

from .findings import message_for, skip_reason
from .i18n import DEFAULT_LANG, t
from .model import DocReport, Finding, RunReport
from .registry import REGISTRY, installed_version, size_text, survey_note

CSS = """
body{font-family:system-ui,sans-serif;margin:24px;color:#1b1f24;background:#fff}
h1,h2{margin:.6em 0 .3em} table{border-collapse:collapse;margin:8px 0}
th,td{border:1px solid #c9d1d9;padding:4px 8px;text-align:left;font-size:14px;vertical-align:top}
th{background:#f3f4f6} .notice{background:#fff8c5;border:1px solid #d4a72c;padding:8px 12px;margin:8px 0}
.badge{display:inline-block;border-radius:4px;padding:0 6px;font-size:12px;font-weight:600;margin-right:4px}
.FAIL{background:#ffd7d5;color:#82071e}.WARN{background:#fff1c2;color:#6a4b00}.INFO{background:#ddf4ff;color:#0a3069}
.page{border-top:2px solid #8c959f;margin-top:18px;padding-top:6px}
.grid{display:flex;gap:12px;align-items:flex-start;overflow-x:auto}
.col{min-width:260px;flex:1 1 260px;max-width:520px}.img img{max-width:340px;border:1px solid #c9d1d9}
pre{background:#f6f8fa;border:1px solid #d0d7de;padding:8px;white-space:pre-wrap;word-break:break-word;font-size:12px}
.muted{color:#57606a;font-size:13px} details{margin:4px 0}
"""


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.0%}"


def _badge(f: Finding, lang: str) -> str:
    return f'<span class="badge {f.level}" title="{_e(message_for(f, lang))}">{_e(f.code)}</span>'


def _page(title: str, body: str, lang: str) -> str:
    return (
        f'<!doctype html>\n<html lang="{_e(lang)}"><head><meta charset="utf-8">'
        f"<title>{_e(title)}</title><style>{CSS}</style></head><body>\n{body}\n</body></html>\n"
    )


def _notice(report: RunReport, lang: str) -> str:
    return f'<div class="notice">{_e(t("notice.demo" if report.demo else "notice", lang))}</div>'


def _finding_li(f: Finding, slug_of: dict[str, str], lang: str) -> str:
    where = []
    if f.doc:
        label = f.doc + (t("where.page", lang, page=f.page) if f.page else "")
        link = f"doc-{slug_of[f.doc]}.html" + (f"#p{f.page}" if f.page else "")
        where.append(f'<a href="{_e(link)}">{_e(label)}</a>')
    if f.parser:
        where.append(_e(f.parser))
    return f"<li>{_badge(f, lang)} {' / '.join(where)} {_e(message_for(f, lang))}</li>"


def render_index(report: RunReport, lang: str = DEFAULT_LANG) -> str:
    c = report.counts()
    slug_of = {d.doc_id: d.slug for d in report.docs}
    parts = [f"<h1>{_e(t('html.title', lang))}</h1>", _notice(report, lang)]
    parts.append(
        f'<p><span class="badge FAIL">FAIL {c["FAIL"]}</span><span class="badge WARN">WARN {c["WARN"]}</span>'
        f'<span class="badge INFO">INFO {c["INFO"]}</span></p>'
    )

    th = lambda key: f"<th>{_e(t(key, lang))}</th>"  # noqa: E731 - tiny local helper
    parts.append(f"<h2>{_e(t('html.parsers', lang))}</h2><table><tr>{th('tbl.parser')}{th('tbl.version')}{th('tbl.license')}"
                 f"<th>{_e(t('html.size_head', lang, survey=survey_note(lang)))}</th>{th('tbl.status')}</tr>")
    for name in report.parsers:
        info = REGISTRY.get(name)
        parts.append(
            f"<tr><td>{_e(name)}</td><td>{_e(installed_version(name) if info else 'custom')}</td>"
            f"<td>{_e(info.license if info else t('license.custom', lang))}</td>"
            f"<td>{_e(size_text(name, lang) if info else '-')}</td><td>{_e(t('html.ran', lang))}</td></tr>"
        )
    for s in report.skipped:
        parts.append(f"<tr><td>{_e(s.name)}</td><td>-</td><td>{_e(REGISTRY[s.name].license)}</td>"
                     f"<td>{_e(size_text(s.name, lang))}</td>"
                     f"<td>{_e(t('html.skipped', lang, reason=skip_reason(s, lang)))}</td></tr>")
    parts.append("</table>")

    parts.append(f"<h2>{_e(t('html.docs', lang))}</h2><table><tr>"
                 + "".join(th(f"tbl.{k}") for k in ("document", "parser", "status", "seconds", "coverage", "tables", "headings", "tokens"))
                 + "</tr>")
    for doc in report.docs:
        link = f'<a href="doc-{_e(doc.slug)}.html">{_e(doc.doc_id)}</a>'
        if doc.open_error:
            parts.append(f"<tr><td>{link}</td><td colspan=\"7\">{_e(t('html.cannot_open_row', lang, error=doc.open_error))}</td></tr>")
        for name, out in doc.outputs.items():
            pm = doc.metrics.parsers.get(name) if doc.metrics else None
            cells = ("-", "-", "-", "-")
            if pm:
                cells = (_pct(pm.mean_coverage), str(sum(m.tables for m in pm.pages)),
                         str(sum(m.headings for m in pm.pages)), str(sum(m.tokens_est for m in pm.pages)))
            parts.append(
                f"<tr><td>{link}</td><td>{_e(name)}</td><td>{_e(out.status)}</td><td>{out.seconds:.2f}</td>"
                + "".join(f"<td>{_e(x)}</td>" for x in cells) + "</tr>"
            )
    parts.append(f"</table><p class=\"muted\">{_e(t('html.tokens_note', lang))}</p>")

    parts.append(f"<h2>{_e(t('html.agreement', lang))}</h2>")
    for doc in report.docs:
        if not doc.metrics or not doc.metrics.mean_agreement:
            continue
        names = list(doc.metrics.parsers)
        parts.append(f"<h3>{_e(doc.doc_id)}</h3><table><tr><th></th>" + "".join(f"<th>{_e(n)}</th>" for n in names) + "</tr>")
        for a in names:
            row = []
            for b in names:
                if a == b:
                    row.append("1.00")
                else:
                    v = doc.metrics.mean_agreement.get((a, b), doc.metrics.mean_agreement.get((b, a)))
                    row.append("-" if v is None else f"{v:.2f}")
            parts.append(f"<tr><th>{_e(a)}</th>" + "".join(f"<td>{r}</td>" for r in row) + "</tr>")
        parts.append("</table>")

    parts.append(f"<h2>{_e(t('html.findings', lang))}</h2>")
    parts.append("<ul>" + "".join(_finding_li(f, slug_of, lang) for f in report.findings) + "</ul>" if report.findings
                 else f"<p>{_e(t('html.no_findings', lang))}</p>")
    return _page(t("html.title", lang), "\n".join(parts), lang)


def render_doc(report: RunReport, doc: DocReport, lang: str = DEFAULT_LANG) -> str:
    parts = [f"<h1>{_e(doc.doc_id)}</h1>", f'<p><a href="index.html">{_e(t("html.back", lang))}</a></p>', _notice(report, lang)]
    if doc.open_error:
        parts.append(f"<p>{_e(t('html.cannot_open', lang, error=doc.open_error))}</p>")
        return _page(doc.doc_id, "\n".join(parts), lang)
    doc_findings = [f for f in report.findings if f.doc == doc.doc_id]
    parts.append(f'<p class="muted">{_e(t("html.docinfo", lang, sha=doc.sha256[:16], total=doc.total_pages, analysed=len(doc.pages)))}</p>')
    parts.append("<p>" + " ".join(_badge(f, lang) for f in doc_findings if f.page is None) + "</p>")
    for name, out in doc.outputs.items():
        if out.status != "ok" or out.stderr:
            shown = t(out.error_key, lang, **out.error_params) if out.error_key else out.error
            parts.append(
                f"<details><summary>{_e(name)}: {_e(out.status)} {_e(shown)}</summary>"
                f"<pre>{_e(out.stderr or t('html.no_stderr', lang))}</pre></details>"
            )
    for idx, page in enumerate(doc.pages):
        page_findings = [f for f in doc_findings if f.page == page]
        parts.append(f'<div class="page" id="p{page}"><h2>{_e(t("html.page", lang, page=page))}</h2>')
        parts.append("<p>" + " ".join(_badge(f, lang) for f in page_findings)
                     + f" <span class=\"muted\">{_e(t('html.layer', lang, chars=doc.layer_chars[idx]))}</span></p>")
        if doc.metrics and doc.metrics.agreement.get(page):
            pairs = ", ".join(
                f"{a}/{b} {v:.2f}" for (a, b), v in doc.metrics.agreement[page].items() if v is not None
            )
            if pairs:
                parts.append(f'<p class="muted">{_e(t("html.agreement_row", lang, pairs=pairs))}</p>')
        parts.append('<div class="grid">')
        if doc.rendered:
            parts.append(f'<div class="col img"><b>{_e(t("html.original", lang))}</b><br><img src="img/{_e(doc.slug)}-p{page}.png" alt="{_e(t("html.page_alt", lang, page=page))}"></div>')
        for name, out in doc.outputs.items():
            pm = doc.metrics.parsers.get(name) if doc.metrics else None
            meta = ""
            if pm:
                m = pm.pages[idx]
                meta = ("<div class=\"muted\">"
                        + _e(t("html.page_metrics", lang, chars=m.chars, coverage=_pct(m.coverage), tables=m.tables, headings=m.headings))
                        + "</div>")
            text = out.pages[idx] if out.status == "ok" and idx < len(out.pages) else f"({out.status})"
            parts.append(f'<div class="col"><b>{_e(name)}</b>{meta}<pre>{_e(text)}</pre></div>')
        parts.append("</div></div>")
    return _page(doc.doc_id, "\n".join(parts), lang)
