"""Batch evaluation + red-team scorecard with live Claude calls (costs money: ~$0.08-0.11 per negotiation).
Usage (from backend/): .venv/bin/python -m scripts.run_eval --rows 24 --attack-rows 4 --concurrency 3
Writes eval/results.json and eval/summary.md."""
import argparse
import asyncio
import json
import random
import statistics
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from negotiation.orchestrator import load_deps, negotiate  # noqa: E402
from negotiation.rules import check_option  # noqa: E402
from negotiation.schemas import NegotiateRequest  # noqa: E402
from negotiation.timeutil import to_hhmm  # noqa: E402

EVENTS = ["RUNWAY_CLOSURE", "WEATHER_CAPACITY_DROP", "GATE_EQUIPMENT_FAILURE"]
ATTACKS = ["PROMPT_INJECTION", "LYING_AGENT", "AGENT_TIMEOUT", "NO_FEASIBLE"]
OUT = Path(__file__).resolve().parent.parent / "eval"


async def one(deps, sem, row: int, event: str, attack: str, seed: int) -> dict:
    async with sem:
        t0 = time.monotonic()
        rec = {"row": row, "event": event, "attack": attack, "seed": seed}
        try:
            world = deps.build_world(row, event, seed, attack)
            res = await negotiate(NegotiateRequest(row_id=row, event=event, seed=seed, attack=attack), deps)
        except Exception as e:  # recorded, not hidden: shows up in the summary as an error
            rec.update(error=f"{type(e).__name__}: {e}", wall_ms=int((time.monotonic() - t0) * 1000))
            print(f"ERROR row {row} {event} {attack}: {rec['error']}", flush=True)
            return rec
        d, m, f = res.decision, res.metrics, res.world.public.flight
        unsafe = d.option is not None and any(c.hard and not c.passed for c in check_option(world, d.option))
        comp = {c.label: c.model_dump(exclude={"option"}) for c in res.comparison}
        gate_catches = sum(1 for e in res.log if e.kind == "GUARDRAIL" and e.summary.startswith("Safety gate removed")
                           and "accepted by agents" in e.summary)
        rec.update(
            flight=f"{f.airline}{f.flight_number}", route=f"{f.origin}->{f.destination}",
            outcome=d.outcome, rounds=d.rounds_used, unsafe_recommendation=unsafe,
            plan=(f"{to_hhmm(d.option.landing_time)} {d.option.runway} {d.option.gate} {d.option.turnaround}"
                  if d.option else None),
            comparison=comp, safety_gate_catches=gate_catches,
            vetoes_confirmed=m.vetoes_confirmed, vetoes_rejected=m.vetoes_rejected,
            invalid_outputs=m.invalid_outputs, llm_calls=m.llm_calls, cost_usd=m.est_cost_usd, wall_ms=m.wall_ms,
            guardrail_flags=sorted({fl.split(":")[0] for r in res.rounds for t in r.turns for fl in t.guardrail_flags}),
        )
        print(f"{'UNSAFE' if unsafe else 'ok'} row {row} {rec['flight']} {event} {attack}: {d.outcome} "
              f"{rec['plan']} rounds={d.rounds_used} ${m.est_cost_usd}", flush=True)
        return rec


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.0f}%" if d else "n/a"


def mean(xs) -> str:
    xs = [x for x in xs if x is not None]
    return f"{statistics.mean(xs):.1f}" if xs else "n/a"


def summarize(normal: list[dict], attacks: list[dict]) -> str:
    ok = [r for r in normal if "error" not in r]
    n = len(ok)
    L = ["# Evaluation results", "",
         f"Live runs with Claude ({'model from CLAUDE_MODEL'}). {len(normal)} disruption scenarios from real "
         f"flights.csv rows (seeded random sample) x 3 event types; {len(attacks)} red-team runs. "
         "Synthetic parts of each scenario (event, gates occupancy, crew, fuel, connections) are generated and labelled.", ""]
    L += ["## Outcomes", "", "| Metric | Value |", "|---|---|",
          f"| Scenarios run / errors | {len(normal)} / {len(normal) - n} |",
          f"| Consensus | {pct(sum(r['outcome'] == 'CONSENSUS' for r in ok), n)} |",
          f"| Fallback | {pct(sum(r['outcome'] == 'FALLBACK' for r in ok), n)} |",
          f"| No feasible plan (escalated) | {pct(sum(r['outcome'] == 'NO_FEASIBLE' for r in ok), n)} |",
          f"| Average turns | {mean(r['rounds'] for r in ok)} |",
          f"| Finished in <= 2 turns | {pct(sum(r['rounds'] <= 2 for r in ok), n)} |",
          f"| **Unsafe recommendations** | **{sum(r['unsafe_recommendation'] for r in ok)}** |",
          f"| Violations agents accepted but safety gate caught | {sum(r['safety_gate_catches'] for r in ok)} |",
          f"| Vetoes confirmed / rejected by checker | {sum(r['vetoes_confirmed'] for r in ok)} / "
          f"{sum(r['vetoes_rejected'] for r in ok)} |",
          f"| Invalid LLM outputs | {sum(r['invalid_outputs'] for r in ok)} |",
          f"| Latency p50 / max (s) | {statistics.median([r['wall_ms'] for r in ok]) / 1000:.1f} / "
          f"{max(r['wall_ms'] for r in ok) / 1000:.1f} |" if ok else "| Latency | n/a |",
          f"| Cost per negotiation (mean) / total | ${statistics.mean([r['cost_usd'] for r in ok] or [0]):.3f} / "
          f"${sum(r['cost_usd'] for r in ok):.2f} |", ""]

    def col(label, key):
        return [r["comparison"][label][key] for r in ok if r["comparison"].get(label)]

    L += ["## Versus baselines", "",
          "SOLVER_ONLY = deterministic solver with public data only. ORACLE = same solver given everyone's private "
          "data (an upper bound no real organisation has). Delays assume the aircraft waits if its gate is still busy.",
          "", "| | Plans that fail a hard rule in reality | Mean arrival delay (min) | Mean next-leg delay (min) | "
          "Connecting pax missed |", "|---|---|---|---|---|"]
    for label in ("SOLVER_ONLY", "NEGOTIATED", "ORACLE"):
        feas = [x for x in col(label, "feasible_in_reality") if x is not None]
        L.append(f"| {label} | {pct(sum(not x for x in feas), len(feas))} ({sum(not x for x in feas)}/{len(feas)}) | "
                 f"{mean(col(label, 'arrival_delay_min'))} | {mean(col(label, 'next_leg_delay_min'))} | "
                 f"{sum(x or 0 for x in col(label, 'connection_pax_missed'))} |")
    L.append(f"| HISTORICAL (2015, real weather) | n/a | {mean(col('HISTORICAL', 'arrival_delay_min'))} | "
             f"{mean(col('HISTORICAL', 'next_leg_delay_min'))} | n/a |")
    better = sum(1 for r in ok if r["comparison"]["NEGOTIATED"]["next_leg_delay_min"] is not None
                 and r["comparison"]["ORACLE"]["next_leg_delay_min"] is not None
                 and r["comparison"]["NEGOTIATED"]["next_leg_delay_min"] < r["comparison"]["ORACLE"]["next_leg_delay_min"])
    L += ["", f"Negotiated plan had a shorter next-leg delay than the oracle in {better} scenario(s) "
              "(agents weighted the knock-on flight more than the fixed cost formula).", ""]

    L += ["## Red-team scorecard", "", "| Attack | Runs | Unsafe recommendations | Outcomes |", "|---|---|---|---|"]
    for a in ATTACKS:
        rs = [r for r in attacks if r["attack"] == a and "error" not in r]
        outs = ", ".join(f"{o} {sum(r['outcome'] == o for r in rs)}" for o in ("CONSENSUS", "FALLBACK", "NO_FEASIBLE")
                         if any(r["outcome"] == o for r in rs))
        L.append(f"| {a} | {len(rs)} | {sum(r['unsafe_recommendation'] for r in rs)} | {outs} |")
    rej = sum(r["vetoes_rejected"] for r in attacks if r["attack"] == "LYING_AGENT" and "error" not in r)
    L += ["", f"False vetoes rejected by the checker in LYING_AGENT runs: {rej}.", ""]

    fails = [r for r in ok if r["outcome"] != "CONSENSUS" or r["safety_gate_catches"] or r["invalid_outputs"]]
    errs = [r for r in normal + attacks if "error" in r]
    L += ["## Where it degrades (for the honest-evaluation slide)", ""]
    for r in fails[:8]:
        L.append(f"- row {r['row']} {r['flight']} {r['route']} {r['event']}: {r['outcome']}"
                 + (f", safety gate caught {r['safety_gate_catches']} option(s) the agents accepted" if r['safety_gate_catches'] else "")
                 + (f", {r['invalid_outputs']} invalid LLM output(s)" if r['invalid_outputs'] else ""))
    for r in errs[:5]:
        L.append(f"- ERROR row {r['row']} {r['event']} {r['attack']}: {r['error']}")
    if not fails and not errs:
        L.append("- No degraded cases in this sample.")
    return "\n".join(L) + "\n"


async def main_async(a) -> None:
    deps = load_deps()
    import negotiation.data as data
    df = data.load_flights()
    rng = random.Random(a.seed)
    rows = rng.sample(range(len(df)), a.rows)
    sem = asyncio.Semaphore(a.concurrency)
    normal_jobs = [one(deps, sem, row, EVENTS[i % 3], "NONE", a.seed) for i, row in enumerate(rows)]
    attack_rows = rng.sample(range(len(df)), a.attack_rows)
    attack_jobs = [one(deps, sem, row, "RUNWAY_CLOSURE", att, a.seed) for att in ATTACKS for row in attack_rows]
    results = await asyncio.gather(*normal_jobs, *attack_jobs)
    normal, attacks = results[:len(normal_jobs)], results[len(normal_jobs):]
    OUT.mkdir(exist_ok=True)
    (OUT / "results.json").write_text(json.dumps({"normal": normal, "attacks": attacks}, indent=2))
    (OUT / "summary.md").write_text(summarize(normal, attacks))
    print(f"\nwrote {OUT / 'summary.md'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=24)
    ap.add_argument("--attack-rows", type=int, default=4)
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--seed", type=int, default=7)
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
