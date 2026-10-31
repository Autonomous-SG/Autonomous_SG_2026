"""Rule evaluation for the negotiation referee and public solver."""
from __future__ import annotations

from .schemas import HARD_RULES, PUBLIC_HARD_RULES, RULE_DOMAIN, AgentName, Option, RuleCheck, RuleId, SharedConstraint, World, PublicState


def _check(rule_id: RuleId, passed: bool, detail: str, private: bool = False) -> RuleCheck:
    return RuleCheck(rule_id=rule_id, domain=RULE_DOMAIN[rule_id], hard=rule_id in HARD_RULES,
                     passed=passed, detail=detail, private=private)


def _wake_gap(leader: str, follower: str) -> int:
    return 3 if leader == "HEAVY" and follower == "LIGHT" else 2


def _checks(public: PublicState, option: Option, *, private=None, shared=(), full=False) -> list[RuleCheck]:
    out: list[RuleCheck] = []
    runway = next((r for r in public.runways if r.name == option.runway), None)
    reopen = None if runway is None else (private.runway_reopen_actual if full and private else runway.reopen_estimate)
    open_ok = runway is not None and (runway.open or (reopen is not None and option.landing_time >= reopen))
    out.append(_check("RUNWAY_OPEN", open_ok, f"{option.runway} {'open' if open_ok else 'closed'} at {option.landing_time}", full))
    gaps = [q for q in public.arrival_queue if q.runway == option.runway and q.landing_time <= option.landing_time]
    sep = all(option.landing_time - q.landing_time >= _wake_gap(q.wake, public.aircraft.wake) for q in gaps)
    out.append(_check("WAKE_SEPARATION", sep, "wake separation satisfied" if sep else "insufficient wake separation", False))
    min_turn = public.aircraft.min_turnaround_min if option.turnaround == "STANDARD" else public.aircraft.expedited_turnaround_min
    turn_ok = option.next_leg_departure is None or option.next_leg_departure >= option.in_gate_time + min_turn
    out.append(_check("MIN_TURNAROUND", turn_ok, f"turnaround requires {min_turn} min", False))
    if full and private:
        p = private
        capacity = (p.fuel_at_eta_kg - p.min_landing_fuel_kg) / p.hold_burn_kg_per_min
        ok = option.hold_min <= capacity
        out.append(_check("FUEL_RESERVE", ok, f"hold {option.hold_min} min vs reserve {capacity:.1f} min", True))
        gate_free = option.in_gate_time >= public_world_gate(private, option.gate)
        # public_world_gate is replaced below by the closure carrying the world in check_option.
        out.append(_check("GATE_CONFLICT", gate_free, "gate conflict checked", True))
    for constraint in shared:
        ok = True
        if constraint.kind == "GATE_UNAVAILABLE": ok = option.gate != constraint.gate or option.in_gate_time >= (constraint.time or 0)
        elif constraint.kind == "RUNWAY_UNAVAILABLE": ok = option.runway != constraint.runway
        elif constraint.kind == "LATEST_LANDING": ok = option.landing_time <= (constraint.time or option.landing_time)
        elif constraint.kind == "EARLIEST_LANDING": ok = option.landing_time >= (constraint.time or option.landing_time)
        elif constraint.kind == "NO_EXPEDITED": ok = option.turnaround != "EXPEDITED"
        out.append(_check(constraint.from_rule, ok, constraint.statement, False))
    return out


def public_world_gate(private, gate):
    return 0


def check_option(world: World, option: Option) -> list[RuleCheck]:
    p = world.public
    out = _checks(p, option, private=world.private.atc, full=False)
    # Replace/add full private checks explicitly to keep each rule present exactly once.
    out = [c for c in out if c.rule_id not in {"FUEL_RESERVE", "GATE_CONFLICT"}]
    atc = world.private.atc
    runway = next((r for r in p.runways if r.name == option.runway), None)
    reopen = None if runway is None else (atc.runway_reopen_actual if not runway.open else None)
    out[0] = _check("RUNWAY_OPEN", runway is not None and (runway.open or (reopen is not None and option.landing_time >= reopen)), "actual runway reopening", True)
    pilot = world.private.pilot
    reserve = (pilot.fuel_at_eta_kg - pilot.min_landing_fuel_kg) / pilot.hold_burn_kg_per_min
    out.append(_check("FUEL_RESERVE", option.hold_min <= reserve, f"hold {option.hold_min} vs {reserve:.1f} min fuel reserve", True))
    busy = world.private.ground.gate_busy_until.get(option.gate, 0)
    out.append(_check("GATE_CONFLICT", option.in_gate_time >= busy, f"gate free at {busy}, in-gate {option.in_gate_time}", True))
    teams = [t for t in world.private.ground.crew if option.gate in t.gates]
    deadline = option.next_leg_departure or option.in_gate_time
    crew_ok = any(deadline <= t.shift_end or t.overtime_allowed for t in teams)
    out.append(_check("CREW_DUTY_LIMIT", crew_ok, "crew duty limit", True))
    tug_ok = any(e.kind == "TUG" and (e.out_until is None or (option.next_leg_departure or option.in_gate_time) >= e.out_until) for e in world.private.ground.equipment)
    out.append(_check("EQUIPMENT_AVAILABLE", tug_ok, "tug availability", True))
    return out


def check_public(public: PublicState, option: Option, shared=()) -> list[RuleCheck]:
    return [c for c in _checks(public, option, shared=shared) if c.rule_id in PUBLIC_HARD_RULES or c.rule_id in {s.from_rule for s in shared}]


def verify_veto(world: World, agent: AgentName, option: Option, rule_id: RuleId) -> RuleCheck:
    if RULE_DOMAIN.get(rule_id) != agent or rule_id not in HARD_RULES:
        return _check(rule_id, True, "veto is outside the agent's hard-rule domain", True)
    found = next((c for c in check_option(world, option) if c.rule_id == rule_id), None)
    return found or _check(rule_id, True, "rule unavailable", True)


def derive_shared_constraint(world: World, agent: AgentName, rule_id: RuleId, option: Option, round: int) -> SharedConstraint:
    time = None; gate = None; runway = None; kind = "LATEST_LANDING"
    if rule_id == "GATE_CONFLICT":
        kind, gate, time = "GATE_UNAVAILABLE", option.gate, world.private.ground.gate_busy_until.get(option.gate)
    elif rule_id == "RUNWAY_OPEN":
        kind, runway, time = "RUNWAY_UNAVAILABLE", option.runway, world.private.atc.runway_reopen_actual
    elif rule_id == "FUEL_RESERVE":
        kind, time = "LATEST_LANDING", option.landing_time - max(0, option.hold_min)
    elif rule_id == "CREW_DUTY_LIMIT": kind = "TURNAROUND_DEADLINE"; time = option.next_leg_departure
    elif rule_id == "MIN_TURNAROUND": kind = "NO_EXPEDITED"
    statement = {"GATE_UNAVAILABLE": f"Gate {gate} unavailable before {time}", "RUNWAY_UNAVAILABLE": f"Runway {runway} unavailable", "LATEST_LANDING": f"Landing no later than {time}", "TURNAROUND_DEADLINE": f"Turnaround deadline {time}", "NO_EXPEDITED": "Expedited turnaround unavailable"}[kind]
    return SharedConstraint(kind=kind, statement=statement, time=time, gate=gate, runway=runway, from_rule=rule_id, from_agent=agent, round=round)
