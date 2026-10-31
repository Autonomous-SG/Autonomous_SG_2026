"""Run one negotiation from the command line and save the result as JSON.
Usage (from backend/): .venv/bin/python -m scripts.run_once --row 20919 --event RUNWAY_CLOSURE --attack NONE --out fixtures/negotiation_example.json
"""
import argparse
import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from negotiation.orchestrator import load_deps, negotiate  # noqa: E402
from negotiation.schemas import NegotiateRequest  # noqa: E402
from negotiation.timeutil import to_hhmm  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--row", type=int, default=20919)
    ap.add_argument("--event", default="RUNWAY_CLOSURE")
    ap.add_argument("--attack", default="NONE")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out")
    a = ap.parse_args()

    deps = load_deps()
    res = asyncio.run(negotiate(NegotiateRequest(row_id=a.row, event=a.event, seed=a.seed, attack=a.attack), deps))
    for e in res.log:
        print(f"[{e.round}] {e.actor:7} {e.kind:17} {e.summary}")
    d = res.decision
    print(f"\nDECISION {d.outcome}: " + (f"{to_hhmm(d.option.landing_time)} {d.option.runway} gate {d.option.gate} "
                                       f"{d.option.turnaround}" if d.option else "none"))
    for c in res.comparison:
        print(f"  {c.label:12} feasible={c.feasible_in_reality} failed={c.failed_rules} arr_delay={c.arrival_delay_min} "
              f"next_leg_delay={c.next_leg_delay_min} pax_missed={c.connection_pax_missed}")
    m = res.metrics
    print(f"\nrounds={m.rounds_used} calls={m.llm_calls} invalid={m.invalid_outputs} vetoes ok/rejected="
          f"{m.vetoes_confirmed}/{m.vetoes_rejected} counters {m.counters_passed}/{m.counters_proposed} "
          f"tokens={m.input_tokens}/{m.output_tokens} cost=${m.est_cost_usd} wall={m.wall_ms}ms")
    flags = [f"{t.agent}@R{t.round}: {t.guardrail_flags}" for r in res.rounds for t in r.turns if t.guardrail_flags]
    if flags:
        print("guardrail flags:", *flags, sep="\n  ")
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(res.model_dump(), indent=2))
        print(f"saved {a.out}")


if __name__ == "__main__":
    main()
