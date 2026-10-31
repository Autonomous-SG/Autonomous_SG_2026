"""Evaluation baselines using the same public grid and full-truth referee."""
from __future__ import annotations
from .schemas import PlanEvaluation
from .solver import generate_options
from . import rules

def _evaluation(label, option, world):
    checks=[] if option is None else rules.check_option(world, option)
    failed=[c.rule_id for c in checks if c.hard and not c.passed]
    if option is None:
        return PlanEvaluation(label=label, option=None, feasible_in_reality=None, failed_rules=[],
                              arrival_delay_min=None, next_leg_delay_min=None,
                              connection_pax_missed=None, note="No plan available")
    public=world.public
    arrival_delay=option.in_gate_time-public.flight.scheduled_arrival
    next_delay=None
    if public.next_leg is not None and option.next_leg_departure is not None:
        next_delay=max(0, option.next_leg_departure-public.next_leg.scheduled_departure)
    missed=0
    for connection in world.private.pilot.connections:
        if option.in_gate_time+connection.min_connect_min > connection.departure:
            missed += connection.pax
    return PlanEvaluation(label=label, option=option, feasible_in_reality=not failed,
                          failed_rules=failed, arrival_delay_min=arrival_delay,
                          next_leg_delay_min=next_delay, connection_pax_missed=missed,
                          note="Full-truth hard-rule evaluation")

def compare(world, negotiated):
    public=world.public
    solver_opts=generate_options(public, [], 1)
    solver=solver_opts[0] if solver_opts else None
    # Oracle uses the same grid, but filters each public candidate with all truth.
    oracle=None
    for t in range(public.eta_earliest, public.eta_earliest+61, 2):
      for rw in public.runways:
       for gate in public.gates:
        for turn in ("STANDARD","EXPEDITED"):
         from .solver import make_option
         o=make_option(public,t,rw.name,gate,turn,option_id="O",source="SOLVER",round=1)
         if not [c for c in rules.check_option(world,o) if c.hard and not c.passed]:
          if oracle is None or o.public_cost < oracle.public_cost: oracle=o
    historical=PlanEvaluation(label="HISTORICAL", option=None, feasible_in_reality=None,
                              failed_rules=[], arrival_delay_min=world.public.flight.arrival_delay,
                              next_leg_delay_min=None, connection_pax_missed=None,
                              note="Historical CSV outcome; no revised plan")
    return [_evaluation("SOLVER_ONLY",solver,world), _evaluation("NEGOTIATED",negotiated.option,world), _evaluation("ORACLE",oracle,world), historical]
