"""Synthetic statement pages (PDF bytes) for layouts the sample corpus does not contain.

Each option reproduces one real-world layout feature, so a fix can be tested without a company's file:
note-number column, IFRS names, unit, top-aligned wrapped labels, ruled grid.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pymupdf

FONT = "japan"
SIZE = 9.0
PITCH = 14.0


@dataclass
class Line:
    label: str
    values: tuple[str, ...] = ()
    level: int = 0
    note: str = ""


@dataclass
class Layout:
    title: str = "連結貸借対照表"
    unit: str = "（単位：百万円）"
    headers: tuple[str, ...] = (
        "前連結会計年度\n(2025年3月31日)",
        "当連結会計年度\n(2026年3月31日)",
    )
    note_header: str = ""  # e.g. "注記": adds a note-number column
    wrap_labels_top_aligned: bool = False
    grid: bool = False
    footer: str = ""  # a page number printed under the table, e.g. "- 4 -"
    period_header_lines: bool = (
        False  # years on their own line: "(自 年8月1日 至 年7月31日)" + "2025 2026"
    )
    lines: list[Line] = field(default_factory=list)


J_GAAP = [
    Line("資産の部"),
    Line("流動資産", level=1),
    Line("現金及び預金", ("1,000", "1,200"), 2, note="5"),
    Line("受取手形及び売掛金", ("2,000", "2,100"), 2, note="6"),
    Line("流動資産合計", ("3,000", "3,300"), 2),
    Line("固定資産", level=1),
    Line("土地", ("500", "500"), 2),
    Line("固定資産合計", ("500", "500"), 2),
    Line("資産合計", ("3,500", "3,800"), 1),
    Line("負債の部"),
    Line("流動負債", level=1),
    Line("支払手形及び買掛金", ("1,000", "1,100"), 2, note="12"),
    Line("流動負債合計", ("1,000", "1,100"), 2),
    Line("負債合計", ("1,000", "1,100"), 1),
    Line("純資産の部"),
    Line("株主資本", level=1),
    Line("資本金", ("1,500", "1,500"), 2),
    Line("利益剰余金", ("1,000", "1,200"), 2),
    Line("株主資本合計", ("2,500", "2,700"), 2),
    Line("純資産合計", ("2,500", "2,700"), 1),
    Line("負債純資産合計", ("3,500", "3,800"), 1),
]

IFRS = [
    Line("資産"),
    Line("流動資産", level=1),
    Line("現金及び現金同等物", ("1,000", "1,200"), 2, note="7"),
    Line("営業債権及びその他の債権", ("2,000", "2,100"), 2, note="8"),
    Line("流動資産合計", ("3,000", "3,300"), 2),
    Line("非流動資産", level=1),
    Line("有形固定資産", ("500", "500"), 2, note="10"),
    Line("非流動資産合計", ("500", "500"), 2),
    Line("資産合計", ("3,500", "3,800"), 1),
    Line("負債及び資本"),
    Line("負債", level=1),
    Line("営業債務及びその他の債務", ("1,000", "1,100"), 2, note="15"),
    Line("負債合計", ("1,000", "1,100"), 2),
    Line("資本", level=1),
    Line("資本金", ("1,500", "1,500"), 2),
    Line("利益剰余金", ("1,000", "1,200"), 2),
    Line("資本合計", ("2,500", "2,700"), 2),
    Line("負債及び資本合計", ("3,500", "3,800"), 1),
]


def make_pdf(layout: Layout | None = None, lines: list[Line] | None = None) -> bytes:
    layout = layout or Layout()
    rows = lines or layout.lines or J_GAAP
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)

    def text(x: float, y: float, s: str, right: bool = False) -> None:
        if right:
            x -= pymupdf.get_text_length(s, fontname=FONT, fontsize=SIZE)
        page.insert_text((x, y), s, fontname=FONT, fontsize=SIZE)

    y = 60.0
    text(230, y, layout.title)
    y += 20
    text(430, y, layout.unit)
    y += 20
    n = len(layout.headers)
    last = 500.0 if not layout.note_header else 520.0
    cols = [last - 100.0 * (n - 1 - i) for i in range(n)]
    for col, h in zip(cols, layout.headers, strict=False):
        for k, part in enumerate(h.split("\n")):
            text(col, y + k * 11, part, right=True)
    if layout.note_header:
        text(cols[0] - 100, y + 11, layout.note_header, right=True)
    y += 34
    top = y
    for line in rows:
        x = 40 + 10 * line.level
        label = line.label
        if layout.wrap_labels_top_aligned and len(label) > 8 and line.values:
            half = len(label) // 2
            text(x, y, label[:half])
            text(x, y + 11, label[half:])
            ytext = y  # amounts printed level with the FIRST label line
            text_y = ytext
            height = PITCH + 11
        else:
            text(x, y, label)
            text_y = y
            height = PITCH
        values = (
            line.values + line.values[-1:] * max(0, n - len(line.values)) if line.values else ()
        )
        for col, v in zip(cols, values, strict=False):
            text(col, text_y, v, right=True)
        if layout.note_header and line.note:
            text(cols[0] - 100, text_y, line.note, right=True)
        y += height
    if layout.footer:
        text(300, y + 40, layout.footer)
    if layout.grid:
        for k in range(len(rows) + 1):
            yy = top - 10 + k * PITCH
            page.draw_line((35, yy), (545, yy), width=0.5)
        for xx in (35, 330, 360, 460, 545):
            page.draw_line((xx, top - 10), (xx, y - 10), width=0.5)
    return bytes(doc.tobytes())


def make_account_form_pdf(lines: list[Line] | None = None, split: int = 9) -> bytes:
    """Account form (勘定式): assets in the left panel, liabilities and equity in the right panel."""
    rows = lines or J_GAAP
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)

    def text(x: float, y: float, s: str, right: bool = False) -> None:
        if right:
            x -= pymupdf.get_text_length(s, fontname=FONT, fontsize=SIZE)
        page.insert_text((x, y), s, fontname=FONT, fontsize=SIZE)

    text(230, 60, "貸借対照表")
    text(230, 80, "（単位：百万円）")
    for part, label_x, amount_x in ((rows[:split], 30, 250), (rows[split:], 300, 540)):
        y = 120.0
        for line in part:
            text(label_x + 8 * line.level, y, line.label)
            if line.values:
                text(amount_x, y, line.values[1], right=True)
            y += PITCH
    return bytes(doc.tobytes())
