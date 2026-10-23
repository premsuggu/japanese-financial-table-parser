"""Streamlit UI: upload a PDF, get its statement tables, checks and an Excel file.

Run:  python -m fin_table_parser ui     (or: streamlit run src/fin_table_parser/app.py)
"""

from __future__ import annotations

import streamlit as st

from fin_table_parser.document import PageResult, parse_document
from fin_table_parser.export import workbook_bytes
from fin_table_parser.ocr import available_engines
from fin_table_parser.pdf_io import page_count, render_page
from fin_table_parser.ui_model import (
    KIND_LABELS,
    SCOPES,
    findings_frame,
    group_health,
    parse_page_spec,
    row_styles,
    select_results,
    skipped_pages,
    table_frame,
    table_title,
)
from fin_table_parser.validate import summarize, validate_tables

st.set_page_config(page_title="Statement parser", page_icon="📄", layout="wide")


@st.cache_data(show_spinner=False)
def run_parse(
    data: bytes,
    pages: tuple[int, ...] | None,
    strategy: str,
    engine_name: str,
    force_ocr: bool,
    verify: bool,
) -> list[PageResult]:
    engine = available_engines().get(engine_name)
    return parse_document(
        data,
        pages=pages,
        strategy=strategy,  # type: ignore[arg-type]
        ocr=engine,
        force_ocr=force_ocr,
        verify=verify,
    )


@st.cache_data(show_spinner=False)
def preview(data: bytes, page_no: int) -> bytes:
    return render_page(data, page_no)


STATUS_ICON = {"ok": "✅", "review": "👁️", "check": "⚠️", "unsupported": "🚧", "unverified": "❔"}
STATUS_COLOR = {
    "PASS": "#2e7d32",
    "PASS_ROUNDING": "#9e8600",
    "FAIL": "#c62828",
    "WARN": "#ef6c00",
    "SKIP": "#757575",
}


def color_status(value: str) -> str:
    return f"color: {STATUS_COLOR.get(value, 'inherit')}; font-weight: 600"


st.title("Financial statement parser")
st.caption("Upload a PDF. Each statement becomes a table that is checked against accounting rules.")

upload = st.file_uploader("PDF file", type=["pdf"], label_visibility="collapsed")

with st.sidebar:
    st.header("Options")
    scope = st.radio("Extract", list(SCOPES), help="Which kinds of tables to show.")
    pages_text = st.text_input("Pages", "all", help="For example: all, 1-5, 8, 10-12")
    engines = available_engines()
    engine_name = st.selectbox(
        "Scanned pages",
        ["no OCR", *engines],
        help="OCR engine used when a page has no usable text layer (a scan).",
    )
    verify = st.checkbox(
        "Read twice and compare",
        value=False,
        disabled=engine_name == "no OCR",
        help="Reads each page a second time (OCR against the text layer, or OCR at another size) and"
        " flags the cells where the reads differ. Doubles the OCR time.",
    )
    with st.expander("Advanced"):
        force_ocr = st.checkbox(
            "Force OCR on every page",
            value=False,
            disabled=engine_name == "no OCR",
            help="Read the page image instead of the text layer: for testing OCR on a normal PDF.",
        )
        strategy = st.selectbox(
            "Method",
            ["auto", "banded", "text"],
            help="auto: shaded rows when the page has them, otherwise the words alone.",
        )
        numeric = st.checkbox("Show signed numbers instead of printed text", value=False)

if upload is None:
    st.info("Drop a PDF above to begin. Try a 決算短信 or 有価証券報告書 with a 貸借対照表.")
    st.stop()

data = upload.getvalue()
try:
    total = page_count(data)
    wanted = parse_page_spec(pages_text, total)
except Exception as exc:  # noqa: BLE001 - show any problem with the file or the page range
    st.error(f"Cannot open this file or page range: {exc}")
    st.stop()

with st.spinner(f"Reading {len(wanted) if wanted else total} page(s)…"):
    results = run_parse(
        data,
        tuple(wanted) if wanted is not None else None,
        strategy,
        engine_name if engine_name != "no OCR" else "",
        force_ocr,
        verify,
    )

shown = select_results(results, scope)
tables = [r.table for r in shown if r.table is not None]
findings = validate_tables(tables)
counts = summarize(findings)

left, mid, right = st.columns([3, 3, 2])
left.metric("Tables found", len(tables))
mid.metric(
    "Checks passed",
    counts["PASS"] + counts["PASS_ROUNDING"],
    help="Includes totals that differ from the sum of their lines only by rounding.",
)
right.metric("Checks failed", counts["FAIL"] + counts["WARN"])

if not tables:
    st.warning(
        "No table of this kind was found. Try 'Every table found' in the sidebar"
        " or check the Pages tab for the reason each page was skipped."
    )

if tables:
    st.download_button(
        "⬇ Download Excel",
        workbook_bytes(tables, findings),
        file_name=f"{upload.name.rsplit('.', 1)[0]}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )

_states = group_health([r.table for r in shown if r.table is not None])
health = {id(r): state for r, state in zip(shown, _states, strict=True)}
tab_names = [f"{STATUS_ICON[health[id(r)][0]]} {table_title(r)}" for r in shown]
tabs = st.tabs([*tab_names, "Checks", "Pages"])

for tab, result in zip(tabs, shown, strict=False):
    table = result.table
    assert table is not None
    state, own = health[id(result)]
    with tab:
        meta = [table.statement or KIND_LABELS.get(table.kind, table.kind)]
        if table.unit:
            meta.append(f"unit: {table.unit}")
        if table.meta.get("revision"):
            meta.append(str(table.meta["revision"]))
        layout = table.meta.get("strategy", "text")
        meta.append(f"read via {result.route or 'text-layer'} ({layout} layout)")
        st.caption(" · ".join(meta))
        if state == "unsupported":
            st.warning(
                "This kind of layout is not fully supported yet. Some numbers may be wrong or missing;"
                " see the Checks tab."
            )
        elif state == "unverified":
            st.info(
                "No accounting check could run on this table, so its numbers are not verified."
                " Compare it with the page image."
            )
        elif state == "review":
            st.info(
                "Read by OCR and not double-checked: the numbers add up, but a misread label would not"
                " show in the checks. Compare with the page image, or turn on 'Read twice and compare'."
            )
        elif state == "check":
            st.warning("Some accounting checks do not hold. See the Checks tab.")
        table_col, page_col = st.columns([3, 2])
        frame = table_frame(table, numeric)
        styles = row_styles(table)
        table_col.dataframe(
            frame.style.apply(lambda row, st_=styles: [st_[row.name]] * len(row), axis=1),
            hide_index=True,
            use_container_width=True,
            height=min(760, 38 + 35 * len(frame)),
        )
        table_col.download_button(
            "CSV",
            frame.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{table_title(result)}.csv",
            mime="text/csv",
            key=f"csv-{result.page_no}",
        )
        page_col.image(preview(data, result.page_no), caption=f"page {result.page_no + 1}")

with tabs[len(shown)]:
    if findings:
        frame = findings_frame(findings)
        only_bad = st.checkbox("Only problems", value=False)
        if only_bad:
            frame = frame[frame["Status"].isin(["FAIL", "WARN", "SKIP"])]
        st.dataframe(
            frame.style.map(color_status, subset=["Status"]),
            hide_index=True,
            use_container_width=True,
        )
        st.caption(
            "PASS_ROUNDING: the printed total differs from the sum of its lines by no more than one unit"
            " per figure, which is normal because each figure is rounded separately."
        )
    else:
        st.write("No checks ran.")

with tabs[len(shown) + 1]:
    skipped = skipped_pages(results)
    if skipped.empty:
        st.write("Every page produced a table.")
    else:
        st.dataframe(skipped, hide_index=True, use_container_width=True)
