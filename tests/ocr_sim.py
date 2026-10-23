"""Stand-in OCR engine for tests: the page's own words, degraded the way real OCR degrades them.

Real OCR boxes are less exact than a text layer (jitter), engines often split a sign from its
digits (``△`` + ``2,979``), and scans are rotated. This lets the routing and the tolerance of the
text strategy be tested without a real engine.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, field

import pymupdf

from fin_table_parser.models import PageGeometry
from fin_table_parser.ocr import OcrBatch, PixelWord

SIGNS = "△▲"


@dataclass
class SimulatedOcr:
    geom: PageGeometry
    dpi: int = 300
    jitter_pt: float = 0.0  # max random shift of each box edge, in PDF points
    split_signs: bool = False
    skew_deg: float = 0.0  # rotate the whole page by this angle (clockwise positive)
    seed: int = 0
    name: str = "simulated"
    calls: list[int] = field(default_factory=list)
    wrong_on_call: dict[int, tuple[str, str]] = field(
        default_factory=dict
    )  # call number -> (from, to)

    def read_images(self, images: Sequence[bytes]) -> OcrBatch:
        pages = []
        for image in images:
            self.calls.append(len(image))
            # boxes are in the pixel frame of the image actually given (it may have been rescaled)
            scale = pymupdf.Pixmap(image).width / (self.geom.width * self.dpi / 72.0)
            words = self._words(scale)
            swap = self.wrong_on_call.get(len(self.calls))
            if swap:
                words = [
                    PixelWord(swap[1] if w.text == swap[0] else w.text, w.x0, w.y0, w.x1, w.y1)
                    for w in words
                ]
            pages.append(words)
        return OcrBatch(pages=pages, page_seconds=[0.0] * len(images))

    def _words(self, scale: float = 1.0) -> list[PixelWord]:
        rng = random.Random(self.seed)
        k = self.dpi / 72.0 * scale
        angle = math.radians(self.skew_deg)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        ox, oy = self.geom.width / 2, self.geom.height / 2

        def j() -> float:
            return rng.uniform(-self.jitter_pt, self.jitter_pt) * k

        def rot(x: float, y: float) -> tuple[float, float]:
            dx, dy = x - ox, y - oy
            return ox + dx * cos_a - dy * sin_a, oy + dx * sin_a + dy * cos_a

        def box(text: str, x0: float, y0: float, x1: float, y1: float) -> PixelWord:
            cx, cy = rot((x0 + x1) / 2, (y0 + y1) / 2)
            hw, hh = (x1 - x0) / 2, (y1 - y0) / 2
            return PixelWord(
                text,
                (cx - hw) * k + j(),
                (cy - hh) * k + j(),
                (cx + hw) * k + j(),
                (cy + hh) * k + j(),
            )

        out: list[PixelWord] = []
        for w in self.geom.words:
            if self.split_signs and w.text[:1] in SIGNS and len(w.text) > 1:
                cut = w.x0 + (w.x1 - w.x0) / len(w.text)
                out.append(box(w.text[0], w.x0, w.y0, cut, w.y1))
                out.append(box(w.text[1:], cut, w.y0, w.x1, w.y1))
            else:
                out.append(box(w.text, w.x0, w.y0, w.x1, w.y1))
        return out
