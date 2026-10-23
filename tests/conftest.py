from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORRECTED_PDF = ROOT / "balance_sheet_after_correction.pdf"
COMPLETE_PDF = ROOT / "complete_pdf.pdf"
TRUTH_JSON = ROOT / "tests" / "fixtures" / "ground_truth" / "balance_sheet_after_correction.json"


@pytest.fixture(scope="session")
def corrected_pdf() -> Path:
    if not CORRECTED_PDF.exists():
        pytest.skip(
            "balance_sheet_after_correction.pdf not present (not redistributed; see data/README.md)"
        )
    return CORRECTED_PDF


@pytest.fixture(scope="session")
def complete_pdf() -> Path:
    if not COMPLETE_PDF.exists():
        pytest.skip("complete_pdf.pdf not present")
    return COMPLETE_PDF


def pytest_collection_modifyitems(config, items):
    """The sample PDFs are third-party documents and are not in the repository: skip what needs them."""
    if CORRECTED_PDF.exists():
        return
    skip = pytest.mark.skip(reason="sample PDFs not present (see data/README.md)")
    for item in items:
        if "CORRECTED_PDF" in vars(item.module) or "corrected_pdf" in item.fixturenames:
            item.add_marker(skip)
