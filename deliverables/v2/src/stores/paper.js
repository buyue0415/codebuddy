/**
 * Paper Trading Pinia Store
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  fetchPaperAccount, fetchPaperPositions, fetchPaperSuggestions,
  fetchPaperTrades, fetchPaperPerformance, resetPaperAccount,
  runBacktest, fetchBacktestStatus, stopBacktest as apiStopBacktest,
  fetchBacktestResults, fetchBacktestHistory,
  fetchIntraday,
} from '@/api/paper.js'

export const usePaperStore = defineStore('paper', () => {
  const loading = ref(false)
  const error = ref(null)

  // Account
  const account = ref(null)  // {initialized, cash, total_asset, ...}
  const positions = ref([])  // [{code, qty, avg_cost, market_value, ...}]
  const suggestions = ref([]) // [{code, action, qty, price, confidence, ...}]
  const trades = ref([])     // [{date, code, direction, qty, price, ...}]
  const tradesTotal = ref(0)
  const performance = ref(null) // {sharpe_ratio, max_drawdown, equity_curve, ...}
  const equityCurve = ref([])

  // Intraday
  const intradayData = ref([])       // [{timestamp, price, change_pct, volume}, ...]
  const intradayCode = ref('')       // currently viewing stock code
  const selectedDate = ref('')       // selected date YYYY-MM-DD
  const availableDates = ref([])     // dates with intraday data
  const marketStatus = ref('open')   // 'open' | 'closed' | 'non_trading_day'

  // Backtest
  const backtestStatus = ref('idle') // idle | running | done | error | cancelled
  const backtestRunId = ref(null)
  const backtestProgress = ref(null)
  const backtestResults = ref(null)
  const backtestHistory = ref([])

  const isInitialized = computed(() => account.value?.initialized === true)

  async function loadAccount() {
    const r = await fetchPaperAccount()
    if (r?.success) account.value = r.data
  }

  async function loadPositions() {
    const r = await fetchPaperPositions()
    if (r?.success) positions.value = r.data || []
  }

  async function loadSuggestions(code = '', date = '') {
    const r = await fetchPaperSuggestions(code, date)
    if (r?.success) {
      suggestions.value = r.data || []
      // Capture market_status from response
      if (r.market_status) {
        marketStatus.value = r.market_status
      }
    }
  }

  async function loadIntraday(code, date = '') {
    intradayCode.value = code
    selectedDate.value = date || new Date().toISOString().slice(0, 10)
    const r = await fetchIntraday(code, date)
    if (r?.success && r.data) {
      intradayData.value = r.data.data || []
      availableDates.value = r.data.available_dates || []
    }
  }

  async function loadTrades(code = '', limit = 50, offset = 0) {
    const r = await fetchPaperTrades(code, limit, offset)
    if (r?.success) {
      trades.value = r.data || []
      tradesTotal.value = r.total || 0
    }
  }

  async function loadPerformance(days = 90) {
    const r = await fetchPaperPerformance(days)
    if (r?.success) {
      // Only set performance if we got actual data (not just a message)
      if (r.data && r.data.equity_curve) {
        performance.value = r.data
        equityCurve.value = r.data.equity_curve || []
      } else {
        performance.value = null
        equityCurve.value = []
      }
    }
  }

  async function resetAccount(capital = 100000) {
    const r = await resetPaperAccount(capital)
    if (r?.success) {
      account.value = {
        initialized: true,
        cash: r.data.cash,
        initial_capital: r.data.initial_capital,
        total_asset: r.data.total_asset,
        position_value: r.data.position_value,
        cumulative_return_pct: 0,
      }
      positions.value = []
      suggestions.value = []
    }
    return r
  }

  // ── Backtest ──

  async function startBacktest(params = {}) {
    backtestStatus.value = 'running'
    backtestResults.value = null
    backtestProgress.value = null
    const r = await runBacktest(params)
    if (r?.success) {
      backtestRunId.value = r.data.run_id
      return r.data.run_id
    }
    backtestStatus.value = 'idle'
    return null
  }

  async function stopBacktest() {
    const r = await apiStopBacktest()
    if (r?.success) {
      backtestStatus.value = 'cancelled'
    }
    return r
  }

  async function pollBacktestStatus() {
    const r = await fetchBacktestStatus()
    if (r?.success) {
      backtestStatus.value = r.data.status
      backtestProgress.value = r.data.progress
      if (r.data.run_id) backtestRunId.value = r.data.run_id
    }
    return r
  }

  async function loadBacktestResults(runId) {
    const r = await fetchBacktestResults(runId)
    if (r?.success) backtestResults.value = r.data
    return r
  }

  async function loadBacktestHistory() {
    const r = await fetchBacktestHistory()
    if (r?.success) backtestHistory.value = r.data || []
    return r
  }

  return {
    loading, error, account, positions, suggestions, trades, tradesTotal,
    performance, equityCurve, isInitialized,
    intradayData, intradayCode, selectedDate, availableDates, marketStatus,
    backtestStatus, backtestRunId, backtestProgress, backtestResults, backtestHistory,
    loadAccount, loadPositions, loadSuggestions, loadTrades, loadPerformance,
    resetAccount, loadIntraday,
    startBacktest, pollBacktestStatus, stopBacktest, loadBacktestResults, loadBacktestHistory,
  }
})
