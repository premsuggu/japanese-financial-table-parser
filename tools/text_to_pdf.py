"""Turn a plain-text file (here the exported chat) into a paginated PDF with an embedded Japanese font.

python -X utf8 tools/text_to_pdf.py docs/chat.md chat.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

FONT_FILE = Path("C:/Windows/Fonts/msgothic.ttc")  # MS Gothic: monospaced, Latin + Japanese
EMOJI = {
    "✅": "[ok]",
    "👁": "[review]",
    "🚧": "[unsupported]",
    "⚠": "[check]",
    "❔": "[unverified]",
    "🔸": "*",
    "️": "",
}
SIZE = 7.0
LEADING = 8.4
MARGIN = 36.0
A4 = (595.0, 842.0)


def to_pdf(src: Path, dest: Path) -> int:
    font = pymupdf.Font(fontfile=str(FONT_FILE))
    width = A4[0] - 2 * MARGIN
    doc = pymupdf.open()
    page = None
    y = A4[1]
    pages = 0
    for raw in src.read_text(encoding="utf-8").splitlines():
        for emoji, text in EMOJI.items():
            raw = raw.replace(emoji, text)
        line = "".join(
            c if font.has_glyph(ord(c)) or c == " " else "?" for c in raw.replace("\t", "    ")
        )
        pieces = [""]
        for ch in line:  # wrap by measured width
            if font.text_length(pieces[-1] + ch, fontsize=SIZE) > width:
                pieces.append("")
            pieces[-1] += ch
        for piece in pieces:
            if page is None or y + LEADING > A4[1] - MARGIN:
                page = doc.new_page(width=A4[0], height=A4[1])
                page.insert_font(fontname="jp", fontfile=str(FONT_FILE))
                pages += 1
                y = MARGIN + SIZE
                page.insert_text(
                    (A4[0] - MARGIN - 40, A4[1] - 20), f"{pages}", fontname="jp", fontsize=6
                )
            page.insert_text((MARGIN, y), piece, fontname="jp", fontsize=SIZE)
            y += LEADING
    doc.save(str(dest), garbage=3, deflate=True)
    return pages


if __name__ == "__main__":
    print(to_pdf(Path(sys.argv[1]), Path(sys.argv[2])), "pages")
