"""OCR route: turn page images into words with boxes, the same input the text strategy uses.

Engines (PaddleOCR, YomiToku, ...) live in their own virtual environments so the main environment
stays light and an engine can be removed by deleting one folder. The main code talks to an engine
through a worker script; ``OcrEngine`` is the only interface the rest of the package sees, so a
test can use a stand-in.

Worker protocol (see ``tools/ocr``): ``python worker.py --out result.json image1 image2 ...``.
The worker writes ONE JSON file and sends all its logging to stderr, so library banners can never
corrupt the result. Several images go in one call so that model loading is paid once and can be
reported separately from per-page recognition time.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .models import PageGeometry, Word
from .pdf_io import PdfSource, page_size, render_page

OCR_DPI = 300
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# OCR engines often return a visually similar character instead of the accounting sign.
# A bare dash-like token means "nil"; the same characters inside a word are NOT touched (the
# katakana long-vowel mark in リース資産 is the character ー).
_NIL_LOOKALIKES = {"ー", "―", "—", "–", "−", "-"}
_SIGN_LOOKALIKE = re.compile(r"^[Δ∆▲](?=[\d,，.．]|$)")


@dataclass(frozen=True)
class PixelWord:
    """A recognised text box in image pixels (origin top-left)."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class OcrBatch:
    """Words for each image, plus timing: model load is reported apart from recognition."""

    pages: list[list[PixelWord]]
    load_seconds: float = 0.0
    page_seconds: list[float] = field(default_factory=list)


class OcrEngine(Protocol):
    name: str

    def read_images(self, images: Sequence[bytes]) -> OcrBatch: ...


class SubprocessEngine:
    """Runs ``<venv python> <worker> --out <json> <images...>`` and reads the JSON file."""

    def __init__(self, name: str, python: Path, script: Path, timeout: float = 3600) -> None:
        self.name = name
        self.python = python
        self.script = script
        self.timeout = timeout

    def read_images(self, images: Sequence[bytes]) -> OcrBatch:
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for i, data in enumerate(images):
                suffix = ".jpg" if data[:2] == b"\xff\xd8" else ".png"
                path = Path(tmp) / f"page{i:03d}{suffix}"
                path.write_bytes(data)
                paths.append(str(path))
            out = Path(tmp) / "result.json"
            done = subprocess.run(
                [str(self.python), "-X", "utf8", str(self.script), "--out", str(out), *paths],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout,
                check=False,
            )
            if done.returncode != 0 or not out.exists():
                raise RuntimeError(f"{self.name} worker failed: {done.stderr.strip()[-600:]}")
            payload = json.loads(out.read_text(encoding="utf-8"))
        pages = [[PixelWord(**w) for w in page["words"]] for page in payload["pages"]]
        return OcrBatch(
            pages=pages,
            load_seconds=float(payload.get("load_seconds", 0.0)),
            page_seconds=[float(p.get("seconds", 0.0)) for p in payload["pages"]],
        )


def available_engines(root: Path = PROJECT_ROOT) -> dict[str, SubprocessEngine]:
    """Engines whose virtual environment and worker script both exist."""
    found: dict[str, SubprocessEngine] = {}
    for name in ("paddle", "yomitoku"):
        python = (
            root
            / f".venv-{name}"
            / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        )
        script = root / "tools" / "ocr" / f"{name}_worker.py"
        if python.exists() and script.exists():
            found[name] = SubprocessEngine(name, python, script)
    return found


def read_one(engine: OcrEngine, png: bytes) -> list[PixelWord]:
    return engine.read_images([png]).pages[0]


def clean_text(text: str) -> str:
    text = text.strip()
    if text in _NIL_LOOKALIKES:
        return "－"
    return _SIGN_LOOKALIKE.sub("△", text)


def words_from_pixels(pixel_words: Sequence[PixelWord], dpi: int) -> list[Word]:
    """Pixel boxes -> PDF points, dropping empty boxes."""
    k = 72.0 / dpi
    words = []
    for w in pixel_words:
        text = clean_text(w.text)
        if text:
            words.append(Word(text, w.x0 * k, w.y0 * k, w.x1 * k, w.y1 * k))
    return words


def geometry_from_words(
    source: PdfSource, page_no: int, pixel_words: Sequence[PixelWord], dpi: int = OCR_DPI
) -> PageGeometry:
    width, height = page_size(source, page_no)
    return PageGeometry(
        page_no=page_no,
        width=width,
        height=height,
        words=words_from_pixels(pixel_words, dpi),
        fills=[],
        rules=[],
    )


def ocr_geometry(
    source: PdfSource, page_no: int, engine: OcrEngine, dpi: int = OCR_DPI
) -> PageGeometry:
    """Rasterise a page, run OCR, and return it as a words-only ``PageGeometry``."""
    png = render_page(source, page_no, dpi=dpi)
    return geometry_from_words(source, page_no, read_one(engine, png), dpi)
