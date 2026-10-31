import { useState } from 'react'
import Badge from './Badge'
import { airports, attacks, events } from '../mocks/scenarios'
import { formatMinute } from '../utils/time'
import { isSynthetic } from '../utils/presentation'

export default function ScenarioOverview({ world, source, provenance }) {
  const [showNotes, setShowNotes] = useState(false)
  const scenario = world.public
  const { flight, next_leg: nextLeg } = scenario
  const syntheticFlight = provenance === 'synthetic' || isSynthetic(world, 'flight')
  const disruptionTitle = scenario.event.type === 'RUNWAY_CLOSURE'
    ? `Runway ${scenario.event.runway} closed` : events.find(item => item.value === scenario.event.type)?.label
  return <>
    <div className="overview-grid">
      <section className="panel flight-panel" aria-labelledby="flight-title">
        <div className="section-heading"><div className="inline-heading"><h2 id="flight-title">Flight overview</h2><Badge tone={syntheticFlight ? 'synthetic' : 'real'}>{syntheticFlight ? 'Synthetic flight' : source === 'demo' ? 'Real flight · plan reference' : 'Real flight record'}</Badge></div><span className="subtle">{syntheticFlight ? 'INVENTED DEMO' : `CSV ROW ${flight.row_id}`}</span></div>
        <div className="flight-identity"><strong>{flight.airline}{flight.flight_number}</strong><span>{{ DL: 'Delta Air Lines', UA: 'United Airlines', AA: 'American Airlines' }[flight.airline] ?? flight.airline} <span className="separator">/</span> {flight.tail_number}</span></div>
        <div className="route"><div><strong>{flight.origin}</strong><span>{airports[flight.origin] ?? flight.origin}</span></div><div className="route-line"><span aria-hidden="true">✈</span><small>INBOUND TO {flight.destination}</small></div><div className="route-destination"><strong>{flight.destination}</strong><span>{airports[flight.destination] ?? flight.destination}</span></div></div>
        <div className="flight-stats">
          <div><span>Scheduled arrival</span><strong>{formatMinute(flight.scheduled_arrival)}</strong></div>
          <div><span>Historical arrival</span><strong>{formatMinute(flight.actual_arrival)} {flight.arrival_delay != null && <small>{flight.arrival_delay > 0 ? '+' : ''}{flight.arrival_delay}m</small>}</strong></div>
          <div><span>Earliest landing {isSynthetic(world, 'eta_earliest') && <Badge tone="synthetic">Synthetic</Badge>}</span><strong>{formatMinute(scenario.eta_earliest)}</strong></div>
        </div>
        {nextLeg ? <div className="next-leg"><span className="connection-icon" aria-hidden="true">↳</span><div><span className="eyebrow">SAME AIRCRAFT · NEXT LEG</span><p><strong>{nextLeg.airline}{nextLeg.flight_number}</strong> {nextLeg.origin} → {nextLeg.destination}</p></div><div className="next-leg-time"><strong>{formatMinute(nextLeg.scheduled_departure)}</strong><span>scheduled departure</span></div></div> : <div className="next-leg"><span className="connection-icon" aria-hidden="true">↳</span><p>No next leg supplied for this flight.</p></div>}
      </section>
      <section className="panel disruption-panel" aria-labelledby="disruption-title">
        <div className="section-heading"><h2 id="disruption-title">Active disruption</h2>{isSynthetic(world, 'event') && <Badge tone="synthetic">Synthetic</Badge>}</div>
        <div className="disruption-symbol" aria-hidden="true">!</div><h3>{disruptionTitle}</h3><p className="disruption-description">{scenario.event.description}</p>
        <dl className="event-details"><div><dt>Disruption started</dt><dd>{formatMinute(scenario.event.start)}</dd></div><div><dt>Estimated recovery</dt><dd>{formatMinute(scenario.event.end_estimate)}</dd></div><div><dt>Planned arrival gate</dt><dd>{scenario.planned_gate}</dd></div></dl>
        <div className="disruption-footnote"><span className="status-dot status-dot--amber" /> Recovery estimate is public information</div>
        <p className="test-condition">Test condition: {attacks.find(item => item.value === world.attack)?.label}</p>
      </section>
    </div>
    <section className="panel notes-panel" aria-labelledby="notes-title">
      <button className="notes-toggle" aria-expanded={showNotes} aria-controls="private-notes" onClick={() => setShowNotes(!showNotes)}><span><span className="eyebrow">SCENARIO CONTEXT</span><span id="notes-title" className="notes-title">Private operational notes <Badge tone="synthetic">Synthetic scenario data</Badge></span></span><span>{showNotes ? 'Hide notes −' : 'View notes +'}</span></button>
      <div id="private-notes" hidden={!showNotes}><div className="notes-grid">{Object.entries(world.private).map(([agent, data]) => <article key={agent}><h3>{agent.toUpperCase()}</h3><span className="subtle">Only this agent received these notes</span><p className="private-note-text">{data.notes}</p></article>)}</div></div>
      <details className="public-context"><summary>Public airport context & data provenance</summary><div className="public-context-grid"><div><h3>Runways</h3><ul>{scenario.runways.map(runway => <li key={runway.name}>{runway.name} · {runway.open ? 'Open' : `Unavailable · estimated return ${formatMinute(runway.reopen_estimate)}`}</li>)}</ul></div><div><h3>Arrival queue</h3>{scenario.arrival_queue.length ? <ul>{scenario.arrival_queue.map((item, index) => <li key={index}>{item.flight} · {formatMinute(item.landing_time)} · {item.runway} · {item.wake} · {item.real ? 'Real flight; timing may be synthetic' : 'Synthetic flight'}</li>)}</ul> : <p>No queued arrivals supplied.</p>}</div><div><h3>Generated fields</h3><p>{scenario.synthetic_fields.join(', ') || 'None declared'}</p><p>Aircraft: {scenario.aircraft.type} · {scenario.aircraft.wake} wake. Turnaround: {scenario.aircraft.min_turnaround_min}m standard / {scenario.aircraft.expedited_turnaround_min}m expedited.</p></div></div></details>
    </section>
  </>
}
