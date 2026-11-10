"""Subprocess entry point: ``python -m parseoff.worker`` runs ONE parser on ONE PDF.

Running each (document, parser) pair in its own process isolates crashes, native-library noise on
stderr and hangs - the parent enforces a timeout and simply kills the process.
The result is written as JSON to ``--out``; a parser exception is captured into the JSON, not raised.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def _version(parser: str, custom: bool) -> str:
    if custom:
        return "custom"
    from .registry import installed_version

    return installed_version(parser) or ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m parseoff.worker")
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--pages", required=True, help="comma separated 1-based page numbers")
    ap.add_argument("--out", required=True)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--parser")
    group.add_argument("--custom", help="NAME=module:function")
    args = ap.parse_args(argv)

    pages = [int(p) for p in args.pages.split(",") if p]
    result: dict = {"pages": [], "seconds": 0.0, "error": "", "version": ""}
    started = time.perf_counter()
    try:
        if args.custom:
            from .adapters.custom import load, parse_spec

            spec = parse_spec(args.custom)
            convert, name = load(spec), spec.name
        else:
            from .adapters import get_adapter

            convert, name = get_adapter(args.parser), args.parser
        result["version"] = _version(name, bool(args.custom))
        texts = convert(args.pdf, pages)
        if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
            raise TypeError("a parser must return a list of strings, one per requested page")
        if len(texts) != len(pages):
            raise ValueError(f"parser returned {len(texts)} page(s) but {len(pages)} were requested")
        result["pages"] = texts
    except Exception as exc:  # noqa: BLE001 - every parser failure must be reported, not raised
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["seconds"] = round(time.perf_counter() - started, 3)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=True), encoding="utf-8")
    return 1 if result["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
