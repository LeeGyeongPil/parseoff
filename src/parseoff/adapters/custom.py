"""User-supplied parsers: ``--custom NAME=module:function``.

The function receives ``(pdf_path: str, page_numbers: list[int])`` (1-based pages) and must return
one string per requested page. It runs inside the worker subprocess, never in the main process.
Only the module you name is imported - make sure you trust it, it can run any code.
"""

from __future__ import annotations

import importlib
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass

from ..i18n import LocalizedError
from ..registry import BUILTIN_NAMES

_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
_DOTTED = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


@dataclass(frozen=True)
class CustomSpec:
    name: str
    module: str
    function: str

    @property
    def spec(self) -> str:
        return f"{self.name}={self.module}:{self.function}"


class SpecError(LocalizedError, ValueError):
    """A malformed ``--custom`` value. The message is English; ``text(lang)`` translates it."""


def parse_spec(text: str) -> CustomSpec:
    """Parse ``NAME=module:function``; raise SpecError (a ValueError) with the fix on a malformed value."""
    name, sep, target = text.partition("=")
    module, colon, function = target.partition(":")
    if not (sep and colon and name and module and function):
        raise SpecError("custom.bad_value", text=text)
    if not _NAME.match(name):
        raise SpecError("custom.bad_name", name=name)
    if name in BUILTIN_NAMES:
        raise SpecError("custom.taken", name=name)
    if not _DOTTED.match(module) or not function.isidentifier():
        raise SpecError("custom.bad_target", target=target)
    return CustomSpec(name, module, function)


def load(spec: CustomSpec) -> Callable[[str, list[int]], list[str]]:
    """Import the user's module (current directory and PARSEOFF_PATH are searched) and get the function."""
    for extra in [os.getcwd(), *os.environ.get("PARSEOFF_PATH", "").split(os.pathsep)]:
        if extra and extra not in sys.path:
            sys.path.append(extra)
    try:
        module = importlib.import_module(spec.module)
    except ImportError as exc:
        raise RuntimeError(
            f"cannot import module {spec.module!r} for custom parser {spec.name!r}: {exc}. "
            "Run parseoff from the folder that contains it or install the package."
        ) from exc
    func = getattr(module, spec.function, None)
    if not callable(func):
        raise RuntimeError(f"module {spec.module!r} has no callable {spec.function!r}")
    return func
