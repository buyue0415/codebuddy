/**
 * Paper Trading & Backtest API
 */
import { apiCall } from './client.js'

// ── Backtest ──

export async function runBacktest(params = {}) {
  return apiCall('POST', '/api/v2/backtest/run', {
    train_window: params.train_window || 252,
    test_window: params.test_window || 21,
    codes: params.codes || '',
  })
}

export async function fetchBacktestStatus() {
  return apiCall('GET', '/api/v2/backtest/status')
}

export async function stopBacktest() {
  return apiCall('POST', '/api/v2/backtest/stop')
}

export async function fetchBacktestResults(runId) {
  return apiCall('GET', `/api/v2/backtest/results/${runId}`)
}

export async function fetchBacktestHistory() {
  return apiCall('GET', '/api/v2/backtest/history')
}

// ── Paper Trading ──

export async function fetchPaperAccount() {
  return apiCall('GET', '/api/v2/paper/account')
}

export async function fetchPaperPositions() {
  return apiCall('GET', '/api/v2/paper/positions')
}

export async function fetchPaperSuggestions(code = '', date = '') {
  const params = new URLSearchParams()
  if (code) params.set('code', code)
  if (date) params.set('date', date)
  const qs = params.toString()
  return apiCall('GET', `/api/v2/paper/suggestions${qs ? '?' + qs : ''}`)
}

export async function fetchPaperTrades(code = '', limit = 50, offset = 0) {
  const params = new URLSearchParams()
  if (code) params.set('code', code)
  params.set('limit', limit)
  params.set('offset', offset)
  return apiCall('GET', `/api/v2/paper/trades?${params}`)
}

export async function fetchPaperPerformance(days = 90) {
  return apiCall('GET', `/api/v2/paper/performance?days=${days}`)
}

export async function resetPaperAccount(initialCapital = 100000) {
  return apiCall('POST', '/api/v2/paper/reset', { initial_capital: initialCapital })
}

export async function executePaperTrading() {
  return apiCall('POST', '/api/v2/paper/execute')
}

// ── Intraday Quotes ──

export async function fetchIntraday(code, date = '') {
  const params = date ? `?date=${date}` : ''
  return apiCall('GET', `/api/v2/paper/intraday/${code}${params}`)
}
