"""Static HTML report: index.html plus one doc-<slug>.html per PDF.

Self-contained: inline CSS, no scripts, no external resources. Every piece of text that comes from a
document or a parser goes through html.escape. Page images are relative links to img/*.png.
"""

from __future__ import annotations

from html import escape

from .model import DocReport, Finding, RunReport
from .registry import REGISTRY, SURVEY_NOTE, installed_version
from .report_text import DEMO_NOTICE, NOTICE

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


def _badge(f: Finding) -> str:
    return f'<span class="badge {f.level}" title="{_e(f.message)}">{_e(f.code)}</span>'


def _page(title: str, body: str) -> str:
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        f"<title>{_e(title)}</title><style>{CSS}</style></head><body>\n{body}\n</body></html>\n"
    )


def _notice(report: RunReport) -> str:
    text = DEMO_NOTICE if report.demo else NOTICE
    return f'<div class="notice">{_e(text)}</div>'


def _finding_li(f: Finding, slug_of: dict[str, str]) -> str:
    where = []
    if f.doc:
        label = f.doc + (f" page {f.page}" if f.page else "")
        link = f"doc-{slug_of[f.doc]}.html" + (f"#p{f.page}" if f.page else "")
        where.append(f'<a href="{_e(link)}">{_e(label)}</a>')
    if f.parser:
        where.append(_e(f.parser))
    return f"<li>{_badge(f)} {' / '.join(where)} {_e(f.message)}</li>"


def render_index(report: RunReport) -> str:
    c = report.counts()
    slug_of = {d.doc_id: d.slug for d in report.docs}
    parts = ["<h1>parseoff report</h1>", _notice(report)]
    parts.append(
        f'<p><span class="badge FAIL">FAIL {c["FAIL"]}</span><span class="badge WARN">WARN {c["WARN"]}</span>'
        f'<span class="badge INFO">INFO {c["INFO"]}</span></p>'
    )

    parts.append("<h2>Parsers</h2><table><tr><th>parser</th><th>version</th><th>license</th>"
                 f"<th>install size ({_e(SURVEY_NOTE)})</th><th>status</th></tr>")
    for name in report.parsers:
        info = REGISTRY.get(name)
        parts.append(
            f"<tr><td>{_e(name)}</td><td>{_e(installed_version(name) if info else 'custom')}</td>"
            f"<td>{_e(info.license if info else 'unknown (custom)')}</td>"
            f"<td>{_e(info.size_text if info else '-')}</td><td>ran</td></tr>"
        )
    for s in report.skipped:
        parts.append(f"<tr><td>{_e(s.name)}</td><td>-</td><td>{_e(REGISTRY[s.name].license)}</td>"
                     f"<td>{_e(REGISTRY[s.name].size_text)}</td><td>skipped: {_e(s.reason)}</td></tr>")
    parts.append("</table>")

    parts.append("<h2>Documents x parsers</h2><table><tr><th>document</th><th>parser</th><th>status</th>"
                 "<th>seconds</th><th>mean coverage</th><th>tables</th><th>headings</th><th>est. tokens</th></tr>")
    for doc in report.docs:
        link = f'<a href="doc-{_e(doc.slug)}.html">{_e(doc.doc_id)}</a>'
        if doc.open_error:
            parts.append(f"<tr><td>{link}</td><td colspan=\"7\">cannot open: {_e(doc.open_error)}</td></tr>")
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
    parts.append("</table><p class=\"muted\">Token counts are estimates (characters / 4).</p>")

    parts.append("<h2>Agreement between parsers (mean word-order similarity)</h2>")
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

    parts.append("<h2>Findings</h2>")
    parts.append("<ul>" + "".join(_finding_li(f, slug_of) for f in report.findings) + "</ul>" if report.findings
                 else "<p>No findings.</p>")
    return _page("parseoff report", "\n".join(parts))


def render_doc(report: RunReport, doc: DocReport) -> str:
    parts = [f"<h1>{_e(doc.doc_id)}</h1>", '<p><a href="index.html">back to overview</a></p>', _notice(report)]
    if doc.open_error:
        parts.append(f"<p>Cannot open this PDF: {_e(doc.open_error)}</p>")
        return _page(doc.doc_id, "\n".join(parts))
    doc_findings = [f for f in report.findings if f.doc == doc.doc_id]
    parts.append(f'<p class="muted">sha256 {_e(doc.sha256[:16])}..., {doc.total_pages} page(s), '
                 f"{len(doc.pages)} analysed</p>")
    parts.append("<p>" + " ".join(_badge(f) for f in doc_findings if f.page is None) + "</p>")
    for name, out in doc.outputs.items():
        if out.status != "ok" or out.stderr:
            parts.append(
                f"<details><summary>{_e(name)}: {_e(out.status)} {_e(out.error)}</summary>"
                f"<pre>{_e(out.stderr or '(no stderr)')}</pre></details>"
            )
    for idx, page in enumerate(doc.pages):
        page_findings = [f for f in doc_findings if f.page == page]
        parts.append(f'<div class="page" id="p{page}"><h2>Page {page}</h2>')
        parts.append("<p>" + " ".join(_badge(f) for f in page_findings) + f" <span class=\"muted\">text layer: {doc.layer_chars[idx]} chars</span></p>")
        if doc.metrics and doc.metrics.agreement.get(page):
            pairs = ", ".join(
                f"{a}/{b} {v:.2f}" for (a, b), v in doc.metrics.agreement[page].items() if v is not None
            )
            if pairs:
                parts.append(f'<p class="muted">agreement: {_e(pairs)}</p>')
        parts.append('<div class="grid">')
        if doc.rendered:
            parts.append(f'<div class="col img"><b>original</b><br><img src="img/{_e(doc.slug)}-p{page}.png" alt="page {page}"></div>')
        for name, out in doc.outputs.items():
            pm = doc.metrics.parsers.get(name) if doc.metrics else None
            meta = ""
            if pm:
                m = pm.pages[idx]
                meta = (f"<div class=\"muted\">chars {m.chars}, coverage {_pct(m.coverage)}, "
                        f"tables {m.tables}, headings {m.headings}</div>")
            text = out.pages[idx] if out.status == "ok" and idx < len(out.pages) else f"({out.status})"
            parts.append(f'<div class="col"><b>{_e(name)}</b>{meta}<pre>{_e(text)}</pre></div>')
        parts.append("</div></div>")
    return _page(doc.doc_id, "\n".join(parts))
