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

import json
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .evaluate import GroundTruth, score_against_truth, truth_from_table
from .labels import edit_distance, label_key
from .models import Table
from .normalize import parse_value
from .ocr import OcrEngine, PixelWord, geometry_from_words
from .pdf_io import degrade_image, page_texts, render_page, rescale_image
from .pipeline import parse_ocr_words, parse_page
from .triage import UnsupportedPage
from .validate import summarize, validate_tables

Condition = dict[str, float | int | bool | None]
CONDITIONS: dict[str, Condition] = {
    "clean (300 dpi)": {"dpi": 300, "rotate_deg": 0.0, "jpeg_quality": None},
    "scan-like (150 dpi, JPEG q40)": {"dpi": 150, "rotate_deg": 0.0, "jpeg_quality": 40},
    "skewed (1 degree)": {"dpi": 300, "rotate_deg": 1.0, "jpeg_quality": None},
    "photo-like (150 dpi, blur, noise, uneven light)": {
        "dpi": 150,
        "rotate_deg": 0.5,
        "jpeg_quality": 60,
        "degrade": True,
    },
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


def condition_image(page: SilverPage, cond: Condition) -> bytes:
    """The page as a picture under one test condition (resolution, rotation, compression, degradation)."""
    degrade = bool(cond.get("degrade"))
    image = render_page(
        page.pdf,
        page.page_no,
        dpi=int(cond["dpi"] or 300),
        rotate_deg=float(cond["rotate_deg"] or 0.0),
        jpeg_quality=None
        if degrade
        else (int(cond["jpeg_quality"]) if cond["jpeg_quality"] else None),
    )
    return degrade_image(image) if degrade else image


def run_bakeoff(engines: Sequence[OcrEngine], pages: Sequence[SilverPage]) -> Bakeoff:
    """One batch call per engine and condition: the model loads once, pages are timed separately."""
    out = Bakeoff()
    for engine in engines:
        for name, cond in CONDITIONS.items():
            dpi = int(cond["dpi"] or 300)
            images = [condition_image(p, cond) for p in pages]
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


ReadKey = tuple[str, str, float]  # (page name, condition, rescale factor)
RESCALES = (1.0, 0.75)  # 1.33 was tried too: see docs/reports/phase3-second-read-size.md


def collect_reads(
    engine: OcrEngine,
    pages: Sequence[SilverPage],
    cache: Path | None = None,
    factors: Sequence[float] = RESCALES,
) -> dict[ReadKey, list[PixelWord]]:
    """OCR words of every page under every condition, each image also read after rescaling.

    Words are returned in the pixel frame of the unscaled image, so reads of one page are comparable.
    The result is cached in a JSON file because reading is slow and the safety-net experiments
    reuse the same reads many times.
    """
    reads: dict[ReadKey, list[PixelWord]] = {}
    if cache and cache.exists():
        for key, words in json.loads(cache.read_text(encoding="utf-8")).items():
            name, cond, factor = key.split("|")
            reads[(name, cond, float(factor))] = [PixelWord(*w) for w in words]
    for cname, cond in CONDITIONS.items():
        todo = [p for p in pages for f in factors if (p.name, cname, f) not in reads]
        if not todo:
            continue
        images = {p.name: condition_image(p, cond) for p in pages}
        for f in factors:
            missing = [p for p in pages if (p.name, cname, f) not in reads]
            if not missing:
                continue
            batch = engine.read_images(
                [rescale_image(images[p.name], f) if f != 1.0 else images[p.name] for p in missing]
            )
            for p, words in zip(missing, batch.pages, strict=True):
                reads[(p.name, cname, f)] = [
                    PixelWord(w.text, w.x0 / f, w.y0 / f, w.x1 / f, w.y1 / f) for w in words
                ]
            if cache:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(
                    json.dumps(
                        {
                            f"{n}|{c}|{fa}": [[w.text, w.x0, w.y0, w.x1, w.y1] for w in ws]
                            for (n, c, fa), ws in reads.items()
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
    return reads


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


# ------------------------------------------------------------ safety-net evaluation


def labels_by_document(pdfs: Sequence[Path]) -> dict[str, set[str]]:
    """Label keys of every statement page that passes all its checks, per document."""
    from .labelcheck import table_labels
    from .pdf_io import page_count

    statement_kinds = {"balance_sheet", "income_statement", "comprehensive_income", "cash_flow"}
    out: dict[str, set[str]] = {}
    for pdf in pdfs:
        labels: set[str] = set()
        for page in range(page_count(pdf)):
            try:
                table = parse_page(pdf, page)
            except UnsupportedPage:
                continue
            counts = summarize(validate_tables([table]))
            if table.kind in statement_kinds and counts["FAIL"] == 0 and counts["PASS"] > 0:
                labels |= {
                    k for k in table_labels([table]) if len(k) <= 30 and not set(k) & set("。「」")
                }
        out[pdf.parent.name] = labels
    return out


@dataclass
class SafetyRun:
    page: str
    condition: str
    wrong: bool  # the OCR table differs from the silver reference
    wrong_cells: int
    checks_fail: bool  # an accounting check failed (what exists today)
    label_flags: int
    label_hits: int  # flags that point at a label that really is wrong
    agree_flags: int
    agree_hits: int  # flags that point at a cell/label that really is wrong
    second_failed: bool = False


def _meanings(raws: Sequence[str]) -> list[tuple[object, ...] | None]:
    out: list[tuple[object, ...] | None] = []
    for x in raws:
        v = parse_value(x) if x else None
        out.append((v.kind, v.number, v.negative_zero) if v else None)
    return out


def _truth_cells(truth: GroundTruth) -> dict[str, tuple[str, ...]]:
    seen: dict[str, tuple[str, ...]] = {}
    dup: set[str] = set()
    for r in truth.rows:
        k = label_key(r.label)
        if k in seen:
            dup.add(k)
        seen[k] = tuple(v or "" for v in r.values)
    return {k: v for k, v in seen.items() if k not in dup}


def safety_runs(
    pages: Sequence[SilverPage],
    reads: dict[ReadKey, list[PixelWord]],
    lexicons: dict[str, frozenset[str]],
    second_factor: float,
) -> list[SafetyRun]:
    """Score the two detectors against the silver reference, on cached reads.

    ``lexicons`` maps a page's document directory to the label list used for that page, so a list
    can be built without the page's own document.
    """
    from .crosscheck import compare_reads
    from .labelcheck import check_labels

    runs: list[SafetyRun] = []
    for page in pages:
        known = _truth_cells(page.truth)
        for cname, cond in CONDITIONS.items():
            dpi = int(cond["dpi"] or 300)
            first_key, second_key = (page.name, cname, 1.0), (page.name, cname, second_factor)
            if first_key not in reads or second_key not in reads:
                continue
            geoms = [
                geometry_from_words(page.pdf, page.page_no, reads[k], dpi)
                for k in (first_key, second_key)
            ]
            try:
                t1 = parse_ocr_words(geoms[0], page.pdf.name)
            except UnsupportedPage:
                continue
            try:
                t2: Table | None = parse_ocr_words(geoms[1], page.pdf.name)
            except UnsupportedPage:
                t2 = None
            scores = score_against_truth(t1, page.truth)
            # wrong = a value or a label differs in meaning; print-format differences (a space inside
            # a number, a full-width marker) do not count
            value, label = scores.metrics["cell.parsed_value"], scores.metrics["row.label"]
            wrong_cells = (value.total - value.correct) + (label.total - label.correct)
            wrong = wrong_cells > 0 or scores.rows_pred != scores.rows_truth
            fail = summarize(validate_tables([t1]))["FAIL"] > 0
            labels = [f for f in check_labels(t1, lexicons[page.pdf.parent.name])]
            truth_labels = {label_key(r.label) for r in page.truth.rows}
            label_hits = sum(label_key(f.row) not in truth_labels for f in labels)
            agree = compare_reads(t1, t2) if t2 is not None else []
            agree_hits = 0
            for f in agree:
                key = label_key(f.row)
                if f.column:  # an amount disagreement: is the first read's cell really wrong?
                    row = next((r for r in t1.rows if label_key(r.label) == key), None)
                    ref = known.get(key)
                    if row is not None and ref is not None:
                        got = tuple(v.raw if v else "" for v in row.values)
                        agree_hits += _meanings(got) != _meanings(ref)
                elif (
                    wrong
                ):  # a label / missing-row disagreement: counted as a hit when the page is wrong
                    agree_hits += 1
            runs.append(
                SafetyRun(
                    page.name,
                    cname,
                    wrong,
                    wrong_cells,
                    fail,
                    len(labels),
                    label_hits,
                    len(agree),
                    agree_hits,
                    t2 is None,
                )
            )
    return runs


def render_safety(variants: dict[str, list[SafetyRun]], pages: Sequence[SilverPage]) -> str:
    """Markdown: how many wrong OCR pages each safety net catches, and what it costs in false alarms."""
    lines = [
        "# Safety-net evaluation (YomiToku reads)",
        "",
        f"{len(pages)} silver pages x {len(CONDITIONS)} conditions. A page is *wrong* when the OCR table differs "
        "from the silver reference. *Accounting checks* = a check failed (what existed before this phase). "
        "*Label* = vocabulary check flagged a label. *Reads* = read agreement flagged a difference. "
        "*Any new* = label or reads. *False alarms* = right pages flagged.",
        "",
        "Caveats: silver is not gold; one company; label list built from the same company's filings.",
        "",
    ]
    for name, runs in variants.items():
        lines += [
            f"## {name}",
            "",
            "| Condition | Pages | Wrong | Accounting checks | Label | Reads | Checks + new | False alarms (right pages) | Finding precision |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for cond in [*CONDITIONS, "all"]:
            rs = [r for r in runs if cond == "all" or r.condition == cond]
            wrong = [r for r in rs if r.wrong]
            right = [r for r in rs if not r.wrong]
            flagged = sum(r.label_flags + r.agree_flags for r in rs)
            hits = sum(r.label_hits + r.agree_hits for r in rs)
            lines.append(
                f"| {cond} | {len(rs)} | {len(wrong)} | {sum(r.checks_fail for r in wrong)} "
                f"| {sum(r.label_flags > 0 for r in wrong)} | {sum(r.agree_flags > 0 for r in wrong)} "
                f"| {sum(r.checks_fail or r.label_flags > 0 or r.agree_flags > 0 for r in wrong)} "
                f"| {sum(r.label_flags > 0 or r.agree_flags > 0 for r in right)}/{len(right)} "
                f"| {hits}/{flagged} |"
            )
        lines.append("")
    return "\n".join(lines)
