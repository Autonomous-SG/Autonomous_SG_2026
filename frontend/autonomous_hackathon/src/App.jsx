import { useEffect, useRef, useState } from 'react'
import ScenarioPicker from './components/ScenarioPicker'
import ScenarioOverview from './components/ScenarioOverview'
import NegotiationTimeline from './components/NegotiationTimeline'
import DecisionPanel from './components/DecisionPanel'
import EvidencePanels from './components/EvidencePanels'
import { mockScenarios } from './mocks/scenarios'
import { buildDemoResult } from './mocks/negotiation'
import { negotiate, submitDecision, validateResult } from './services/api'
import { formatMinute } from './utils/time'
import './App.css'

function App() {
  const [mode, setMode] = useState('demo')
  const [active, setActive] = useState(() => ({
    result: buildDemoResult(mockScenarios[0], 'RUNWAY_CLOSURE', 'NONE'),
    source: 'demo', provenance: 'reference', id: 0,
  }))
  const [busy, setBusy] = useState(false)
  const [reviewBusy, setReviewBusy] = useState(false)
  const [error, setError] = useState('')
  const [announcement, setAnnouncement] = useState('')
  const controllerRef = useRef(null)
  const runId = useRef(0)
  useEffect(() => () => controllerRef.current?.abort(), [])

  const result = active?.result
  const flight = result?.world.public.flight
  const locked = busy || reviewBusy
  const displayDate = flight ? new Intl.DateTimeFormat('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC',
  }).format(new Date(`${flight.date}T00:00:00Z`)).toUpperCase() : 'SELECT A FLIGHT'

  async function runScenario(entry, request) {
    if (locked) return
    const controller = new AbortController()
    controllerRef.current = controller
    setBusy(true)
    setError('')
    setActive(null)
    setAnnouncement(mode === 'live' ? 'Negotiation running. Up to three rounds may take several minutes.' : 'Loading scripted demonstration…')
    try {
      const data = mode === 'demo'
        ? buildDemoResult(entry, request.event, request.attack, request.seed)
        : await negotiate(request, controller.signal)
      if (controller.signal.aborted) return
      setActive({ result: data, source: mode, provenance: mode === 'demo' ? entry.provenance : 'real', id: ++runId.current })
      setAnnouncement(`${mode === 'demo' ? 'Scripted demo loaded' : 'Negotiation complete'}: ${data.world.public.flight.airline}${data.world.public.flight.flight_number}. Review the recommendation below.`)
    } catch (error) {
      if (!controller.signal.aborted) { setError(error.message); setAnnouncement('Negotiation did not complete. You can retry the selected scenario.') }
    } finally {
      if (controllerRef.current === controller) { setBusy(false); controllerRef.current = null }
    }
  }

  function cancelRun() {
    controllerRef.current?.abort()
    setBusy(false)
    setAnnouncement('Stopped waiting for the result. A live backend run may continue; no result was applied.')
  }

  function changeMode(value) {
    if (locked || value === mode) return
    setMode(value)
    setActive(null)
    setError('')
    setAnnouncement(value === 'live' ? 'Live mode selected. Load a backend scenario to begin.' : 'Demo mode selected. Choose a flight and run the scripted example.')
  }

  async function importFixture(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file || locked) return
    const controller = new AbortController()
    controllerRef.current = controller
    setBusy(true)
    setAnnouncement('Importing saved result…')
    setError('')
    try {
      if (file.size > 10 * 1024 * 1024) throw new Error('Choose a result JSON file smaller than 10 MB.')
      const data = validateResult(JSON.parse(await file.text()))
      if (controller.signal.aborted) return
      setActive({ result: data, source: 'fixture', provenance: 'imported', id: ++runId.current })
      setAnnouncement('Saved result imported. Reviews of this file are recorded locally.')
    } catch (error) { if (!controller.signal.aborted) setError(`Cannot import this result: ${error.message}`) }
    finally { if (controllerRef.current === controller) { setBusy(false); controllerRef.current = null } }
  }

  async function recordDecision(body) {
    if (!active || locked) throw new Error('Wait for the current operation to finish.')
    setReviewBusy(true)
    try {
      if (active.source === 'live') await submitDecision(body)
      const entry = {
        seq: Math.max(0, ...result.log.map(item => item.seq)) + 1,
        wall_time: new Date().toISOString(), round: result.decision.rounds_used,
        actor: 'HUMAN', kind: 'HUMAN_DECISION',
        summary: `${body.approve ? result.decision.outcome === 'NO_FEASIBLE' ? 'Escalation acknowledged' : 'Recommendation approved' : 'Recommendation rejected'}${body.note ? `: ${body.note}` : ''}${active.source === 'live' ? '' : ' (local review)'}`,
        ref: body.scenario_id, rule_checks: [],
      }
      setActive(current => ({ ...current, result: { ...current.result, log: [...current.result.log, entry] } }))
    } finally { setReviewBusy(false) }
  }

  function exportResult() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `negotiation-${result.world.public.flight.row_id}.json`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return <>
    <title>Vector · Airport Operations Control</title>
    <header className="topbar"><a className="brand" href="#overview" aria-label="Vector control room home"><span className="brand-mark" aria-hidden="true">↗</span> VECTOR <span className="brand-divider" /><span className="brand-caption">OPERATIONS CONTROL</span></a><div className="header-status"><span className="status-dot" />{active?.source === 'fixture' ? 'Saved result' : mode === 'demo' ? 'Demo workspace' : 'Live workspace'}<span className="avatar">DM</span></div></header>
    <main id="overview">
      <div className="page-heading"><div><p className="eyebrow">AIRPORT DISRUPTION MANAGEMENT</p><h1>A clear path through disruption.</h1><p className="subtitle">One flight. Three perspectives. A decision you can trace.</p></div><div className="airport-clock"><span>{flight?.destination ?? 'AIRPORT'} · LOCAL SCENARIO TIME</span><strong>{result ? formatMinute(result.world.public.now) : '—'}</strong><span>{displayDate}</span></div></div>
      <div className="workspace-toolbar"><div className="mode-switch" aria-label="Data source"><button aria-pressed={mode === 'demo'} disabled={locked} onClick={() => changeMode('demo')}>Demo</button><button aria-pressed={mode === 'live'} disabled={locked} onClick={() => changeMode('live')}>Live backend</button></div><div className="result-actions"><label className={`file-import ${locked ? 'is-disabled' : ''}`}>Import saved result<input type="file" accept=".json,application/json" onChange={importFixture} disabled={locked} /></label><button className="text-button" onClick={exportResult} disabled={!result || locked}>Export JSON</button></div></div>
      <div className={`demo-banner ${active?.source === 'live' ? 'live-banner' : ''}`}><span className="demo-label">{active?.source === 'fixture' ? 'SAVED RESULT' : mode === 'demo' ? 'SCRIPTED DEMO' : 'LIVE BACKEND'}</span><p>{active?.source === 'fixture' ? 'Imported result file. Its contents are shown as provided; local reviews do not update the backend.' : mode === 'demo' ? 'Demonstration data, scripted votes and illustrative comparisons. No AI calls or operational actions are performed.' : 'Scenarios and recommendations come from the backend. Synthetic operational assumptions are labelled. Human review records a decision.'}</p></div>
      <ScenarioPicker key={mode} mode={mode} busy={locked} onRun={runScenario} />
      <p className="preview-announcement" role="status">{announcement}</p>
      {error && <div className="error-message app-error" role="alert">{error}</div>}
      {busy && <div className="panel loading-panel" role="status"><span className="loading-indicator" aria-hidden="true" /><div><h2>Loading scenario result</h2><p>Preparing the complete scenario record and decision.</p></div><button className="text-button" onClick={cancelRun}>Stop waiting</button></div>}
      {result && <div key={active.id}>
        <ScenarioOverview world={result.world} source={active.source} provenance={active.provenance} />
        <div className="negotiation-layout"><NegotiationTimeline result={result} /><DecisionPanel result={result} source={active.source} locked={locked} onDecision={recordDecision} /></div>
        <EvidencePanels result={result} source={active.source} />
      </div>}
      {!result && !busy && <section className="panel welcome-panel"><span className="eyebrow">READY WHEN YOU ARE</span><h2>Select a flight to begin.</h2><p>{mode === 'demo' ? 'Explore a complete scripted negotiation, including fallback and no-feasible scenarios.' : 'Choose an airport and date, then run a scenario from the connected backend.'}</p></section>}
      <footer className="page-footer"><span><span className="status-dot" /> Human approval required for every recommendation</span><span>{result ? `${active.source.toUpperCase()} · SEED ${result.world.seed}` : 'OPERATIONS CONTROL'}</span></footer>
    </main>
  </>
}

export default App
