import { useState } from 'react'
import Badge from './Badge'
import { RuleChecks } from './NegotiationTimeline'
import { humanize, minutes } from '../utils/presentation'

export default function EvidencePanels({ result, source }) {
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState('')
  const { metrics } = result
  const entries = result.log.filter(entry => (!kind || entry.kind === kind)
    && `${entry.actor} ${entry.summary} ${entry.ref ?? ''} ${entry.rule_checks.map(check => check.detail).join(' ')}`.toLowerCase().includes(query.toLowerCase()))
  const cards = [
    ['Rounds', metrics.rounds_used], ['LLM calls', metrics.llm_calls],
    ['Confirmed vetoes', metrics.vetoes_confirmed], ['Rejected vetoes', metrics.vetoes_rejected],
    ['Counters passed', `${metrics.counters_passed} / ${metrics.counters_proposed}`],
    ['Invalid outputs', metrics.invalid_outputs],
    ['Input / output tokens', `${metrics.input_tokens.toLocaleString()} / ${metrics.output_tokens.toLocaleString()}`],
    ['Runtime', `${(metrics.wall_ms / 1000).toFixed(1)}s`],
    ['Estimated API cost', `$${metrics.est_cost_usd.toFixed(4)}`],
  ]
  return <>
    <section className="panel evidence-panel" aria-labelledby="comparison-title">
      <div className="section-heading"><div><p className="eyebrow">04 / COMPARE</p><h2 id="comparison-title">What changed with negotiation?</h2></div><Badge tone={source === 'demo' ? 'synthetic' : 'neutral'}>{source === 'demo' ? 'Illustrative values' : source === 'fixture' ? 'Imported evaluation' : 'Backend evaluation'}</Badge></div>
      <p className="panel-description">Historical delays are observations. Generated plans and passenger impacts are estimates under the scenario assumptions.</p>
      <div className="table-scroll" tabIndex={0} aria-label="Plan comparison"><table><caption className="sr-only">Solver-only, negotiated, oracle and historical plans</caption><thead><tr><th>Plan</th><th>Feasible in reality</th><th>Arrival delay</th><th>Next-leg delay</th><th>Connections missed</th><th>Context</th></tr></thead><tbody>{result.comparison.map(row => <tr key={row.label} className={row.label === 'NEGOTIATED' ? 'highlight-row' : ''}><th scope="row">{humanize(row.label)}</th><td><Badge tone={row.feasible_in_reality == null ? 'neutral' : row.feasible_in_reality ? 'real' : 'danger'}>{row.feasible_in_reality == null ? 'Not evaluated' : row.feasible_in_reality ? 'Yes' : 'No'}</Badge>{!!row.failed_rules.length && <small>{row.failed_rules.map(humanize).join(', ')}</small>}</td><td>{minutes(row.arrival_delay_min)}</td><td>{minutes(row.next_leg_delay_min)}</td><td>{row.connection_pax_missed ?? '—'}</td><td className="comparison-note">{row.note}</td></tr>)}</tbody></table></div>
    </section>
    <section className="panel evidence-panel" aria-labelledby="metrics-title"><div className="section-heading"><h2 id="metrics-title">Run metrics</h2><span className="subtle">{result.model}</span></div>{source === 'demo' && <p className="panel-description">Scripted demonstration: no AI calls, latency measurements or API charges. Counts describe the fixture.</p>}<dl className="metrics-grid">{cards.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></section>
    <section className="panel evidence-panel" aria-labelledby="log-title"><div className="section-heading"><div><p className="eyebrow">05 / TRACE</p><h2 id="log-title">Audit trail</h2></div><Badge>{result.log.length} entries</Badge></div>
      <div className="log-controls"><label>Search log<input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Agent, option, rule or message" /></label><label>Entry type<select value={kind} onChange={e => setKind(e.target.value)}><option value="">All entries</option>{[...new Set(result.log.map(entry => entry.kind))].map(value => <option key={value} value={value}>{humanize(value)}</option>)}</select></label></div>
      <p className="field-hint" role="status">{entries.length} matching entries</p>
      <ol className="audit-log">{entries.map(entry => <li key={entry.seq}><span className="log-seq">{String(entry.seq).padStart(2, '0')}</span><div><div className="log-meta"><strong>{entry.actor}</strong><Badge>{humanize(entry.kind)}</Badge><span>Round {entry.round} · {entry.wall_time}</span></div><p>{entry.summary}</p>{entry.ref && <small>Reference: {entry.ref}</small>}<RuleChecks checks={entry.rule_checks} /></div></li>)}</ol>
      {!entries.length && <p className="empty-state">No log entries match your search.</p>}
      <details className="raw-result"><summary>View full result JSON</summary><pre>{JSON.stringify(result, null, 2)}</pre></details>
    </section>
  </>
}
