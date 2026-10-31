"""Runs the 3-round negotiation protocol (PLAN.md §4). All safety decisions are delegated to code (rules/decision)."""
from __future__ import annotations

import asyncio
import importlib
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from . import agent_runner, devkit
from .schemas import (
    AGENTS, AgentTurn, AgentView, LogEntry, Metrics, NegotiateRequest, NegotiationResult, Option, PeerAssessment,
    RoundRecord, RuleCheck, SharedConstraint, World,
)
from .timeutil import parse_hhmm, to_hhmm

MAX_ROUNDS = 3
K_OPTIONS = 3
EARLY_STOP_SCORE = 7
PRICES_PER_MTOK = {  # (input, output) USD
    "claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0), "claude-haiku-5-5": (0.10, 0.50),
}

# (owner module, function name). Each falls back to the devkit stand-in until P1/P2 merge their module.
_DEP_SOURCES = {
    "build_world": ("world", "build_world"),
    "list_scenarios": ("data", "list_scenarios"),
    "generate_options": ("solver", "generate_options"),
    "make_option": ("solver", "make_option"),
    "check_option": ("rules", "check_option"),
    "verify_veto": ("rules", "verify_veto"),
    "derive_shared_constraint": ("rules", "derive_shared_constraint"),
    "decide": ("decision", "decide"),
    "compare": ("baselines", "compare"),
}


@dataclass
class Deps:
    sources: dict[str, str]  # function -> "real" | "dev"
    fns: dict[str, Callable[..., Any]]

    def __getattr__(self, name: str) -> Callable[..., Any]:
        try:
            return self.fns[name]
        except KeyError:
            raise AttributeError(name) from None


def load_deps(mode: str | None = None) -> Deps:
    """mode: "dev" = all devkit, "real" = all real modules, "auto" (default) = real where available."""
    mode = mode or os.getenv("DEPS", "auto")
    fns, sources = {}, {}
    for fn, (module, attr) in _DEP_SOURCES.items():
        real = None
        if mode != "dev":
            try:
                real = getattr(importlib.import_module(f"negotiation.{module}"), attr)
            except (ImportError, AttributeError):
                if mode == "real":
                    raise
        fns[fn] = real or getattr(devkit, fn)
        sources[fn] = "real" if real else "dev"
    return Deps(sources=sources, fns=fns)


class Log:
    def __init__(self) -> None:
        self.entries: list[LogEntry] = []

    def add(self, round: int, actor: str, kind: str, summary: str,
            rule_checks: list[RuleCheck] | None = None, ref: str | None = None) -> None:
        self.entries.append(LogEntry(
            seq=len(self.entries) + 1, wall_time=datetime.now().astimezone().isoformat(timespec="seconds"),
            round=round, actor=actor, kind=kind, summary=summary, rule_checks=rule_checks or [], ref=ref,
        ))


def _key(o: Option) -> tuple:
    return (o.landing_time, o.runway, o.gate, o.turnaround)


def _describe(o: Option) -> str:
    return f"{o.option_id}: {to_hhmm(o.landing_time)} {o.runway} gate {o.gate} {o.turnaround.lower()}"


class _Ids:
    def __init__(self) -> None:
        self.n = 0

    def next(self) -> str:
        n, s = self.n, ""
        self.n += 1
        while True:
            s = chr(ord("A") + n % 26) + s
            n = n // 26 - 1
            if n < 0:
                return s


async def _run(view: AgentView, world: World, run_agent) -> AgentTurn:
    if world.attack == "AGENT_TIMEOUT" and view.agent == "GROUND":
        return AgentTurn(agent=view.agent, round=view.round, status="TIMEOUT", response=None, veto_checks=[],
                         counter_option_id=None, counter_checks=[], guardrail_flags=["SIMULATED_TIMEOUT"],
                         latency_ms=0, input_tokens=0, output_tokens=0)
    return await run_agent(view)


async def negotiate(req: NegotiateRequest, deps: Deps, run_agent=agent_runner.run_agent) -> NegotiationResult:
    t0 = time.monotonic()
    log = Log()
    world: World = deps.build_world(req.row_id, req.event, req.seed, req.attack)
    pub = world.public
    notes = {"ATC": world.private.atc.notes, "PILOT": world.private.pilot.notes, "GROUND": world.private.ground.notes}
    log.add(0, "ORCH", "SCENARIO",
            f"Scenario {pub.scenario_id}: {pub.flight.airline}{pub.flight.flight_number} "
            f"{pub.flight.origin}->{pub.flight.destination}, event {pub.event.type}, attack {world.attack}",
            ref=f"flights.csv#{req.row_id}")

    ids = _Ids()
    seen: list[Option] = []
    alive: list[Option] = []
    shared: list[SharedConstraint] = []
    rounds: list[RoundRecord] = []
    turns_by_round: list[list[AgentTurn]] = []
    peers: list[PeerAssessment] = []
    rounds_used = 0

    for r in range(1, MAX_ROUNDS + 1):
        if r < MAX_ROUNDS:
            new = deps.generate_options(pub, shared, K_OPTIONS, seen, r, "A")
            new = [o.model_copy(update={"option_id": ids.next()}) for o in new if _key(o) not in {_key(s) for s in seen}]
            seen += new
            alive += new
            if new:
                log.add(r, "SOLVER", "OPTIONS", "New options: " + "; ".join(_describe(o) for o in new))
        if not alive:
            log.add(r, "ORCH", "DECISION", "No options left to negotiate")
            break
        rounds_used = r
        round_options = list(alive)
        views = [AgentView(agent=a, round=r, max_rounds=MAX_ROUNDS, public=pub, private_notes=notes[a],
                           options=round_options, shared_constraints=list(shared),
                           peer_assessments=[p for p in peers if p.agent != a], counter_allowed=r < MAX_ROUNDS)
                 for a in AGENTS]
        turns = list(await asyncio.gather(*(_run(v, world, run_agent) for v in views)))

        eliminated: set[str] = set()
        confirmed_vetoes: set[tuple[str, str]] = set()
        new_shared: list[SharedConstraint] = []
        counters: list[Option] = []
        by_id = {o.option_id: o for o in round_options}
        for turn in turns:
            if turn.response is None:
                log.add(r, turn.agent, "ERROR", f"{turn.agent} unavailable: {turn.status}")
                continue
            summary = ", ".join(
                f"{a.option_id}={'VETO ' + (a.veto_rule or '') if a.verdict == 'VETO' else a.score}"
                for a in turn.response.assessments)
            log.add(r, turn.agent, "ASSESSMENT", summary)
            if turn.guardrail_flags:
                log.add(r, "ORCH", "GUARDRAIL", f"{turn.agent}: {', '.join(turn.guardrail_flags)}")
            for a in turn.response.assessments:
                if a.verdict != "VETO":
                    continue
                opt = by_id[a.option_id]
                chk = deps.verify_veto(world, turn.agent, opt, a.veto_rule)
                turn.veto_checks.append(chk)
                confirmed = not chk.passed
                log.add(r, "CHECKER", "VETO_CHECK",
                        f"{turn.agent} veto of {a.option_id} ({a.veto_rule}) {'confirmed' if confirmed else 'REJECTED'}",
                        rule_checks=[chk], ref=a.option_id)
                if not confirmed:
                    turn.guardrail_flags.append(f"VETO_UNVERIFIED:{a.option_id}")
                    continue
                confirmed_vetoes.add((turn.agent, a.option_id))
                eliminated.add(a.option_id)
                sc = deps.derive_shared_constraint(world, turn.agent, a.veto_rule, opt, r)
                if sc and all(sc.statement != s.statement for s in shared + new_shared):
                    new_shared.append(sc)
                    log.add(r, "ORCH", "SHARED_CONSTRAINT", sc.statement, ref=a.option_id)
            c = turn.response.counter_proposal
            if c is not None and r < MAX_ROUNDS:
                opt = deps.make_option(pub, parse_hhmm(c.landing_time), c.runway, c.gate, c.turnaround,
                                       option_id=ids.next(), source="COUNTER", proposed_by=turn.agent, round=r)
                checks = deps.check_option(world, opt)
                turn.counter_option_id = opt.option_id
                turn.counter_checks = checks
                failed = [ch.rule_id for ch in checks if ch.hard and not ch.passed]
                log.add(r, turn.agent, "COUNTER", f"Counter {_describe(opt)} — {c.reason}", ref=opt.option_id)
                log.add(r, "CHECKER", "COUNTER_CHECK",
                        f"Counter {opt.option_id} " + ("passed all hard rules" if not failed else f"failed {', '.join(failed)}"),
                        rule_checks=checks, ref=opt.option_id)
                if not failed and _key(opt) not in {_key(s) for s in seen}:
                    counters.append(opt)
                    seen.append(opt)

        shared += new_shared
        survivors = []
        for o in alive:
            if o.option_id in eliminated:
                continue
            hits = [s for s in new_shared if not _respects(o, s)]
            if hits:
                eliminated.add(o.option_id)
                log.add(r, "ORCH", "SHARED_CONSTRAINT",
                        f"{o.option_id} removed: violates '{hits[0].statement}'", ref=o.option_id)
                continue
            survivors.append(o)
        alive = survivors + counters
        rounds.append(RoundRecord(round=r, options=round_options, turns=turns, new_shared_constraints=new_shared,
                                  eliminated=sorted(eliminated)))
        turns_by_round.append(turns)
        peers = [PeerAssessment(agent=t.agent, round=r, option_id=a.option_id, verdict=a.verdict,
                                veto_confirmed=((t.agent, a.option_id) in confirmed_vetoes) if a.verdict == "VETO" else None,
                                score=a.score, cited_rules=a.cited_rules, reason=a.reason)
                 for t in turns if t.response for a in t.response.assessments]

        if all(t.status == "OK" for t in turns) and _unanimous(turns, alive):
            log.add(r, "ORCH", "DECISION", f"Early stop after round {r}: unanimous acceptance with every score ≥ {EARLY_STOP_SCORE}")
            break

    final_turns = turns_by_round[-1] if turns_by_round else []
    assessed = {a.option_id for t in final_turns if t.response for a in t.response.assessments}
    final_options = [o for o in alive if o.option_id in assessed]
    fallback = None
    if any(t.status != "OK" for t in final_turns):
        fb = deps.generate_options(pub, shared, 1, [], 0, "A")
        if fb:
            match = next((o for o in seen if _key(o) == _key(fb[0])), None)
            fallback = match or fb[0].model_copy(update={"option_id": ids.next()})
    decision = deps.decide(final_options, turns_by_round, rounds_used, fallback)
    log.add(rounds_used, "ORCH", "DECISION",
            f"{decision.outcome}: " + (_describe(decision.option) if decision.option else "no plan") + f". {decision.explanation}",
            ref=decision.option.option_id if decision.option else None)
    comparison = deps.compare(world, decision)

    all_turns = [t for ts in turns_by_round for t in ts]
    tin = sum(t.input_tokens for t in all_turns)
    tout = sum(t.output_tokens for t in all_turns)
    model = agent_runner.model_name()
    p_in, p_out = PRICES_PER_MTOK.get(model, (2.0, 10.0))
    metrics = Metrics(
        rounds_used=rounds_used,
        llm_calls=sum(1 for t in all_turns if "SIMULATED_TIMEOUT" not in t.guardrail_flags),
        invalid_outputs=sum(1 for t in all_turns if t.status in ("INVALID_OUTPUT", "REFUSAL")),
        vetoes_confirmed=sum(1 for t in all_turns for ch in t.veto_checks if not ch.passed),
        vetoes_rejected=sum(1 for t in all_turns for ch in t.veto_checks if ch.passed),
        counters_proposed=sum(1 for t in all_turns if t.counter_option_id),
        counters_passed=sum(1 for t in all_turns if t.counter_option_id
                            and all(ch.passed for ch in t.counter_checks if ch.hard)),
        input_tokens=tin, output_tokens=tout,
        est_cost_usd=round((tin * p_in + tout * p_out) / 1e6, 4),
        wall_ms=int((time.monotonic() - t0) * 1000),
    )
    return NegotiationResult(scenario_id=pub.scenario_id, model=model, world=world, rounds=rounds, decision=decision,
                             comparison=comparison, log=log.entries, metrics=metrics)


def _respects(o: Option, s: SharedConstraint) -> bool:
    if s.kind == "LATEST_LANDING":
        return o.landing_time <= s.time
    if s.kind == "EARLIEST_LANDING":
        return o.landing_time >= s.time
    if s.kind == "GATE_UNAVAILABLE":
        return o.gate != s.gate or o.in_gate_time >= s.time
    if s.kind == "RUNWAY_UNAVAILABLE":
        return o.runway != s.runway or o.landing_time >= s.time
    if s.kind == "TURNAROUND_DEADLINE":
        return o.gate != s.gate or (o.next_leg_departure or 0) <= s.time
    if s.kind == "NO_EXPEDITED":
        return o.turnaround != "EXPEDITED"
    return True


def _unanimous(turns: list[AgentTurn], alive: list[Option]) -> bool:
    alive_ids = {o.option_id for o in alive}
    for oid in alive_ids:
        votes = [next((a for a in t.response.assessments if a.option_id == oid), None) for t in turns]
        if all(v is not None and v.verdict == "ACCEPT" and v.score >= EARLY_STOP_SCORE for v in votes):
            return True
    return False
