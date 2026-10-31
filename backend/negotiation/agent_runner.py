"""One agent turn: render the agent's view, call Claude with a structured-output schema, apply guardrails."""
from __future__ import annotations

import os
import time
from functools import lru_cache
from pathlib import Path

import anthropic
from pydantic import ValidationError

from .schemas import HARD_RULES, RULE_DOMAIN, AgentName, AgentResponse, AgentTurn, AgentView, OptionAssessment
from .timeutil import parse_hhmm, to_hhmm

PROMPT_DIR = Path(__file__).parent / "agents"
MAX_REASON = 240
MAX_TOKENS = 8000
CALL_TIMEOUT_S = 30.0

_client: anthropic.AsyncAnthropic | None = None


def model_name() -> str:
    return os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")


def client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(timeout=CALL_TIMEOUT_S, max_retries=1)
    return _client


@lru_cache(maxsize=None)
def system_prompt(agent: AgentName) -> str:
    return (PROMPT_DIR / f"{agent.lower()}.md").read_text()


def _clean(text: str) -> str:
    # Stops data from closing or opening our XML-style tags.
    return text.replace("<", "(").replace(">", ")")


def render_public(p) -> str:
    f, ac = p.flight, p.aircraft
    rwys = "; ".join(
        f"{r.name} open" if r.open else
        f"{r.name} CLOSED" + (f", estimated reopen {to_hhmm(r.reopen_estimate)}" if r.reopen_estimate else "")
        for r in p.runways
    )
    queue = "\n".join(f"  - {q.flight} ({q.wake}) lands {q.runway} at {to_hhmm(q.landing_time)}" for q in p.arrival_queue)
    nxt = (f"{p.next_leg.airline}{p.next_leg.flight_number} to {p.next_leg.destination}, scheduled off-block "
           f"{to_hhmm(p.next_leg.scheduled_departure)}") if p.next_leg else "none today"
    ev = p.event
    return (
        f"Time now: {to_hhmm(p.now)} local.\n"
        f"Flight: {f.airline}{f.flight_number} {f.origin}->{f.destination}, aircraft {f.tail_number} {ac.type} "
        f"(wake {ac.wake}), scheduled in-gate {to_hhmm(f.scheduled_arrival)}.\n"
        f"Disruption: {ev.description} (since {to_hhmm(ev.start)}"
        + (f", estimated end {to_hhmm(ev.end_estimate)}" if ev.end_estimate else "") + ").\n"
        f"Runways: {rwys}.\nArrival queue:\n{queue or '  (none)'}\n"
        f"Earliest possible landing: {to_hhmm(p.eta_earliest)}. Taxi-in {p.taxi_in_min} min.\n"
        f"Planned gate: {p.planned_gate}. Assignable gates: {', '.join(p.gates)}.\n"
        f"Turnaround: standard {ac.standard_turnaround_min} min, expedited {ac.expedited_turnaround_min} min.\n"
        f"This aircraft's next leg: {nxt}."
    )


def render_options(options) -> str:
    return "\n".join(
        f"  - {o.option_id}: land {to_hhmm(o.landing_time)} on {o.runway}, gate {o.gate}, {o.turnaround} turnaround, "
        f"hold {o.hold_min} min, in-gate {to_hhmm(o.in_gate_time)}"
        + (f", next leg off-block {to_hhmm(o.next_leg_departure)}" if o.next_leg_departure else "")
        + (f" [counter-proposal by {o.proposed_by}]" if o.source == "COUNTER" else "")
        for o in options
    )


def render_view(v: AgentView) -> str:
    public = render_public(v.public)
    opts = render_options(v.options)
    shared = "\n".join(f"  - {c.statement} (from {c.from_agent}, round {c.round})" for c in v.shared_constraints)
    peers = "\n".join(
        f'<peer_message agent="{a.agent}" round="{a.round}">option {a.option_id}: {a.verdict}'
        + (f" ({'confirmed' if a.veto_confirmed else 'REJECTED by checker'})" if a.verdict == "VETO" else f", score {a.score}")
        + f" — {_clean(a.reason)}</peer_message>"
        for a in v.peer_assessments
    )
    final = v.round == v.max_rounds
    return (
        f"Negotiation round {v.round} of {v.max_rounds}.\n\n"
        f"<public_situation>\n{public}\n</public_situation>\n\n"
        f"<private_notes>\n{_clean(v.private_notes)}\n</private_notes>\n\n"
        f"Shared constraints already confirmed by the rule checker:\n{shared or '  (none)'}\n\n"
        + (f"Other agents' assessments from the previous round:\n{peers}\n\n" if peers else "")
        + f"Options to assess (assess every one):\n{opts}\n\n"
        f"Counter-proposal allowed this round: {'yes (at most one)' if v.counter_allowed else 'no — set counter_proposal to null'}.\n"
        + ("This is the FINAL round: only VETO an option if it breaks a hard rule in your domain; "
           "express any softer objection as a low score.\n" if final else "")
    )


def tidy_reason(text: str) -> str:
    """Strip stray JSON punctuation and cut rambling text after the second sentence."""
    t = " ".join(text.split()).strip().strip("{}\"'").strip()
    ends = [i for i, ch in enumerate(t) if ch in ".!?" and (i + 1 == len(t) or t[i + 1] == " " or t[i + 1].isupper())]
    if len(ends) >= 2:
        t = t[: ends[1] + 1]
    return t[:MAX_REASON]


def sanitize(v: AgentView, resp: AgentResponse) -> tuple[AgentResponse, list[str], list[str]]:
    """Returns (cleaned response, guardrail flags, problems worth one retry)."""
    flags: list[str] = []
    valid_ids = {o.option_id for o in v.options}
    seen: dict[str, OptionAssessment] = {}
    for a in resp.assessments:
        if a.option_id not in valid_ids:
            flags.append(f"UNKNOWN_OPTION_ID:{a.option_id}")
            continue
        if a.option_id in seen:
            flags.append(f"DUPLICATE_ASSESSMENT:{a.option_id}")
            continue
        upd: dict = {}
        if not 0 <= a.score <= 10:
            upd["score"] = min(10, max(0, a.score))
            flags.append(f"SCORE_CLAMPED:{a.option_id}")
        tidy = tidy_reason(a.reason)
        if tidy != a.reason:
            upd["reason"] = tidy
            if len(a.reason) > MAX_REASON:
                flags.append(f"REASON_TRUNCATED:{a.option_id}")
        if a.verdict == "VETO":
            rule = a.veto_rule
            bad = None
            if rule is None:
                bad = "VETO_WITHOUT_RULE"
            elif rule not in HARD_RULES:
                bad = f"VETO_SOFT_RULE:{rule}"
            elif RULE_DOMAIN[rule] != v.agent:
                bad = f"VETO_OUTSIDE_DOMAIN:{rule}"
            if bad:
                flags.append(f"{bad}:{a.option_id}")
                upd.update(verdict="ACCEPT", score=0, veto_rule=None)
        seen[a.option_id] = a.model_copy(update=upd) if upd else a

    missing = sorted(valid_ids - seen.keys())
    problems = [f"no assessment for option(s) {', '.join(missing)}"] if missing else []

    counter = resp.counter_proposal
    if counter is not None:
        reason = None
        if not v.counter_allowed:
            reason = "NOT_ALLOWED_THIS_ROUND"
        elif counter.based_on not in valid_ids:
            reason = f"UNKNOWN_BASE:{counter.based_on}"
        elif counter.gate not in v.public.gates:
            reason = f"UNKNOWN_GATE:{counter.gate}"
        elif counter.runway not in {r.name for r in v.public.runways}:
            reason = f"UNKNOWN_RUNWAY:{counter.runway}"
        else:
            try:
                t = parse_hhmm(counter.landing_time)
                if not v.public.eta_earliest <= t <= v.public.eta_earliest + 60:
                    reason = f"TIME_OUT_OF_WINDOW:{counter.landing_time}"
            except ValueError:
                reason = f"BAD_TIME:{counter.landing_time}"
        if reason:
            flags.append(f"COUNTER_DROPPED:{reason}")
            counter = None
        else:
            counter = counter.model_copy(update={"reason": tidy_reason(counter.reason)})

    return AgentResponse(assessments=list(seen.values()), counter_proposal=counter), flags, problems


def _fill_missing(v: AgentView, resp: AgentResponse, flags: list[str]) -> AgentResponse:
    have = {a.option_id for a in resp.assessments}
    extra = []
    for o in v.options:
        if o.option_id not in have:
            flags.append(f"MISSING_ASSESSMENT:{o.option_id}")
            extra.append(OptionAssessment(option_id=o.option_id, verdict="ACCEPT", score=0, veto_rule=None,
                                          cited_rules=[], reason="No assessment returned; scored 0 by guardrail."))
    return resp.model_copy(update={"assessments": resp.assessments + extra}) if extra else resp


def _turn(v: AgentView, status: str, resp, flags, t0, tin, tout) -> AgentTurn:
    return AgentTurn(agent=v.agent, round=v.round, status=status, response=resp, veto_checks=[],
                     counter_option_id=None, counter_checks=[], guardrail_flags=flags,
                     latency_ms=int((time.monotonic() - t0) * 1000), input_tokens=tin, output_tokens=tout)


async def run_agent(v: AgentView) -> AgentTurn:
    t0 = time.monotonic()
    text = render_view(v)
    flags: list[str] = []
    tin = tout = 0
    last_problem = ""
    for attempt in range(2):
        prompt = text if attempt == 0 else f"{text}\nYour previous answer was invalid: {last_problem}. Answer again."
        try:
            msg = await client().messages.parse(
                model=model_name(),
                max_tokens=MAX_TOKENS,
                system=system_prompt(v.agent),
                messages=[{"role": "user", "content": prompt}],
                output_format=AgentResponse,
                output_config={"effort": "low"},
            )
        except anthropic.APITimeoutError:
            return _turn(v, "TIMEOUT", None, flags, t0, tin, tout)
        except anthropic.APIError as e:
            flags.append(f"API_ERROR:{type(e).__name__}")
            return _turn(v, "API_ERROR", None, flags, t0, tin, tout)
        except (ValidationError, ValueError) as e:
            last_problem = f"output did not match the schema ({type(e).__name__})"
            flags.append("SCHEMA_RETRY")
            continue
        tin += msg.usage.input_tokens
        tout += msg.usage.output_tokens
        if msg.stop_reason == "refusal":
            return _turn(v, "REFUSAL", None, flags, t0, tin, tout)
        if msg.stop_reason == "max_tokens" or msg.parsed_output is None:
            last_problem = "output was cut off or empty"
            flags.append("EMPTY_RETRY")
            continue
        resp, g_flags, problems = sanitize(v, msg.parsed_output)
        flags.extend(g_flags)
        if problems and attempt == 0:
            last_problem = "; ".join(problems)
            flags.append("INCOMPLETE_RETRY")
            continue
        return _turn(v, "OK", _fill_missing(v, resp, flags), flags, t0, tin, tout)
    return _turn(v, "INVALID_OUTPUT", None, flags, t0, tin, tout)
