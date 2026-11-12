"""Command line interface: `parseoff doctor | run | demo`.

Screen language: ``--lang en|ko`` > ``PARSEOFF_LANG`` > ``LC_ALL`` / ``LC_MESSAGES`` / ``LANG`` (see i18n.py).
The language is read from the command line *before* the real parser is built, so even the
argparse sentences (usage, options, errors) come out in the chosen language.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from . import __version__
from .adapters.custom import CustomSpec, SpecError, parse_spec
from .doctor import render_doctor
from .findings import skip_reason
from .i18n import LANGS, argparse_language, resolve_lang, t
from .model import Thresholds
from .report_html import render_doc, render_index
from .report_text import summary_json, summary_markdown
from .runner import RunOptions, UsageError, run_pipeline
from .samples import create_samples


def read_lang_option(argv: list[str]) -> str | None:
    """Find ``--lang X`` / ``--lang=X`` anywhere in argv (before the real parser exists)."""
    for i, arg in enumerate(argv):
        if arg == "--":
            break
        if arg == "--lang":
            return argv[i + 1] if i + 1 < len(argv) else None
        if arg.startswith("--lang="):
            return arg.partition("=")[2]
    return None


def _fraction_type(lang: str) -> Callable[[str], float]:
    def convert(text: str) -> float:
        try:
            value = float(text)
        except ValueError:
            raise argparse.ArgumentTypeError(t("arg.not_fraction", lang, text=text)) from None
        if not 0.0 <= value <= 1.0:
            raise argparse.ArgumentTypeError(t("arg.out_of_range", lang, text=text))
        return value

    return convert


def _positive_type(lang: str) -> Callable[[str], float]:
    def convert(text: str) -> float:
        try:
            value = float(text)
        except ValueError:
            raise argparse.ArgumentTypeError(t("arg.not_number", lang, text=text)) from None
        if value <= 0:
            raise argparse.ArgumentTypeError(t("arg.not_positive", lang, text=text))
        return value

    return convert


def _custom_type(lang: str) -> Callable[[str], CustomSpec]:
    def convert(text: str) -> CustomSpec:
        try:
            return parse_spec(text)
        except SpecError as exc:
            raise argparse.ArgumentTypeError(exc.text(lang)) from None

    return convert


def _add_lang_option(p: argparse.ArgumentParser, lang: str) -> None:
    # SUPPRESS: the value was already read by read_lang_option; this entry is for --help and validation
    p.add_argument("--lang", choices=LANGS, default=argparse.SUPPRESS, metavar="{en,ko}", help=t("cli.help.lang", lang))


def _add_run_options(p: argparse.ArgumentParser, lang: str) -> None:
    fraction, positive = _fraction_type(lang), _positive_type(lang)
    p.add_argument("--parsers", help=t("cli.help.parsers", lang))
    p.add_argument("--max-pages", type=int, metavar="N", help=t("cli.help.max_pages", lang))
    p.add_argument("--timeout", type=positive, default=120.0, metavar="SEC", help=t("cli.help.timeout", lang))
    p.add_argument("--custom", action="append", default=[], type=_custom_type(lang), metavar="NAME=module:function",
                   help=t("cli.help.custom", lang))
    p.add_argument("--min-coverage", type=fraction, default=0.8, metavar="X", help=t("cli.help.min_coverage", lang))
    p.add_argument("--min-agreement", type=fraction, default=0.6, metavar="X", help=t("cli.help.min_agreement", lang))
    p.add_argument("--strict", action="store_true", help=t("cli.help.strict", lang))
    p.add_argument("--fresh", action="store_true", help=t("cli.help.fresh", lang))
    p.add_argument("--no-render", action="store_true", help=t("cli.help.no_render", lang))
    _add_lang_option(p, lang)


def build_parser(lang: str = "en") -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="parseoff", description=t("cli.description", lang))
    ap.add_argument("--version", action="version", version=f"parseoff {__version__}", help=t("cli.help.version", lang))
    _add_lang_option(ap, lang)
    sub = ap.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help=t("cli.help.doctor", lang))
    _add_lang_option(doctor, lang)
    run = sub.add_parser("run", help=t("cli.help.run", lang))
    run.add_argument("input", type=Path, help=t("cli.help.input", lang))
    run.add_argument("--out", type=Path, default=Path("parseoff-out"), help=t("cli.help.out_run", lang))
    _add_run_options(run, lang)
    demo = sub.add_parser("demo", help=t("cli.help.demo", lang))
    demo.add_argument("--out", type=Path, default=Path("demo-out"), help=t("cli.help.out_demo", lang))
    _add_run_options(demo, lang)
    return ap


def _write_outputs(out: Path, report, lang: str) -> Path:
    """Write summary.json, summary.md and report/*.html; return the index.html path."""
    report_dir = out / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(summary_json(report), encoding="utf-8")  # same bytes in every language
    (out / "summary.md").write_text(summary_markdown(report, lang), encoding="utf-8")
    (report_dir / "index.html").write_text(render_index(report, lang), encoding="utf-8")
    for doc in report.docs:
        (report_dir / f"doc-{doc.slug}.html").write_text(render_doc(report, doc, lang), encoding="utf-8")
    return report_dir / "index.html"


def _fail(message: str, lang: str) -> int:
    print(t("cli.error_prefix", lang) + message, file=sys.stderr)
    return 2


def _execute(args: argparse.Namespace, input_path: Path, demo: bool, lang: str) -> int:
    if args.max_pages is not None and args.max_pages < 1:
        return _fail(t("err.max_pages", lang), lang)
    requested = [p.strip() for p in args.parsers.split(",") if p.strip()] if args.parsers else None
    options = RunOptions(
        input_path=input_path, out_dir=args.out, parsers=requested, customs=args.custom,
        max_pages=args.max_pages, timeout=args.timeout, fresh=args.fresh, render=not args.no_render,
        thresholds=Thresholds(args.min_coverage, args.min_agreement), demo=demo, lang=lang,
    )
    try:
        report = run_pipeline(options, progress=print)
    except UsageError as exc:
        return _fail(exc.text(lang), lang)
    index = _write_outputs(args.out, report, lang)

    counts = report.counts()
    failed = counts["FAIL"] > 0
    code = 1 if (args.strict and failed) else 0
    print()
    print(t("run.summary", lang, count=len(report.docs), parsers=", ".join(report.parsers) or t("run.none", lang)))
    for skip in report.skipped:
        print(t("run.skipped", lang, name=skip.name, reason=skip_reason(skip, lang)))
    hint = "" if code else t("run.strict_hint", lang)
    print(t("run.counts", lang, fail=counts["FAIL"], warn=counts["WARN"], info=counts["INFO"], code=code, hint=hint))
    print(t("run.report", lang, path=index))
    return code


def _tolerate_unencodable_output() -> None:
    """A terminal whose encoding cannot show Korean should print '?' instead of crashing."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            pass  # not a real text stream (for example a test capture): nothing to do


def main(argv: list[str] | None = None) -> int:
    args_in = list(sys.argv[1:] if argv is None else argv)
    lang = resolve_lang(read_lang_option(args_in))
    _tolerate_unencodable_output()
    with argparse_language(lang):
        args = build_parser(lang).parse_args(args_in)
    if args.command == "doctor":
        print(render_doctor(lang))
        return 0
    if args.command == "demo":
        print(t("demo.banner", lang))
        samples = create_samples(args.out / "samples")
        return _execute(args, samples[0].parent, True, lang)
    return _execute(args, args.input, False, lang)


if __name__ == "__main__":
    sys.exit(main())
