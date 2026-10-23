"""Declarative accounting rules (see ``statement_rules.yaml``) and the engine that evaluates them."""

from .engine import check_formulas, check_ties, load_rules

__all__ = ["check_formulas", "check_ties", "load_rules"]
