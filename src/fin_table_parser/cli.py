"""Command line: parse a PDF page to Excel, check a workbook, or evaluate against ground truth.

python -m fin_table_parser parse  in.pdf -o output/in.xlsx [--page 0]
python -m fin_table_parser check  output/in.xlsx
python -m fin_table_parser evaluate in.pdf truth.json -o docs/reports/metrics.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .evaluate import load_truth, mutation_test, score_against_truth, score_baseline
from .export import write_workbook
from .pdf_io import baseline_find_tables
from .pipeline import parse_page
from .report import render_report
from .triage import UnsupportedPage
from .validate import summarize, validate_tables
from .xlsx_reader import read_workbook


def _cmd_parse(args: argparse.Namespace) -> int:
    table = parse_page(args.pdf, args.page)
    findings = validate_tables([table])
    out = write_workbook([table], findings, args.output)
    print(f"wrote {out}  ({len(table.rows)} rows)  checks: {summarize(findings)}")
    return 1 if summarize(findings)["FAIL"] else 0


def _cmd_check(args: argparse.Namespace) -> int:
    tables = read_workbook(args.xlsx)
    findings = validate_tables(tables)
    for f in findings:
        if f.status in ("FAIL", "SKIP") or args.verbose:
            print(
                f"{f.status:13s} {f.check:34s} {f.column[:8]:8s} {f.row}  expected={f.expected} actual={f.actual}  {f.detail}"
            )
    counts = summarize(findings)
    print(counts)
    return 1 if counts["FAIL"] else 0


def _cmd_evaluate(args: argparse.Namespace) -> int:
    truth = load_truth(args.truth)
    table = parse_page(args.pdf, truth_page(args.truth))
    xlsx = Path(args.workdir) / (Path(args.pdf).stem + ".xlsx")
    write_workbook([table], validate_tables([table]), xlsx)
    reread = read_workbook(xlsx)[0]  # evaluate what is in the file, not the in-memory object
    scores = score_against_truth(reread, truth)
    baseline = score_baseline(baseline_find_tables(args.pdf, truth_page(args.truth)), truth)
    findings = validate_tables([reread])
    report = render_report(
        Path(args.pdf).name, truth, scores, baseline, findings, mutation_test(reread)
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(report, encoding="utf-8")
    print(report)
    return 0 if scores.page_exact else 1


def _cmd_ui(args: argparse.Namespace) -> int:
    import subprocess

    app = Path(__file__).with_name("app.py")
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app),
        "--server.port",
        str(args.port),
        # passed explicitly: .streamlit/config.toml is only read from the project directory, and
        # the page handles financial documents, so it must never listen on the network
        "--server.address",
        "localhost",
        "--browser.gatherUsageStats",
        "false",
    ]
    return subprocess.call(cmd)


def _cmd_ocr_eval(args: argparse.Namespace) -> int:
    from .ocr import available_engines
    from .ocr_eval import find_silver_pages, render_markdown, run_bakeoff

    found = available_engines()
    wanted = [n for n in args.engines.split(",") if n]
    missing = [n for n in wanted if n not in found]
    if missing:
        print(f"engine(s) not available: {missing}; available: {sorted(found)}", file=sys.stderr)
        return 2
    pdfs = sorted(Path(args.corpus).glob("*/*.pdf"))
    pages = find_silver_pages(pdfs, args.limit)
    print(f"{len(pages)} silver pages: {[p.name for p in pages]}")
    from .ocr_eval import Bakeoff

    combined = Bakeoff()
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    for name in wanted:  # one engine at a time; the report is rewritten after each, so none is lost
        part = run_bakeoff([found[name]], pages)
        combined.results += part.results
        combined.load_seconds.update(part.load_seconds)
        Path(args.output).write_text(render_markdown(combined, pages, {}), encoding="utf-8")
        print(f"finished {name}; report updated", flush=True)
    print(Path(args.output).read_text(encoding="utf-8"))
    return 0


def _cmd_safety_eval(args: argparse.Namespace) -> int:
    from .ocr import available_engines
    from .ocr_eval import (
        RESCALES,
        collect_reads,
        find_silver_pages,
        labels_by_document,
        render_safety,
        safety_runs,
    )

    engines = available_engines()
    if args.engine not in engines:
        print(f"engine {args.engine!r} not available: {sorted(engines)}", file=sys.stderr)
        return 2
    pdfs = sorted(Path(args.corpus).glob("*/*.pdf"))
    pages = find_silver_pages(pdfs, args.limit, one_per_document=not args.every_page)
    reads = collect_reads(engines[args.engine], pages, Path(args.cache))
    per_doc = labels_by_document(pdfs)
    from .labelcheck import load_lexicon

    full = {p.pdf.parent.name: load_lexicon() for p in pages}
    others = {
        d: frozenset(set().union(*(v for k, v in per_doc.items() if k != d))) for d in per_doc
    }
    variants = {}
    for factor in (f for f in RESCALES if f != 1.0):
        variants[f"second read at {factor}x pixels, label list = shipped list"] = safety_runs(
            pages, reads, full, factor
        )
        variants[f"second read at {factor}x pixels, label list without the page's own document"] = (
            safety_runs(pages, reads, others, factor)
        )
    report = render_safety(variants, pages)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(report, encoding="utf-8")
    print(report)
    return 0


def truth_page(truth_path: str) -> int:
    import json

    return int(json.loads(Path(truth_path).read_text(encoding="utf-8")).get("page_no", 0))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="fin_table_parser")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("parse", help="parse one PDF page into an Excel workbook")
    p.add_argument("pdf")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--page", type=int, default=0, help="0-based page number")
    p.set_defaults(func=_cmd_parse)
    c = sub.add_parser("check", help="run the accounting checks on a workbook")
    c.add_argument("xlsx")
    c.add_argument("-v", "--verbose", action="store_true")
    c.set_defaults(func=_cmd_check)
    e = sub.add_parser("evaluate", help="score the parser against a ground-truth JSON")
    e.add_argument("pdf")
    e.add_argument("truth")
    e.add_argument("-o", "--output", required=True, help="Markdown report path")
    e.add_argument("--workdir", default="output")
    e.set_defaults(func=_cmd_evaluate)
    o = sub.add_parser("ocr-eval", help="compare OCR engines against text-layer parses")
    o.add_argument("--engines", default="paddle,yomitoku")
    o.add_argument("--corpus", default="data/corpus/yamato")
    o.add_argument("--limit", type=int, default=6, help="number of silver pages to use")
    o.add_argument("-o", "--output", default="docs/reports/ocr-comparison.md")
    o.set_defaults(func=_cmd_ocr_eval)
    sf = sub.add_parser("safety-eval", help="how many wrong OCR pages do the extra checks catch")
    sf.add_argument("--engine", default="yomitoku")
    sf.add_argument("--corpus", default="data/corpus/yamato")
    sf.add_argument("--limit", type=int, default=6)
    sf.add_argument(
        "--every-page", action="store_true", help="every silver page, not one per document"
    )
    sf.add_argument("--cache", default="data/cache/yomitoku_reads.json")
    sf.add_argument("-o", "--output", default="docs/reports/phase3-metrics.md")
    sf.set_defaults(func=_cmd_safety_eval)
    u = sub.add_parser("ui", help="open the upload-a-PDF web page")
    u.add_argument("--port", type=int, default=8501)
    u.set_defaults(func=_cmd_ui)
    args = ap.parse_args(argv)
    try:
        return int(args.func(args))
    except UnsupportedPage as exc:
        print(f"unsupported page: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
