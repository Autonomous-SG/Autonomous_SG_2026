import { useEffect, useState } from 'react'
import { attacks, events } from '../utils/scenarioOptions'
import AirportPicker from './AirportPicker'
import { listScenarios } from '../services/api'
import { formatMinute } from '../utils/time'

export default function ScenarioPicker({ busy, onRun }) {
  const [source, setSource] = useState('')
  const [airport, setAirport] = useState('')
  const [date, setDate] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [event, setEvent] = useState('RUNWAY_CLOSURE')
  const [attack, setAttack] = useState('NONE')
  const [retry, setRetry] = useState(0)
  const [remote, setRemote] = useState({ key: '', status: 'idle', rows: [], error: '' })
  const queryKey = JSON.stringify([airport, date, retry])

  useEffect(() => {
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
  }, [airport, date, queryKey])

  const ready = remote.key === queryKey && remote.status === 'ready'
  const failed = remote.key === queryKey && remote.status === 'error'
  const matches = ready ? remote.rows
    .filter(row => !source || row.origin === source)
    .map(row => ({ ...row, id: String(row.row_id) })) : []
  const selected = matches.find(entry => entry.id === selectedId) ?? matches[0]

  function submit(e) {
    e.preventDefault()
    if (!selected || busy || !ready) return
    onRun({ row_id: selected.row_id, event, attack, seed: 42 })
  }

  return <section className="panel scenario-picker" aria-labelledby="scenario-title">
    <div className="section-heading"><h2 id="scenario-title">Scenario setup</h2><span className="subtle">01 / SELECT</span></div>
    <form onSubmit={submit}>
      <fieldset disabled={busy}>
        <div className="controls">
          <AirportPicker label="Source airport" value={source} onChange={setSource} />
          <AirportPicker label="Destination airport" value={airport} onChange={setAirport} />
          <label>Flight date<input type="date" value={date} onChange={e => setDate(e.target.value)} /></label>
          <label>Disruption<select value={event} onChange={e => setEvent(e.target.value)}>{events.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          <label>Test condition<select value={attack} onChange={e => setAttack(e.target.value)}>{attacks.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        </div>
        <div className="flight-selection">
          <label>Flight<select value={selected?.id ?? ''} disabled={!matches.length} onChange={e => setSelectedId(e.target.value)}>
            {!matches.length && <option value="">{failed ? 'Flights unavailable' : ready ? 'No matching flights' : 'Loading flights…'}</option>}
            {matches.map(row => <option key={row.id} value={row.id}>{row.flight} · {row.origin} → {row.destination} · {row.date} · {formatMinute(row.scheduled_arrival)}</option>)}
          </select></label>
          <button className="run-button" type="submit" disabled={!selected || !ready || busy}>{busy ? 'Running…' : 'Run negotiation'} <span aria-hidden="true">↗</span></button>
        </div>
        <div className="picker-footer"><p className="field-hint" role="status">{failed ? 'Unable to load flights. Check the connection and retry.' : ready ? matches.length ? `${matches.length} matching flights${source ? ` from ${source} among ${remote.rows.length} loaded flights` : ' (up to 50 per search)'}. Run to load the selected scenario.` : source && remote.rows.length ? `No flights from ${source} in the loaded results. Refine destination/date or clear the source filter.` : 'No flights match. Change the filters or clear them.' : 'Fetching flights from the backend. The first load can take up to two minutes…'}</p><button type="button" className="text-button" onClick={() => { setSource(''); setAirport(''); setDate(''); setSelectedId('') }}>Clear filters</button></div>
        {ready && source && remote.rows.length === 50 && <p className="field-hint">Source filters the first 50 flights returned for your destination/date. Narrow those filters to find additional flights.</p>}
        {failed && <div className="error-message" role="alert"><p>{remote.error}</p><button type="button" className="text-button" onClick={() => setRetry(value => value + 1)}>Retry connection</button></div>}
        <p className="field-hint">Flight data and negotiation results come from the backend. Each run may make paid model calls.</p>
      </fieldset>
    </form>
  </section>
}
