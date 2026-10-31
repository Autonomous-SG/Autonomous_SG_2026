import { useEffect, useState } from 'react'
import { airports, attacks, events, filterScenarios } from '../mocks/scenarios'
import { listScenarios } from '../services/api'
import { formatMinute } from '../utils/time'

export default function ScenarioPicker({ mode, busy, onRun }) {
  const [airport, setAirport] = useState('')
  const [date, setDate] = useState('')
  const [selectedId, setSelectedId] = useState('reference')
  const [event, setEvent] = useState('RUNWAY_CLOSURE')
  const [attack, setAttack] = useState('NONE')
  const [seed, setSeed] = useState('42')
  const [retry, setRetry] = useState(0)
  const [remote, setRemote] = useState({ key: '', status: 'idle', rows: [], error: '' })
  const queryKey = JSON.stringify([airport, date, retry])

  useEffect(() => {
    if (mode !== 'live') return
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      setRemote({ key: queryKey, status: 'loading', rows: [], error: '' })
      try {
        const rows = await listScenarios({ airport, date, signal: controller.signal })
        if (!controller.signal.aborted) setRemote({ key: queryKey, status: 'ready', rows, error: '' })
      } catch (error) {
        if (!controller.signal.aborted) setRemote({ key: queryKey, status: 'error', rows: [], error: error.message })
      }
    }, 250)
    return () => { clearTimeout(timer); controller.abort() }
  }, [mode, airport, date, queryKey])

  const ready = mode === 'demo' || (remote.key === queryKey && remote.status === 'ready')
  const matches = mode === 'demo' ? filterScenarios(airport, date).map(entry => {
    const flight = entry.world.public.flight
    return { id: entry.id, row_id: flight.row_id, flight: `${flight.airline}${flight.flight_number}`, origin: flight.origin, destination: flight.destination, date: flight.date, scheduled_arrival: flight.scheduled_arrival, entry }
  }) : ready ? remote.rows.map(row => ({ ...row, id: String(row.row_id) })) : []
  const selected = matches.find(entry => entry.id === selectedId) ?? matches[0]

  function submit(e) {
    e.preventDefault()
    if (!selected || busy || !ready) return
    onRun(selected.entry ?? selected, { row_id: selected.row_id, event, attack, seed: Number(seed) })
  }

  return <section className="panel scenario-picker" aria-labelledby="scenario-title">
    <div className="section-heading"><h2 id="scenario-title">Scenario setup</h2><span className="subtle">01 / SELECT · {mode.toUpperCase()}</span></div>
    <form onSubmit={submit}>
      <fieldset disabled={busy}>
        <div className="controls">
          <label>Destination airport<input list="airport-options" placeholder="All airports" value={airport} maxLength={3} onChange={e => setAirport(e.target.value.toUpperCase().replace(/[^A-Z]/g, ''))} /><datalist id="airport-options">{['ATL', 'ORD', 'DFW'].map(code => <option key={code} value={code}>{airports[code]}</option>)}</datalist></label>
          <label>Flight date<input type="date" value={date} onChange={e => setDate(e.target.value)} /></label>
          <label>Disruption<select value={event} onChange={e => setEvent(e.target.value)}>{events.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          <label>Test condition<select value={attack} onChange={e => setAttack(e.target.value)}>{attacks.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        </div>
        <div className="flight-selection">
          <label>Flight<select value={selected?.id ?? ''} disabled={!matches.length} onChange={e => setSelectedId(e.target.value)}>
            {!matches.length && <option value="">{ready ? 'No matching flights' : 'Loading flights…'}</option>}
            {matches.map(row => <option key={row.id} value={row.id}>{row.flight} · {row.origin} → {row.destination} · {row.date} · {formatMinute(row.scheduled_arrival)}{mode === 'demo' ? row.entry.provenance === 'reference' ? ' · Plan reference' : ' · Invented demo' : ''}</option>)}
          </select></label>
          <label className="seed-input">Seed<input type="number" required step="1" min="0" max="2147483647" value={seed} onChange={e => setSeed(e.target.value)} /></label>
          <button className="run-button" type="submit" disabled={!selected || !ready || busy}>{busy ? 'Running…' : mode === 'demo' ? 'Run scripted demo' : 'Run negotiation'} <span aria-hidden="true">↗</span></button>
        </div>
        <div className="picker-footer"><p className="field-hint" role="status">{ready ? matches.length ? `${matches.length} matching flights${mode === 'live' ? ' (up to 50 per search)' : ''}. Run to load the selected scenario.` : 'No flights match. Change the filters or clear them.' : 'Fetching flights from the backend…'}</p><button type="button" className="text-button" onClick={() => { setAirport(''); setDate(''); setSelectedId('reference') }}>Clear filters</button></div>
        {mode === 'live' && remote.key === queryKey && remote.status === 'error' && <div className="error-message" role="alert"><p>{remote.error}</p><button type="button" className="text-button" onClick={() => setRetry(value => value + 1)}>Retry connection</button></div>}
        <p className="field-hint">{mode === 'demo' ? 'Scripted fixtures demonstrate the UI, including failure and attack states. They do not measure AI performance or safety.' : 'Flight data and negotiation results come from the backend. Each run may make paid model calls.'}</p>
      </fieldset>
    </form>
  </section>
}
