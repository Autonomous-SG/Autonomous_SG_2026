"""Public-data option generator (PLAN.md §6). Deterministic: same input, same options."""
from __future__ import annotations

from .rules import check_public
from .schemas import AgentName, Option, PublicState, SharedConstraint

COST_WEIGHTS = {"arrival_delay": 1.0, "hold": 0.5, "gate_change": 10.0, "expedited": 8.0, "next_leg_delay": 0.5}
GRID_STEP_MIN = 2
HORIZON_MIN = 60
DIVERSITY_MIN = 6


def make_option(public: PublicState, landing_time: int, runway: str, gate: str, turnaround: str, *,
                option_id: str, source: str = "SOLVER", proposed_by: AgentName | None = None, round: int = 1) -> Option:
    ac = public.aircraft
    turn = ac.expedited_turnaround_min if turnaround == "EXPEDITED" else ac.standard_turnaround_min
    in_gate = landing_time + public.taxi_in_min
    nxt = in_gate + turn if public.next_leg else None
    hold = max(0, landing_time - public.eta_earliest)
    arr_delay = max(0, in_gate - public.flight.scheduled_arrival)
    nl_delay = max(0, nxt - public.next_leg.scheduled_departure) if nxt is not None else 0
    parts = {
        "arrival_delay": COST_WEIGHTS["arrival_delay"] * arr_delay,
        "hold": COST_WEIGHTS["hold"] * hold,
        "gate_change": COST_WEIGHTS["gate_change"] * (gate != public.planned_gate),
        "expedited": COST_WEIGHTS["expedited"] * (turnaround == "EXPEDITED"),
        "next_leg_delay": COST_WEIGHTS["next_leg_delay"] * nl_delay,
    }
    return Option(option_id=option_id, landing_time=landing_time, runway=runway, gate=gate, turnaround=turnaround,
                  hold_min=hold, in_gate_time=in_gate, next_leg_departure=nxt, source=source, proposed_by=proposed_by,
                  round_introduced=round, public_cost=float(f"{sum(parts.values()):.1f}"), cost_breakdown=parts)


def option_key(o: Option) -> tuple:
    return (o.landing_time, o.runway, o.gate, o.turnaround)


def all_candidates(public: PublicState, round: int = 0) -> list[Option]:
    return [make_option(public, t, rwy.name, gate, turn, option_id="?", round=round)
            for t in range(public.eta_earliest, public.eta_earliest + HORIZON_MIN + 1, GRID_STEP_MIN)
            for rwy in public.runways for gate in public.gates for turn in ("STANDARD", "EXPEDITED")]


def generate_options(public: PublicState, shared: list[SharedConstraint], k: int, exclude: list[Option],
                     round: int, next_id: str) -> list[Option]:
    """Top-k cheapest options that pass public hard rules + shared constraints, excluding ones already offered."""
    taken = {option_key(o) for o in exclude}
    pool = [o for o in all_candidates(public, round)
            if option_key(o) not in taken and all(c.passed for c in check_public(public, o, shared) if c.hard)]
    pool.sort(key=lambda o: (o.public_cost, o.landing_time))
    picked: list[Option] = []
    for o in pool:
        if any(p.gate == o.gate and p.runway == o.runway and abs(p.landing_time - o.landing_time) < DIVERSITY_MIN
               for p in picked):
            continue
        picked.append(o)
        if len(picked) == k:
            break
    return [o.model_copy(update={"option_id": chr(ord(next_id) + i)}) for i, o in enumerate(picked)]
