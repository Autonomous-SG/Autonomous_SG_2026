"""Deterministic consensus, fallback, and escalation decisions."""
from __future__ import annotations
from .schemas import Decision, Option, AgentTurn
from . import rules

def decide(options, turns_by_round, rounds_used):
    turns = [t for ts in turns_by_round.values() for t in ts]
    valid_agents = {t.agent for t in turns if t.status == "OK"}
    vetoed=set()
    scores={}
    for t in turns:
        if not t.response: continue
        for a in t.response.assessments:
            if a.verdict == "VETO" and any(c.rule_id == a.veto_rule and not c.passed for c in t.veto_checks): vetoed.add(a.option_id)
            if a.verdict == "ACCEPT": scores.setdefault(a.option_id,[]).append(max(0,min(10,a.score)))
    survivors=[o for o in options if o.option_id not in vetoed]
    if not survivors:
        return Decision(outcome="NO_FEASIBLE", option=None, min_score=None, rounds_used=rounds_used, explanation="No feasible option survives verified hard-rule checks; escalate or divert.", party_messages={"ATC":"Escalate to duty manager.","PILOT":"Escalate to duty manager.","GROUND":"Escalate to duty manager."})
    fallback = len(valid_agents) < 3
    ranked=sorted(survivors,key=lambda o:(-min(scores.get(o.option_id,[0])),o.public_cost,o.landing_time))
    chosen=ranked[0]; minimum=min(scores.get(chosen.option_id,[0]))
    outcome="FALLBACK" if fallback else "CONSENSUS"
    msg={a:f"{outcome}: proposed {chosen.option_id} at {chosen.landing_time} via {chosen.gate}; human approval required." for a in ("ATC","PILOT","GROUND")}
    return Decision(outcome=outcome, option=chosen, min_score=minimum, rounds_used=rounds_used, explanation=f"Selected {chosen.option_id} by highest worst-party score, then public cost.", party_messages=msg)
