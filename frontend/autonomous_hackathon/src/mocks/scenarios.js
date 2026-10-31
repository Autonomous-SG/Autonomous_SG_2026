import { referenceWorld } from './referenceWorld.js'

export const airports = {
  ATL: 'Atlanta', ORD: 'Chicago O’Hare', DFW: 'Dallas/Fort Worth',
  AVL: 'Asheville', DEN: 'Denver', BOS: 'Boston', MIA: 'Miami',
}

export const events = [
  { value: 'RUNWAY_CLOSURE', label: 'Runway closure' },
  { value: 'WEATHER_CAPACITY_DROP', label: 'Weather capacity drop' },
  { value: 'GATE_EQUIPMENT_FAILURE', label: 'Gate equipment failure' },
]

export const attacks = [
  { value: 'NONE', label: 'None · standard scenario' },
  { value: 'LYING_AGENT', label: 'Contradictory agent notes' },
  { value: 'PROMPT_INJECTION', label: 'Prompt injection' },
  { value: 'NO_FEASIBLE', label: 'No feasible plan' },
  { value: 'AGENT_TIMEOUT', label: 'Agent timeout' },
]

// Extra flights are invented UI examples, not records from flights.csv.
function demoWorld({ row_id, date, airline, flight_number, origin, destination, arrival }) {
  const world = structuredClone(referenceWorld)
  world.public.scenario_id = `demo-${Math.abs(row_id)}`
  world.public.flight = {
    row_id, date, airline, flight_number, tail_number: 'DEMO', origin, destination,
    scheduled_departure: arrival - 120, scheduled_arrival: arrival,
    actual_arrival: null, arrival_delay: null, departure_delay: null,
    weather_delay: 0, late_aircraft_delay: 0, distance: 500, taxi_in: null,
  }
  world.public.next_leg = null
  world.public.now = arrival - 11
  world.public.eta_earliest = arrival + 14
  world.public.planned_gate = 'B10'
  world.public.gates = ['B10', 'B12', 'B14']
  world.public.runways = [
    { name: 'RWY-1', open: true, reopen_estimate: null },
    { name: 'RWY-2', open: true, reopen_estimate: null },
  ]
  world.public.synthetic_fields = ['public', 'private']
  world.private.pilot = {
    notes: 'DEMO: Fuel at ETA 4200 kg, minimum landing fuel 3300 kg, holding burn 45 kg/min. No connecting passenger data supplied.',
    fuel_at_eta_kg: 4200, min_landing_fuel_kg: 3300, hold_burn_kg_per_min: 45, connections: [],
  }
  world.private.ground = {
    notes: 'DEMO: B10, B12 and B14 open. Team Demo on duty until 22:00, no overtime. Tug DEMO-1 available.',
    gate_busy_until: {},
    crew: [{ team: 'Team Demo', gates: ['B10', 'B12', 'B14'], shift_end: 1320, overtime_allowed: false }],
    equipment: [{ id: 'DEMO-1', kind: 'TUG', out_until: null }],
  }
  return world
}

export const mockScenarios = [
  { id: 'reference', provenance: 'reference', world: referenceWorld },
  { id: 'demo-atl', provenance: 'synthetic', world: demoWorld({ row_id: -1, date: '2015-01-12', airline: 'DL', flight_number: 1402, origin: 'BOS', destination: 'ATL', arrival: 930 }) },
  { id: 'demo-ord', provenance: 'synthetic', world: demoWorld({ row_id: -2, date: '2015-01-13', airline: 'UA', flight_number: 608, origin: 'DEN', destination: 'ORD', arrival: 780 }) },
  { id: 'demo-dfw', provenance: 'synthetic', world: demoWorld({ row_id: -3, date: '2015-01-12', airline: 'AA', flight_number: 1250, origin: 'MIA', destination: 'DFW', arrival: 1110 }) },
]

export function filterScenarios(airport, date) {
  return mockScenarios.filter(({ world: { public: { flight } } }) =>
    (!airport || flight.destination === airport) && (!date || flight.date === date))
}

export function buildPreviewWorld(entry, event, attack) {
  const world = structuredClone(entry.world)
  const state = world.public
  world.attack = attack
  state.scenario_id = `${entry.id}-${event}-${attack}-${world.seed}`
  if (event === 'RUNWAY_CLOSURE' && entry.provenance === 'reference') return world

  const runway = state.runways[0].name
  const start = state.now - 5
  const end = state.now + 55
  state.runways = state.runways.map(item => ({ ...item, open: true, reopen_estimate: null }))
  if (event === 'GATE_EQUIPMENT_FAILURE') {
    state.event = { type: event, description: `Equipment at planned gate ${state.planned_gate} is unavailable. A different gate or a later arrival may be needed.`, start, runway: null, gate: state.planned_gate, end_estimate: end }
    world.private.atc = { notes: 'DEMO: Both runways available. No runway reopening restriction.', runway_reopen_actual: null, reopen_uncertainty_min: 0 }
    world.private.ground.gate_busy_until[state.planned_gate] = end
    world.private.ground.notes = `DEMO: Planned gate ${state.planned_gate} unavailable until the end of the equipment outage. Other gate, crew and equipment constraints remain in force.`
  } else {
    state.runways[0].open = false
    state.runways[0].reopen_estimate = end
    state.event = { type: event, description: event === 'WEATHER_CAPACITY_DROP'
      ? 'Weather reduces arrival capacity. One runway is unavailable, leaving fewer arrival slots.'
      : `Runway ${runway} is unavailable. Coordinate an alternative runway, gate and turnaround.`,
    start, runway, gate: null, end_estimate: end }
    world.private.atc = { notes: `DEMO: ${runway} unavailable; estimated return in 55 minutes. Inspection may take another 12 minutes.`, runway_reopen_actual: end + 12, reopen_uncertainty_min: 12 }
  }
  return world
}
