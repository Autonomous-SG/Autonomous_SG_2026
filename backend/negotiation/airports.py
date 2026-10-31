"""Small, deterministic airport catalogue used by the world builder.

The DOT data contains airport codes, but it does not contain the operational
runway/gate state needed by a negotiation scenario.  This module deliberately
keeps that synthetic catalogue small: the three airports called out in the
project plan use real runway names, while every other airport gets a clearly
synthetic pair.
"""
from __future__ import annotations

from typing import Final


# These are representative runway pairs used by the demo.  They are real
# runway designators, rather than airport/runway data being inferred from the
# flight CSV.  Keeping two per airport also makes the generated scenarios easy
# to read in the UI and leaves one runway available during a closure.
REAL_RUNWAYS: Final[dict[str, tuple[str, str]]] = {
    "ATL": ("26R", "27L"),
    "ORD": ("27R", "28C"),
    "DFW": ("17R", "18L"),
}

AIRPORT_GATES: Final[dict[str, tuple[str, ...]]] = {
    "ATL": ("A15", "A17", "A19", "A21", "A23"),
    "ORD": ("B15", "B17", "B19", "B21", "B23"),
    "DFW": ("E15", "E17", "E19", "E21", "E23"),
}

DEFAULT_GATES: Final[tuple[str, ...]] = ("G1", "G2", "G3", "G4", "G5")


def runway_names(airport: str) -> list[str]:
    """Return the synthetic scenario's runway names for ``airport``."""

    code = (airport or "").upper()
    return list(REAL_RUNWAYS.get(code, ("RWY-1", "RWY-2")))


def gate_names(airport: str) -> list[str]:
    """Return a small set of assignable gates for ``airport``."""

    code = (airport or "").upper()
    return list(AIRPORT_GATES.get(code, DEFAULT_GATES))

