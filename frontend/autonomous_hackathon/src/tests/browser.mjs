// Optional UI integration check. Requires playwright and installed Microsoft Edge.
// API responses are intercepted; no model calls or operational reviews are sent.
import assert from 'node:assert/strict'
import { chromium } from 'playwright'
import { readFile } from 'node:fs/promises'
import { validateResult } from '../services/validateResult.js'

const fixture = validateResult(JSON.parse(await readFile(new URL('../../../../backend/fixtures/negotiation_example.json', import.meta.url), 'utf8')))
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
const errors = []
const requests = []
let failList = true
let failDecision = true
let delayNegotiation = false
page.on('pageerror', error => errors.push(error.message))
try {
  await page.route('**/api/**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    requests.push({ path, body: request.postDataJSON() })
    if (path === '/api/scenarios') return route.fulfill({ status: failList ? 503 : 200, contentType: 'application/json', body: JSON.stringify(failList ? { detail: 'Unavailable for test' } : [{ row_id: 20919, flight: 'DL912', origin: 'ORD', destination: 'ATL', date: '2015-01-12', scheduled_arrival: 1026 }]) })
    if (path === '/api/negotiate') {
      if (delayNegotiation) await new Promise(resolve => setTimeout(resolve, 800))
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify(fixture) })
    }
    if (path === '/api/decision') return route.fulfill({ status: failDecision ? 500 : 200, contentType: 'application/json', body: JSON.stringify(failDecision ? { detail: 'Save failed for test' } : { ok: true }) })
    return route.abort()
  })
  await page.goto(process.env.VECTOR_BASE_URL ?? 'http://localhost:5173')
  await page.getByText('API 503:', { exact: false }).waitFor()
  assert.equal(await page.getByRole('button', { name: 'Demo', exact: true }).count(), 0)
  assert.equal(await page.getByRole('button', { name: 'Live backend', exact: true }).count(), 0)
  assert.equal(await page.getByText('Loading flights…', { exact: true }).count(), 0)
  await page.getByText('Flights unavailable', { exact: true }).waitFor({ state: 'attached' })
  assert.equal(await page.getByRole('heading', { name: 'Recommended decision' }).count(), 0)
  failList = false
  await page.getByRole('button', { name: 'Retry connection' }).click()
  await page.waitForFunction(() => [...document.querySelectorAll('button')].some(button => button.textContent.includes('Run negotiation') && !button.disabled))
  await page.getByRole('button', { name: /Run negotiation/ }).click()
  await page.getByRole('heading', { name: 'Recommended decision' }).waitFor()
  await page.getByRole('heading', { name: 'Negotiation timeline' }).waitFor()
  await page.getByRole('button', { name: /Round/ }).first().click()
  await page.getByRole('button', { name: /View notes/ }).click()
  await page.getByText('Public airport context & data provenance', { exact: true }).click()
  await page.getByText(`Turnaround: ${fixture.world.public.aircraft.standard_turnaround_min}m standard`, { exact: false }).waitFor()
  await page.getByRole('button', { name: 'Reject', exact: true }).click()
  await page.getByText('Your review has not been saved.', { exact: false }).waitFor()
  assert.equal(await page.getByRole('button', { name: 'Reject', exact: true }).isEnabled(), true)
  failDecision = false
  await page.getByLabel('Duty manager note').fill('Test live rejection')
  await page.getByRole('button', { name: 'Reject', exact: true }).click()
  await page.getByText('Recommendation rejected · Saved by backend', { exact: true }).waitFor()
  assert.equal(requests.findLast(item => item.path === '/api/decision').body.approve, false)
  assert.equal(requests.find(item => item.path === '/api/negotiate').body.row_id, 20919)
  for (const width of [320, 390, 768]) {
    await page.setViewportSize({ width, height: 900 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `No page overflow at ${width}px`)
  }
  await page.setViewportSize({ width: 1440, height: 1100 })
  delayNegotiation = true
  await page.getByRole('button', { name: /Run negotiation/ }).click()
  await page.getByRole('button', { name: 'Stop waiting' }).click()
  await page.waitForTimeout(1000)
  assert.equal(await page.getByRole('heading', { name: 'Recommended decision' }).count(), 0)
  await page.locator('input[type=file]').setInputFiles({ name: 'example.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(fixture)) })
  await page.getByRole('heading', { name: 'Recommended decision' }).waitFor()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export JSON' }).click()
  assert.match((await download).suggestedFilename(), /negotiation-.*\.json/)
  assert.deepEqual(errors, [])
  console.log('Passed: backend-only startup, no demo tab/data, load failure/retry, actual backend fixture rendering, review failure/retry, responsive layout, cancellation, import/export.')
} finally { await browser.close() }
