// The 30 busiest destinations in flights.csv (plus AVL, DL912's next leg). Any other code can still be typed.
export const airports = {
  ATL: 'Atlanta', AVL: 'Asheville', BOS: 'Boston', BWI: 'Baltimore', CLT: 'Charlotte',
  DAL: 'Dallas Love Field', DCA: 'Washington National', DEN: 'Denver', DFW: 'Dallas/Fort Worth',
  DTW: 'Detroit', EWR: 'Newark', FLL: 'Ft. Lauderdale', HOU: 'Houston Hobby',
  IAH: 'Houston Intercontinental', JFK: 'New York JFK', LAS: 'Las Vegas', LAX: 'Los Angeles',
  LGA: 'New York LaGuardia', MCO: 'Orlando', MDW: 'Chicago Midway', MIA: 'Miami',
  MSP: 'Minneapolis', OAK: 'Oakland', ORD: 'Chicago O’Hare', PHL: 'Philadelphia',
  PHX: 'Phoenix', SAN: 'San Diego', SEA: 'Seattle', SFO: 'San Francisco',
  SLC: 'Salt Lake City', TPA: 'Tampa',
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
