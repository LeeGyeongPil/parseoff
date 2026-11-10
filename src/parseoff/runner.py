"""Find PDFs, run every selected parser in a worker subprocess, cache results, compute metrics."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import findings, metrics, textlayer
from .adapters.custom import CustomSpec
from .model import DocReport, ParserOutput, RunReport, Skipped, Thresholds
from .registry import REGISTRY, installed_version, is_installed

CACHE_SCHEMA = 1
STDERR_LIMIT = 2000


class UsageError(Exception):
    """Bad input from the user (exit code 2). The message says how to fix it."""


@dataclass(frozen=True)
class ParserSpec:
    name: str
    custom: CustomSpec | None = None


@dataclass
class RunOptions:
    input_path: Path
    out_dir: Path
    parsers: list[str] | None = None  # None = automatic selection
    customs: list[CustomSpec] = field(default_factory=list)
    max_pages: int | None = None
    timeout: float = 120.0
    fresh: bool = False
    render: bool = True
    thresholds: Thresholds = field(default_factory=Thresholds)
    demo: bool = False


# --- document discovery -------------------------------------------------------------------------


def find_pdfs(path: Path) -> list[tuple[str, Path]]:
    """Return (doc_id, file) pairs sorted by doc_id. doc_id is relative to the input folder."""
    if not path.exists():
        raise UsageError(f"{path}: no such file or folder. Pass a PDF file or a folder that contains PDFs.")
    if path.is_file():
        if path.suffix.lower() != ".pdf":
            raise UsageError(f"{path}: not a .pdf file. Pass a PDF file or a folder that contains PDFs.")
        return [(path.name, path)]
    found = sorted(
        ((p.relative_to(path).as_posix(), p) for p in path.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf"),
        key=lambda pair: pair[0],
    )
    if not found:
        raise UsageError(f"{path}: no PDF files found. Pass a folder that contains .pdf files.")
    return found


def make_slugs(doc_ids: list[str]) -> list[str]:
    """Filesystem- and URL-safe names derived from the relative path; duplicates get -2, -3 ..."""
    slugs: list[str] = []
    seen: dict[str, int] = {}
    for doc_id in doc_ids:
        base = re.sub(r"[^A-Za-z0-9._-]+", "_", re.sub(r"\.pdf$", "", doc_id, flags=re.I)).strip("._") or "doc"
        seen[base] = seen.get(base, 0) + 1
        slugs.append(base if seen[base] == 1 else f"{base}-{seen[base]}")
    return slugs


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# --- parser selection ---------------------------------------------------------------------------


def select_parsers(
    requested: list[str] | None, customs: list[CustomSpec]
) -> tuple[list[ParserSpec], list[Skipped]]:
    """Decide which parsers run. Missing optional parsers are skipped (with an install hint)."""
    names = list(dict.fromkeys(requested)) if requested else [n for n, i in REGISTRY.items() if i.auto]
    unknown = [n for n in names if n not in REGISTRY]
    if unknown:
        raise UsageError(f"unknown parser(s): {', '.join(unknown)}. Known parsers: {', '.join(REGISTRY)}")
    selected: list[ParserSpec] = []
    skipped: list[Skipped] = []
    for name in REGISTRY:  # registry order, so reports always list parsers in the same order
        info = REGISTRY[name]
        if name not in names:
            if not requested and not info.auto:
                skipped.append(Skipped(name, f"opt-in only: add {name} to --parsers (model download on first run)"))
            continue
        if is_installed(name):
            selected.append(ParserSpec(name))
        else:
            skipped.append(Skipped(name, f"not installed ({info.install_hint or 'install it first'})"))
    selected += [ParserSpec(c.name, c) for c in customs]
    return selected, skipped


# --- running one parser -------------------------------------------------------------------------


def _launch(cmd: list[str], timeout: float, env: dict[str, str]) -> tuple[int | None, bytes]:
    """Run a worker. Returns (exit code or None on timeout, stderr bytes). Kills it on timeout."""
    try:
        done = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env, check=False)
        return done.returncode, done.stderr
    except subprocess.TimeoutExpired as exc:
        return None, exc.stderr or b""


def _scrub(text: str, roots: dict[str, str]) -> str:
    """Replace absolute paths with placeholders so reports can be shared and compared."""
    for root in sorted(roots, key=len, reverse=True):
        if root:
            text = text.replace(root, roots[root])
    return text


def _cache_key(sha: str, spec: ParserSpec, version: str, pages: list[int]) -> dict:
    return {"schema": CACHE_SCHEMA, "sha256": sha, "parser": spec.name, "version": version, "pages": pages}


def run_parser(
    spec: ParserSpec,
    pdf: Path,
    sha: str,
    pages: list[int],
    raw_dir: Path,
    options: RunOptions,
    roots: dict[str, str],
) -> ParserOutput:
    raw_dir.mkdir(parents=True, exist_ok=True)
    final = raw_dir / f"{spec.name}.json"
    version = "custom" if spec.custom else (installed_version(spec.name) or "")
    key = _cache_key(sha, spec, version, pages)
    # custom parsers are never cached: their code can change without any version change
    cacheable = not spec.custom and bool(version)

    if cacheable and not options.fresh and final.is_file():
        try:
            stored = json.loads(final.read_text(encoding="utf-8"))
            if stored.get("key") == key and stored["output"]["status"] == "ok":
                return ParserOutput(**{**stored["output"], "cached": True})
        except (ValueError, KeyError, TypeError):
            pass  # unreadable cache entry: just run the parser again

    tmp = raw_dir / f"{spec.name}.running.json"
    tmp.unlink(missing_ok=True)
    cmd = [sys.executable, "-m", "parseoff.worker", "--pdf", str(pdf), "--pages", ",".join(map(str, pages)), "--out", str(tmp)]
    cmd += ["--custom", spec.custom.spec] if spec.custom else ["--parser", spec.name]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PARSEOFF_PATH": os.pathsep.join(p for p in [os.environ.get("PARSEOFF_PATH", ""), *sys.path] if p)}
    code, raw_err = _launch(cmd, options.timeout, env)
    stderr = _scrub(raw_err.decode("utf-8", "replace"), roots)[-STDERR_LIMIT:]

    if code is None:
        output = ParserOutput(
            spec.name, "timeout", version, float(options.timeout), [],
            f"timed out after {options.timeout:g}s (raise --timeout or use --max-pages)", stderr,
        )
    else:
        try:
            data = json.loads(tmp.read_text(encoding="utf-8"))
            error = _scrub(str(data.get("error", "")), roots)
            output = ParserOutput(
                spec.name, "error" if error else "ok", data.get("version") or version,
                float(data.get("seconds", 0.0)), list(data.get("pages", [])), error, stderr,
            )
        except (OSError, ValueError):
            output = ParserOutput(
                spec.name, "error", version, 0.0, [],
                f"worker exited with code {code} without a result", stderr,
            )
    tmp.unlink(missing_ok=True)
    stored = {"key": key, "output": {k: v for k, v in output.__dict__.items() if k != "cached"}}
    final.write_text(json.dumps(stored, ensure_ascii=True, indent=1, sort_keys=True), encoding="utf-8")
    return output


# --- the whole pipeline -------------------------------------------------------------------------


def run_pipeline(options: RunOptions, progress: Callable[[str], None] = lambda _msg: None) -> RunReport:
    """Run every selected parser over every PDF and return a report with metrics and findings."""
    docs = find_pdfs(options.input_path)
    specs, skipped = select_parsers(options.parsers, options.customs)
    slugs = make_slugs([doc_id for doc_id, _ in docs])
    root = options.input_path.resolve()
    roots = {
        str(root): "<input>", str(options.out_dir.resolve()): "<out>", os.getcwd(): "<cwd>",
        str(Path.home()): "~", sys.prefix: "<python>", sys.base_prefix: "<python>",
    }
    img_dir = options.out_dir / "report" / "img"
    reports: list[DocReport] = []

    for (doc_id, pdf), slug in zip(docs, slugs):
        doc = DocReport(doc_id=doc_id, slug=slug)
        reports.append(doc)
        try:
            doc.sha256 = file_sha256(pdf)
            doc.total_pages = textlayer.page_count(pdf)
            if doc.total_pages == 0:
                raise ValueError("the PDF has no pages")
            last = min(doc.total_pages, options.max_pages or doc.total_pages)
            doc.pages = list(range(1, last + 1))
            layer = textlayer.layer_texts(pdf, doc.pages)
        except Exception as exc:  # noqa: BLE001 - one unreadable file must not stop the run
            doc.open_error = _scrub(f"{type(exc).__name__}: {exc}", roots)
            doc.pages = []
            progress(f"  {doc_id}: cannot open ({doc.open_error})")
            continue
        doc.layer_chars = [len(t.strip()) for t in layer]
        if options.render:
            try:
                textlayer.render_pages(pdf, doc.pages, img_dir, slug)
                doc.rendered = True
            except Exception as exc:  # noqa: BLE001 - images are a convenience, not required
                progress(f"  {doc_id}: page images skipped ({type(exc).__name__})")
        for spec in specs:
            out = run_parser(spec, pdf, doc.sha256, doc.pages, options.out_dir / "raw" / slug, options, roots)
            doc.outputs[spec.name] = out
            note = " (cached)" if out.cached else ""
            progress(f"  {doc_id}: {spec.name} {out.status} {out.seconds:.2f}s{note}")
            if out.status != "ok" and out.error.strip():
                # show the cause in the terminal too, not only in summary.md
                progress(f"    {out.error.strip().splitlines()[0][:160]}")
        ok = {n: o.pages for n, o in doc.outputs.items() if o.status == "ok"}
        doc.metrics = metrics.compute_doc_metrics(doc.pages, layer, ok)

    report = RunReport(
        docs=reports, parsers=[s.name for s in specs], skipped=skipped,
        thresholds=options.thresholds, demo=options.demo,
    )
    report.findings = findings.build_findings(report)
    return report
