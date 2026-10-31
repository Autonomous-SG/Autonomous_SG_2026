"""Naive single-prompt baseline on the SAME scenarios as eval/results.json (live Claude calls, ~$0.02 each).
Usage (from backend/): .venv/bin/python -m scripts.run_naive
Writes eval/naive.json and appends a section to eval/summary.md."""
import asyncio
import json
import statistics
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from negotiation.baselines import evaluate  # noqa: E402
from negotiation.naive import naive_plan  # noqa: E402
from negotiation.orchestrator import load_deps  # noqa: E402
from negotiation.timeutil import to_hhmm  # noqa: E402

EVAL = Path(__file__).resolve().parent.parent / "eval"


async def one(deps, sem, rec: dict) -> dict:
    async with sem:
        world = deps.build_world(rec["row"], rec["event"], rec["seed"], "NONE")
        r = await naive_plan(world)
        o = r.pop("option")
        out = {"row": rec["row"], "event": rec["event"], **r}
        if o is None:
            out.update(unsafe=None, plan=None)
        else:
            ev = evaluate(world, "NEGOTIATED", o, "single prompt, all data")  # label is schema-bound and unused here
            out.update(unsafe=not ev.feasible_in_reality, failed_rules=ev.failed_rules,
                       plan=f"{to_hhmm(o.landing_time)} {o.runway} {o.gate} {o.turnaround}",
                       arrival_delay_min=ev.arrival_delay_min, next_leg_delay_min=ev.next_leg_delay_min,
                       connection_pax_missed=ev.connection_pax_missed)
        print(f"{'UNSAFE' if out.get('unsafe') else ('ok' if out.get('unsafe') is False else out['status'])} "
              f"row {rec['row']} {rec['event']}: {out.get('plan')} {out.get('failed_rules', '')}", flush=True)
        return out


async def main_async() -> None:
    data = json.loads((EVAL / "results.json").read_text())
    recs = [r for r in data["normal"] if "error" not in r]
    deps = load_deps()
    sem = asyncio.Semaphore(4)
    res = await asyncio.gather(*(one(deps, sem, r) for r in recs))
    (EVAL / "naive.json").write_text(json.dumps(res, indent=2))

    planned = [r for r in res if r.get("unsafe") is not None]
    unsafe = [r for r in planned if r["unsafe"]]
    invalid = len(res) - len(planned)
    neg_unsafe = sum(r["unsafe_recommendation"] for r in recs)
    rules: dict[str, int] = {}
    for r in unsafe:
        for f in r["failed_rules"]:
            rules[f] = rules.get(f, 0) + 1

    def m(key):
        xs = [r[key] for r in planned if r.get(key) is not None]
        return f"{statistics.mean(xs):.1f}" if xs else "n/a"

    section = [
        "", "## Naive single-prompt baseline (what the challenge says to avoid)", "",
        "One Claude call (same model, same effort) plays ATC, airline and ground at once, sees ALL private notes, "
        "is told every safety rule, and returns one plan. Same 24 scenarios as above; plans checked by the same referee.", "",
        "| | Plans that break a hard rule in reality | Invalid output | Mean arrival delay (min) | "
        "Mean next-leg delay (min) | Connecting pax missed |", "|---|---|---|---|---|---|",
        f"| NAIVE single prompt | **{100 * len(unsafe) / max(1, len(planned)):.0f}%** ({len(unsafe)}/{len(planned)}) | "
        f"{invalid} | {m('arrival_delay_min')} | {m('next_leg_delay_min')} | "
        f"{sum(r.get('connection_pax_missed') or 0 for r in planned)} |",
        f"| Vector (multi-agent + checker) | {neg_unsafe} unsafe recommendations | 0 | see above | see above | see above |",
        "", "Rules the naive plans broke: " + (", ".join(f"{k} x{v}" for k, v in sorted(rules.items(), key=lambda x: -x[1]))
                                              or "none") + ".",
        f"Cost per naive call (mean): ${statistics.mean([r['cost_usd'] for r in res] or [0]):.3f}.", "",
    ]
    with open(EVAL / "summary.md", "a") as fh:
        fh.write("\n".join(section))
    print("\n".join(section))


if __name__ == "__main__":
    asyncio.run(main_async())
