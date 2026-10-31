// Hand-authored World fixture from PLAN.md §8; not loaded from the CSV or API.
// Values not specified by the plan are illustrative and listed as synthetic.
export const referenceWorld = {
  public: {
    scenario_id: 'reference-20919-42', now: 1015,
    flight: {
      row_id: 20919, date: '2015-01-12', airline: 'DL', flight_number: 912,
      tail_number: 'N927DA', origin: 'ORD', destination: 'ATL',
      scheduled_departure: 840, scheduled_arrival: 1026, actual_arrival: 1114,
      arrival_delay: 88, departure_delay: null, weather_delay: 76,
      late_aircraft_delay: 0, distance: 606, taxi_in: null,
    },
    next_leg: {
      row_id: 21156, date: '2015-01-12', airline: 'DL', flight_number: 2289,
      tail_number: 'N927DA', origin: 'ATL', destination: 'AVL',
      scheduled_departure: 1074, scheduled_arrival: 1130, actual_arrival: null,
      arrival_delay: null, departure_delay: 85, weather_delay: 0,
      late_aircraft_delay: 0, distance: 164, taxi_in: null,
    },
    aircraft: { type: 'Reference aircraft', wake: 'MEDIUM', min_turnaround_min: 40, expedited_turnaround_min: 30 },
    event: { type: 'RUNWAY_CLOSURE', description: 'Arrivals must be reassigned while runway 27L is unavailable. Coordinate a revised landing, gate and turnaround.', start: 1010, runway: '27L', gate: null, end_estimate: 1070 },
    runways: [{ name: '27L', open: false, reopen_estimate: 1070 }, { name: '26R', open: true, reopen_estimate: null }],
    arrival_queue: [], eta_earliest: 1040, taxi_in_min: 9,
    planned_gate: 'A17', gates: ['A15', 'A17', 'A19', 'A21'],
    synthetic_fields: ['now', 'aircraft', 'event', 'runways', 'arrival_queue', 'eta_earliest', 'taxi_in_min', 'planned_gate', 'gates', 'private', 'flight.scheduled_departure', 'flight.late_aircraft_delay', 'flight.distance', 'next_leg.scheduled_arrival', 'next_leg.weather_delay', 'next_leg.late_aircraft_delay', 'next_leg.distance'],
  },
  private: {
    atc: { notes: '27L estimated reopening 1750L. Inspection completion expected 1802L; allow 12 minutes of uncertainty.', runway_reopen_actual: 1082, reopen_uncertainty_min: 12 },
    pilot: { notes: 'FOB at ETA 4200KG. MIN LDG FUEL 3300KG (ALTN BHM + 30MIN). HOLD BURN ~45KG/MIN. 9 PAX CNX DL72 AMS 1845L LAST TODAY, INTL MCT 60.', fuel_at_eta_kg: 4200, min_landing_fuel_kg: 3300, hold_burn_kg_per_min: 45, connections: [{ flight: 'DL72', destination: 'AMS', departure: 1125, pax: 9, min_connect_min: 60, last_of_day: true }] },
    ground: { notes: 'A17 occupied delayed outbound, push ~1755. A15 busy till ~1740. A19 jetbridge fault till 1830. A21 open. Team 3 (A15–A19) off 1800 no OT. Team 4 (A21–A23) till 2200. Tug A-1 OOS till 1830, A-2 avail.', gate_busy_until: { A17: 1075, A15: 1060, A19: 1110 }, crew: [{ team: 'Team 3', gates: ['A15', 'A17', 'A19'], shift_end: 1080, overtime_allowed: false }, { team: 'Team 4', gates: ['A21', 'A23'], shift_end: 1320, overtime_allowed: false }], equipment: [{ id: 'A-1', kind: 'TUG', out_until: 1110 }, { id: 'A-2', kind: 'TUG', out_until: null }] },
  },
  seed: 42, attack: 'NONE',
}
