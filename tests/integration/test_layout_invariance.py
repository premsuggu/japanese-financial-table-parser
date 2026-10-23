"""The parser must not depend on absolute coordinates, page size or zoom.

The sample page is re-rendered (vector content and text layer intact) at different scales and
offsets, and the result must still match the ground truth exactly.
"""

import pymupdf
import pytest

from fin_table_parser.evaluate import load_truth, score_against_truth
from fin_table_parser.pipeline import parse_page

from ..conftest import CORRECTED_PDF, TRUTH_JSON


def render_scaled(dest, scale: float, dx: float, dy: float, margin: float = 20):
    with pymupdf.open(str(CORRECTED_PDF)) as src:
        w, h = src[0].rect.width, src[0].rect.height
        doc = pymupdf.open()
        page = doc.new_page(width=w * scale + dx + margin, height=h * scale + dy + margin)
        page.show_pdf_page(pymupdf.Rect(dx, dy, dx + w * scale, dy + h * scale), src, 0)
        doc.save(str(dest))
        doc.close()
    return dest


@pytest.mark.parametrize(
    ("scale", "dx", "dy"),
    [(1.0, 40, 90), (0.5, 20, 20), (0.7, 0, 0), (1.3, 0, 0), (2.0, 0, 0), (3.0, 0, 0), (0.4, 5, 5)],
)
def test_result_is_independent_of_scale_and_offset(tmp_path, scale, dx, dy):
    pdf = render_scaled(tmp_path / "scaled.pdf", scale, dx, dy)
    scores = score_against_truth(parse_page(pdf), load_truth(TRUTH_JSON))
    assert scores.errors == []
    assert scores.page_exact
