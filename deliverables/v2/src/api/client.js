/**
 * API Client — 与旧版 core.js apiCall 完全一致的接口封装
 * 通过 Vite proxy 调用 http://127.0.0.1:8765 的后端 API
 */

const API_BASE = ''  // Vite proxy handles /api → :8765

export async function apiCall(method, path, body) {
  try {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
    }
    if (body) opts.body = JSON.stringify(body)
    const r = await fetch(API_BASE + path, opts)
    return await r.json()
  } catch (e) {
    console.error('API error:', e)
    return { success: false, error: e.message }
  }
}

// Cache
let _cache = {}

export function clearCache() { _cache = {} }

export async function loadData(key, endpoint) {
  if (_cache[key]) return _cache[key]
  try {
    const r = await apiCall('GET', endpoint)
    if (r && r.success) {
      _cache[key] = r.data
      return r.data
    }
    console.warn('loadData[' + key + '] failed:', r)
    return null
  } catch (e) {
    console.warn('loadData[' + key + '] error:', e)
    return null
  }
}

/**
 * Load all data in parallel (15 APIs) — same as old init()
 * Returns the full DATA object
 */
export async function loadAllData() {
  const [cfg, wl, quotes, kd, km, pc, pcl, trades, divs, preds, sea, news, expert, accStats, learn] =
    await Promise.all([
      loadData('config', '/api/v2/config'),
      loadData('watchlist', '/api/v2/watchlist'),
      loadData('quotes', '/api/v2/quotes'),
      loadData('kline_daily', '/api/v2/kline/daily'),
      loadData('kline_monthly', '/api/v2/kline/monthly'),
      loadData('pos_current', '/api/v2/positions/current'),
      loadData('pos_closed', '/api/v2/positions/closed'),
      loadData('trades', '/api/v2/trades'),
      loadData('dividends', '/api/v2/dividends'),
      loadData('predictions', '/api/v2/predictions/daily'),
      loadData('seasonal', '/api/v2/seasonal'),
      loadData('news', '/api/v2/news'),
      loadData('expert', '/api/v2/expert'),
      loadData('accuracy', '/api/v2/accuracy'),
      loadData('learning', '/api/v2/learning'),
    ])

  // Build compat DATA object (same shape as old /api/v2/init response)
  const DATA = {
    account: cfg?.account || '51312640',
    broker: cfg?.broker || '广发证券',
    generated: new Date().toISOString().slice(0, 16).replace('T', ' '),
    watchlist: wl || [],
    quotes: quotes || {},
    positions: {
      current_positions: pc || {},
      closed_positions: pcl || {},
      all_trades: trades || [],
    },
    kline_daily: kd || {},
    kline: km || {},
    seasonal: sea || {},
    daily_predictions: preds || [],
    news: news || [],
    expert_reports: expert || [],
    accuracy_stats: accStats || {},
    learning_params: learn || {},
  }

  // Inject dividends_{code} keys
  if (divs && divs.length) {
    const divByCode = {}
    divs.forEach(d => {
      if (!divByCode[d.code]) divByCode[d.code] = []
      divByCode[d.code].push({
        date: d.date, amount: d.amount,
        price: d.price, per_share: d.per_share || 0,
      })
    })
    Object.keys(divByCode).forEach(code => {
      DATA['dividends_' + code] = divByCode[code]
    })
  }

  // Inject monthly_changes_{code}
  if (km) {
    Object.keys(km).forEach(code => {
      const bars = km[code] || []
      DATA['monthly_changes_' + code] = bars
        .filter(b => b[6] !== 0)
        .map(b => [b[0], b[6]])
    })
  }

  return { DATA, config: cfg, dividends: divs || [] }
}

// Utility functions — same as old core.js
export function fmt(n, d = 2) {
  return n == null ? '--' : Number(n).toFixed(d)
}

export function fmtMoney(n) {
  return n >= 10000 ? (n / 10000).toFixed(2) + '万' : fmt(n)
}

export function pnlClass(v) {
  return v > 0 ? 'up' : v < 0 ? 'down' : 'flat'
}

export function pnlSign(v) {
  return v > 0 ? '+' : ''
}

export function getStockName(code, watchlist) {
  if (!watchlist) return code
  const s = watchlist.find(x => x.code === code)
  return s ? s.name : code
}
