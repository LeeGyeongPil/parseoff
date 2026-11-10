"""Tiny parser functions for `--custom NAME=fake_parsers:function` tests."""

from __future__ import annotations

import time


def ok(pdf_path: str, pages: list[int]) -> list[str]:
    return [f"fake text for page {p}" for p in pages]


def boom(pdf_path: str, pages: list[int]) -> list[str]:
    raise ValueError("this parser always fails")


def leaky(pdf_path: str, pages: list[int]) -> list[str]:
    # an error message that contains an absolute path, to check that reports scrub paths
    raise RuntimeError(f"cannot read {pdf_path}")


def slow(pdf_path: str, pages: list[int]) -> list[str]:
    time.sleep(30)  # ends by itself even if nobody kills it
    return ["never returned" for _ in pages]


def script(pdf_path: str, pages: list[int]) -> list[str]:
    return ["<script>alert('x')</script> <b>bold</b>" for _ in pages]
