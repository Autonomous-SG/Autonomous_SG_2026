"""Public-data option generator."""
from __future__ import annotations
from .schemas import Option, PublicState, SharedConstraint
from . import rules

COST_WEIGHTS = {"arrival_delay": 1.0, "hold_min": .5, "gate_change": 10.0, "expedited": 8.0, "next_leg_delay": .5}

def make_option(public, landing_time, runway, gate, turnaround, *, option_id, source, proposed_by=None, round=1):
    hold = landing_time - public.eta_earliest; ingate = landing_time + public.taxi_in_min
    turn = public.aircraft.standard_turnaround_min if turnaround == "STANDARD" else public.aircraft.expedited_turnaround_min
    nxt = None if public.next_leg is None else ingate + turn
    next_delay = 0 if public.next_leg is None else max(0, nxt - public.next_leg.scheduled_departure)
    breakdown = {"arrival_delay": ingate-public.flight.scheduled_arrival, "hold_min": hold, "gate_change": int(gate != public.planned_gate), "expedited": int(turnaround == "EXPEDITED"), "next_leg_delay": next_delay}
    cost = sum(COST_WEIGHTS[k]*v for k,v in breakdown.items())
    return Option(option_id=option_id, landing_time=landing_time, runway=runway, gate=gate, turnaround=turnaround, hold_min=hold, in_gate_time=ingate, next_leg_departure=nxt, source=source, proposed_by=proposed_by, round_introduced=round, public_cost=cost, cost_breakdown=breakdown)

def generate_options(public, shared, k, exclude=(), round=1, next_id="A"):
    used=set(exclude); candidates=[]
    for t in range(public.eta_earliest, public.eta_earliest+61, 2):
      for rw in public.runways:
       for gate in public.gates:
        for turn in ("STANDARD","EXPEDITED"):
         o=make_option(public,t,rw.name,gate,turn,option_id="_",source="SOLVER",round=round)
         if all(c.passed for c in rules.check_public(public,o,shared)):
          candidates.append(o)
    candidates.sort(key=lambda x:(x.public_cost,x.landing_time))
    result=[]
    for index, o in enumerate(candidates):
      candidate_id = chr(ord(next_id) + index)
      if candidate_id in used: continue
      if any(x.runway==o.runway and x.gate==o.gate and x.turnaround==o.turnaround and abs(x.landing_time-o.landing_time)<6 for x in result): continue
      o.option_id=chr(ord(next_id)+len(result)); result.append(o)
      if len(result)>=k: break
    return result
