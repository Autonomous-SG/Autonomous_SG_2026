"""Offline integration check (no API calls): runs full negotiations with scripted agents through the orchestrator.
Usage (from backend/): .venv/bin/python -m scripts.check_deps          # current auto deps
                       .venv/bin/python -m scripts.check_deps --real   # every real P1/P2 module that exists, ignoring pins
Exit code 0 = every scenario ran and no unsafe plan was recommended."""
import argparse
import asyncio
import sys
import traceback

from negotiation import devkit, orchestrator
from negotiation.orchestrator import load_deps, negotiate
from negotiation.schemas import AgentResponse, AgentTurn, NegotiateRequest, OptionAssessment
from negotiation.timeutil import to_hhmm

CASES = [(20919, "RUNWAY_CLOSURE", a) for a in ("NONE", "AGENT_TIMEOUT", "NO_FEASIBLE", "LYING_AGENT")]


def scripted_agent(world):
    """Vetoes exactly the options that break a hard rule in its own domain (using devkit truth as the oracle)."""
    async def run(view):
        out = []
        for o in view.options:
            f = [c for c in devkit.check_option(world, o) if c.hard and not c.passed and c.domain == view.agent]
            out.append(OptionAssessment(option_id=o.option_id, verdict="VETO" if f else "ACCEPT", score=0 if f else 6,
                                        veto_rule=f[0].rule_id if f else None, cited_rules=[], reason="scripted"))
        return AgentTurn(agent=view.agent, round=view.round, status="OK",
                         response=AgentResponse(assessments=out, counter_proposal=None), veto_checks=[],
                         counter_option_id=None, counter_checks=[], guardrail_flags=[], latency_ms=0,
                         input_tokens=0, output_tokens=0)
    return run


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true")
    a = ap.parse_args()
    if a.real:
        orchestrator.PINNED_TO_DEVKIT.clear()
    deps = load_deps("auto")
    print("deps:", deps.sources)
    ok = True
    for row, event, attack in CASES:
        try:
            world = deps.build_world(row, event, 42, attack)
            res = asyncio.run(negotiate(NegotiateRequest(row_id=row, event=event, attack=attack), deps,
                                        run_agent=scripted_agent(world)))
            d = res.decision
            unsafe = d.option is not None and any(c.hard and not c.passed for c in devkit.check_option(world, d.option))
            ok &= not unsafe
            plan = f"{to_hhmm(d.option.landing_time)} {d.option.gate} {d.option.turnaround}" if d.option else "-"
            print(f"{'UNSAFE' if unsafe else 'ok    '} row {row} {attack:14} {d.outcome:12} {plan:24} rounds={d.rounds_used}")
        except Exception as e:
            ok = False
            print(f"CRASH  row {row} {attack:14} {type(e).__name__}: {e}")
            traceback.print_exc(limit=3)
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
