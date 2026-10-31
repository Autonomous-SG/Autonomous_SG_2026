"""Evaluation baselines: solver-only (public data), negotiated, oracle (all data), and what happened in 2015."""
from __future__ import annotations

from .rules import check_option
from .schemas import Decision, Option, PlanEvaluation, World
from .solver import all_candidates, generate_options


def evaluate(world: World, label: str, o: Option | None, note: str) -> PlanEvaluation:
    """Full-truth outcome of a plan. If the gate is still busy, the aircraft waits for it (delay counted)."""
    if o is None:
        return PlanEvaluation(label=label, option=None, feasible_in_reality=None, failed_rules=[],
                              arrival_delay_min=None, next_leg_delay_min=None, connection_pax_missed=None, note=note)
    pub = world.public
    failed = [c.rule_id for c in check_option(world, o) if c.hard and not c.passed]
    in_gate = max(o.in_gate_time, world.private.ground.gate_busy_until.get(o.gate, 0))
    ac = pub.aircraft
    turn = ac.expedited_turnaround_min if o.turnaround == "EXPEDITED" else ac.standard_turnaround_min
    nl = max(0, in_gate + turn - pub.next_leg.scheduled_departure) if pub.next_leg else None
    missed = sum(c.pax for c in world.private.pilot.connections if in_gate + c.min_connect_min > c.departure)
    return PlanEvaluation(label=label, option=o, feasible_in_reality=not failed, failed_rules=failed,
                          arrival_delay_min=max(0, in_gate - pub.flight.scheduled_arrival), next_leg_delay_min=nl,
                          connection_pax_missed=missed, note=note)


def compare(world: World, negotiated: Decision) -> list[PlanEvaluation]:
    pub = world.public
    solo = generate_options(pub, [], 1, [], 0, "S")
    feasible = [o for o in all_candidates(pub) if all(c.passed for c in check_option(world, o) if c.hard)]
    oracle = min(feasible, key=lambda o: (o.public_cost, o.landing_time), default=None)
    f, nl = pub.flight, pub.next_leg
    return [
        evaluate(world, "SOLVER_ONLY", solo[0] if solo else None, "Solver with public data only, fixed weights."),
        evaluate(world, "NEGOTIATED", negotiated.option, f"Outcome: {negotiated.outcome}."),
        evaluate(world, "ORACLE", oracle, "Solver that sees all private data (upper bound), fixed weights."),
        PlanEvaluation(label="HISTORICAL", option=None, feasible_in_reality=None, failed_rules=[],
                       arrival_delay_min=f.arrival_delay, next_leg_delay_min=nl.departure_delay if nl else None,
                       connection_pax_missed=None,
                       note="What actually happened in 2015 (real weather, not our injected event): indicative only."),
    ]
