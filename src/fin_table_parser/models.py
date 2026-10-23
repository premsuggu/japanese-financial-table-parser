"""Plain data containers shared by every stage of the pipeline.

Every stage takes and returns these dataclasses, so each stage can be unit-tested without a PDF.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ValueKind = Literal["number", "nil", "text"]
RowType = Literal["section", "item", "total", "net"]


@dataclass(frozen=True)
class Word:
    """A word from the PDF text layer with its bounding box (PDF points, origin top-left)."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass(frozen=True)
class Rect:
    """A filled rectangle from the page drawings. ``fill`` is rounded RGB in 0..1."""

    x0: float
    y0: float
    x1: float
    y1: float
    fill: tuple[float, float, float] | None = None

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass
class PageGeometry:
    """Everything the extractors need from one PDF page."""

    page_no: int
    width: float
    height: float
    words: list[Word]
    fills: list[Rect]  # non-black filled rectangles (row bands)
    rules: list[Rect]  # black filled rectangles (table rules, underlines)


@dataclass(frozen=True)
class Value:
    """A parsed table cell. ``raw`` is the text exactly as printed (``△2,979``, ``－``)."""

    raw: str
    number: int | None
    kind: ValueKind
    negative_zero: bool = False  # printed as a negative marker followed by 0 (``△0``)
    notes: tuple[str, ...] = ()  # footnote markers printed with the number, e.g. ("※1",)


@dataclass
class Row:
    index: int
    label: str
    level: int
    path: tuple[str, ...]
    values: list[Value | None]  # one entry per value column; None = empty cell
    row_type: RowType
    rule_above: bool = False
    underlined: list[bool] = field(default_factory=list)
    label_x0: float = 0.0
    note_ref: str = (
        ""  # the 注記 (note number) printed beside the label, when the page has that column
    )


@dataclass
class Table:
    statement: str
    unit: str | None
    headers: list[str]
    periods: list[str | None]  # ISO period-end date per value column, when parseable
    rows: list[Row]
    source: str = ""
    page_no: int = 0
    meta: dict[str, object] = field(default_factory=dict)
    kind: str = "unknown"  # balance_sheet / income_statement / comprehensive_income / cash_flow


# WARN = an advisory check disagreed (may be legitimate), or a non-numeric cell sits in a number column.
Status = Literal["PASS", "PASS_ROUNDING", "FAIL", "WARN", "SKIP"]


@dataclass
class Finding:
    """Result of one accounting check on one column."""

    check: str
    status: Status
    table: str
    column: str
    row: str
    expected: int | None = None
    actual: int | None = None
    tolerance: int = 0
    detail: str = ""

    @property
    def diff(self) -> int | None:
        if self.expected is None or self.actual is None:
            return None
        return self.actual - self.expected
