import assert from 'node:assert/strict'
import { test, afterEach } from 'node:test'
import { mockScenarios, events, attacks, filterScenarios } from '../mocks/scenarios.js'
import { buildDemoResult } from '../mocks/negotiation.js'
import { listScenarios, negotiate, submitDecision, validateResult } from '../services/api.js'
import { formatMinute } from '../utils/time.js'
import { isSynthetic } from '../utils/presentation.js'

const originalFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = originalFetch })

test('complete demos cover all scenario/event/attack combinations without mutating source data', () => {
  const original = JSON.stringify(mockScenarios)
  for (const entry of mockScenarios) for (const event of events) for (const attack of attacks) {
    const result = validateResult(buildDemoResult(entry, event.value, attack.value, 7))
    assert.equal(result.world.seed, 7)
    assert.equal(result.metrics.llm_calls, 0)
    assert.equal(result.decision.requires_human, true)
    assert.equal(result.decision.outcome, attack.value === 'NO_FEASIBLE' ? 'NO_FEASIBLE' : attack.value === 'AGENT_TIMEOUT' ? 'FALLBACK' : 'CONSENSUS')
    assert.equal(result.decision.option === null, attack.value === 'NO_FEASIBLE')
  }
  assert.equal(JSON.stringify(mockScenarios), original)
})

test('reference result preserves the shared worked example and source labels', () => {
  const result = buildDemoResult(mockScenarios[0], 'RUNWAY_CLOSURE', 'NONE')
  assert.equal(result.decision.option.gate, 'A21')
  assert.equal(result.decision.option.next_leg_departure, 1083)
  assert.equal(result.comparison.find(item => item.label === 'HISTORICAL').next_leg_delay_min, 85)
  assert.equal(isSynthetic(result.world, 'eta_earliest'), true)
  assert.equal(isSynthetic(result.world, 'flight'), false)
  assert.equal(isSynthetic(buildDemoResult(mockScenarios[1], 'RUNWAY_CLOSURE', 'NONE').world, 'flight'), true)
})

test('filters, unavailable historical values and midnight times remain distinct', () => {
  assert.equal(filterScenarios('ATL', '2015-01-12').length, 2)
  assert.equal(filterScenarios('ORD', '2015-01-12').length, 0)
  assert.equal(formatMinute(null), '—')
  assert.equal(formatMinute(0), '00:00')
  assert.equal(formatMinute(1464), '00:24 (+1d)')
})

test('a rejected veto does not eliminate its option; later confirmed evidence can', () => {
  const result = buildDemoResult(mockScenarios[0], 'RUNWAY_CLOSURE', 'LYING_AGENT')
  assert.equal(result.rounds[0].eliminated.includes('A'), false)
  assert.equal(result.rounds[1].eliminated.includes('A'), true)
  assert.equal(result.metrics.vetoes_rejected, 1)
})

test('malformed imported or API results are rejected before rendering', () => {
  const valid = buildDemoResult(mockScenarios[0], 'RUNWAY_CLOSURE', 'NONE')
  for (const mutate of [
    result => { result.decision.option = null },
    result => { result.metrics.wall_ms = 'unknown' },
    result => { result.rounds[0].turns[0].response.assessments = null },
    result => { result.world.public.flight.date = 'not a date' },
    result => { result.log[0].rule_checks = {} },
  ]) {
    const data = structuredClone(valid)
    mutate(data)
    assert.throws(() => validateResult(data), /Invalid negotiation result/)
  }
})

test('API serializes scenario filters and negotiation/review bodies as agreed', async () => {
  const calls = []
  const fixture = buildDemoResult(mockScenarios[0], 'RUNWAY_CLOSURE', 'NONE')
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options })
    const payload = url.startsWith('/api/scenarios') ? [{ row_id: 20919, flight: 'DL912' }] : url === '/api/decision' ? { ok: true } : fixture
    return new Response(JSON.stringify(payload), { status: 200 })
  }
  await listScenarios({ airport: 'ATL', date: '2015-01-12' })
  const body = { row_id: 20919, event: 'RUNWAY_CLOSURE', attack: 'NONE', seed: 42 }
  await negotiate(body)
  const review = { scenario_id: fixture.scenario_id, approve: false, note: 'Needs review' }
  await submitDecision(review)
  assert.equal(new URL(calls[0].url, 'http://localhost').searchParams.get('airport'), 'ATL')
  assert.deepEqual(JSON.parse(calls[1].options.body), body)
  assert.deepEqual(JSON.parse(calls[2].options.body), review)
})

test('API failures and unconfirmed review saves are not presented as success', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Not Found' }), { status: 404 })
  await assert.rejects(listScenarios({}), /API 404/)
  globalThis.fetch = async () => new Response(JSON.stringify({ ok: false }), { status: 200 })
  await assert.rejects(submitDecision({}), /did not confirm/)
  globalThis.fetch = async () => { throw new TypeError('Connection refused') }
  await assert.rejects(negotiate({}), /Cannot reach the backend/)
})

test('scenario loading survives 15 seconds and times out only after two minutes', async context => {
  context.mock.timers.enable({ apis: ['setTimeout'] })
  let signal
  let complete
  globalThis.fetch = async (_url, options) => {
    signal = options.signal
    return new Promise((resolve, reject) => {
      complete = resolve
      signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    })
  }
  const loading = listScenarios({})
  context.mock.timers.tick(15001)
  assert.equal(signal.aborted, false)
  complete(new Response(JSON.stringify([{ row_id: 20919, flight: 'DL912' }]), { status: 200 }))
  await loading
  const stalled = listScenarios({})
  context.mock.timers.tick(119999)
  assert.equal(signal.aborted, false)
  context.mock.timers.tick(1)
  await assert.rejects(stalled, /timed out/)
})

test('negotiations retain their longer timeout and support explicit cancellation', async context => {
  context.mock.timers.enable({ apis: ['setTimeout'] })
  let signal
  globalThis.fetch = async (_url, options) => {
    signal = options.signal
    return new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))))
  }
  const controller = new AbortController()
  const running = negotiate({}, controller.signal)
  context.mock.timers.tick(120001)
  assert.equal(signal.aborted, false)
  controller.abort()
  await assert.rejects(running, { name: 'AbortError' })
})
