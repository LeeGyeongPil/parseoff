"""Known parsers: licence, surveyed install size, warnings and detection helpers.

The surveyed numbers (licence, size) come from a one-off survey and are labelled as such wherever
they are shown. Installed versions are always read at runtime from the installed distribution.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from .i18n import MESSAGES, t

SURVEY_NOTE = "surveyed 2026-11-10, macOS arm64, Python 3.12, isolated install"
HEAVY_INSTALL_MB = 100.0


@dataclass(frozen=True)
class ParserInfo:
    name: str
    dists: tuple[str, ...]  # distribution names tried for the installed version
    module: str  # top-level module used to detect an installation
    license: str
    size_mb: float | None  # surveyed isolated install size; None = not measured
    size_text: str
    auto: bool  # run automatically when installed (False = only via --parsers)
    core: bool  # installed together with parseoff
    copyleft: bool = False
    weights_restricted: bool = False
    model_download: bool = False
    install_hint: str = ""
    note: str = ""


REGISTRY: dict[str, ParserInfo] = {
    p.name: p
    for p in (
        ParserInfo(
            "pypdf", ("pypdf",), "pypdf", "BSD-3-Clause", 1.8, "1.8 MB", True, True,
            note="pure Python; text in content-stream order, no structure",
        ),
        ParserInfo(
            "pdfplumber", ("pdfplumber",), "pdfplumber", "MIT", 41.0, "41 MB", True, True,
            note="text by position + tables as GFM (includes pypdfium2, pdfminer.six)",
        ),
        ParserInfo(
            "pdfminer", ("pdfminer.six",), "pdfminer", "MIT", None, "part of pdfplumber", True, True,
            note="layout-box text; markitdown's PDF path is pdfminer text extraction",
        ),
        ParserInfo(
            "markitdown", ("markitdown",), "markitdown", "MIT", 147.0, "147 MB", True, False,
            install_hint='uv sync --extra markitdown',
            note="most of the size is onnxruntime; page-split (one conversion per page)",
        ),
        ParserInfo(
            "pymupdf4llm", ("pymupdf4llm", "pymupdf"), "pymupdf4llm", "AGPL-3.0 or commercial",
            214.0, "214 MB", True, False, copyleft=True,
            install_hint="uv pip install pymupdf4llm; AGPL-3.0, check its terms",
            note="detected only if you installed it; not an extra of parseoff",
        ),
        ParserInfo(
            "docling", ("docling",), "docling", "MIT", None, "not measured (large, torch)",
            False, False, model_download=True,
            install_hint='uv sync --extra docling',
            note="experimental",
        ),
    )
}
BUILTIN_NAMES = tuple(REGISTRY)


def is_importable(module: str) -> bool:
    """True if `module` can be imported (without importing it). Tolerates fake modules in tests."""
    if module in sys.modules:
        return True
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def installed_version(name: str) -> str | None:
    """Installed distribution version for a known parser, or None if not installed."""
    info = REGISTRY[name]
    for dist in info.dists:
        try:
            return metadata.version(dist)
        except metadata.PackageNotFoundError:
            continue
    return None


def is_installed(name: str) -> bool:
    return is_importable(REGISTRY[name].module)


def docling_models_present() -> bool:
    """Existence check only: DOCLING_ARTIFACTS_PATH or docling's default cache directory."""
    env = os.environ.get("DOCLING_ARTIFACTS_PATH")
    if env and Path(env).is_dir():
        return True
    return (Path.home() / ".cache" / "docling" / "models").is_dir()


def disk_size_mb(name: str) -> float | None:
    """Size of the installed distribution's own files (not its dependencies), or None."""
    info = REGISTRY[name]
    for dist in info.dists:
        try:
            files = metadata.distribution(dist).files
        except metadata.PackageNotFoundError:
            continue
        if not files:
            return None
        total = 0
        for f in files:
            try:
                total += f.locate().stat().st_size
            except OSError:
                continue
        return total / 1_000_000
    return None


# --- screen text for registry facts (English values stay in REGISTRY, Korean ones live in i18n) ----


def size_text(name: str, lang: str = "en") -> str:
    """Surveyed install size as text; the two non-numeric ones ('part of ...', 'not measured') translate."""
    return _facts_text(f"size.{name}", REGISTRY[name].size_text, lang)


def install_hint(name: str, lang: str = "en") -> str:
    """How to install a parser. Commands stay as they are; only the explanation is translated."""
    return _facts_text(f"hint.{name}", REGISTRY[name].install_hint, lang)


def survey_note(lang: str = "en") -> str:
    return SURVEY_NOTE if lang == "en" else t("survey", lang)


def _facts_text(key: str, default: str, lang: str) -> str:
    if lang != "en" and key in MESSAGES.get(lang, {}):
        return t(key, lang)
    return default
