"""Plain data classes shared by the runner, metrics, findings and report writers."""

from __future__ import annotations

from dataclasses import dataclass, field

FAIL = "FAIL"
WARN = "WARN"
INFO = "INFO"
LEVELS = (FAIL, WARN, INFO)


@dataclass
class ParserOutput:
    """Result of one parser on one document (pages are Markdown/plain text, one string per page)."""

    parser: str
    status: str  # "ok" | "error" | "timeout"
    version: str = ""
    seconds: float = 0.0
    pages: list[str] = field(default_factory=list)
    error: str = ""
    stderr: str = ""
    cached: bool = False


@dataclass
class PageMetrics:
    chars: int
    tokens_est: int
    coverage: float | None  # None when the text layer has no words (never computed as 0)
    tables: int
    headings: int


@dataclass
class ParserMetrics:
    pages: list[PageMetrics]
    mean_coverage: float | None
    boilerplate_ratio: float
    boilerplate_example: str


@dataclass
class DocMetrics:
    parsers: dict[str, ParserMetrics]
    # page number -> {(parser_a, parser_b): agreement or None}
    agreement: dict[int, dict[tuple[str, str], float | None]]
    # (parser_a, parser_b) -> mean over pages where it could be computed
    mean_agreement: dict[tuple[str, str], float | None]


@dataclass
class DocReport:
    doc_id: str  # path relative to the input folder, posix style
    slug: str
    sha256: str = ""
    total_pages: int = 0
    pages: list[int] = field(default_factory=list)  # analysed 1-based page numbers
    layer_chars: list[int] = field(default_factory=list)
    outputs: dict[str, ParserOutput] = field(default_factory=dict)
    metrics: DocMetrics | None = None
    open_error: str = ""
    rendered: bool = False


@dataclass(frozen=True)
class Skipped:
    name: str
    reason: str


@dataclass(frozen=True)
class Finding:
    code: str
    level: str
    message: str
    doc: str | None = None
    page: int | None = None
    parser: str | None = None


@dataclass(frozen=True)
class Thresholds:
    min_coverage: float = 0.8
    min_agreement: float = 0.6


@dataclass
class RunReport:
    docs: list[DocReport]
    parsers: list[str]  # parsers that were executed, in display order
    skipped: list[Skipped]
    thresholds: Thresholds
    demo: bool = False
    findings: list[Finding] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {lvl: sum(1 for f in self.findings if f.level == lvl) for lvl in LEVELS}
