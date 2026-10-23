"""Build chat_briefed.pdf: only the user's prompts and the assistant's final answer to each.

    python -X utf8 tools/chat_brief.py <session>.jsonl chat_briefed.pdf

Tool calls, tool results, system notices and intermediate messages are left out. Prompts are shown in
a coloured box, answers as plain text.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

FONT = "C:/Windows/Fonts/msgothic.ttc"
FONT_BOLD = "C:/Windows/Fonts/MEIRYOB.TTC"
SIZE = 8.0
LEADING = 10.4
MARGIN = 40.0
A4 = (595.0, 842.0)
EMOJI = {
    "✅": "[ok]",
    "👁": "[review]",
    "🚧": "[unsupported]",
    "⚠": "[check]",
    "❔": "[unverified]",
    "🔸": "*",
    "️": "",
}
SYSTEM_BLOCKS = re.compile(
    r"<(system-reminder|local-command-caveat|command-[a-z]+|local-command-stdout)>.*?</\1>", re.S
)
NOT_A_PROMPT = (
    "This session is being continued",
    "[SYSTEM NOTIFICATION",
    "<task-notification",
    "Caveat:",
    "[Request interrupted",
)

USER_BG = (0.86, 0.92, 1.0)
USER_BAR = (0.12, 0.36, 0.70)


@dataclass
class Turn:
    prompt: str
    answers: list[str] = field(default_factory=list)


def _text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def read_turns(path: Path) -> list[Turn]:
    turns: list[Turn] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("isSidechain") or rec.get("type") not in ("user", "assistant"):
            continue
        msg = rec.get("message") or {}
        text = _text(msg.get("content"))
        if rec["type"] == "user":
            if isinstance(msg.get("content"), list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in msg["content"]
            ):
                continue
            clean = SYSTEM_BLOCKS.sub("", text).strip()
            if not clean or clean.startswith(NOT_A_PROMPT) or "<command-name>" in text:
                continue
            turns.append(Turn(clean))
        elif turns and text.strip():
            turns[-1].answers.append(text.strip())
    return turns


SHORT = 600  # a closing line this short is a status note: the report it followed is shown too


def final_answers(turn: Turn) -> list[str]:
    """The last message of the turn; with it the longest earlier message when the last is only a short note."""
    if not turn.answers:
        return []
    last = turn.answers[-1]
    earlier = turn.answers[:-1]
    if len(last) < SHORT and earlier:
        report = max(earlier, key=len)
        if len(report) > len(last):
            return [report, last]
    return [last]


def _clean(s: str) -> str:
    for emoji, repl in EMOJI.items():
        s = s.replace(emoji, repl)
    return s.replace("\t", "    ").replace("**", "")


class Writer:
    def __init__(self) -> None:
        self.doc = pymupdf.open()
        self.font = pymupdf.Font(fontfile=FONT)
        self.page: pymupdf.Page | None = None
        self.y = A4[1]
        self.width = A4[0] - 2 * MARGIN

    def _new_page(self) -> None:
        self.page = self.doc.new_page(width=A4[0], height=A4[1])
        self.page.insert_font(fontname="jp", fontfile=FONT)
        self.page.insert_font(fontname="jpb", fontfile=FONT_BOLD)
        self.y = MARGIN
        n = self.doc.page_count
        self.page.insert_text((A4[0] - MARGIN - 10, A4[1] - 20), str(n), fontname="jp", fontsize=6)

    def _wrap(self, text: str, width: float) -> list[str]:
        out: list[str] = []
        for raw in _clean(text).splitlines() or [""]:
            line = "".join(c if self.font.has_glyph(ord(c)) or c == " " else "?" for c in raw)
            piece = ""
            for ch in line:
                if self.font.text_length(piece + ch, fontsize=SIZE) > width:
                    out.append(piece)
                    piece = ""
                piece += ch
            out.append(piece)
        return out

    def label(self, text: str, color: tuple[float, float, float]) -> None:
        if self.page is None or self.y + 22 > A4[1] - MARGIN:
            self._new_page()
        assert self.page is not None
        self.y += 6
        self.page.insert_text((MARGIN, self.y + 8), text, fontname="jpb", fontsize=8, color=color)
        self.y += 14

    def block(self, text: str, boxed: bool) -> None:
        pad = 5.0
        inner = self.width - (2 * pad + 3 if boxed else 0)
        lines = self._wrap(text, inner)
        i = 0
        while i < len(lines):
            if self.page is None or self.y + LEADING + 2 * pad > A4[1] - MARGIN:
                self._new_page()
            assert self.page is not None
            room = int((A4[1] - MARGIN - self.y - 2 * pad) // LEADING)
            chunk = lines[i : i + max(room, 1)]
            i += len(chunk)
            top = self.y
            height = len(chunk) * LEADING + (2 * pad if boxed else 0)
            if boxed:
                self.page.draw_rect(
                    pymupdf.Rect(MARGIN, top, MARGIN + self.width, top + height),
                    color=None,
                    fill=USER_BG,
                )
                self.page.draw_rect(
                    pymupdf.Rect(MARGIN, top, MARGIN + 3, top + height), color=None, fill=USER_BAR
                )
            x = MARGIN + (pad + 3 if boxed else 0)
            ty = top + (pad if boxed else 0) + SIZE
            for ln in chunk:
                self.page.insert_text(
                    (x, ty),
                    ln,
                    fontname="jp",
                    fontsize=SIZE,
                    color=(0.05, 0.05, 0.25) if boxed else (0.1, 0.1, 0.1),
                )
                ty += LEADING
            self.y = top + height + 2

    def gap(self, h: float = 6.0) -> None:
        self.y += h


def build(jsonl: Path, dest: Path) -> tuple[int, int]:
    turns = read_turns(jsonl)
    w = Writer()
    w._new_page()
    assert w.page is not None
    w.page.insert_text(
        (MARGIN, w.y + 14),
        "Project chat (briefed): prompts and final answers only",
        fontname="jpb",
        fontsize=13,
    )
    w.y += 24
    w.block(
        "Tool calls, tool output and intermediate messages are omitted. Blue boxes are the user's prompts; "
        "plain text is the assistant's final answer to each prompt. Full transcript: chat.pdf.",
        boxed=False,
    )
    w.gap(10)
    for n, t in enumerate(turns, start=1):
        w.label(f"USER  #{n}", USER_BAR)
        w.block(t.prompt, boxed=True)
        shown = final_answers(t)
        if shown:
            w.label("ASSISTANT", (0.25, 0.25, 0.25))
            for answer in shown:
                w.block(answer, boxed=False)
                w.gap(4)
        w.gap(8)
    w.doc.save(str(dest), garbage=3, deflate=True)
    return len(turns), w.doc.page_count


if __name__ == "__main__":
    turns, pages = build(Path(sys.argv[1]), Path(sys.argv[2]))
    print(turns, "prompts,", pages, "pages")
