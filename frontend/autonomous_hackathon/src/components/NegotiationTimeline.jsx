import { useState } from 'react'
import Badge from './Badge'
import { formatMinute } from '../utils/time'
import { humanize, vetoState } from '../utils/presentation'

export function RuleChecks({ checks = [] }) {
  if (!checks.length) return null
  return <ul className="rule-checks">{checks.map((check, index) => (
    <li key={`${check.rule_id}-${index}`}>
      <Badge tone={check.passed ? 'real' : 'danger'}>{check.passed ? '✓ Pass' : '✕ Fail'} · {humanize(check.rule_id)}</Badge>
      <span>{check.detail}</span>
      <small>{check.domain} · {check.hard ? 'Hard rule' : 'Soft rule'}{check.private ? ' · Private detail for human review' : ''}</small>
    </li>
  ))}</ul>
}

export default function NegotiationTimeline({ result }) {
  const [roundNumber, setRoundNumber] = useState(result.rounds[0]?.round)
  const record = result.rounds.find(item => item.round === roundNumber) ?? result.rounds[0]
  return <section className="panel timeline-panel" aria-labelledby="timeline-title">
    <div className="section-heading">
      <div><p className="eyebrow">02 / COORDINATE</p><h2 id="timeline-title">Negotiation timeline</h2></div>
      <Badge>{result.rounds.length} round{result.rounds.length === 1 ? '' : 's'}</Badge>
    </div>
    {!record ? <p className="empty-state">No rounds were recorded. Review the decision and audit log.</p> : <>
      <div className="round-tabs" aria-label="Negotiation rounds">{result.rounds.map(item => (
        <button type="button" key={item.round} aria-pressed={record.round === item.round} onClick={() => setRoundNumber(item.round)}>
          Round {item.round}<small>{item.options.length} options · {item.eliminated.length} eliminated</small>
        </button>
      ))}</div>
      <div className="table-scroll" tabIndex={0} aria-label={`Round ${record.round} proposed plans`}>
        <table><caption className="sr-only">Proposed plans for round {record.round}</caption><thead><tr><th>Option</th><th>Landing</th><th>Runway / gate</th><th>Turnaround</th><th>Hold</th><th>In gate</th><th>Next departure</th><th>Public cost</th><th>Status</th></tr></thead>
          <tbody>{record.options.map(option => <tr key={option.option_id} className={record.eliminated.includes(option.option_id) ? 'eliminated-row' : ''}>
            <th scope="row">{option.option_id}<small>{option.source === 'COUNTER' ? `Counter · ${option.proposed_by}` : 'Solver'}</small></th>
            <td>{formatMinute(option.landing_time)}</td><td>{option.runway} / {option.gate}</td><td>{humanize(option.turnaround)}</td>
            <td>{option.hold_min}m</td><td>{formatMinute(option.in_gate_time)}</td><td>{formatMinute(option.next_leg_departure)}</td>
            <td><details><summary>{option.public_cost.toFixed(1)}</summary><dl className="cost-breakdown">{Object.entries(option.cost_breakdown).map(([key, value]) => <div key={key}><dt>{humanize(key)}</dt><dd>{value.toFixed(1)}</dd></div>)}</dl></details></td>
            <td><Badge tone={record.eliminated.includes(option.option_id) ? 'danger' : 'neutral'}>{record.eliminated.includes(option.option_id) ? 'Eliminated' : 'In consideration'}</Badge></td>
          </tr>)}</tbody>
        </table>
      </div>
      <div className="agent-grid">{record.turns.map(turn => <article className="agent-card" key={turn.agent}>
        <div className="section-heading"><h3>{turn.agent}</h3><Badge tone={turn.status === 'OK' ? 'real' : 'danger'}>{humanize(turn.status)}</Badge></div>
        {turn.response ? <>
          <div className="assessments">{turn.response.assessments.map(assessment => <div className="assessment" key={assessment.option_id}>
            <div className="assessment-heading"><strong>Option {assessment.option_id}</strong><Badge tone={assessment.verdict === 'VETO' ? 'danger' : 'real'}>{assessment.verdict === 'VETO' ? 'Veto' : `Accept · ${assessment.score}/10`}</Badge></div>
            <p>{assessment.reason}</p>
            {assessment.veto_rule && <small>{humanize(assessment.veto_rule)} · {vetoState(record, assessment.option_id, assessment)}</small>}
            {!!assessment.cited_rules.length && <small>Cites: {assessment.cited_rules.map(humanize).join(', ')}</small>}
          </div>)}</div>
          {turn.response.counter_proposal && <div className="counter-card"><strong>Counterproposal {turn.counter_option_id ?? 'not admitted'}</strong><p>Based on {turn.response.counter_proposal.based_on} · {turn.response.counter_proposal.landing_time} · {turn.response.counter_proposal.runway} / {turn.response.counter_proposal.gate} · {humanize(turn.response.counter_proposal.turnaround)}</p><p>{turn.response.counter_proposal.reason}</p><RuleChecks checks={turn.counter_checks} /></div>}
        </> : <p className="empty-state">No valid response. {humanize(turn.status)} recorded; see the fallback decision.</p>}
        {!!turn.veto_checks.length && <details className="agent-checks"><summary>Checker evidence ({turn.veto_checks.length})</summary><RuleChecks checks={turn.veto_checks} /><p className="field-hint">Checks are recorded for this agent’s turn. The options table identifies eliminated plans.</p></details>}
        {!!turn.guardrail_flags.length && <ul className="guardrail-list">{turn.guardrail_flags.map((flag, index) => <li key={index}>{flag}</li>)}</ul>}
        <p className="turn-meta">{turn.latency_ms} ms · {turn.input_tokens + turn.output_tokens} tokens</p>
      </article>)}</div>
      <div className="shared-constraints"><h3>New shared constraints</h3>{record.new_shared_constraints.length ? <ul>{record.new_shared_constraints.map((constraint, index) => <li key={index}><p>{constraint.statement}</p><small>{constraint.from_agent} · {humanize(constraint.from_rule)}</small></li>)}</ul> : <p>No new constraints published this round.</p>}</div>
    </>}
  </section>
}
