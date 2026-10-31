"""Evaluation baselines using the same public grid and full-truth referee."""
from __future__ import annotations
from .schemas import PlanEvaluation
from .solver import generate_options
from . import rules

def _evaluation(label, option, world):
    checks=[] if option is None else rules.check_option(world, option)
    failed=[c.rule_id for c in checks if c.hard and not c.passed]
    return PlanEvaluation(label=label, option=option, feasible_in_reality=not failed if option else None, failed_rules=failed)

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
    return [_evaluation("SOLVER_ONLY",solver,world), _evaluation("NEGOTIATED",negotiated.option,world), _evaluation("ORACLE",oracle,world), PlanEvaluation(label="HISTORICAL",option=None,feasible_in_reality=None,failed_rules=[])]
