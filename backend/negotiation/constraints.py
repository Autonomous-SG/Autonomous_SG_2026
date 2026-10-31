"""SHARED. Organiser limits from data/challenge2_operational_constraints.xlsx (synthetic planning values).
Every deviation or interpretation below is listed in PLAN.md "Stated assumptions" and must be said in the demo."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .schemas import WakeCategory

XLSX = Path(os.getenv("CONSTRAINTS_XLSX", Path(__file__).resolve().parents[2] / "data" / "challenge2_operational_constraints.xlsx"))


@dataclass(frozen=True)
class AirportLimits:
    iata: str
    name: str
    size_class: str
    active_runways: int
    gates: int
    max_runway_ops_per_hour: int
    min_turnaround_min: int
    spare_gates: int


@lru_cache(maxsize=1)
def _airports() -> dict[str, AirportLimits]:
    df = pd.read_excel(XLSX, sheet_name="airport_capacity", header=2)
    return {
        r.IATA_CODE: AirportLimits(
            iata=r.IATA_CODE, name=r.AIRPORT, size_class=r.size_class, active_runways=int(r.active_runways),
            gates=int(r.gates), max_runway_ops_per_hour=int(r.max_runway_ops_per_hour),
            min_turnaround_min=int(r.min_turnaround_min), spare_gates=int(r.spare_gates_at_any_time),
        )
        for r in df.itertuples(index=False)
        if isinstance(r.IATA_CODE, str)
    }


def airport(iata: str) -> AirportLimits:
    """Workbook row for an airport. Unknown codes get the smallest (Non-hub) limits."""
    a = _airports().get(iata)
    if a is None:
        return AirportLimits(iata=iata, name=iata, size_class="Non-hub", active_runways=1, gates=8,
                             max_runway_ops_per_hour=20, min_turnaround_min=35, spare_gates=2)
    return a


# --- wake_separation sheet (FAA JO 7110.65, simplified). Our categories: HEAVY=Heavy, MEDIUM=Large, LIGHT=Small.
# Super (A380) is not modelled: no A380s in the 2015 US domestic data.
WAKE_NM: dict[tuple[str, str], int] = {
    ("HEAVY", "HEAVY"): 4,
    ("HEAVY", "MEDIUM"): 5,
    ("HEAVY", "LIGHT"): 6,
    ("MEDIUM", "LIGHT"): 4,
}
WAKE_NM_DEFAULT = 3  # "Any other pair"
APPROACH_SPEED_KT = 140  # assumption: converts arrival separation in NM to minutes on final approach


def wake_sep_min(leader: WakeCategory, follower: WakeCategory) -> float:
    return WAKE_NM.get((leader, follower), WAKE_NM_DEFAULT) * 60 / APPROACH_SPEED_KT


# --- fuel_and_crew sheet
FINAL_RESERVE_MIN = 30  # never plan below 30 min of holding fuel
CONTINGENCY_FUEL_PCT = 5  # of trip fuel
HOLD_BURN_KG_PER_MIN = {"NARROWBODY": 2400 / 60, "WIDEBODY": 6500 / 60}
DEFAULT_SPARE_HOLD_MIN = 45  # spare fuel on arrival, unless the team states otherwise
FLIGHT_CREW_MAX_DUTY_H = 13
GROUND_SHIFT_H = 8
GROUND_OVERTIME_COST_MULT = 1.5
GATE_CHANGE_NOTICE_MIN = 20  # a gate change must be notified at least 20 min before arrival (in-gate)

# --- turnaround: the workbook gives the per-airport minimum. Assumption: EXPEDITED = that minimum,
# STANDARD = minimum + STANDARD_TURN_BUFFER_MIN.
STANDARD_TURN_BUFFER_MIN = 10


def turnarounds(iata: str) -> tuple[int, int]:
    """(standard, expedited) turnaround minutes at an airport."""
    m = airport(iata).min_turnaround_min
    return m + STANDARD_TURN_BUFFER_MIN, m
