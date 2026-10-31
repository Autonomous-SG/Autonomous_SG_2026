import { validateResult } from './validateResult.js'
export { validateResult } from './validateResult.js'

// The first scenario request may load and index the full flight CSV.
async function request(path, { signal, timeout = 120000, ...options } = {}) {
  const controller = new AbortController()
  const abort = () => controller.abort()
  signal?.addEventListener('abort', abort, { once: true })
  if (signal?.aborted) controller.abort()
  const timer = setTimeout(abort, timeout)
  try {
    const response = await fetch(`/api${path}`, {
      ...options, signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...options.headers },
    })
    const data = await response.json().catch(() => null)
    if (!response.ok) {
      const detail = typeof data?.detail === 'string' ? data.detail : response.statusText
      throw new Error(`API ${response.status}: ${detail || 'Request failed'}. Check that the negotiation backend is running.`)
    }
    if (data == null) throw new Error('The API returned an empty or invalid JSON response.')
    return data
  } catch (error) {
    if (error.name === 'AbortError') {
      if (signal?.aborted) throw error
      throw new Error('The API request timed out. Try again or check the backend.', { cause: error })
    }
    if (error instanceof TypeError) throw new Error('Cannot reach the backend. Check that it is running on port 8000, then retry.', { cause: error })
    throw error
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', abort)
  }
}

export async function listScenarios({ airport, date, signal }) {
  const query = new URLSearchParams({ limit: '50' })
  if (airport) query.set('airport', airport)
  if (date) query.set('date', date)
  const data = await request(`/scenarios?${query}`, { signal })
  if (!Array.isArray(data) || data.some(item => !Number.isInteger(item.row_id) || typeof item.flight !== 'string')) {
    throw new Error('Scenario response does not match the agreed API format.')
  }
  return data
}

export async function negotiate(body, signal) {
  return validateResult(await request('/negotiate', {
    method: 'POST', body: JSON.stringify(body), signal, timeout: 330000,
  }))
}

export async function submitDecision(body, signal) {
  const data = await request('/decision', { method: 'POST', body: JSON.stringify(body), signal })
  if (data.ok !== true) throw new Error('The backend did not confirm that the decision was saved.')
  return data
}
