"""Indentation levels and parent paths.

In these statements the indent of the label encodes the account tree. Levels are the *rank* of
the indent cluster on the page, never an absolute x position, because the first indent differs
between pages (e.g. 62 pt on one page, 75 pt on another).
"""

from __future__ import annotations

from collections.abc import Sequence


def cluster_levels(x0s: Sequence[float], tol: float = 2.0) -> list[int]:
    """Map each label x0 to the rank of its 1-D cluster (0 = leftmost)."""
    ordered = sorted(set(x0s))
    clusters: list[list[float]] = []
    for x in ordered:
        if clusters and x - clusters[-1][-1] <= tol:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    level_of = {x: i for i, cluster in enumerate(clusters) for x in cluster}
    return [level_of[x] for x in x0s]


def build_paths(labels: Sequence[str], levels: Sequence[int]) -> list[tuple[str, ...]]:
    """Parent path (root first, own label last) for every row, using a level stack."""
    stack: list[tuple[int, str]] = []
    paths: list[tuple[str, ...]] = []
    for label, level in zip(labels, levels, strict=True):
        while stack and stack[-1][0] >= level:
            stack.pop()
        paths.append(tuple(lab for _, lab in stack) + (label,))
        stack.append((level, label))
    return paths


def parent_indices(levels: Sequence[int]) -> list[int | None]:
    """Index of each row's parent (nearest preceding row with a smaller level)."""
    stack: list[int] = []
    parents: list[int | None] = []
    for i, level in enumerate(levels):
        while stack and levels[stack[-1]] >= level:
            stack.pop()
        parents.append(stack[-1] if stack else None)
        stack.append(i)
    return parents
