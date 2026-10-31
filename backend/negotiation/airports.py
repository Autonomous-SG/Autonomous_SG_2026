"""Deterministic airport names backed by the organiser's capacity limits.

The DOT data supplies airport codes, not the operational runway/gate state
needed by a negotiation scenario.  ``constraints.py`` supplies the number of
active runways and spare gates; this module supplies readable runway and gate
names for those synthetic resources.
"""
from __future__ import annotations

from typing import Final

from . import constraints


# These are representative real runway designators, rather than runway data
# inferred from the flight CSV.  The workbook decides how many are active in a
# scenario; the extra names make that count visible for the large hubs.
REAL_RUNWAYS: Final[dict[str, tuple[str, ...]]] = {
    "ATL": ("26R", "27L", "26L", "27R"),
    "ORD": ("27R", "28C", "27L", "28R"),
    "DFW": ("17R", "18L", "17C", "18R"),
}

AIRPORT_GATES: Final[dict[str, tuple[str, ...]]] = {
    "ATL": ("A15", "A17", "A19", "A21", "A23"),
    "ORD": ("B15", "B17", "B19", "B21", "B23"),
    "DFW": ("E15", "E17", "E19", "E21", "E23"),
}

DEFAULT_GATES: Final[tuple[str, ...]] = ("G1", "G2", "G3", "G4", "G5")


def runway_names(airport: str) -> list[str]:
    """Return exactly the configured number of active runway names."""

    code = (airport or "").upper()
    count = constraints.airport(code).active_runways
    catalog = list(REAL_RUNWAYS.get(code, ()))
    if len(catalog) < count:
        catalog.extend(f"RWY-{index}" for index in range(len(catalog) + 1, count + 1))
    return catalog[:count]


def gate_names(airport: str, planned_gate: str | None = None) -> list[str]:
    """Return the planned gate followed by the configured spare gates.

    ``planned_gate`` is optional for compatibility with callers that only need
    a deterministic pool.  The world builder supplies it so the public gate
    list has the exact shape required by the workbook: one planned gate plus
    ``spare_gates`` alternatives.
    """

    code = (airport or "").upper()
    limits = constraints.airport(code)
    catalog = list(AIRPORT_GATES.get(code, DEFAULT_GATES))
    if planned_gate is None:
        planned_gate = catalog[0]
    elif planned_gate not in catalog:
        catalog.insert(0, planned_gate)

    ordered = [planned_gate] + [gate for gate in catalog if gate != planned_gate]
    needed = 1 + limits.spare_gates
    while len(ordered) < needed:
        candidate = f"{code or 'G'}{len(ordered) + 1}"
        if candidate not in ordered:
            ordered.append(candidate)
    return ordered[:needed]

