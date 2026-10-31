import { useState } from 'react'
import Badge from './Badge'
import { formatMinute } from '../utils/time'
import { humanize } from '../utils/presentation'

export default function DecisionPanel({ result, source, locked, onDecision }) {
  const [note, setNote] = useState('')
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')
  const [approved, setApproved] = useState(null)
  const { decision } = result
  const plan = decision.option
  const noFeasible = decision.outcome === 'NO_FEASIBLE'
  const saved = status === 'saved'

  async function decide(approve) {
    if (locked || status === 'saving' || saved) return
    setStatus('saving')
    setError('')
    try {
      await onDecision({ scenario_id: result.scenario_id, approve, note })
      setApproved(approve)
      setStatus('saved')
    } catch (error) {
      setError(error.message)
      setStatus('idle')
    }
  }

  return <section className={`panel decision-panel decision-panel--${decision.outcome.toLowerCase()}`} aria-labelledby="decision-title">
    <div className="section-heading"><div><p className="eyebrow">03 / HUMAN REVIEW</p><h2 id="decision-title">Recommended decision</h2></div><Badge tone={noFeasible ? 'danger' : decision.outcome === 'FALLBACK' ? 'synthetic' : 'real'}>{humanize(decision.outcome)}</Badge></div>
    <h3>{noFeasible ? 'No feasible plan. Escalate.' : `Option ${plan.option_id} · ${plan.gate}`}</h3>
    <p className="decision-explanation">{decision.explanation}</p>
    {plan && <dl className="decision-plan"><div><dt>Landing</dt><dd>{formatMinute(plan.landing_time)}</dd></div><div><dt>Runway</dt><dd>{plan.runway}</dd></div><div><dt>Turnaround</dt><dd>{humanize(plan.turnaround)}</dd></div><div><dt>Next departure</dt><dd>{formatMinute(plan.next_leg_departure)}</dd></div><div><dt>Lowest party score</dt><dd>{decision.min_score == null ? '—' : `${decision.min_score}/10`}</dd></div><div><dt>Rounds used</dt><dd>{decision.rounds_used}</dd></div></dl>}
    <div className="party-messages">{Object.entries(decision.party_messages).map(([party, message]) => <div key={party}><strong>{party}</strong><p>{message}</p></div>)}</div>
    <p className="approval-context">{source === 'live' ? 'Your review is sent to the backend. Approval records a decision; it does not execute flight operations.' : 'Reviews of imported files are recorded only in this browser session.'}</p>
    <label className="review-note">Duty manager note<textarea rows={2} maxLength={2000} value={note} onChange={e => setNote(e.target.value)} disabled={saved || locked || status === 'saving'} placeholder="Optional reason or handover note" /></label>
    {error && <p className="error-message" role="alert">{error} Your review has not been saved.</p>}
    <div className="approval-buttons"><button className="approve-button" disabled={saved || locked || status === 'saving'} onClick={() => decide(true)}>{status === 'saving' ? 'Saving…' : noFeasible ? 'Acknowledge escalation' : 'Approve recommendation'}</button><button className="reject-button" disabled={saved || locked || status === 'saving'} onClick={() => decide(false)}>Reject</button></div>
    <p className="review-status" role="status">{saved ? `${approved ? noFeasible ? 'Escalation acknowledged' : 'Recommendation approved' : 'Recommendation rejected'} · ${source === 'live' ? 'Saved by backend' : 'Recorded locally'}` : 'Awaiting duty manager review'}</p>
  </section>
}
