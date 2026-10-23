"""OCR bake-off: how well does each engine reproduce a trusted parse from a picture of the page?

Reference ("silver"): balance-sheet pages whose text-layer parse passes every accounting check, one
page per company document so that near-identical pages do not dominate. Each page is rendered as an
image under three conditions and the engine's words go through ``pipeline.parse_ocr_words``, the
same function the production OCR route uses. Scores are the usual cell / structure metrics, a
character error rate, and whether the accounting checks notice the engine's mistakes.

Timing: the model is loaded once per engine and condition (one batch call). Load time is reported
apart from per-page recognition time.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .evaluate import GroundTruth, score_against_truth, truth_from_table
from .labels import label_key
from .models import Table
from .ocr import OcrEngine, geometry_from_words
from .pdf_io import page_texts, render_page
from .pipeline import parse_ocr_words, parse_page
from .triage import UnsupportedPage
from .validate import summarize, validate_tables

Condition = dict[str, float | int | None]
CONDITIONS: dict[str, Condition] = {
    "clean (300 dpi)": {"dpi": 300, "rotate_deg": 0.0, "jpeg_quality": None},
    "scan-like (150 dpi, JPEG q40)": {"dpi": 150, "rotate_deg": 0.0, "jpeg_quality": 40},
    "skewed (1 degree)": {"dpi": 300, "rotate_deg": 1.0, "jpeg_quality": None},
}


@dataclass
class SilverPage:
    pdf: Path
    page_no: int
    table: Table
    truth: GroundTruth

    @property
    def name(self) -> str:
        return f"{self.pdf.parent.name}:p{self.page_no + 1}"


def find_silver_pages(
    pdfs: Sequence[Path], limit: int | None = None, one_per_document: bool = True
) -> list[SilverPage]:
    """Assets-half balance-sheet pages that parse from the text layer with no failing check."""
    pages: list[SilverPage] = []
    for pdf in pdfs:
        found_here = 0
        for i, text in enumerate(page_texts(pdf)):
            if "資産合計" not in label_key(text):
                continue
            try:
                table = parse_page(pdf, i)
            except UnsupportedPage:
                continue
            counts = summarize(validate_tables([table]))
            if table.kind == "balance_sheet" and counts["FAIL"] == 0 and len(table.rows) >= 20:
                pages.append(SilverPage(pdf, i, table, truth_from_table(table)))
                found_here += 1
                if one_per_document:
                    break
    if limit and len(pages) > limit:
        # spread the choice over all documents instead of taking the first few (which would be
        # near-identical correction notices)
        step = (len(pages) - 1) / max(1, limit - 1)
        pages = [pages[round(i * step)] for i in range(limit)]
    return pages


def edit_distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


@dataclass
class RunResult:
    engine: str
    page: str
    condition: str
    seconds: float
    ok: bool
    error: str = ""
    cell_f1: float = 0.0
    label_acc: float = 0.0
    level_acc: float = 0.0
    type_acc: float = 0.0
    rows_pred: int = 0
    rows_truth: int = 0
    cer: float = 1.0
    failing_checks: int = 0
    wrong_cells: int = 0
    skew_degrees: float = 0.0


def _cer(table: Table, truth: GroundTruth) -> float:
    """Character error rate over all amount cells; 1.0 when the rows cannot be paired."""
    pred = [v.raw if v else "" for r in table.rows for v in r.values]
    ref = [v or "" for r in truth.rows for v in r.values]
    if len(pred) != len(ref):
        return 1.0
    errors = sum(edit_distance(p, r) for p, r in zip(pred, ref, strict=True))
    return errors / max(1, sum(len(r) for r in ref))


def score_words(
    engine_name: str,
    page: SilverPage,
    condition: str,
    geom_words: Sequence[object],
    seconds: float,
    dpi: int,
) -> RunResult:
    geom = geometry_from_words(page.pdf, page.page_no, geom_words, dpi)  # type: ignore[arg-type]
    try:
        table = parse_ocr_words(geom, page.pdf.name)
    except Exception as exc:  # noqa: BLE001 - a failed run is a result, not a crash
        return RunResult(engine_name, page.name, condition, seconds, False, error=str(exc)[:200])
    scores = score_against_truth(table, page.truth)
    counts = summarize(validate_tables([table]))
    metrics = scores.metrics
    return RunResult(
        engine_name,
        page.name,
        condition,
        seconds,
        True,
        cell_f1=scores.cells.f1,
        label_acc=metrics["row.label"].value,
        level_acc=metrics["row.level"].value,
        type_acc=metrics["row.type"].value,
        rows_pred=scores.rows_pred,
        rows_truth=scores.rows_truth,
        cer=_cer(table, page.truth),
        failing_checks=counts["FAIL"],
        wrong_cells=scores.cells.fp + scores.cells.fn,
        skew_degrees=float(table.meta.get("skew_degrees", 0.0) or 0.0),  # type: ignore[arg-type]
    )


@dataclass
class Bakeoff:
    results: list[RunResult] = field(default_factory=list)
    load_seconds: dict[tuple[str, str], float] = field(default_factory=dict)

    def summary(self, engine: str, condition: str) -> dict[str, float]:
        rows = [r for r in self.results if r.engine == engine and r.condition == condition]
        good = [r for r in rows if r.ok]
        wrong = [r for r in good if r.wrong_cells > 0]
        return {
            "pages": len(rows),
            "failed_runs": len(rows) - len(good),
            "cell_f1": statistics.mean(r.cell_f1 for r in good) if good else 0.0,
            "pages_exact": sum(r.wrong_cells == 0 and r.rows_pred == r.rows_truth for r in good),
            "label_acc": statistics.mean(r.label_acc for r in good) if good else 0.0,
            "level_acc": statistics.mean(r.level_acc for r in good) if good else 0.0,
            "cer": statistics.mean(r.cer for r in good) if good else 1.0,
            "seconds": statistics.mean(r.seconds for r in rows) if rows else 0.0,
            "load": self.load_seconds.get((engine, condition), 0.0),
            "wrong_pages": len(wrong),
            "wrong_pages_flagged": sum(r.failing_checks > 0 for r in wrong),
        }


def run_bakeoff(engines: Sequence[OcrEngine], pages: Sequence[SilverPage]) -> Bakeoff:
    """One batch call per engine and condition: the model loads once, pages are timed separately."""
    out = Bakeoff()
    for engine in engines:
        for name, cond in CONDITIONS.items():
            dpi = int(cond["dpi"] or 300)
            images = [
                render_page(
                    p.pdf,
                    p.page_no,
                    dpi=dpi,
                    rotate_deg=float(cond["rotate_deg"] or 0.0),
                    jpeg_quality=int(cond["jpeg_quality"]) if cond["jpeg_quality"] else None,
                )
                for p in pages
            ]
            try:
                batch = engine.read_images(images)
            except Exception as exc:  # noqa: BLE001 - the whole call failed: every page fails
                for p in pages:
                    out.results.append(
                        RunResult(engine.name, p.name, name, 0.0, False, error=str(exc)[:200])
                    )
                continue
            out.load_seconds[(engine.name, name)] = batch.load_seconds
            for p, words, seconds in zip(pages, batch.pages, batch.page_seconds, strict=True):
                out.results.append(score_words(engine.name, p, name, words, seconds, dpi))
    return out


def render_markdown(bake: Bakeoff, pages: Sequence[SilverPage], sizes: dict[str, str]) -> str:
    engines = sorted({r.engine for r in bake.results})
    lines = [
        "# OCR engine comparison",
        "",
        f"Reference ('silver'): {len(pages)} balance-sheet pages, one per company document, whose text-layer parse "
        "passes every accounting check (" + ", ".join(p.name for p in pages) + ").",
        "Each page is rendered as an image, read by the engine, and the words go through the production OCR "
        "function (`pipeline.parse_ocr_words`: de-skew + words-only extractor).",
        "",
        "Caveats: silver is not gold (a mistake the text layer and the extractor share is invisible), and every "
        "page comes from the same company, so layout variety is small.",
        "",
    ]
    for cond in CONDITIONS:
        lines += [
            f"## {cond}",
            "",
            "| Engine | Cell F1 | Pages exact | Label acc. | Indent acc. | Char error rate | s/page | model load (s) | Wrong pages caught by checks | Failed runs |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for e in engines:
            s = bake.summary(e, cond)
            lines.append(
                f"| {e} | {s['cell_f1']:.1%} | {int(s['pages_exact'])}/{int(s['pages'])} | {s['label_acc']:.1%} "
                f"| {s['level_acc']:.1%} | {s['cer']:.2%} | {s['seconds']:.1f} | {s['load']:.1f} | "
                f"{int(s['wrong_pages_flagged'])}/{int(s['wrong_pages'])} | {int(s['failed_runs'])} |"
            )
        lines.append("")
    errors = [r for r in bake.results if not r.ok]
    if errors:
        lines += ["## Failed runs", ""]
        lines += [f"- {r.engine} {r.page} {r.condition}: {r.error}" for r in errors[:10]] + [""]
    if sizes:
        lines += ["## Disk footprint", ""] + [f"- {k}: {v}" for k, v in sizes.items()] + [""]
    return "\n".join(lines)
