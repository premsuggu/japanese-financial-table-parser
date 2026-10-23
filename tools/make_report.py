"""Write the one-page project report (report.pdf).

python -X utf8 tools/make_report.py
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
FONTS = Path("C:/Windows/Fonts")

CSS = """
@font-face { font-family: jp; src: url(MEIRYO.TTC); }
@font-face { font-family: jp; font-weight: bold; src: url(MEIRYOB.TTC); }
body { font-family: jp; font-size: 9.3pt; line-height: 1.28; color: #1a1a1a; }
h1 { font-size: 15pt; margin: 0 0 1pt 0; }
p.sub { font-size: 8.6pt; color: #555; margin: 0 0 5pt 0; }
h2 { font-size: 9.6pt; margin: 6pt 0 2pt 0; color: #1f4e79; border-bottom: 0.6pt solid #1f4e79; }
p { margin: 0 0 2.5pt 0; }
ul { margin: 0 0 2pt 0; padding-left: 11pt; }
li { margin: 0 0 1.5pt 0; }
table { border-collapse: collapse; width: 100%; margin: 2pt 0; }
th { background: #dce6f1; text-align: left; font-size: 8.8pt; padding: 1.5pt 3pt; border: 0.4pt solid #999; }
td { font-size: 8.8pt; padding: 1.5pt 3pt; border: 0.4pt solid #999; }
"""

HTML = """
<h1>Japanese consolidated balance-sheet parser: project report</h1>
<p class="sub">PDF page (text layer or scan) in, verified Excel table out. Personal, non-commercial project.
Code and test material: github.com/premsuggu/japanese-financial-table-parser. October 2026.</p>

<h2>Goal</h2>
<p>Read a page of a Japanese consolidated balance sheet whose layout may vary and which may be scanned, and produce a correct
table: row labels, values, columns, hierarchy, units and accounting signs (&#9651; negative, &#65293; nil), with no hard-coded
coordinates. Output: one Excel workbook per PDF, one sheet per statement, plus Validation and Metadata sheets.</p>

<h2>Approach</h2>
<ul>
<li><b>Triage and routing.</b> A healthy text layer is used directly. A scan, or a page with no usable text, goes to OCR
(YomiToku, chosen over PaddleOCR in a bake-off), after de-skewing.</li>
<li><b>Extraction.</b> Rows come from line spacing, value columns from the right edges of the amounts, hierarchy from label
indent, header and period from the block above the first amount. A second strategy uses shaded row bands when they exist.
Every tolerance is a fraction of a length measured on the page (word height, row pitch), so scale and layout do not matter;
tested from 0.4x to 3x.</li>
<li><b>Validation.</b> Assets = liabilities + equity, totals equal their components (rounding tolerance), income-statement and
cash-flow formulas from a readable YAML rule file (J-GAAP and IFRS variants). An unreadable cell is a loud failure, never a zero.</li>
<li><b>OCR safety net.</b> The accounting checks cannot see a misread label, so a page can be read twice and compared, and
labels one character from a known account name are flagged. Nothing is corrected silently.</li>
<li><b>Layouts.</b> Note-number column, wrapped labels, two-panel account form, IFRS statements, page-number footers.</li>
<li><b>UI.</b> Local Streamlit page (python -m fin_table_parser ui): upload a PDF, see tables, checks and the page image,
download Excel or CSV. Each table is marked ok, review (OCR), check, unverified or unsupported.</li>
</ul>

<h2>Results</h2>
<table>
<tr><th>What was measured</th><th>Result</th></tr>
<tr><td>Sample page vs ground truth (human-reviewed, 43 rows)</td><td>43/43 rows, 86/86 values, labels, levels, paths, types 100%; page exact</td></tr>
<tr><td>Whole company filing, 13 test PDFs (12 PDFs of one company, 1 IFRS filing of another)</td><td>all statements found; 0 failed checks (e.g. 80 passed on the filing, 119 on the 109-page annual report)</td></tr>
<tr><td>Text-only strategy vs band strategy</td><td>identical output on 28 of 28 comparable pages</td></tr>
<tr><td>OCR, YomiToku, 6 pages, clean / scan-like</td><td>cell F1 97% / 93%, about 12 s per page (PaddleOCR: 84% / 91%, about 72 s)</td></tr>
<tr><td>Wrong OCR pages caught (22 pages x 3 simulated conditions)</td><td>accounting checks alone 10 of 15; with read agreement and label check 15 of 15; 8 of 51 right pages flagged</td></tr>
<tr><td>Harder photo-like scans (blur, noise, uneven light)</td><td>about 93% of values right; 21 of 22 wrong pages flagged</td></tr>
<tr><td>Quality gates</td><td>189 tests, mypy strict and ruff clean</td></tr>
</table>

<h2>Limits and honest caveats</h2>
<ul>
<li>Exact ground truth exists for one page. Other references are the parser's own output that passes every accounting check
(&#8220;silver&#8221;), so a mistake shared by the text layer and the extractor would be invisible.</li>
<li>Test documents are one company plus one other filing; the other layouts were tested on synthetic pages only. No real scanned
PDF was available: scans are simulated (resolution, JPEG, skew, blur, noise).</li>
<li>Not supported: grid-ruled pages (equity statement, notes) and statements with more than two panels. OCR can merge two-line
column headers on tight layouts, so periods may be wrong on scans. A flagged cell shows where to look, not which read is right.</li>
</ul>
"""


def main() -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    story = pymupdf.Story(HTML, user_css=CSS, archive=pymupdf.Archive(str(FONTS)))
    spare, _ = page.insert_htmlbox(pymupdf.Rect(34, 30, 561, 812), story, scale_low=0.5)
    print("spare height:", spare)
    doc.save(str(ROOT / "report.pdf"), garbage=3, deflate=True)
    print("pages:", doc.page_count)


if __name__ == "__main__":
    main()
