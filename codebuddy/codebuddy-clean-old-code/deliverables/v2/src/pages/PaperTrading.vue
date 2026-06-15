<template>
  <div class="page-content">
    <!-- Market status banner -->
    <div v-if="marketStatus === 'closed'" class="status-banner status-closed">
      📊 当前非交易时段，交易需在开市后执行（9:30-11:30, 13:00-15:00）
    </div>
    <div v-if="marketStatus === 'non_trading_day'" class="status-banner status-non-trading">
      📅 今日非交易日（周末），不开市
    </div>

    <!-- Error banner -->
    <div v-if="errorText" class="error-banner" @click="errorText=''">
      ⚠️ {{ errorText }} (点击关闭)
    </div>

    <div v-if="loading" class="loading"><div class="spinner"></div></div>
    <template v-else>
      <!-- Account Card -->
      <div class="card account-card" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px">
        <div>
          <h2 style="margin:0 0 8px;font-size:16px">💼 虚拟账户</h2>
          <div v-if="account?.initialized" style="font-size:12px;color:#6b7280">
            初始资金: ¥{{ fmtMoney(account.initial_capital) }} &nbsp;|&nbsp;
            {{ (account.created_at || '').slice(0,16) }}
          </div>
        </div>
        <div v-if="account?.initialized" style="display:flex;gap:24px;flex-wrap:wrap">
          <div><div style="font-size:11px;color:#6b7280">当前总资产</div>
            <div style="font-size:22px;font-weight:700" :class="pnlClass(account.cumulative_return_pct)">
              ¥{{ fmtMoney(account.total_asset) }}
              <span style="font-size:14px">({{ pnlSign(account.cumulative_return_pct) }}{{ fmtPct(account.cumulative_return_pct) }})</span>
            </div>
          </div>
          <div><div style="font-size:11px;color:#6b7280">可用现金</div>
            <div style="font-size:18px;font-weight:600">¥{{ fmtMoney(account.cash) }}</div>
          </div>
          <div><div style="font-size:11px;color:#6b7280">持仓市值</div>
            <div style="font-size:18px;font-weight:600">¥{{ fmtMoney(account.position_value) }}</div>
          </div>
        </div>
        <div v-else style="color:#dc2626;display:flex;align-items:center;gap:12px">
          <span>虚拟账户未初始化</span>
          <button class="tab-btn" style="background:#16a34a;color:#fff;border-color:#16a34a;padding:6px 16px"
            @click="initAccount" :disabled="initLoading">
            {{ initLoading ? '初始化中...' : '初始化 ¥100,000' }}
          </button>
        </div>
        <button v-if="account?.initialized" class="tab-btn" style="background:#f59e0b;color:#fff;border-color:#f59e0b"
          @click="confirmReset">🔄 重置</button>
        <button v-if="account?.initialized" class="tab-btn" style="background:#16a34a;color:#fff;border-color:#16a34a;padding:6px 16px"
          @click="handleExecute" :disabled="execLoading">
          {{ execLoading ? '执行中...' : '▶ 执行交易' }}
        </button>
      </div>

      <!-- Intraday Chart -->
      <div class="card" v-if="account?.initialized && wl.length">
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:12px">
          <h2 style="margin:0;font-size:16px">📈 分时走势</h2>
          <div style="display:flex;align-items:center;gap:8px">
            <select v-model="intradayCode" @change="onCodeChange" style="padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:13px">
              <option value="" disabled>选择股票</option>
              <option v-for="s in wl" :key="s.code" :value="s.code">{{ s.name || s.code }} ({{ s.code }})</option>
            </select>
            <input type="date" v-model="selectedDate" @change="onDateChange" :max="todayStr" style="padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:13px" />
          </div>
        </div>
        <div class="chart-wrap" style="height:300px;position:relative">
          <canvas ref="intradayCanvas" style="display:block;width:100%;height:100%"></canvas>
        </div>
        <div style="font-size:11px;color:#9ca3af;margin-top:4px" v-if="intradayData.length">{{ intradayData[0]?.timestamp?.slice(11,16) || '' }} - {{ intradayData[intradayData.length-1]?.timestamp?.slice(11,16) || '' }} ({{ intradayData.length }} 个数据点)</div>
        <div v-else class="empty" style="margin-top:12px">该日期暂无分时数据</div>
      </div>

      <!-- Suggestions -->
      <div class="card" v-if="suggestions.length">
        <h2>{{ tradingTitle }} <span style="font-size:10px;color:#9ca3af;font-weight:400">v2.1</span></h2>
        <div style="font-size:11px;color:#6b7280;margin-bottom:12px">
          交易由算法自动执行，以下为已执行的交易结果
        </div>
        <table class="paper-table">
          <thead><tr><th>股票名称</th><th>代码</th><th>操作</th><th>方向</th><th>数量</th><th>执行价</th><th>置信度</th><th>说明</th></tr></thead>
          <tbody>
            <tr v-for="sug in suggestions" :key="sug.code">
              <td>{{ sug.name || sug.code }}</td>
              <td>{{ sug.code }}</td>
              <td><span class="sug-table-badge" :class="sug.action">{{ actionText(sug) }}</span></td>
              <td :class="dirClass(sug.direction)">{{ dirText(sug.direction) }}</td>
              <td>{{ sug.qty ? sug.qty + '股' : '--' }}</td>
              <td>¥{{ sug.price ? fmt(sug.price) : '--' }}</td>
              <td>{{ pct(sug.confidence) }}%</td>
              <td class="sug-reason-cell" :title="sug.reason || ''">{{ fmtReason(sug) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="card" v-else>
        <h2>{{ tradingTitle }}</h2>
        <div class="empty">{{ selectedDate === todayStr ? '今日' : selectedDate }}暂无自动交易结果</div>
      </div>

      <!-- Positions -->
      <div class="card">
        <h2>📦 虚拟持仓 <span style="font-size:12px;color:#f59e0b;font-weight:400">(橙色标识)</span></h2>
        <table v-if="positions.length" class="paper-table">
          <thead><tr><th>股票</th><th>代码</th><th>持仓量</th><th>成本价</th><th>现价</th><th>市值</th><th>浮盈亏</th></tr></thead>
          <tbody>
            <tr v-for="p in positions" :key="p.code">
              <td>{{ p.name || p.code }}</td>
              <td>{{ p.code }}</td>
              <td>{{ p.qty }}股</td>
              <td>¥{{ fmt(p.avg_cost) }}</td>
              <td>¥{{ p.last_price ? fmt(p.last_price) : '--' }}</td>
              <td>¥{{ fmtMoney(p.market_value) }}</td>
              <td :class="pnlClass(p.unrealized_pnl)">
                {{ pnlSign(p.unrealized_pnl) }}¥{{ fmtMoney(Math.abs(p.unrealized_pnl||0)) }}
                <span v-if="p.unrealized_pnl_pct">({{ pnlSign(p.unrealized_pnl_pct) }}{{ fmtPct(p.unrealized_pnl_pct) }})</span>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty">暂无虚拟持仓</div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { storeToRefs } from 'pinia'
import { usePaperStore } from '@/stores/paper.js'
import { useDataStore } from '@/stores/data.js'

const store = usePaperStore()
const { account, positions, suggestions, intradayData, intradayCode, selectedDate, availableDates, marketStatus } = storeToRefs(store)
const { loadAccount, loadPositions, loadSuggestions, resetAccount, loadIntraday, executeTrading } = store

// Use data store watchlist (all self-selected stocks, not just positions)
const dataStore = useDataStore()
const wl = computed(() => dataStore.watchlist || [])

const loading = ref(false)
const errorText = ref('')
const initLoading = ref(false)
const execLoading = ref(false)
const intradayCanvas = ref(null)
const todayStr = new Date().toISOString().slice(0, 10)
const tradingTitle = computed(() => {
  return selectedDate.value === todayStr ? '📋 今日交易结果' : `📋 ${selectedDate.value} 交易结果`
})
let chartInst = null

onMounted(async () => {
  loading.value = true
  errorText.value = ''
  try {
    if (!dataStore.watchlist.length) await dataStore.fetchAll()
    await Promise.all([loadAccount(), loadSuggestions()])
    await loadPositions()
    if (wl.value.length > 0) {
      intradayCode.value = wl.value[0].code
      selectedDate.value = todayStr
      await loadIntraday(intradayCode.value, todayStr)
    }
  } catch (e) {
    errorText.value = '加载数据失败: ' + (e.message || '网络错误，请确认后端服务已启动(端口8766)')
  }
  loading.value = false
})

// Same pattern as PaperHistory.vue: watch data + canvas, draw on changes
watch([intradayData, intradayCanvas], () => {
  nextTick(() => {
    try { renderIntradayChart() } catch (e) { console.warn('intraday chart:', e) }
  })
})

async function onCodeChange() {
  selectedDate.value = todayStr
  if (intradayCode.value) {
    await loadIntraday(intradayCode.value, todayStr)
    await nextTick()
    renderIntradayChart()
    // 加载当日全量交易结果（不按代码过滤）
    await loadSuggestions('', todayStr)
  }
}

async function onDateChange() {
  console.log('[PaperTrading] onDateChange triggered, selectedDate:', selectedDate.value)
  if (intradayCode.value) {
    await loadIntraday(intradayCode.value, selectedDate.value)
    await nextTick()
    renderIntradayChart()
    // 加载所选日期全量交易结果（不按代码过滤）
    console.log('[PaperTrading] calling loadSuggestions with date:', selectedDate.value)
    await loadSuggestions('', selectedDate.value)
  }
}

function renderIntradayChart() {
  const canvas = intradayCanvas.value
  const data = intradayData.value

  // 先销毁旧图表，避免日期切换后旧图残留
  if (chartInst) { chartInst.destroy(); chartInst = null }

  if (!canvas || !data || !data.length) return

  const C = window.Chart
  if (!C) { console.warn('Chart.js not loaded'); return }

  const labels = data.map(d => d.timestamp?.slice(11, 16) || '')
  const prices = data.map(d => d.price)
  const vols = data.map(d => d.volume)
  if (!prices.length) return

  const minPrice = Math.min(...prices)
  const maxPrice = Math.max(...prices)
  const startPrice = prices[0]

  chartInst = new C(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: '价格',
        data: prices,
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245, 158, 11, 0.05)',
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.2,
        fill: true,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        tooltip: {
          backgroundColor: 'rgba(0,0,0,0.8)',
          titleColor: '#fff',
          bodyColor: '#f59e0b',
          padding: 10,
          cornerRadius: 6,
          displayColors: false,
          callbacks: {
            title: items => {
              const i = items[0]?.dataIndex
              return data[i]?.timestamp?.slice(11, 16) || ''
            },
            label: ctx => {
              const i = ctx.dataIndex
              const chg = startPrice > 0 ? ((prices[i] - startPrice) / startPrice * 100) : 0
              const sign = chg >= 0 ? '+' : ''
              return `¥${prices[i].toFixed(2)}  (${sign}${chg.toFixed(2)}%)`
            },
            afterBody: ctx => {
              const i = ctx[0]?.dataIndex
              if (i == null) return ''
              const vol = vols[i] || 0
              return `成交量: ${vol >= 10000 ? (vol / 10000).toFixed(1) + '万' : vol}手`
            },
          },
        },
        legend: { display: false },
      },
      scales: {
        x: {
          ticks: {
            maxTicksLimit: 8,
            maxRotation: 0,
          },
        },
        y: {
          min: Math.floor(minPrice * 0.999 * 100) / 100,
          max: Math.ceil(maxPrice * 1.001 * 100) / 100,
          ticks: { callback: v => '¥' + v.toFixed(2) },
        },
      },
    },
  })
}

async function initAccount() {
  initLoading.value = true
  errorText.value = ''
  try {
    const r = await resetAccount(100000)
    if (!r?.success) {
      errorText.value = '初始化失败: ' + (r?.error || 'API返回异常，请确认后端已启动')
      return
    }
    // Load suggestions (read-only) and positions after reset
    await loadSuggestions()
    await loadPositions()
  } catch (e) {
    errorText.value = '初始化异常: ' + (e.message || '未知错误')
  } finally {
    initLoading.value = false
  }
}

async function confirmReset() {
  if (!confirm('确认重置虚拟账户？所有持仓将被清空，现金恢复为 ¥100,000。交易历史记录将保留。')) return
  loading.value = true
  errorText.value = ''
  try {
    await resetAccount(100000)
    // Load suggestions (read-only) and positions after reset
    await loadSuggestions()
    await loadPositions()
  } catch (e) {
    errorText.value = '重置失败: ' + (e.message || '未知错误')
  }
  loading.value = false
}

async function handleExecute() {
  execLoading.value = true
  errorText.value = ''
  try {
    const r = await executeTrading()
    if (!r?.success) {
      errorText.value = '执行失败: ' + (r?.error || 'API返回异常')
      return
    }
    // Refresh account and positions after execution
    await Promise.all([loadAccount(), loadPositions()])
    if (r.message) {
      errorText.value = '✅ ' + r.message
      setTimeout(() => { if (errorText.value?.startsWith('✅')) errorText.value = '' }, 5000)
    }
  } catch (e) {
    errorText.value = '执行异常: ' + (e.message || '未知错误')
  } finally {
    execLoading.value = false
  }
}

function fmt(v) { return v != null ? Number(v).toFixed(2) : '--' }
function fmtMoney(v) {
  if (v == null) return '--'
  if (v >= 10000) {
    const wan = v / 10000
    return wan.toFixed(wan < 10 ? 3 : 2) + '万'
  }
  return Number(v).toFixed(0)
}
function fmtPct(v) { return v != null ? Number(v).toFixed(1) + '%' : '--' }
function pct(v) { return v != null ? Math.round(v * 100) : '--' }
function pnlClass(v) { return Number(v) > 0 ? 'up' : Number(v) < 0 ? 'down' : 'flat' }
function pnlSign(v) { return Number(v) > 0 ? '+' : Number(v) < 0 ? '-' : '' }
function dirClass(d) { return d === 'bullish' ? 'up' : d === 'bearish' ? 'down' : '' }
function dirText(d) { return d === 'bullish' ? '看涨 ↑' : d === 'bearish' ? '看跌 ↓' : '中性 →' }

function actionText(sug) {
  const a = sug.action || 'hold'
  const done = sug.executed === 1
  if (a === 'buy') return done ? '已买入' : '待买入'
  if (a === 'sell') return done ? '已卖出' : '待卖出'
  if (a === 'watch') return '关注'
  return '观望'
}
function fmtReason(sug) {
  const r = (sug.reason || '').toLowerCase()
  if (r.includes('no valid market price')) return '暂无有效市价'
  const dirMap = { bullish: '看涨', bearish: '看跌', neutral: '中性' }
  const dt = dirMap[sug.direction] || ''
  const conf = pct(sug.confidence)
  if (sug.action === 'buy') return sug.executed === 1 ? `预测${dt}，信心${conf}%，已买入` : `预测${dt}，信心${conf}%，待开市执行`
  if (sug.action === 'sell') return sug.executed === 1 ? `预测${dt}，信心${conf}%，已卖出` : `预测${dt}，信心${conf}%，待开市执行`
  if (sug.action === 'watch') return `看好${dt}但未达买入条件`
  if (sug.direction === 'neutral' || conf < 50) return '信号不明确，暂观望'
  return `预测${dt}但无持仓，暂无法操作`
}
</script>

<style scoped>
.status-banner {
  padding: 10px 16px; border-radius: 8px; margin-bottom: 16px;
  font-size: 13px; text-align: center; font-weight: 500;
}
.status-closed {
  background: #fffbeb; border: 1px solid #fde68a; color: #92400e;
}
.status-non-trading {
  background: #f3f4f6; border: 1px solid #d1d5db; color: #6b7280;
}
.error-banner {
  background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px;
  padding: 10px 16px; margin-bottom: 16px; color: #991b1b;
  font-size: 13px; cursor: pointer;
}
.account-card {
  border-left: 4px solid #f59e0b;
}
.paper-table { width: 100%; border-collapse: collapse; }
.paper-table thead { background: rgba(245,158,11,.08); }
.paper-table th, .paper-table td { padding: 8px 10px; text-align: left; font-size: 13px; white-space: nowrap; }
.paper-table th { font-weight: 600; color: #4b5563; }
.paper-table tbody tr { border-bottom: 1px solid #f3f4f6; }
.paper-table tbody tr:last-child { border-bottom: none; }
.paper-table tbody tr:hover { background: rgba(245,158,11,.04); }
.sug-table-badge { font-size: 11px; padding: 2px 10px; border-radius: 10px; font-weight: 600; display: inline-block; }
.sug-table-badge.buy { background: #fecaca; color: #991b1b; }
.sug-table-badge.sell { background: #bbf7d0; color: #166534; }
.sug-table-badge.watch { background: #e5e7eb; color: #4b5563; }
.sug-table-badge.hold { background: #e5e7eb; color: #4b5563; }
.sug-reason-cell { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
