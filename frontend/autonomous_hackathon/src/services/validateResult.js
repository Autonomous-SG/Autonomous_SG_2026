// Validate fields used by the UI before accepting API responses or saved JSON.
// Safety and negotiation decisions remain the backend's responsibility.
const fail = path => { throw new Error(`Invalid negotiation result at ${path}.`) }
const object = (value, path) => { if (!value || typeof value !== 'object' || Array.isArray(value)) fail(path) }
const text = (value, path) => { if (typeof value !== 'string') fail(path) }
const number = (value, path) => { if (typeof value !== 'number' || !Number.isFinite(value)) fail(path) }
const bool = (value, path) => { if (typeof value !== 'boolean') fail(path) }
const list = (value, path, check) => { if (!Array.isArray(value)) fail(path); value.forEach((item, i) => check(item, `${path}[${i}]`)) }
const nullable = check => (value, path) => { if (value !== null) check(value, path) }
const oneOf = values => (value, path) => { if (!values.includes(value)) fail(path) }
const fields = (value, path, spec) => { object(value, path); for (const [key, check] of Object.entries(spec)) check(value[key], `${path}.${key}`) }
const texts = (value, path) => list(value, path, text)
const agent = oneOf(['ATC', 'PILOT', 'GROUND'])

function flight(value, path) {
  fields(value, path, { row_id: number, date: text, airline: text, flight_number: number,
    origin: text, destination: text, tail_number: text, scheduled_arrival: number,
    scheduled_departure: number, actual_arrival: nullable(number), arrival_delay: nullable(number), departure_delay: nullable(number) })
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value.date) || !Number.isFinite(Date.parse(`${value.date}T00:00:00Z`))) fail(`${path}.date`)
}
function option(value, path) {
  fields(value, path, { option_id: text, landing_time: number, runway: text, gate: text,
    turnaround: oneOf(['STANDARD', 'EXPEDITED']), hold_min: number, in_gate_time: number,
    next_leg_departure: nullable(number), source: oneOf(['SOLVER', 'COUNTER']), proposed_by: nullable(agent),
    public_cost: number, cost_breakdown: object })
  Object.entries(value.cost_breakdown).forEach(([key, val]) => number(val, `${path}.cost_breakdown.${key}`))
}
function rule(value, path) {
  fields(value, path, { rule_id: text, domain: agent, hard: bool, passed: bool, detail: text, private: bool })
}
const rules = (value, path) => list(value, path, rule)
function turn(value, path) {
  fields(value, path, { agent, status: oneOf(['OK', 'INVALID_OUTPUT', 'TIMEOUT', 'API_ERROR', 'REFUSAL']),
    response: nullable((value, path) => {
      fields(value, path, {
        assessments: (value, path) => list(value, path, (value, path) => fields(value, path, {
          option_id: text, verdict: oneOf(['ACCEPT', 'VETO']), score: number,
          veto_rule: nullable(text), cited_rules: texts, reason: text,
        })),
        counter_proposal: nullable((value, path) => fields(value, path, {
          based_on: text, landing_time: text, runway: text, gate: text, turnaround: text, reason: text,
        })),
      })
    }),
    veto_checks: rules, counter_checks: rules, counter_option_id: nullable(text),
    guardrail_flags: texts, latency_ms: number, input_tokens: number, output_tokens: number,
  })
}

export function validateResult(data) {
  fields(data, 'result', {
    scenario_id: text, model: text,
    world: (world, path) => {
      fields(world, path, { seed: number, attack: text, private: object, public: object })
      for (const key of ['atc', 'pilot', 'ground']) fields(world.private[key], `${path}.private.${key}`, { notes: text })
      fields(world.public, `${path}.public`, {
        now: number, flight, next_leg: nullable(flight), eta_earliest: number, planned_gate: text,
        gates: texts, synthetic_fields: texts,
        aircraft: (value, path) => fields(value, path, { type: text, wake: text, min_turnaround_min: number, expedited_turnaround_min: number }),
        event: (value, path) => fields(value, path, { type: text, description: text, start: number, end_estimate: nullable(number) }),
        runways: (value, path) => list(value, path, (value, path) => fields(value, path, { name: text, open: bool, reopen_estimate: nullable(number) })),
        arrival_queue: (value, path) => list(value, path, (value, path) => fields(value, path, { flight: text, landing_time: number, runway: text, wake: text, real: bool })),
      })
    },
    rounds: (value, path) => list(value, path, (value, path) => fields(value, path, {
      round: number, options: (value, path) => list(value, path, option), turns: (value, path) => list(value, path, turn),
      eliminated: texts, new_shared_constraints: (value, path) => list(value, path, (value, path) => fields(value, path, { statement: text, from_agent: agent, from_rule: text })),
    })),
    decision: (value, path) => {
      fields(value, path, { outcome: oneOf(['CONSENSUS', 'FALLBACK', 'NO_FEASIBLE']), option: nullable(option), min_score: nullable(number), rounds_used: number, explanation: text, requires_human: bool, party_messages: object })
      Object.entries(value.party_messages).forEach(([key, val]) => text(val, `${path}.party_messages.${key}`))
      if (value.outcome !== 'NO_FEASIBLE' && !value.option) fail(`${path}.option`)
      if (value.outcome === 'NO_FEASIBLE' && value.option !== null) fail(`${path}.option`)
    },
    comparison: (value, path) => list(value, path, (value, path) => fields(value, path, {
      label: oneOf(['SOLVER_ONLY', 'NEGOTIATED', 'ORACLE', 'HISTORICAL']), option: nullable(option),
      feasible_in_reality: nullable(bool), failed_rules: texts, arrival_delay_min: nullable(number),
      next_leg_delay_min: nullable(number), connection_pax_missed: nullable(number), note: text,
    })),
    log: (value, path) => list(value, path, (value, path) => fields(value, path, {
      seq: number, wall_time: text, round: number, actor: text, kind: text, summary: text, ref: nullable(text), rule_checks: rules,
    })),
    metrics: (value, path) => {
      fields(value, path, Object.fromEntries(['rounds_used', 'llm_calls', 'invalid_outputs', 'vetoes_confirmed', 'vetoes_rejected', 'counters_proposed', 'counters_passed', 'input_tokens', 'output_tokens', 'est_cost_usd', 'wall_ms'].map(key => [key, number])))
    },
  })
  return data
}
