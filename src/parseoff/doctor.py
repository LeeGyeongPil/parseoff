"""`parseoff doctor`: which parsers are installed, with licence, size and warnings."""

from __future__ import annotations

import unicodedata

from .i18n import DEFAULT_LANG, t
from .registry import (
    REGISTRY,
    disk_size_mb,
    docling_models_present,
    install_hint,
    installed_version,
    is_installed,
    size_text,
    survey_note,
)

_HEADER_KEYS = ("parser", "installed", "version", "license", "size", "disk", "notes")


def _width(text: str) -> int:
    """Columns the text takes in a terminal (Korean letters are two columns wide)."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * (width - _width(text))


def _notes(name: str, lang: str) -> str:
    info = REGISTRY[name]
    notes = [t(f"note.{name}", lang)]
    if info.copyleft:
        notes.append(t("doctor.copyleft", lang))
    if info.model_download:
        found = t("doctor.found" if docling_models_present() else "doctor.not_found", lang)
        notes.append(t("doctor.model_download", lang, found=found))
    if not info.core:
        notes.append(t("doctor.install", lang, hint=install_hint(name, lang)))
    return "; ".join(n for n in notes if n)


def render_doctor(lang: str = DEFAULT_LANG) -> str:
    header = tuple(t(f"doctor.h.{k}", lang) for k in _HEADER_KEYS)
    rows = [header]
    for name, info in REGISTRY.items():
        installed = is_installed(name)
        disk = disk_size_mb(name) if installed else None
        rows.append((
            name,
            t("doctor.yes" if installed else "doctor.no", lang),
            (installed_version(name) or "-") if installed else "-",
            info.license,
            size_text(name, lang),
            f"{disk:.1f} MB" if disk is not None else "-",
            _notes(name, lang),
        ))
    widths = [max(_width(r[i]) for r in rows) for i in range(len(header) - 1)]
    lines = []
    for r in rows:
        lines.append("  ".join(_pad(r[i], widths[i]) for i in range(len(widths))) + "  " + r[-1])
    lines += ["", t("doctor.foot1", lang, survey=survey_note(lang)), t("doctor.foot2", lang)]
    return "\n".join(lines)
