# Test corpus (downloaded, untrusted)

Downloaded 2026-10-23 from the company's public IR page https://www.yamato-in.co.jp/ir/
(ヤマト モビリティ & Mfg.株式会社, code 7886). Each file sits in its own directory. Files are treated as
untrusted data: nothing here is executed, and Python that reads them runs with `python -I`.

| Directory | Document | Balance-sheet pages (0-based) |
|---|---|---|
| ir202603q4 | FY2026 full-year 決算短信 (consolidated, JGAAP) | 6, 7 (p. 6 is the page in `complete_pdf.pdf`) |
| ir202603q3 | Q3 決算短信 | 5, 6 |
| ir202603q2 | Q2 (interim) 決算短信 | 5, 6 |
| ir202603q1 | Q1 決算短信 | 4, 5 |
| ir202703q1 | FY2027 Q1 決算短信 | 5, 6 |
| 20260626b | Correction notice, Q2 (中間連結貸借対照表) | 2, 3 (likely 訂正前 / 訂正後) |
| 20260626c | Correction notice, Q3 (四半期連結貸借対照表) | 1, 2 (likely 訂正前 / 訂正後) |
| 20260626d | Correction notice, full year (連結貸借対照表) | 2, 3 (likely 訂正前 / 訂正後; the page in `balance_sheet_after_correction.pdf`) |
| S100X0Y3 | 半期報告書 (interim securities report) | 10, 11 |
| S100YMK7 | 有価証券報告書 (annual securities report, 109 pp.) | 42, 43, 74, 85, 86 (footnote markers ※, different header block) |

No XBRL was offered on the IR page. Same company throughout, so layout variety is limited to the
document types above; other companies are still untested.
