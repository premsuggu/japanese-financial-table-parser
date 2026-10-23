"""YomiToku OCR worker. Runs inside ``.venv-yomitoku`` (not the main environment).

    python yomitoku_worker.py --out result.json page1.png page2.png ...

Protocol: all logging goes to stderr; the result is ONE JSON file:
    {"engine": "yomitoku", "load_seconds": float,
     "pages": [{"seconds": float, "words": [{"text", "x0", "y0", "x1", "y1"}, ...]}, ...]}
Boxes are in image pixels, origin top-left.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

# Libraries print banners and progress to stdout; keep stdout clean by sending it to stderr.
_real_stdout = sys.stdout
sys.stdout = sys.stderr


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("images", nargs="+")
    args = parser.parse_args()

    import cv2
    from yomitoku import OCR

    t0 = time.time()
    ocr = OCR(visualize=False, device="cpu")
    load_seconds = time.time() - t0

    pages = []
    for path in args.images:
        image = cv2.imread(path)
        if image is None:
            raise SystemExit(f"cannot read image {path}")
        t = time.time()
        results, _ = ocr(image)
        seconds = time.time() - t
        words = []
        for w in results.words:
            xs = [p[0] for p in w.points]
            ys = [p[1] for p in w.points]
            words.append(
                {
                    "text": w.content,
                    "x0": float(min(xs)),
                    "y0": float(min(ys)),
                    "x1": float(max(xs)),
                    "y1": float(max(ys)),
                }
            )
        pages.append({"seconds": seconds, "words": words})
        print(f"{path}: {len(words)} words in {seconds:.1f}s", file=sys.stderr)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(
            {"engine": "yomitoku", "load_seconds": load_seconds, "pages": pages},
            fh,
            ensure_ascii=False,
        )
    sys.stdout = _real_stdout
    return 0


if __name__ == "__main__":
    sys.exit(main())
