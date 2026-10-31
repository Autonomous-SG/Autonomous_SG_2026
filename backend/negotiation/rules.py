"""Rule evaluation: the referee (full truth) and the public checks the solver may use. Limits from constraints.py."""
from __future__ import annotations

from . import constraints as C
from .schemas import (
    HARD_RULES, RULE_DOMAIN, AgentName, Option, PublicState, RuleCheck, SharedConstraint, World,
)
from .timeutil import to_hhmm


def _check(rule: str, passed: bool, detail: str, private: bool) -> RuleCheck:
    return RuleCheck(rule_id=rule, domain=RULE_DOMAIN[rule], hard=rule in HARD_RULES, passed=passed,
                     detail=detail, private=private)


def max_hold_min(world: World) -> int:
    p = world.private.pilot
    return (p.fuel_at_eta_kg - p.min_landing_fuel_kg) // p.hold_burn_kg_per_min


def _runway_check(public: PublicState, o: Option, truth_reopen: int | None) -> RuleCheck:
    rwy = next((r for r in public.runways if r.name == o.runway), None)
    if rwy is None:
        return _check("RUNWAY_OPEN", False, f"unknown runway {o.runway}", False)
    if rwy.open:
        return _check("RUNWAY_OPEN", True, f"{o.runway} open", False)
    reopen = truth_reopen if truth_reopen is not None else rwy.reopen_estimate
    if reopen is None or o.landing_time < reopen:
        return _check("RUNWAY_OPEN", False, f"{o.runway} closed until {to_hhmm(reopen) if reopen else 'unknown'}",
                      truth_reopen is not None)
    return _check("RUNWAY_OPEN", True, f"{o.runway} reopens {to_hhmm(reopen)}", truth_reopen is not None)


def _wake_check(public: PublicState, o: Option) -> RuleCheck:
    """Separation from every queued arrival on the same runway, both ahead of and behind us."""
    me = public.aircraft.wake
    for q in public.arrival_queue:
        if q.runway != o.runway:
            continue
        if q.landing_time <= o.landing_time:
            need, gap = C.wake_sep_min(q.wake, me), o.landing_time - q.landing_time
        else:
            need, gap = C.wake_sep_min(me, q.wake), q.landing_time - o.landing_time
        if gap < need:
            return _check("WAKE_SEPARATION", False, f"{gap} min from {q.flight} ({q.wake}), need {need:.1f} min", False)
    return _check("WAKE_SEPARATION", True, "separation OK on " + o.runway, False)


def _turn_check(public: PublicState, o: Option) -> RuleCheck:
    ac = public.aircraft
    need = ac.expedited_turnaround_min if o.turnaround == "EXPEDITED" else ac.standard_turnaround_min
    have = (o.next_leg_departure or o.in_gate_time + need) - o.in_gate_time
    return _check("MIN_TURNAROUND", have >= need, f"{have} min turnaround, need {need}", False)


def respects(o: Option, c: SharedConstraint) -> bool:
    if c.kind == "LATEST_LANDING":
        return o.landing_time <= c.time
    if c.kind == "EARLIEST_LANDING":
        return o.landing_time >= c.time
    if c.kind == "GATE_UNAVAILABLE":
        return o.gate != c.gate or o.in_gate_time >= c.time
    if c.kind == "RUNWAY_UNAVAILABLE":
        return o.runway != c.runway or o.landing_time >= c.time
    if c.kind == "TURNAROUND_DEADLINE":
        return o.gate != c.gate or (o.next_leg_departure or 0) <= c.time
    if c.kind == "NO_EXPEDITED":
        return o.turnaround != "EXPEDITED"
    return True


def check_public(public: PublicState, o: Option, shared: list[SharedConstraint]) -> list[RuleCheck]:
    """What the solver may know: public hard rules plus constraints revealed by confirmed vetoes."""
    checks = [_runway_check(public, o, None), _wake_check(public, o), _turn_check(public, o)]
    for c in shared:
        if not respects(o, c):
            checks.append(_check(c.from_rule, False, f"violates shared constraint: {c.statement}", False))
    return checks


def check_option(world: World, o: Option) -> list[RuleCheck]:
    """Referee: every rule against the full (public + private) truth."""
    pub, priv = world.public, world.private
    truth_reopen = priv.atc.runway_reopen_actual if o.runway == pub.event.runway else None
    checks = [_runway_check(pub, o, truth_reopen), _wake_check(pub, o), _turn_check(pub, o)]
    mh = max_hold_min(world)
    checks.append(_check("FUEL_RESERVE", o.hold_min <= mh, f"hold {o.hold_min} min, max {mh} min", True))
    free_at = priv.ground.gate_busy_until.get(o.gate, 0)
    notice = o.in_gate_time - pub.now
    late_change = o.gate != pub.planned_gate and notice < C.GATE_CHANGE_NOTICE_MIN
    busy = f"{o.gate} busy until {to_hhmm(free_at)}" if free_at else f"{o.gate} free"
    checks.append(_check("GATE_CONFLICT", o.in_gate_time >= free_at and not late_change,
                         f"{busy}, in-gate {to_hhmm(o.in_gate_time)}"
                         + (f"; gate change notice {notice} min < {C.GATE_CHANGE_NOTICE_MIN}" if late_change else ""),
                         True))
    team = next((t for t in priv.ground.crew if o.gate in t.gates), None)
    end = o.next_leg_departure or o.in_gate_time
    if team is None:
        checks.append(_check("CREW_DUTY_LIMIT", False, f"no crew team covers {o.gate}", True))
    else:
        checks.append(_check("CREW_DUTY_LIMIT", team.overtime_allowed or end <= team.shift_end,
                             f"team {team.team} shift ends {to_hhmm(team.shift_end)}, turn ends {to_hhmm(end)}", True))
    tugs = [e for e in priv.ground.equipment if e.kind == "TUG" and (e.out_until is None or e.out_until <= end)]
    checks.append(_check("EQUIPMENT_AVAILABLE", bool(tugs), f"{len(tugs)} tug(s) available", True))
    missed = sum(c.pax for c in priv.pilot.connections if o.in_gate_time + c.min_connect_min > c.departure)
    checks.append(_check("PAX_CONNECTION", missed == 0, f"{missed} connecting pax would miss", True))
    if pub.next_leg and o.next_leg_departure:
        d = max(0, o.next_leg_departure - pub.next_leg.scheduled_departure)
        checks.append(_check("NEXT_LEG_DELAY", d <= 15, f"next leg ~{d} min late", False))
    checks.append(_check("GATE_CHANGE", o.gate == pub.planned_gate, f"gate {o.gate} (planned {pub.planned_gate})", False))
    return checks


def verify_veto(world: World, agent: AgentName, o: Option, rule_id: str) -> RuleCheck:
    """Confirmed (passed=False) only if the rule is a hard rule in the agent's own domain and really fails."""
    if rule_id not in HARD_RULES or RULE_DOMAIN.get(rule_id) != agent:
        return RuleCheck(rule_id=rule_id, domain=RULE_DOMAIN.get(rule_id, agent), hard=rule_id in HARD_RULES,
                         passed=True, detail=f"{agent} cannot veto with {rule_id}", private=False)
    c = next((c for c in check_option(world, o) if c.rule_id == rule_id), None)
    return c or _check(rule_id, True, f"{rule_id} not evaluated", False)


def derive_shared_constraint(world: World, agent: AgentName, rule_id: str, o: Option,
                             round: int) -> SharedConstraint | None:
    """What a confirmed veto reveals to everyone, without the private details behind it."""
    pub, priv = world.public, world.private
    base = dict(from_rule=rule_id, from_agent=agent, round=round)
    if rule_id == "GATE_CONFLICT":
        t = priv.ground.gate_busy_until.get(o.gate, 0)
        if o.gate != pub.planned_gate:
            t = max(t, pub.now + C.GATE_CHANGE_NOTICE_MIN)
        return SharedConstraint(kind="GATE_UNAVAILABLE", gate=o.gate, time=t,
                                statement=f"Gate {o.gate} unavailable before {to_hhmm(t)}", **base)
    if rule_id == "FUEL_RESERVE":
        t = pub.eta_earliest + max_hold_min(world)
        return SharedConstraint(kind="LATEST_LANDING", time=t,
                                statement=f"{pub.flight.airline}{pub.flight.flight_number} must land by {to_hhmm(t)}",
                                **base)
    if rule_id == "CREW_DUTY_LIMIT":
        team = next((t for t in priv.ground.crew if o.gate in t.gates), None)
        if team is None:
            return None
        return SharedConstraint(kind="TURNAROUND_DEADLINE", gate=o.gate, time=team.shift_end,
                                statement=f"Turnaround at {o.gate} must finish by {to_hhmm(team.shift_end)}", **base)
    if rule_id == "RUNWAY_OPEN" and priv.atc.runway_reopen_actual is not None:
        t = priv.atc.runway_reopen_actual
        return SharedConstraint(kind="RUNWAY_UNAVAILABLE", runway=o.runway, time=t,
                                statement=f"Runway {o.runway} unavailable before {to_hhmm(t)}", **base)
    if rule_id == "EQUIPMENT_AVAILABLE":
        return SharedConstraint(kind="NO_EXPEDITED", statement="Expedited turnaround not possible", **base)
    return None
