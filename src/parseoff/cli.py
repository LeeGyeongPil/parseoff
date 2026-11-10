"""Command line interface: `parseoff doctor | run | demo`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .adapters.custom import CustomSpec, parse_spec
from .doctor import render_doctor
from .model import Thresholds
from .report_html import render_doc, render_index
from .report_text import summary_json, summary_markdown
from .runner import RunOptions, UsageError, run_pipeline
from .samples import create_samples


def _fraction(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a number between 0 and 1") from None
    if not 0.0 <= value <= 1.0:
        raise argparse.ArgumentTypeError(f"{text} is out of range: use a value between 0 and 1")
    return value


def _positive(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a number") from None
    if value <= 0:
        raise argparse.ArgumentTypeError(f"{text} must be greater than 0")
    return value


def _custom(text: str) -> CustomSpec:
    try:
        return parse_spec(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def _add_run_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--parsers", help="comma separated parsers to run (default: every installed one except docling)")
    p.add_argument("--max-pages", type=int, metavar="N", help="analyse only the first N pages of each PDF")
    p.add_argument("--timeout", type=_positive, default=120.0, metavar="SEC", help="per parser and document (default 120)")
    p.add_argument("--custom", action="append", default=[], type=_custom, metavar="NAME=module:function",
                   help="add your own parser function (repeatable)")
    p.add_argument("--min-coverage", type=_fraction, default=0.8, metavar="X", help="LOW_COVERAGE threshold (default 0.8)")
    p.add_argument("--min-agreement", type=_fraction, default=0.6, metavar="X", help="LOW_AGREEMENT threshold (default 0.6)")
    p.add_argument("--strict", action="store_true", help="exit 1 if any FAIL finding exists (for CI)")
    p.add_argument("--fresh", action="store_true", help="ignore cached parser results")
    p.add_argument("--no-render", action="store_true", help="do not write page images")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="parseoff", description="Compare PDF parsers side by side on your own documents.")
    ap.add_argument("--version", action="version", version=f"parseoff {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="show installed parsers, versions, licences and warnings")
    run = sub.add_parser("run", help="compare parsers on a PDF file or a folder of PDFs")
    run.add_argument("input", type=Path, help="a .pdf file or a folder (searched recursively)")
    run.add_argument("--out", type=Path, default=Path("parseoff-out"), help="output folder (default parseoff-out)")
    _add_run_options(run)
    demo = sub.add_parser("demo", help="generate 3 practice PDFs and compare the default parsers on them")
    demo.add_argument("--out", type=Path, default=Path("demo-out"), help="output folder (default demo-out)")
    _add_run_options(demo)
    return ap


def _write_outputs(out: Path, report) -> Path:
    """Write summary.json, summary.md and report/*.html; return the index.html path."""
    report_dir = out / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(summary_json(report), encoding="utf-8")
    (out / "summary.md").write_text(summary_markdown(report), encoding="utf-8")
    (report_dir / "index.html").write_text(render_index(report), encoding="utf-8")
    for doc in report.docs:
        (report_dir / f"doc-{doc.slug}.html").write_text(render_doc(report, doc), encoding="utf-8")
    return report_dir / "index.html"


def _execute(args: argparse.Namespace, input_path: Path, demo: bool) -> int:
    if args.max_pages is not None and args.max_pages < 1:
        print("error: --max-pages must be 1 or greater", file=sys.stderr)
        return 2
    requested = [p.strip() for p in args.parsers.split(",") if p.strip()] if args.parsers else None
    options = RunOptions(
        input_path=input_path, out_dir=args.out, parsers=requested, customs=args.custom,
        max_pages=args.max_pages, timeout=args.timeout, fresh=args.fresh, render=not args.no_render,
        thresholds=Thresholds(args.min_coverage, args.min_agreement), demo=demo,
    )
    try:
        report = run_pipeline(options, progress=print)
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    index = _write_outputs(args.out, report)

    counts = report.counts()
    failed = counts["FAIL"] > 0
    code = 1 if (args.strict and failed) else 0
    print()
    print(f"{len(report.docs)} documents, parsers: {', '.join(report.parsers) or '(none)'}")
    for skip in report.skipped:
        print(f"skipped {skip.name}: {skip.reason}")
    hint = "" if code else " (use --strict to fail)"
    print(f"FAIL {counts['FAIL']}, WARN {counts['WARN']}, INFO {counts['INFO']} - exit {code}{hint}")
    print(f"report: {index}")
    return code


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        print(render_doctor())
        return 0
    if args.command == "demo":
        print("parseoff demo - practice mode: 3 synthetic PDFs, real parsers")
        samples = create_samples(args.out / "samples")
        return _execute(args, samples[0].parent, demo=True)
    return _execute(args, args.input, demo=False)


if __name__ == "__main__":
    sys.exit(main())
