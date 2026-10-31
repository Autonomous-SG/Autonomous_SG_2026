import { useState } from 'react'
import { referenceWorld } from './mocks/referenceWorld'
import { formatMinute } from './utils/time'
import './App.css'

function Badge({ children, tone = 'neutral' }) {
  return <span className={`badge badge--${tone}`}>{children}</span>
}

function App() {
  const [showNotes, setShowNotes] = useState(false)
  const { public: scenario, private: privateData } = referenceWorld
  const { flight, next_leg: nextLeg } = scenario

  return (
    <>
      <header className="topbar">
        <a className="brand" href="#overview" aria-label="Vector control room home"><span className="brand-mark" aria-hidden="true">↗</span> VECTOR <span className="brand-divider" /><span className="brand-caption">OPERATIONS CONTROL</span></a>
        <div className="header-status"><span className="status-dot" /> Demo workspace <span className="avatar">DM</span></div>
      </header>
      <main id="overview">
        <div className="page-heading">
          <div><p className="eyebrow">AIRPORT DISRUPTION MANAGEMENT</p><h1>A clear path through disruption.</h1><p className="subtitle">One flight. Three perspectives. A decision you can trace.</p></div>
          <div className="airport-clock"><span>ATL · LOCAL SCENARIO TIME</span><strong>{formatMinute(scenario.now)}</strong><span>12 JAN 2015</span></div>
        </div>
        <div className="demo-banner"><span className="demo-label">MOCK PREVIEW</span><p>Reference scenario from the project plan. Operational conditions are synthetic; no live negotiation is running.</p></div>
        <section className="panel scenario-picker" aria-labelledby="scenario-title">
          <div className="section-heading"><h2 id="scenario-title">Scenario setup</h2><span className="subtle">01 / SELECT</span></div>
          <div className="controls">
            <label>Airport<select defaultValue="ATL" disabled><option value="ATL">ATL · Atlanta</option></select></label>
            <label>Flight date<input type="date" value={flight.date} readOnly /></label>
            <label>Disruption<select defaultValue={scenario.event.type} disabled><option value="RUNWAY_CLOSURE">Runway closure</option></select></label>
            <label>Test condition<select defaultValue="NONE" disabled><option value="NONE">None · standard scenario</option></select></label>
            <button className="run-button" disabled>Run negotiation <span aria-hidden="true">↗</span></button>
          </div>
          <p className="field-hint">Scenario selection and running negotiations will be connected in the next stages.</p>
        </section>
        <div className="overview-grid">
          <section className="panel flight-panel" aria-labelledby="flight-title">
            <div className="section-heading"><div className="inline-heading"><h2 id="flight-title">Flight overview</h2><Badge tone="real">Real flight record</Badge></div><span className="subtle">CSV ROW {flight.row_id}</span></div>
            <div className="flight-identity"><strong>{flight.airline}{flight.flight_number}</strong><span>Delta Air Lines <span className="separator">/</span> {flight.tail_number}</span></div>
            <div className="route"><div><strong>{flight.origin}</strong><span>Chicago O’Hare</span></div><div className="route-line"><span aria-hidden="true">✈</span><small>INBOUND TO ATLANTA</small></div><div className="route-destination"><strong>{flight.destination}</strong><span>Hartsfield–Jackson</span></div></div>
            <div className="flight-stats"><div><span>Scheduled arrival</span><strong>{formatMinute(flight.scheduled_arrival)}</strong></div><div><span>Historical arrival</span><strong>{formatMinute(flight.actual_arrival)} <small>+{flight.arrival_delay}m</small></strong></div><div><span>Earliest landing <Badge tone="synthetic">Synthetic</Badge></span><strong>{formatMinute(scenario.eta_earliest)}</strong></div></div>
            <div className="next-leg"><span className="connection-icon" aria-hidden="true">↳</span><div><span className="eyebrow">SAME AIRCRAFT · NEXT LEG</span><p><strong>{nextLeg.airline}{nextLeg.flight_number}</strong> {nextLeg.origin} → {nextLeg.destination}</p></div><div className="next-leg-time"><strong>{formatMinute(nextLeg.scheduled_departure)}</strong><span>scheduled departure</span></div></div>
          </section>
          <section className="panel disruption-panel" aria-labelledby="disruption-title">
            <div className="section-heading"><h2 id="disruption-title">Active disruption</h2><Badge tone="synthetic">Synthetic</Badge></div>
            <div className="disruption-symbol" aria-hidden="true">!</div><h3>Runway {scenario.event.runway} closed</h3><p className="disruption-description">{scenario.event.description}</p>
            <dl className="event-details"><div><dt>Closure started</dt><dd>{formatMinute(scenario.event.start)}</dd></div><div><dt>Estimated reopening</dt><dd>{formatMinute(scenario.event.end_estimate)}</dd></div><div><dt>Planned arrival gate</dt><dd>{scenario.planned_gate}</dd></div></dl>
            <div className="disruption-footnote"><span className="status-dot status-dot--amber" /> Reopening estimate is public information</div>
          </section>
        </div>
        <section className="panel workflow-panel" aria-labelledby="workflow-title">
          <div className="section-heading"><div><p className="eyebrow">02 / COORDINATE</p><h2 id="workflow-title">Three teams. One shared plan.</h2></div><Badge>Awaiting negotiation</Badge></div>
          <div className="teams">{[{ name: 'ATC', label: 'Air traffic control', task: 'Runway availability & arrival spacing', icon: '⌁' }, { name: 'PILOT', label: 'Airline & pilot', task: 'Fuel reserves & onward connections', icon: '✈' }, { name: 'GROUND', label: 'Ground operations', task: 'Gates, turnaround & crew availability', icon: '▦' }].map(team => <div className="team" key={team.name}><span className={`team-icon team-icon--${team.name.toLowerCase()}`} aria-hidden="true">{team.icon}</span><div><h3>{team.label}</h3><p>{team.task}</p><span className="team-status">Private operational perspective</span></div></div>)}</div>
          <div className="workflow-bottom"><p>Proposed options, agent assessments and verified rule checks will appear here.</p><span>UP TO 3 ROUNDS <span aria-hidden="true">→</span> HUMAN REVIEW</span></div>
        </section>
        <section className="panel notes-panel" aria-labelledby="notes-title">
          <button className="notes-toggle" aria-expanded={showNotes} aria-controls="private-notes" onClick={() => setShowNotes(!showNotes)}><span><span className="eyebrow">SCENARIO CONTEXT</span><span id="notes-title" className="notes-title">Private operational notes <Badge tone="synthetic">Synthetic</Badge></span></span><span>{showNotes ? 'Hide notes −' : 'View notes +'}</span></button>
          <div id="private-notes" hidden={!showNotes}><div className="notes-grid">{Object.entries(privateData).map(([agent, data]) => <article key={agent}><h3>{agent.toUpperCase()}</h3><span className="subtle">Only this agent receives these notes</span><p>{data.notes}</p></article>)}</div></div>
        </section>
        <footer className="page-footer"><span><span className="status-dot" /> Human approval required for every recommendation</span><span>REFERENCE SCENARIO · SEED {referenceWorld.seed}</span></footer>
      </main>
    </>
  )
}

export default App
