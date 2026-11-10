"""`parseoff doctor`: which parsers are installed, with licence, size and warnings."""

from __future__ import annotations

from .registry import REGISTRY, SURVEY_NOTE, disk_size_mb, docling_models_present, installed_version, is_installed

HEADER = ("parser", "installed", "version", "license", "install size*", "on disk", "notes")


def _notes(name: str) -> str:
    info = REGISTRY[name]
    notes = [info.note]
    if info.copyleft:
        notes.append("WARNING copyleft licence")
    if info.model_download:
        found = "found" if docling_models_present() else "not found"
        notes.append(f"WARNING model download on first run (local models: {found}); opt-in via --parsers")
    if not info.core:
        notes.append(f"install: {info.install_hint}")
    return "; ".join(n for n in notes if n)


def render_doctor() -> str:
    rows = [HEADER]
    for name, info in REGISTRY.items():
        installed = is_installed(name)
        disk = disk_size_mb(name) if installed else None
        rows.append((
            name,
            "yes" if installed else "no",
            (installed_version(name) or "-") if installed else "-",
            info.license,
            info.size_text,
            f"{disk:.1f} MB" if disk is not None else "-",
            _notes(name),
        ))
    widths = [max(len(r[i]) for r in rows) for i in range(len(HEADER) - 1)]
    lines = []
    for r in rows:
        lines.append("  ".join(r[i].ljust(widths[i]) for i in range(len(widths))) + "  " + r[-1])
    lines += [
        "",
        f"* install size: {SURVEY_NOTE} (docling not measured). Versions and 'on disk' are read from your environment.",
        "Licence and size columns are survey values, not legal advice: verify before you ship.",
    ]
    return "\n".join(lines)
