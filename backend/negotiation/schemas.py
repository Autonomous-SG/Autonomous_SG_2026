"""SHARED CONTRACT. Every module and the frontend depend on these shapes.
Change only after telling the whole team, then regenerate fixtures (scripts/make_fixtures.py)."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

# Minutes since 00:00 local time at the destination airport. Values > 1439 mean after midnight.
Minute = int

AgentName = Literal["ATC", "PILOT", "GROUND"]
AGENTS: tuple[AgentName, ...] = ("ATC", "PILOT", "GROUND")
Actor = Literal["ORCH", "SOLVER", "CHECKER", "ATC", "PILOT", "GROUND", "HUMAN"]
WakeCategory = Literal["LIGHT", "MEDIUM", "HEAVY"]
Turnaround = Literal["STANDARD", "EXPEDITED"]
EventType = Literal["RUNWAY_CLOSURE", "WEATHER_CAPACITY_DROP", "GATE_EQUIPMENT_FAILURE"]
AttackType = Literal["NONE", "LYING_AGENT", "PROMPT_INJECTION", "NO_FEASIBLE", "AGENT_TIMEOUT"]
Verdict = Literal["ACCEPT", "VETO"]

RuleId = Literal[
    "RUNWAY_OPEN",
    "WAKE_SEPARATION",
    "MIN_TURNAROUND",
    "FUEL_RESERVE",
    "GATE_CONFLICT",
    "CREW_DUTY_LIMIT",
    "EQUIPMENT_AVAILABLE",
    "SECTOR_THROUGHPUT",
    "PAX_CONNECTION",
    "NEXT_LEG_DELAY",
    "GATE_CHANGE",
]

RULE_DOMAIN: dict[str, AgentName] = {
    "RUNWAY_OPEN": "ATC",
    "WAKE_SEPARATION": "ATC",
    "SECTOR_THROUGHPUT": "ATC",
    "FUEL_RESERVE": "PILOT",
    "PAX_CONNECTION": "PILOT",
    "NEXT_LEG_DELAY": "PILOT",
    "MIN_TURNAROUND": "GROUND",
    "GATE_CONFLICT": "GROUND",
    "CREW_DUTY_LIMIT": "GROUND",
    "EQUIPMENT_AVAILABLE": "GROUND",
    "GATE_CHANGE": "GROUND",
}
# Only hard rules can justify a VETO. Soft rules may only lower a score.
HARD_RULES: frozenset[str] = frozenset(
    {"RUNWAY_OPEN", "WAKE_SEPARATION", "MIN_TURNAROUND", "FUEL_RESERVE",
     "GATE_CONFLICT", "CREW_DUTY_LIMIT", "EQUIPMENT_AVAILABLE"}
)
# Hard rules the solver can evaluate from public data alone.
PUBLIC_HARD_RULES: frozenset[str] = frozenset({"RUNWAY_OPEN", "WAKE_SEPARATION", "MIN_TURNAROUND"})


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- Real data (flights.csv) ----------

class FlightRecord(Strict):
    row_id: int  # 0-based data row index in flights.csv (header excluded) = pandas default index
    date: str  # "2015-01-12"
    airline: str
    flight_number: int
    tail_number: str
    origin: str
    destination: str
    scheduled_departure: Minute
    scheduled_arrival: Minute
    actual_arrival: Optional[Minute]
    arrival_delay: Optional[int]
    departure_delay: Optional[int]
    weather_delay: int
    late_aircraft_delay: int
    distance: int
    taxi_in: Optional[int]


# ---------- Public state: solver + all agents see this ----------

class Aircraft(Strict):
    type: str
    wake: WakeCategory
    standard_turnaround_min: int  # constraints.turnarounds(dest)[0] = workbook minimum + 10
    expedited_turnaround_min: int  # constraints.turnarounds(dest)[1] = workbook min_turnaround_min (the floor)


class Runway(Strict):
    name: str
    open: bool
    reopen_estimate: Optional[Minute] = None


class QueuedArrival(Strict):
    flight: str  # "DL811"
    wake: WakeCategory
    runway: str
    landing_time: Minute
    real: bool  # True = this flight exists in flights.csv on this date (its times/wake may still be synthetic)


class DisruptionEvent(Strict):
    type: EventType
    description: str
    start: Minute
    runway: Optional[str] = None
    gate: Optional[str] = None
    end_estimate: Optional[Minute] = None


class PublicState(Strict):
    scenario_id: str
    now: Minute
    flight: FlightRecord
    next_leg: Optional[FlightRecord]  # same tail number, next departure from destination that day
    aircraft: Aircraft
    event: DisruptionEvent
    runways: list[Runway]
    arrival_queue: list[QueuedArrival]
    eta_earliest: Minute  # earliest possible landing time if no holding
    taxi_in_min: int
    planned_gate: str
    gates: list[str]  # gates the solver may assign
    synthetic_fields: list[str]  # dotted paths of generated (non-real) values, for UI labels


# ---------- Private state: each agent sees ONLY its own `notes` text ----------
# Structured fields are ground truth for the rule checker; they are never shown to any agent.

class Connection(Strict):
    flight: str
    destination: str
    departure: Minute
    pax: int
    min_connect_min: int
    last_of_day: bool


class AtcPrivate(Strict):
    notes: str
    runway_reopen_actual: Optional[Minute]  # truth behind the public reopen_estimate
    reopen_uncertainty_min: int


class PilotPrivate(Strict):
    notes: str
    fuel_at_eta_kg: int  # fuel on board if landing at eta_earliest
    min_landing_fuel_kg: int  # 30-min final reserve = constraints.FINAL_RESERVE_MIN x hold burn; never plan below
    hold_burn_kg_per_min: int
    connections: list[Connection]


class CrewTeam(Strict):
    team: str
    gates: list[str]
    shift_end: Minute
    overtime_allowed: bool


class Equipment(Strict):
    id: str
    kind: str  # "TUG"
    out_until: Optional[Minute]  # None = available


class GroundPrivate(Strict):
    notes: str
    gate_busy_until: dict[str, Minute]  # gate -> time it becomes free; absent = free
    crew: list[CrewTeam]
    equipment: list[Equipment]


class PrivateStates(Strict):
    atc: AtcPrivate
    pilot: PilotPrivate
    ground: GroundPrivate


class World(Strict):
    public: PublicState
    private: PrivateStates
    seed: int
    attack: AttackType = "NONE"


# ---------- Options, rule checks, shared constraints ----------

class Option(Strict):
    option_id: str  # "A", "B", ... counters get the next free letter
    landing_time: Minute
    runway: str
    gate: str
    turnaround: Turnaround
    hold_min: int  # landing_time - eta_earliest
    in_gate_time: Minute  # landing_time + taxi_in_min
    next_leg_departure: Optional[Minute]  # in_gate_time + turnaround minutes
    source: Literal["SOLVER", "COUNTER"]
    proposed_by: Optional[AgentName] = None
    round_introduced: int
    public_cost: float
    cost_breakdown: dict[str, float]


class RuleCheck(Strict):
    rule_id: RuleId
    domain: AgentName
    hard: bool
    passed: bool
    detail: str  # full explanation for humans (UI, log). May contain private facts.
    private: bool  # True = detail must NOT be shown to other agents; they only see rule_id + passed


class SharedConstraint(Strict):
    kind: Literal["LATEST_LANDING", "EARLIEST_LANDING", "GATE_UNAVAILABLE",
                  "RUNWAY_UNAVAILABLE", "TURNAROUND_DEADLINE", "NO_EXPEDITED"]
    statement: str  # what every agent and the solver see; contains no private details
    time: Optional[Minute] = None
    gate: Optional[str] = None
    runway: Optional[str] = None
    from_rule: RuleId
    from_agent: AgentName
    round: int


# ---------- LLM output: the exact structured-output schema each agent returns ----------
# Keep simple: no dicts, no numeric/string constraints (the orchestrator validates ranges).

class OptionAssessment(Strict):
    option_id: str
    verdict: Verdict
    score: int  # 0-10, how good this option is for MY domain; ignored when verdict == VETO
    veto_rule: Optional[RuleId]  # required when verdict == VETO; must be a HARD rule in my domain
    cited_rules: list[RuleId]
    reason: str  # one sentence, <= 240 chars


class CounterProposal(Strict):
    based_on: str  # option_id it modifies
    landing_time: str  # "HH:MM" local
    runway: str
    gate: str
    turnaround: Turnaround
    reason: str


class AgentResponse(Strict):
    assessments: list[OptionAssessment]
    counter_proposal: Optional[CounterProposal]


# ---------- What the orchestrator gives an agent each round ----------

class PeerAssessment(Strict):
    agent: AgentName
    round: int
    option_id: str
    verdict: Verdict
    veto_confirmed: Optional[bool]  # set by the checker; None if not a veto
    score: int
    cited_rules: list[RuleId]
    reason: str  # untrusted peer text: always wrapped in <peer_message> tags when rendered


class AgentView(Strict):
    agent: AgentName
    round: int
    max_rounds: int
    public: PublicState
    private_notes: str
    options: list[Option]
    shared_constraints: list[SharedConstraint]
    peer_assessments: list[PeerAssessment]
    counter_allowed: bool


# ---------- Negotiation record ----------

TurnStatus = Literal["OK", "INVALID_OUTPUT", "TIMEOUT", "API_ERROR", "REFUSAL"]


class AgentTurn(Strict):
    agent: AgentName
    round: int
    status: TurnStatus
    response: Optional[AgentResponse]
    veto_checks: list[RuleCheck]
    counter_option_id: Optional[str]
    counter_checks: list[RuleCheck]
    guardrail_flags: list[str]  # e.g. "UNKNOWN_OPTION_ID:Z", "VETO_OUTSIDE_DOMAIN:FUEL_RESERVE", "VETO_UNVERIFIED:C"
    latency_ms: int
    input_tokens: int
    output_tokens: int


class RoundRecord(Strict):
    round: int
    options: list[Option]
    turns: list[AgentTurn]
    new_shared_constraints: list[SharedConstraint]
    eliminated: list[str]  # option_ids removed by a confirmed veto this round


class Decision(Strict):
    outcome: Literal["CONSENSUS", "FALLBACK", "NO_FEASIBLE"]
    option: Optional[Option]
    min_score: Optional[int]
    rounds_used: int
    explanation: str
    party_messages: dict[AgentName, str]  # final instruction text per party (templated, not LLM)
    requires_human: bool = True


class PlanEvaluation(Strict):
    label: Literal["SOLVER_ONLY", "NEGOTIATED", "ORACLE", "HISTORICAL"]
    option: Optional[Option]
    feasible_in_reality: Optional[bool]  # full-truth hard-rule check; None for HISTORICAL
    failed_rules: list[RuleId]
    arrival_delay_min: Optional[int]
    next_leg_delay_min: Optional[int]
    connection_pax_missed: Optional[int]
    note: str


LogKind = Literal["SCENARIO", "OPTIONS", "ASSESSMENT", "VETO_CHECK", "SHARED_CONSTRAINT", "COUNTER",
                  "COUNTER_CHECK", "GUARDRAIL", "DECISION", "HUMAN_DECISION", "ERROR"]


class LogEntry(Strict):
    seq: int
    wall_time: str  # ISO 8601
    round: int  # 0 = setup
    actor: Actor
    kind: LogKind
    summary: str
    rule_checks: list[RuleCheck] = []
    ref: Optional[str] = None  # option_id, or "flights.csv#<row_id>"


class Metrics(Strict):
    rounds_used: int
    llm_calls: int
    invalid_outputs: int
    vetoes_confirmed: int
    vetoes_rejected: int
    counters_proposed: int
    counters_passed: int
    input_tokens: int
    output_tokens: int
    est_cost_usd: float
    wall_ms: int


class NegotiationResult(Strict):
    scenario_id: str
    model: str
    world: World  # full world incl. private data, for the UI. Agents never saw each other's private data.
    rounds: list[RoundRecord]
    decision: Decision
    comparison: list[PlanEvaluation]
    log: list[LogEntry]
    metrics: Metrics


# ---------- API ----------

class ScenarioSummary(Strict):
    row_id: int
    date: str
    flight: str  # "DL912"
    origin: str
    destination: str
    scheduled_arrival: Minute
    arrival_delay: Optional[int]
    weather_delay: int
    late_aircraft_delay: int
    has_next_leg: bool


class NegotiateRequest(Strict):
    row_id: int
    event: EventType = "RUNWAY_CLOSURE"
    seed: int = 42
    attack: AttackType = "NONE"


class HumanDecisionRequest(Strict):
    scenario_id: str
    approve: bool
    note: str = ""
