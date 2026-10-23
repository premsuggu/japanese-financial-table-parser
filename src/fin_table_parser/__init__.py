"""Rule-based parser for Japanese financial-statement tables in born-digital PDFs."""

from .models import Finding, Row, Table, Value
from .pipeline import parse_page
from .validate import validate_tables

__all__ = ["Finding", "Row", "Table", "Value", "parse_page", "validate_tables"]
