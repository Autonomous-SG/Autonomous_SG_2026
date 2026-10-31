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
