"""Deterministic decision rule (PLAN.md §4): consensus, fallback, or escalation. No LLM involved."""
from __future__ import annotations

from .schemas import AgentTurn, Decision, Option
from .timeutil import to_hhmm


def decide(options: list[Option], turns_by_round: list[list[AgentTurn]], rounds_used: int,
           fallback: Option | None) -> Decision:
    """`options` are final-round survivors that already passed the safety gate."""
    final = turns_by_round[-1] if turns_by_round else []
    failed = [t.agent for t in final if t.status != "OK"]
    scores: dict[str, list[int]] = {o.option_id: [] for o in options}
    for t in final:
        if t.response is None:
            continue
        for a in t.response.assessments:
            if a.option_id in scores and a.verdict == "ACCEPT":
                scores[a.option_id].append(max(0, min(10, a.score)))

    if failed or not options:
        if fallback is None:
            return Decision(outcome="NO_FEASIBLE", option=None, min_score=None, rounds_used=rounds_used,
                            explanation="No agreement and the deterministic fallback found no option that passes "
                                        "every hard rule. Escalate: consider holding at an alternate or diverting.",
                            party_messages=party_messages(None))
        why = (f"agents unavailable or invalid ({', '.join(failed)})" if failed
               else f"no option accepted by all three agents within {rounds_used} turn(s)")
        return Decision(outcome="FALLBACK", option=fallback, min_score=None, rounds_used=rounds_used,
                        explanation=f"Deterministic fallback: {why}. Solver's best option that passes the rule "
                                    f"checker, without the agents' preferences. Human must confirm.",
                        party_messages=party_messages(fallback))

    # Highest worst-case score protects the worst-off party; then total score, cost, earliest landing.
    ranked = sorted(options, key=lambda o: (-min(scores[o.option_id] or [0]), -sum(scores[o.option_id]),
                                            o.public_cost, o.landing_time))
    best = ranked[0]
    ms = min(scores[best.option_id] or [0])
    return Decision(outcome="CONSENSUS", option=best, min_score=ms, rounds_used=rounds_used,
                    explanation=f"Option {best.option_id} passed every hard rule and had the best worst-case score "
                                f"({ms}/10) across ATC, pilot and ground.", party_messages=party_messages(best))


def party_messages(o: Option | None) -> dict:
    if o is None:
        return {"ATC": "No feasible landing plan. Coordinate holding/diversion with airline.",
                "PILOT": "No feasible landing plan at destination. Prepare for diversion; await instruction.",
                "GROUND": "No arrival plan agreed. Hold resources; await instruction."}
    nxt = f"{to_hhmm(o.next_leg_departure)}L" if o.next_leg_departure else None
    return {
        "ATC": f"Land {o.runway} at {to_hhmm(o.landing_time)}L (hold {o.hold_min} min).",
        "PILOT": f"Expect {o.runway} {to_hhmm(o.landing_time)}L, gate {o.gate}, {o.turnaround.lower()} turnaround"
                 + (f", next leg off-block {nxt}." if nxt else "."),
        "GROUND": f"Gate {o.gate}, in-gate {to_hhmm(o.in_gate_time)}L, {o.turnaround.lower()} turnaround"
                  + (f", target off-block {nxt}." if nxt else "."),
    }
