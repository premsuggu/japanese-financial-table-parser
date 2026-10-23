"""PaddleOCR worker. Runs inside ``.venv-paddle`` (not the main environment).

    python paddle_worker.py --out result.json page1.png page2.png ...

Protocol: all logging goes to stderr; the result is ONE JSON file:
    {"engine": "paddle", "load_seconds": float,
     "pages": [{"seconds": float, "words": [{"text", "x0", "y0", "x1", "y1"}, ...]}, ...]}
Boxes are in image pixels, origin top-left.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Libraries print banners and progress to stdout; keep stdout clean by sending it to stderr.
_real_stdout = sys.stdout
sys.stdout = sys.stderr
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")


def _boxes(result: dict) -> list[tuple[str, float, float, float, float]]:
    texts = list(result["rec_texts"])
    if "rec_boxes" in result and len(result["rec_boxes"]) == len(texts):
        boxes = [tuple(float(v) for v in b[:4]) for b in result["rec_boxes"]]
    else:  # fall back to the polygons
        boxes = []
        for poly in result["rec_polys"]:
            xs = [float(p[0]) for p in poly]
            ys = [float(p[1]) for p in poly]
            boxes.append((min(xs), min(ys), max(xs), max(ys)))
    return [(t, *b) for t, b in zip(texts, boxes, strict=True)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("images", nargs="+")
    args = parser.parse_args()

    from paddleocr import PaddleOCR

    t0 = time.time()
    ocr = PaddleOCR(
        lang="japan",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        # PaddlePaddle 3.x on Windows CPU fails inside oneDNN ("ConvertPirAttribute2RuntimeAttribute
        # not support ...") for these models; turning that acceleration off changes speed only.
        enable_mkldnn=False,
        # A 300 dpi page is 2480 x 3508 px. The default only enforces a MINIMUM side, so the model
        # would run at full size; the usual setting caps the long side (and is far faster).
        text_det_limit_type="max",
        text_det_limit_side_len=int(os.environ.get("PADDLE_DET_SIDE", "1920")),
    )
    load_seconds = time.time() - t0

    pages = []
    for path in args.images:
        t = time.time()
        results = ocr.predict(path)
        seconds = time.time() - t
        words = []
        for result in results:
            for text, x0, y0, x1, y1 in _boxes(result):
                words.append({"text": text, "x0": x0, "y0": y0, "x1": x1, "y1": y1})
        pages.append({"seconds": seconds, "words": words})
        print(f"{path}: {len(words)} words in {seconds:.1f}s", file=sys.stderr)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(
            {"engine": "paddle", "load_seconds": load_seconds, "pages": pages},
            fh,
            ensure_ascii=False,
        )
    sys.stdout = _real_stdout
    return 0


if __name__ == "__main__":
    sys.exit(main())
