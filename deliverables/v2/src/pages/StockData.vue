<template>
  <div class="page-content">
    <div v-if="data.loading && !data.watchlist.length" class="loading"><div class="spinner"></div></div>
    <div v-else-if="data.error && !data.watchlist.length" class="error-card"><h2>加载失败</h2><p>{{ data.error }}</p></div>
    <template v-else>
      <!-- Top bar -->
      <div class="top-bar">
        <div class="top-title">
          <h1 class="page-title">📊 股票数据</h1>
          <span class="stock-count">{{ data.watchlist.length }} 只股票</span>
        </div>
        <div class="right-actions">
          <button class="tab-btn refresh-btn" :class="{ 'refresh-running': data.refreshing }" @click="refresh" :disabled="data.refreshing">
            <span class="btn-icon" :class="{ spinning: data.refreshing }">{{ data.refreshing ? '⏳' : '🔄' }}</span>
            <span>{{ data.refreshing ? '刷新中…' : '刷新行情' }}</span>
          </button>
          <span class="status-text" :class="{ 'status-ok': refreshOk, 'status-err': data.refreshError }" v-if="refreshOk || data.refreshError">
            {{ refreshOk || data.refreshError }}
          </span>
          <span class="refresh-time" v-if="data.lastRefresh && !selectedDate">上次: {{ data.lastRefresh }}</span>
        </div>
      </div>

      <!-- Date bar -->
      <div class="date-bar">
        <div class="dp-wrapper" ref="dpRef">
          <button class="dp-trigger" @click="dpOpen = !dpOpen">
            <span>📅</span><span class="dp-text">{{ selectedDate || '选择日期查询历史' }}</span><span class="dp-arr">▾</span>
          </button>
          <div v-if="dpOpen" class="dp-panel">
            <div class="dp-nav">
              <button @click="dpPrevMonth">◀</button>
              <span>{{ dpYear }}年{{ dpMonth }}月</span>
              <button @click="dpNextMonth">▶</button>
            </div>
            <div class="dp-weekdays"><span v-for="w in weekdays" :key="w">{{ w }}</span></div>
            <div class="dp-days">
              <div v-for="(d, i) in calendarDays" :key="i"
                class="dp-day" :class="d.cls"
                @click="d.day ? selectDate(d.dateStr) : null">
                {{ d.day || '' }}
              </div>
            </div>
            <button class="dp-clear" @click="clearDate">清除 → 最新数据</button>
          </div>
        </div>
        <span class="dp-status" v-if="selectedDate">
          📅 {{ selectedDate }}
          <span class="dp-badge">历史数据</span>
        </span>
        <span class="dp-status" v-else>
          <span class="dp-badge latest">最新行情</span>
        </span>
        <span class="dp-loading" v-if="historyLoading"><div class="mini-spinner"></div> 加载中…</span>
        <span class="dp-error" v-if="historyError">{{ historyError }}</span>
      </div>

      <!-- Card grid -->
      <div class="card-grid" v-if="marketCards.length">
        <div v-for="card in marketCards" :key="card.code" class="stock-card" :class="{ 'is-history': !!selectedDate }">
          <!-- Header -->
          <div class="card-header">
            <div class="card-stock-info">
              <div class="card-stock-name">{{ card.name }}</div>
              <div class="card-stock-code">{{ card.code }}</div>
            </div>
            <div class="card-price" :class="pnlClass(card.change)">¥{{ fmt(card.price) }}</div>
          </div>
          <!-- Body: data grid -->
          <div class="card-body">
            <!-- Row 1: 涨跌额 / 涨跌幅 -->
            <div class="data-row">
              <span class="data-label">
                涨跌额
                <span class="hint-icon" data-tip="今日价格相比昨日收盘价变动了多少元（正=涨，负=跌）">ⓘ</span>
              </span>
              <span class="data-value" :class="pnlClass(card.change)">{{ pnlSign(card.change) }}{{ fmt(card.change) }}</span>
            </div>
            <div class="data-row">
              <span class="data-label">
                涨跌幅
                <span class="hint-icon" data-tip="今日涨跌额占昨日收盘价的百分比，反映今日波动幅度">ⓘ</span>
              </span>
              <span class="data-value" :class="pnlClass(card.change)">{{ pnlSign(card.change) }}{{ fmt(changePct(card), 2) }}%</span>
            </div>
            <!-- Row 2: 今日开盘 / 今日最高 -->
            <div class="data-row">
              <span class="data-label">
                今日开盘
                <span class="hint-icon" data-tip="今日9:30第一笔成交的价格">ⓘ</span>
              </span>
              <span class="data-value">¥{{ fmt(card.open) }}</span>
            </div>
            <div class="data-row">
              <span class="data-label">
                今日最高
                <span class="hint-icon" data-tip="今日盘中达到的最高价格（日内高点）">ⓘ</span>
              </span>
              <span class="data-value up">¥{{ fmt(card.high) }}</span>
            </div>
            <!-- Row 3: 今日最低 / 成交量 -->
            <div class="data-row">
              <span class="data-label">
                今日最低
                <span class="hint-icon" data-tip="今日盘中跌到的最低价格（日内低点）">ⓘ</span>
              </span>
              <span class="data-value down">¥{{ fmt(card.low) }}</span>
            </div>
            <div class="data-row">
              <span class="data-label">
                成交量
                <span class="hint-icon" data-tip="今天一共成交了多少笔，1手=100股。数字越大说明交易越活跃">ⓘ</span>
              </span>
              <span class="data-value">{{ fmtVolume(card.volume) }}</span>
            </div>
            <!-- Row 4: 成交额 / 市盈率 -->
            <div class="data-row">
              <span class="data-label">
                成交额
                <span class="hint-icon" data-tip="今天成交的总金额。反映资金进出规模，越大说明关注度越高">ⓘ</span>
              </span>
              <span class="data-value">{{ fmtAmount(card.amount) }}</span>
            </div>
            <div class="data-row">
              <span class="data-label">
                市盈率
                <span class="hint-icon" data-tip="股价÷每股盈利。衡量'多少年能回本'，越低越便宜；银行股通常5-8倍">ⓘ</span>
              </span>
              <span class="data-value">{{ card.pe > 0 ? fmt(card.pe) : '--' }}</span>
            </div>
            <!-- Bottom: 市净率 / 股息率 -->
            <div class="data-row">
              <span class="data-label">
                市净率
                <span class="hint-icon" data-tip="股价÷每股净资产。衡量股价相对于'家底'，&lt;1就是跌破净资产">ⓘ</span>
              </span>
              <span class="data-value">{{ card.pb > 0 ? fmt(card.pb) : '--' }}</span>
            </div>
            <div class="data-row">
              <span class="data-label">
                股息率
                <span class="hint-icon" data-tip="每股分红÷股价。持有这只股票一年能拿多少分红，银行股的核心吸引力">ⓘ</span>
              </span>
              <span class="data-value dy-value">{{ card.dy > 0 ? fmt(card.dy, 2) + '%' : '--' }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else class="card">
        <div class="empty" v-if="selectedDate && !historyLoading">暂无 {{ selectedDate }} 的数据（可能是非交易日）</div>
        <div class="empty" v-else>暂无自选股数据，请先在管理设置中添加自选股</div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useDataStore } from '@/stores/data.js'
import { fmt, pnlClass, pnlSign, apiCall } from '@/api/client.js'

const data = useDataStore()
const refreshOk = ref('')
const selectedDate = ref('')
const dpOpen = ref(false)
const dpYear = ref(0)
const dpMonth = ref(0)
const historyData = ref(null)
const historyLoading = ref(false)
const historyError = ref('')
let statusTimer = null
let dpRef = ref(null)

const weekdays = ['一','二','三','四','五','六','日']

// Calendar
const calendarDays = computed(() => {
  const first = new Date(dpYear.value, dpMonth.value - 1, 1)
  const last = new Date(dpYear.value, dpMonth.value, 0)
  const startDay = first.getDay()
  const offset = startDay === 0 ? 6 : startDay - 1
  const days = []
  for (let i = 0; i < offset; i++) days.push({ cls: 'other' })
  const today = new Date().toISOString().substring(0, 10)
  for (let d = 1; d <= last.getDate(); d++) {
    const ds = `${dpYear.value}-${String(dpMonth.value).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    const cls = ['dp-day']
    if (ds === today) cls.push('today')
    if (selectedDate.value === ds) cls.push('selected')
    days.push({ day: d, dateStr: ds, cls: cls.join(' ') })
  }
  return days
})

const marketCards = computed(() => {
  // historyData === null → latest data; historyData !== null → historical data
  if (selectedDate.value && historyData.value !== null) {
    return data.watchlist.map(s => {
      const q = historyData.value[s.code]
      if (!q) return null
      const volume = q.volume || 0
      const price = q.price || 0
      const amount = volume * price
      return {
        code: s.code, name: s.name,
        price, change: q.change || 0,
        open: q.open || 0, high: q.high || 0, low: q.low || 0,
        volume, amount,
        pe: q.pe || 0, pb: q.pb || 0, dy: q.dy || 0,
      }
    }).filter(Boolean)
  }
  // Latest data from store
  return data.watchlist.map(s => {
    const q = data.quotes[s.code] || {}
    const volume = q.volume || 0
    const price = q.price || 0
    const amount = volume * price
    return {
      code: s.code,
      name: s.name,
      price,
      change: q.change || 0,
      open: q.open || 0,
      high: q.high || 0,
      low: q.low || 0,
      volume,
      amount,
      pe: q.pe || 0,
      pb: q.pb || 0,
      dy: q.dy || 0,
    }
  })
})

function changePct(card) {
  const prev = card.price - card.change
  return prev > 0 ? (card.change / prev) * 100 : 0
}

function fmtVolume(v) {
  if (!v || v <= 0) return '--'
  if (v >= 100000000) return (v / 100000000).toFixed(2) + '亿'
  if (v >= 10000) return (v / 10000).toFixed(2) + '万'
  return v.toFixed(0)
}

function fmtAmount(a) {
  if (!a || a <= 0) return '--'
  if (a >= 100000000) return '¥' + (a / 100000000).toFixed(2) + '亿'
  if (a >= 10000) return '¥' + (a / 10000).toFixed(2) + '万'
  return '¥' + a.toFixed(0)
}

// Date picker
function initCalendar() {
  const d = new Date()
  dpYear.value = d.getFullYear()
  dpMonth.value = d.getMonth() + 1
}

function dpPrevMonth() {
  if (--dpMonth.value < 1) { dpMonth.value = 12; dpYear.value-- }
}
function dpNextMonth() {
  if (++dpMonth.value > 12) { dpMonth.value = 1; dpYear.value++ }
}

async function selectDate(ds) {
  selectedDate.value = ds
  dpOpen.value = false
  if (!ds) return

  const today = new Date().toISOString().substring(0, 10)

  // Today: use latest quotes from store (no history API call)
  if (ds === today) {
    historyData.value = null  // null means "use latest data"
    historyError.value = ''
    return
  }

  historyLoading.value = true
  historyError.value = ''
  try {
    const r = await apiCall('GET', `/api/v2/quotes/history?date=${ds}`)
    if (r && r.success && r.data && Object.keys(r.data).length > 0) {
      historyData.value = r.data
    } else if (r && r.success) {
      // Empty result (weekend / holiday / no data)
      historyData.value = {}
      historyError.value = ''
    } else {
      historyError.value = r?.error || '查询失败'
      historyData.value = null
    }
  } catch (e) {
    historyError.value = e.message || '网络错误'
    historyData.value = null
  } finally {
    historyLoading.value = false
  }
}

function clearDate() {
  selectedDate.value = ''
  dpOpen.value = false
  historyData.value = null
  historyError.value = ''
}

async function refresh() {
  if (data.refreshing) return
  refreshOk.value = ''
  if (statusTimer) { clearTimeout(statusTimer); statusTimer = null }
  await data.refreshQuotesAndReload()
  if (data.refreshError) {
    refreshOk.value = data.refreshError
  } else {
    refreshOk.value = '✅ 刷新完成'
  }
  statusTimer = setTimeout(() => { refreshOk.value = '' }, 3000)
}

// Click outside to close calendar
function onDocClick(e) {
  if (dpRef.value && !dpRef.value.contains(e.target)) dpOpen.value = false
}

onMounted(async () => {
  if (!data.watchlist.length) await data.fetchAll()
  initCalendar()
  document.addEventListener('click', onDocClick)
})

onUnmounted(() => {
  if (statusTimer) clearTimeout(statusTimer)
  document.removeEventListener('click', onDocClick)
})
</script>

<style scoped>
.page-content { max-width: 1400px; margin: 0 auto; }
.loading { text-align: center; padding: 60px; }
.spinner { width: 36px; height: 36px; border: 3px solid #e5e7eb; border-top-color: #2563eb; border-radius: 50%; animation: spin .8s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-card { background: #fef2f2; border: 1px solid #fca5a5; border-radius: 12px; padding: 32px; text-align: center; }

/* Top bar */
.top-bar {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 6px; padding: 12px 0 4px; flex-wrap: wrap; gap: 8px;
}
.top-title { display: flex; align-items: baseline; gap: 10px; }
.page-title { font-size: 18px; font-weight: 700; color: #1f2937; margin: 0; }
.stock-count { font-size: 12px; color: #9ca3af; }
.right-actions { display: flex; align-items: center; gap: 8px; white-space: nowrap; flex-wrap: wrap; }
.status-text { font-size: 11px; color: #6b7280; transition: color 0.3s; }
.status-text.status-ok { color: #059669; }
.status-text.status-err { color: #dc2626; }
.refresh-time { font-size: 11px; color: #9ca3af; }
.refresh-btn { display: inline-flex; align-items: center; gap: 6px; transition: all 0.25s ease; }
.refresh-btn:disabled { opacity: 0.7; cursor: not-allowed; }
.refresh-btn:not(:disabled):hover { background: #dbeafe; border-color: #93c5fd; transform: translateY(-1px); box-shadow: 0 2px 6px rgba(37, 99, 235, 0.15); }
.refresh-running { background: #eff6ff; border-color: #60a5fa; color: #2563eb; }
.btn-icon { display: inline-block; font-size: 14px; line-height: 1; }
.btn-icon.spinning { animation: btnSpin 1s linear infinite; }
@keyframes btnSpin { to { transform: rotate(360deg); } }

/* Date bar */
.date-bar {
  display: flex; align-items: center; gap: 10px; margin-bottom: 14px; flex-wrap: wrap;
}
.dp-wrapper { position: relative; }
.dp-trigger {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; border: 1px solid #d1d5db; border-radius: 8px;
  background: #fff; cursor: pointer; font-size: 13px; transition: all .15s;
}
.dp-trigger:hover { border-color: #93c5fd; background: #f8faff; }
.dp-text { flex: 1; color: #374151; min-width: 100px; }
.dp-arr { font-size: 10px; color: #9ca3af; }
.dp-panel {
  position: absolute; top: 100%; left: 0;
  background: #fff; border: 1px solid #e5e7eb; border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0,0,0,.1); padding: 14px; width: 264px; z-index: 200; margin-top: 4px;
}
.dp-nav { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.dp-nav button { width: 28px; height: 28px; border: none; border-radius: 6px; background: #f3f4f6; cursor: pointer; }
.dp-nav span { font-size: 14px; font-weight: 600; }
.dp-weekdays { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; margin-bottom: 6px; }
.dp-weekdays span { text-align: center; font-size: 11px; color: #9ca3af; padding: 4px 0; }
.dp-days { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }
.dp-day { text-align: center; padding: 6px 0; font-size: 12px; border-radius: 6px; cursor: pointer; }
.dp-day:hover { background: #f3f4f6; }
.dp-day.other { color: #d1d5db; cursor: default; }
.dp-day.today { font-weight: 700; color: #2563eb; }
.dp-day.selected { background: #2563eb; color: #fff; font-weight: 600; }
.dp-clear {
  display: block; width: 100%; margin-top: 10px; padding: 6px;
  border: 1px solid #e5e7eb; border-radius: 6px; background: #fff;
  cursor: pointer; font-size: 12px; color: #6b7280; transition: all .15s;
}
.dp-clear:hover { background: #f3f4f6; border-color: #d1d5db; color: #374151; }
.dp-status { font-size: 12px; color: #6b7280; display: flex; align-items: center; gap: 6px; }
.dp-badge {
  font-size: 11px; padding: 2px 8px; border-radius: 4px;
  background: #fef3c7; color: #92400e; font-weight: 600;
}
.dp-badge.latest { background: #dbeafe; color: #1e40af; }
.dp-loading { font-size: 11px; color: #2563eb; display: flex; align-items: center; gap: 4px; }
.mini-spinner { width: 12px; height: 12px; border: 2px solid #e5e7eb; border-top-color: #2563eb; border-radius: 50%; animation: spin .8s linear infinite; display: inline-block; }
.dp-error { font-size: 11px; color: #dc2626; }

/* Card grid */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 14px;
}

/* Stock card */
.stock-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0,0,0,.06);
  padding: 18px 20px;
  transition: transform .15s, box-shadow .15s;
}
.stock-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,.09);
}
.stock-card.is-history {
  border: 1px solid #fef3c7;
}

/* Card header */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f1f5f9;
}
.card-stock-info { display: flex; flex-direction: column; gap: 2px; }
.card-stock-name { font-size: 16px; font-weight: 700; color: #1f2937; }
.card-stock-code { font-size: 11px; color: #9ca3af; }
.card-price { font-size: 24px; font-weight: 700; line-height: 1; }

/* Card body - data grid */
.card-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 16px;
}
.data-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 5px 0;
}
.data-label {
  font-size: 11px;
  color: #9ca3af;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.data-value {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  font-variant-numeric: tabular-nums;
}
.dy-value { color: #0891b2; font-weight: 700; }

/* Tooltip hint icon */
.hint-icon {
  position: relative;
  cursor: help;
  font-size: 11px;
  color: #cbd5e1;
  display: inline-flex;
  align-items: center;
  line-height: 1;
}
.hint-icon::after {
  content: attr(data-tip);
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  background: #1f2937;
  color: #fff;
  font-size: 12px;
  line-height: 1.4;
  padding: 7px 12px;
  border-radius: 8px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity .15s;
  max-width: 280px;
  white-space: normal;
  z-index: 50;
  box-shadow: 0 4px 8px rgba(0,0,0,.15);
}
.hint-icon:hover::after { opacity: 1; }

/* Color helpers */
:deep(.up) { color: #16a34a; }
:deep(.down) { color: #dc2626; }
:deep(.flat) { color: #6b7280; }

.empty { text-align: center; padding: 60px; color: #9ca3af; font-size: 14px; }
.card { background: #fff; border-radius: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.06); padding: 20px; }

/* Responsive */
@media (max-width: 700px) {
  .card-grid { grid-template-columns: 1fr; }
  .top-bar { flex-direction: column; align-items: flex-start; }
}
</style>
