<template>
  <div class="page-content">
    <!-- Market status banner -->
    <div v-if="marketStatus === 'closed'" class="status-banner status-closed">
      📊 当前非交易时段，系统将在开盘前自动生成交易建议（9:30-11:30, 13:00-15:00盘中自动执行）
    </div>
    <div v-if="marketStatus === 'non_trading_day'" class="status-banner status-non-trading">
      📅 今日非交易日（周末），不开市
    </div>

    <!-- Error / success banner -->
    <div v-if="bannerMsg" class="banner" :class="bannerType" @click="bannerMsg = ''">
      {{ bannerMsg }} (点击关闭)
    </div>

    <div v-if="loading" class="loading"><div class="spinner"></div></div>
    <template v-else>
      <!-- ===== 1. Account Card ===== -->
      <div class="card account-card">
        <div class="account-header">
          <div>
            <h2 style="margin:0 0 8px;font-size:18px">💼 虚拟账户</h2>
            <div v-if="account?.initialized" class="account-meta">
              初始资金: ¥{{ fmtMoney(account.initial_capital) }}
              &nbsp;|&nbsp; {{ (account.created_at || '').slice(0,16) }}
              &nbsp;|&nbsp; <span class="tag" :class="marketStatus === 'open' ? 'tag-open' : 'tag-closed'">{{ marketStatusText }}</span>
            </div>
          </div>
          <div class="account-actions">
            <button v-if="!account?.initialized" class="tab-btn btn-init"
              @click="initAccount" :disabled="initLoading">
              {{ initLoading ? '初始化中...' : '初始化 ¥100,000' }}
            </button>
            <button v-if="account?.initialized" class="tab-btn btn-gen"
              @click="handleGenerate" :disabled="genLoading || autoStatus?.suggestions_generated">
              {{ genLoading ? '生成中...' : (autoStatus?.suggestions_generated ? '已生成' : '📋 生成建议') }}
            </button>
            <button v-if="account?.initialized" class="tab-btn btn-reset"
              @click="confirmReset">🔄 重置</button>
            <button v-if="account?.initialized" class="tab-btn btn-verify"
              @click="doVerify" :disabled="verifyLoading">
              {{ verifyLoading ? '校验中...' : '✓ 数据校验' }}
            </button>
          </div>
        </div>
        <!-- Verify result -->
        <div v-if="verifyResult" class="verify-result" :class="verifyResult.consistent ? 'verify-ok' : 'verify-fail'">
          <span v-if="verifyResult.consistent">✅ 数据一致性校验通过</span>
          <span v-else>❌ 数据不一致 ({{ verifyResult.errors?.length || 0 }} 个问题)</span>
          <span class="verify-toggle" @click="showVerifyDetail = !showVerifyDetail">
            {{ showVerifyDetail ? '收起' : '详情' }}
          </span>
          <div v-if="showVerifyDetail && verifyResult.checks?.length" class="verify-detail">
            <div v-for="c in verifyResult.checks" :key="c.name" class="verify-check">
              <span :class="c.passed ? 'ok' : 'fail'">{{ c.passed ? '✓' : '✗' }}</span>
              <span>{{ c.name }}</span>
              <span class="verify-detail-text">{{ c.detail }}</span>
            </div>
            <div v-if="verifyResult.errors?.length" class="verify-errors">
              <div v-for="(err, i) in verifyResult.errors" :key="i" class="verify-error-item">⚠ {{ err }}</div>
            </div>
          </div>
        </div>
        <div v-if="account?.initialized" class="account-metrics">
          <div class="metric-item">
            <span class="metric-label">当前总资产</span>
            <span class="metric-value" :class="pnlClass(account.cumulative_return_pct)">
              ¥{{ fmtMoney(account.total_asset) }}
              <span class="metric-chg">({{ pnlSign(account.cumulative_return_pct) }}{{ fmtPct(account.cumulative_return_pct) }})</span>
            </span>
          </div>
          <div class="metric-item">
            <span class="metric-label">可用现金</span>
            <span class="metric-value">¥{{ fmtMoney(account.cash) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">持仓市值</span>
            <span class="metric-value">¥{{ fmtMoney(account.position_value) }}</span>
          </div>
        </div>
        <div v-else class="account-empty">
          <span style="color:#dc2626">虚拟账户未初始化</span>
          <button class="tab-btn btn-init" @click="initAccount" :disabled="initLoading">
            {{ initLoading ? '初始化中...' : '初始化 ¥100,000' }}
          </button>
        </div>
      </div>

      <!-- ===== 2. Performance Stats ===== -->
      <div v-if="perf" class="stat-grid">
        <div class="stat-mini"><span>总收益</span><b :class="pnlClass(perf.total_return_pct)">{{ pnlSign(perf.total_return_pct) }}{{ fmtPct(perf.total_return_pct) }}</b></div>
        <div class="stat-mini"><span>最大回撤</span><b>{{ fmtPct(perf.max_drawdown_pct) }}</b></div>
        <div class="stat-mini"><span>胜率</span><b>{{ fmtPct(perf.win_rate_pct) }}</b></div>
        <div class="stat-mini"><span>盈亏比</span><b>{{ fmtNum(perf.profit_factor) }}</b></div>
        <div class="stat-mini"><span>总交易</span><b>{{ perf.total_trades || 0 }}次</b></div>
        <div class="stat-mini"><span>最大单笔盈利</span><b class="up">+¥{{ fmtMoney(perf.max_single_win) }}</b></div>
      </div>

      <!-- ===== 2.5 Auto-Executor Status ===== -->
      <div v-if="account?.initialized" class="auto-status-bar">
        <span class="auto-status-dot" :class="autoStatus?.running ? 'running' : 'stopped'"></span>
        <span v-if="autoStatus?.running">自动执行中</span>
        <span v-else>待启动</span>
        <span v-if="autoStatus?.last_check" class="auto-status-info">
          · 上次检查 {{ autoStatus.last_check }}
        </span>
        <span v-if="autoStatus?.executed_count > 0" class="auto-status-info">
          · 今日已执行 {{ autoStatus.executed_count }} 笔
        </span>
        <span v-if="autoStatus?.pending_count > 0" class="auto-status-info pending">
          · {{ autoStatus.pending_count }} 笔待执行
        </span>
        <span v-if="autoStatus?.suggestions_generated === false && marketStatus === 'open'" class="auto-status-info warn">
          · 今日建议未生成
        </span>
      </div>

      <!-- ===== 3. Chart Area ===== -->
      <div class="card" v-if="account?.initialized">
        <div class="chart-toolbar">
          <div class="chart-tabs">
            <button class="tab-btn" :class="{ active: chartType === 'intraday' }" @click="switchChart('intraday')">📈 分时走势</button>
            <button class="tab-btn" :class="{ active: chartType === 'equity' }" @click="switchChart('equity')">📊 资金曲线</button>
          </div>
          <div class="chart-controls" v-if="chartType === 'intraday' && wl.length">
            <select v-model="chartStock" @change="onChartStockChange" class="chart-select">
              <option value="" disabled>选择股票</option>
              <option v-for="s in wl" :key="s.code" :value="s.code">{{ s.name || s.code }} ({{ s.code }})</option>
            </select>
            <input type="date" v-model="chartDate" @change="onChartDateChange" :max="todayStr" class="chart-date" />
            <button class="btn-icon-refresh" @click="refreshIntraday" :disabled="refreshing" title="采集并刷新分时数据">
              <span class="refresh-icon" :class="{ spinning: refreshing }">&#x21bb;</span>
            </button>
          </div>
          <div class="chart-controls" v-else-if="chartType === 'equity'">
            <button v-for="d in [30, 90, 180]" :key="d" class="tab-btn"
              :class="{ active: equityDays === d }" @click="switchEquityDays(d)">
              {{ d }}天
            </button>
          </div>
        </div>
        <div class="chart-wrap" style="height:300px;position:relative">
          <canvas ref="chartCanvas" style="display:block;width:100%;height:100%"></canvas>
        </div>
        <div v-if="chartType === 'intraday' && intradayData.length" class="chart-info">
          {{ intradayData[0]?.timestamp?.slice(11,16) || '' }} - {{ intradayData[intradayData.length-1]?.timestamp?.slice(11,16) || '' }} ({{ intradayData.length }} 个数据点)
        </div>
        <div v-else-if="chartType === 'intraday' && chartStock" class="empty">该日期暂无分时数据</div>
        <div v-else-if="chartType === 'intraday' && !chartStock" class="empty">请选择股票查看分时走势</div>
        <div v-else-if="chartType === 'equity' && !equityCurve.length" class="empty">暂无资金曲线数据</div>
      </div>

      <!-- ===== 4. Data Section ===== -->
      <div class="card">
        <div class="data-tabs">
          <button class="tab-btn" :class="{ active: dataTab === 'suggestions' }" @click="dataTab = 'suggestions'">📋 今日交易结果</button>
          <button class="tab-btn" :class="{ active: dataTab === 'trades' }" @click="dataTab = 'trades'">📜 交易记录</button>
          <button class="tab-btn" :class="{ active: dataTab === 'positions' }" @click="dataTab = 'positions'">📦 虚拟持仓</button>
          <button class="tab-btn" :class="{ active: dataTab === 'history' }" @click="switchToHistory">📆 历史建议</button>
        </div>

        <!-- 4a. Today's Suggestions -->
        <template v-if="dataTab === 'suggestions'">
          <div class="section-title">
            <span>{{ suggestions.length ? '算法自动生成的交易信号与执行结果' : '当前日期暂无交易结果' }}</span>
            <span v-if="suggestions.length" style="font-size:11px;color:#9ca3af;font-weight:400">
              共 {{ suggestions.length }} 条信号，{{ executedCount }} 笔已执行
            </span>
          </div>
          <table v-if="suggestions.length" class="paper-table">
            <thead>
              <tr>
                <th>股票名称</th><th>代码</th><th>操作</th><th>方向</th>
                <th>数量</th><th>条件价</th><th>执行价</th><th>置信度</th><th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="sug in suggestions" :key="sug.code">
                <td>{{ sug.name || sug.code }}</td>
                <td>{{ sug.code }}</td>
                <td><span class="badge" :class="sug.action">{{ actionText(sug) }}</span></td>
                <td :class="dirClass(sug.direction)">{{ dirText(sug.direction) }}</td>
                <td>{{ sug.qty ? sug.qty + '股' : '--' }}</td>
                <td>
                  <span v-if="sug.entry_zone && sug.entry_zone > 0" class="entry-zone">¥{{ fmt(sug.entry_zone) }}</span>
                  <span v-else class="entry-zone none">--</span>
                </td>
                <td>¥{{ sug.price ? fmt(sug.price) : '--' }}</td>
                <td>{{ pct(sug.confidence) }}%</td>
                <td class="reason-cell" :title="sug.reason || ''">{{ fmtReason(sug) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty">{{ chartDate === todayStr ? '今日暂无自动交易结果' : chartDate + ' 暂无交易结果' }}</div>
        </template>

        <!-- 4b. Trade History -->
        <template v-if="dataTab === 'trades'">
          <div class="trade-search">
            <input v-model="tradeFilterCode" placeholder="搜索代码..." class="input" style="width:140px"
              @keyup.enter="searchTrades">
            <button class="tab-btn" @click="searchTrades" :disabled="tradesLoading">🔍 查询</button>
            <span v-if="tradesLoading" style="font-size:12px;color:#6b7280">加载中...</span>
            <span v-else style="font-size:12px;color:#6b7280">共 {{ tradesTotal }} 条</span>
          </div>
          <table v-if="trades.length" class="paper-table">
            <thead>
              <tr>
                <th>日期</th><th>股票</th><th>方向</th><th>数量</th>
                <th>价格</th><th>手续费</th><th>发生金额</th><th>盈亏</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in trades" :key="t.id">
                <td>{{ t.date }}</td>
                <td>{{ t.name || t.code }}<br><span class="code-sub">{{ t.code }}</span></td>
                <td :class="t.direction==='buy'?'up':'down'">{{ t.direction==='buy'?'买入':'卖出' }}</td>
                <td>{{ t.qty }}股</td>
                <td>¥{{ fmt(t.price) }}</td>
                <td>¥{{ fmt((t.commission||0)+(t.stamp_tax||0)) }}</td>
                <td :class="t.direction==='buy'?'down':'up'">{{ t.direction==='sell' ? '+' : '-' }}¥{{ fmtMoney(t.settlement) }}</td>
                <td v-if="t.realized_pnl!=null" :class="pnlClass(t.realized_pnl)">
                  {{ pnlSign(t.realized_pnl) }}¥{{ fmtMoney(Math.abs(t.realized_pnl)) }}
                </td>
                <td v-else>—</td>
              </tr>
            </tbody>
          </table>
          <div v-if="trades.length && tradesTotal > tradesLimit" class="pagination">
            <button class="tab-btn" :disabled="tradesOffset <= 0" @click="prevPage">← 上一页</button>
            <span style="font-size:12px;color:#6b7280">
              第 {{ Math.floor(tradesOffset / tradesLimit) + 1 }} / {{ Math.ceil(tradesTotal / tradesLimit) }} 页
            </span>
            <button class="tab-btn" :disabled="tradesOffset + tradesLimit >= tradesTotal" @click="nextPage">下一页 →</button>
          </div>
          <div v-else-if="tradesSearched" class="empty">无匹配交易记录</div>
          <div v-else class="empty">点击"查询"加载交易记录</div>
        </template>

        <!-- 4c. Positions -->
        <template v-if="dataTab === 'positions'">
          <div v-if="positions.length" class="section-title">
            <span>虚拟持仓 <span style="font-size:12px;color:#f59e0b;font-weight:400">(橙色标识)</span></span>
          </div>
          <table v-if="positions.length" class="paper-table">
            <thead>
              <tr>
                <th>股票</th><th>代码</th><th>持仓量</th><th>成本价</th>
                <th>现价</th><th>市值</th><th>浮盈亏</th>
              </tr>
            </thead>
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
        </template>

        <!-- 4d. History Suggestions -->
        <template v-if="dataTab === 'history'">
          <div class="section-title">
            <span>历史建议记录 <span style="font-size:12px;color:#6b7280;font-weight:400">（每日生成时的初始建议）</span></span>
          </div>
          <div v-if="suggestionsHistoryLoading" class="empty">加载中...</div>
          <div v-else-if="suggestionsHistory.length" class="history-date-selector">
            <input type="date" v-model="historySearchDate" :max="todayStr" class="chart-date"
              @change="onHistoryDateChange" />
            <button v-if="historySearchDate" class="tab-btn tab-sm" @click="clearHistoryDate">清除筛选</button>
            <span style="font-size:12px;color:#6b7280;margin-left:8px">
              共 {{ filteredHistory.length }} 条记录
            </span>
          </div>
          <table v-if="suggestionsHistory.length" class="paper-table">
            <thead>
              <tr>
                <th>日期</th><th>股票名称</th><th>代码</th><th>操作</th><th>方向</th>
                <th>数量</th><th>条件价</th><th>执行价</th><th>置信度</th><th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="h in filteredHistory" :key="h.id">
                <td>{{ h.date }}</td>
                <td>{{ h.name || h.code }}</td>
                <td>{{ h.code }}</td>
                <td><span class="badge" :class="h.action">{{ actionText(h) }}</span></td>
                <td :class="dirClass(h.direction)">{{ dirText(h.direction) }}</td>
                <td>{{ h.qty ? h.qty + '股' : '--' }}</td>
                <td>
                  <span v-if="h.entry_zone && h.entry_zone > 0" class="entry-zone">¥{{ fmt(h.entry_zone) }}</span>
                  <span v-else class="entry-zone none">--</span>
                </td>
                <td>¥{{ h.price ? fmt(h.price) : '--' }}</td>
                <td>{{ pct(h.confidence) }}%</td>
                <td class="reason-cell" :title="h.reason || ''">{{ h.reason || '--' }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else-if="!suggestionsHistoryLoading" class="empty">暂无历史建议数据</div>
        </template>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { storeToRefs } from 'pinia'
import { usePaperStore } from '@/stores/paper.js'
import { useDataStore } from '@/stores/data.js'

const store = usePaperStore()
const dataStore = useDataStore()
const {
  account, positions, suggestions, trades, tradesTotal,
  performance: perf, equityCurve,
  intradayData, intradayCode, selectedDate, marketStatus,
  autoStatus,
  suggestionsHistory, suggestionsHistoryLoading,
} = storeToRefs(store)
const {
  loadAccount, loadPositions, loadSuggestions, loadTrades, loadPerformance,
  resetAccount, loadIntraday,
  verifyConsistency, verifyResult, verifyLoading,
  collectAndRefreshIntraday,
  generateSuggestions, refreshAutoStatus, loadSuggestionsHistory,
} = store

// ── Reactive state ──
const loading = ref(false)
const bannerMsg = ref('')
const bannerType = ref('error')
const initLoading = ref(false)
const genLoading = ref(false)
const refreshing = ref(false)
const showVerifyDetail = ref(false)
let autoPollTimer = null

// Chart state
const chartCanvas = ref(null)
const chartType = ref('intraday')       // 'intraday' | 'equity'
const chartStock = ref('')                // selected stock code for intraday
const chartDate = ref('')                 // selected date for intraday
const equityDays = ref(90)                // days window for equity curve
const todayStr = new Date().toISOString().slice(0, 10)
let chartInst = null

// Data tab state
const dataTab = ref('suggestions')        // 'suggestions' | 'trades' | 'positions' | 'history'
const historySearchDate = ref('')
const filteredHistory = computed(() => {
  if (!historySearchDate.value) return suggestionsHistory.value
  return suggestionsHistory.value.filter(h => h.date === historySearchDate.value)
})

// Trade search / pagination
const tradeFilterCode = ref('')
const tradesLoading = ref(false)
const tradesSearched = ref(false)
const tradesLimit = 50
const tradesOffset = ref(0)

// Watchlist from data store
const wl = computed(() => dataStore.watchlist || [])

const marketStatusText = computed(() => {
  const m = {
    'open': '交易中',
    'closed': '已闭市',
    'non_trading_day': '非交易日',
  }
  return m[marketStatus.value] || marketStatus.value
})

const executedCount = computed(() => suggestions.value.filter(s => s.executed === 1).length)

// ── Lifecycle ──
onMounted(async () => {
  loading.value = true
  try {
    if (!dataStore.watchlist.length) await dataStore.fetchAll()
    chartDate.value = todayStr
    // Load all paper data in parallel
    await Promise.all([
      loadAccount(),
      loadPerformance(equityDays.value),
      loadTrades('', tradesLimit, 0),
    ])
    await Promise.all([
      loadPositions(),
      loadSuggestions('', todayStr),
    ])
    // Init intraday chart with first watchlist stock
    if (wl.value.length > 0) {
      chartStock.value = wl.value[0].code
      await loadIntraday(chartStock.value, todayStr)
    }
    // Load auto-executor status
    await refreshAutoStatus()
  } catch (e) {
    showBanner('error', '加载数据失败: ' + (e.message || '网络错误'))
  }
  // 先释放 loading（DOM 才会渲染 canvas），再绘制图表
  loading.value = false
  await nextTick()
  renderChart()

  // 启动自动轮询（交易时段每60秒刷新数据和 autoStatus）
  // 注意：loadSuggestions 始终用 todayStr，不要用 chartDate.value，否则切换到非今日日期时会清空今日建议
  autoPollTimer = setInterval(async () => {
    if (marketStatus.value === 'open') {
      await Promise.all([
        loadAccount(),
        loadPositions(),
        loadPerformance(equityDays.value),
        loadSuggestions('', todayStr),
        refreshAutoStatus(),
      ])
      // 刷新分时数据
      if (chartStock.value) {
        await loadIntraday(chartStock.value, chartDate.value || todayStr)
        await nextTick()
        renderChart()
      }
    } else {
      await refreshAutoStatus()
    }
  }, 60000)
})

onUnmounted(() => {
  if (autoPollTimer) {
    clearInterval(autoPollTimer)
    autoPollTimer = null
  }
})

// ── Chart rendering watcher ──
watch([intradayData, equityCurve, chartCanvas, chartType], () => {
  nextTick(() => {
    try { renderChart() } catch (e) { console.warn('chart render:', e) }
  })
})

function renderChart() {
  const canvas = chartCanvas.value
  if (!canvas) return

  // Destroy existing chart
  if (chartInst) { chartInst.destroy(); chartInst = null }

  if (chartType.value === 'intraday') {
    renderIntradayChart(canvas)
  } else {
    renderEquityChart(canvas)
  }
}

function renderIntradayChart(canvas) {
  const data = intradayData.value
  if (!data || !data.length) return
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
        yAxisID: 'y',
      }, {
        label: '成交量',
        data: vols,
        borderColor: 'rgba(107, 114, 128, 0.3)',
        backgroundColor: 'rgba(107, 114, 128, 0.15)',
        borderWidth: 0,
        pointRadius: 0,
        fill: true,
        yAxisID: 'y1',
        order: 1,
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
              if (ctx.dataset.label === '成交量') return ''
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
        x: { ticks: { maxTicksLimit: 8, maxRotation: 0 } },
        y: {
          min: Math.floor(minPrice * 0.999 * 100) / 100,
          max: Math.ceil(maxPrice * 1.001 * 100) / 100,
          ticks: { callback: v => '¥' + v.toFixed(2) },
          position: 'left',
        },
        y1: {
          position: 'right',
          grid: { display: false },
          ticks: { display: false },
        },
      },
    },
  })
}

function renderEquityChart(canvas) {
  const data = equityCurve.value
  if (!data || !data.length) return
  const C = window.Chart
  if (!C) { console.warn('Chart.js not loaded'); return }

  const labels = data.map(e => e.date)
  const values = data.map(e => e.value)
  const initialVal = data[0]?.value || 0

  chartInst = new C(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: '纸面账户',
          data: values,
          borderColor: '#2563eb',
          backgroundColor: 'rgba(37,99,235,.1)',
          fill: true,
          tension: .3,
          pointRadius: values.length > 1 ? 0 : 4,
        },
        {
          label: '买入持有',
          data: values.map(() => initialVal),
          borderColor: '#9ca3af',
          borderDash: [5, 5],
          fill: false,
          tension: .3,
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { position: 'top' },
        tooltip: {
          backgroundColor: 'rgba(0,0,0,0.8)',
          titleColor: '#fff',
          bodyColor: '#fff',
          padding: 10,
          cornerRadius: 6,
          callbacks: {
            title: items => labels[items[0]?.dataIndex] || '',
            label: ctx => {
              const v = ctx.raw
              const pct = initialVal > 0 ? ((v - initialVal) / initialVal * 100) : 0
              const sign = pct >= 0 ? '+' : ''
              return `${ctx.dataset.label}: ¥${(v/10000).toFixed(2)}万 (${sign}${pct.toFixed(1)}%)`
            },
          },
        },
      },
      scales: {
        y: { ticks: { callback: v => '¥' + (v/10000).toFixed(1) + '万' } },
      },
    },
  })
}

// ── Chart actions ──
function switchChart(type) {
  chartType.value = type
  nextTick(() => renderChart())
}

async function onChartStockChange() {
  if (!chartStock.value) return
  await loadIntraday(chartStock.value, chartDate.value || todayStr)
  await loadSuggestions('', chartDate.value || todayStr)
  await nextTick()
  renderChart()
}

async function onChartDateChange() {
  if (!chartStock.value) return
  const date = chartDate.value || todayStr
  chartDate.value = date
  await loadIntraday(chartStock.value, date)
  await loadSuggestions('', date)
  await nextTick()
  renderChart()
}

async function refreshIntraday() {
  if (!chartStock.value || refreshing.value) return
  refreshing.value = true
  const date = chartDate.value || todayStr
  bannerMsg.value = ''
  bannerType.value = 'error'
  try {
    // Step 1: trigger data collection on the backend
    const r = await collectAndRefreshIntraday()
    if (!r?.success) {
      showBanner('error', '数据采集失败: ' + (r?.error || '后端未响应'))
      return
    }
    // Step 2: reload intraday data from DB
    await loadIntraday(chartStock.value, date)
    await loadSuggestions('', date)
    await nextTick()
    renderChart()
    showBanner('success', '✅ 分时数据已采集并刷新 (' + date + ', ' + intradayData.value.length + ' 个数据点)')
    setTimeout(() => { if (bannerType.value === 'success') bannerMsg.value = '' }, 5000)
  } catch (e) {
    showBanner('error', '刷新异常: ' + (e.message || '未知错误'))
  } finally {
    refreshing.value = false
  }
}

async function switchEquityDays(d) {
  equityDays.value = d
  tradeFilterCode.value = ''
  tradesOffset.value = 0
  await Promise.all([
    loadPerformance(d),
    loadTrades('', tradesLimit, 0),
  ])
  if (chartType.value === 'equity') {
    nextTick(() => renderChart())
  }
}

// ── Account actions ──
async function initAccount() {
  initLoading.value = true
  bannerMsg.value = ''
  try {
    const r = await resetAccount(100000)
    if (!r?.success) {
      showBanner('error', '初始化失败: ' + (r?.error || 'API返回异常'))
      return
    }
    // Full refresh: account + positions + performance
    await Promise.all([loadAccount(), loadPositions(), loadPerformance(equityDays.value)])
    chartDate.value = todayStr
    if (chartStock.value) {
      await loadIntraday(chartStock.value, todayStr)
    }
    // 显式重绘分时图表
    await nextTick()
    renderChart()
    showBanner('success', '✅ 虚拟账户已初始化，初始资金 ¥100,000 (历史交易记录已保留)')
    setTimeout(() => { if (bannerType.value === 'success') bannerMsg.value = '' }, 5000)
  } catch (e) {
    showBanner('error', '初始化异常: ' + (e.message || '未知错误'))
  } finally {
    initLoading.value = false
  }
}

async function confirmReset() {
  if (!confirm('确认重置虚拟账户？所有持仓将被清空，现金恢复为 ¥100,000。交易历史记录将保留。')) return
  loading.value = true
  bannerMsg.value = ''
  try {
    const r = await resetAccount(100000)
    if (!r?.success) {
      showBanner('error', '重置失败: ' + (r?.error || 'API返回异常'))
      return
    }
    // Full refresh
    await Promise.all([loadAccount(), loadPositions(), loadPerformance(equityDays.value)])
    // 显式重绘分时图表
    if (chartStock.value) {
      await loadIntraday(chartStock.value, todayStr)
      await nextTick()
      renderChart()
    }
    showBanner('success', '✅ 虚拟账户已重置')
    setTimeout(() => { if (bannerType.value === 'success') bannerMsg.value = '' }, 5000)
  } catch (e) {
    showBanner('error', '重置失败: ' + (e.message || '未知错误'))
  }
  loading.value = false
}

async function switchToHistory() {
  dataTab.value = 'history'
  historySearchDate.value = ''
  await loadSuggestionsHistory('', '', 60)
}

function onHistoryDateChange() {
  // 日历控件 v-model 已自动更新 historySearchDate
}

function clearHistoryDate() {
  historySearchDate.value = ''
}

async function handleGenerate() {
  genLoading.value = true
  bannerMsg.value = ''
  try {
    const r = await generateSuggestions()
    if (!r?.success) {
      showBanner('error', '生成失败: ' + (r?.error || 'API返回异常'))
      return
    }
    await refreshAutoStatus()
    await Promise.all([
      loadSuggestions('', todayStr),
    ])
    showBanner('success', '✅ ' + (r.message || '建议生成完成'))
    setTimeout(() => { if (bannerType.value === 'success') bannerMsg.value = '' }, 5000)
  } catch (e) {
    showBanner('error', '生成异常: ' + (e.message || '未知错误'))
  } finally {
    genLoading.value = false
  }
}

// ── Data verify ──
async function doVerify() {
  showVerifyDetail.value = true
  await verifyConsistency()
}

// ── Trade history ──
async function searchTrades() {
  tradesLoading.value = true
  tradesSearched.value = true
  tradesOffset.value = 0
  try {
    await loadTrades(tradeFilterCode.value || '', tradesLimit, 0)
  } catch (e) {
    console.warn('searchTrades failed:', e)
  }
  tradesLoading.value = false
}

async function prevPage() {
  if (tradesOffset.value <= 0) return
  tradesOffset.value = Math.max(0, tradesOffset.value - tradesLimit)
  await loadTrades(tradeFilterCode.value || '', tradesLimit, tradesOffset.value)
}

async function nextPage() {
  if (tradesOffset.value + tradesLimit >= tradesTotal.value) return
  tradesOffset.value += tradesLimit
  await loadTrades(tradeFilterCode.value || '', tradesLimit, tradesOffset.value)
}

// ── Helpers ──
function showBanner(type, msg) {
  bannerType.value = type
  bannerMsg.value = msg
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
function fmtNum(v) { return v != null ? Number(v).toFixed(2) : '--' }
function pct(v) { return v != null ? Math.round(v * 100) : '--' }
function pnlClass(v) { return Number(v) > 0 ? 'up' : Number(v) < 0 ? 'down' : 'flat' }
function pnlSign(v) { return Number(v) > 0 ? '+' : Number(v) < 0 ? '' : '' }
function dirClass(d) { return d === 'bullish' ? 'up' : d === 'bearish' ? 'down' : '' }
function dirText(d) { return d === 'bullish' ? '看涨 ↑' : d === 'bearish' ? '看跌 ↓' : '中性 →' }

function actionText(sug) {
  const a = sug.action || 'hold'
  const done = sug.executed === 1
  if (a === 'sell') {
    if (done) return '已卖出'
    // 检查该股票是否有实际持仓，无持仓则不应显示待卖出
    const hasPosition = positions.value.some(p => p.code === sug.code && p.qty > 0)
    if (!hasPosition) return '无持仓'
    return '待卖出'
  }
  if (a === 'buy') return done ? '已买入' : '待买入'
  if (a === 'watch') return '关注'
  return '观望'
}
function fmtReason(sug) {
  const r = (sug.reason || '').toLowerCase()
  if (r.includes('no valid market price')) return '暂无有效市价'
  const dirMap = { bullish: '看涨', bearish: '看跌', neutral: '中性' }
  const dt = dirMap[sug.direction] || ''
  const conf = pct(sug.confidence)
  const ez = sug.entry_zone && sug.entry_zone > 0 ? `，条件价 ¥${fmt(sug.entry_zone)}` : ''
  if (sug.action === 'sell') {
    const hasPosition = positions.value.some(p => p.code === sug.code && p.qty > 0)
    if (!hasPosition) return `预测${dt}(信心${conf}%)，但当前无持仓，无法卖出`
    if (sug.executed === 1) return `预测${dt}，信心${conf}%，已卖出`
    return `预测${dt}，信心${conf}%${ez}，系统将自动监控价格`
  }
  if (sug.action === 'buy') {
    if (sug.executed === 1) return `预测${dt}，信心${conf}%，已买入`
    return `预测${dt}，信心${conf}%${ez}，系统将自动监控价格`
  }
  if (sug.action === 'watch') return `看好${dt}但未达买入条件`
  if (sug.direction === 'neutral' || conf < 50) return '信号不明确，暂观望'
  return `预测${dt}但无持仓，暂无法操作`
}
</script>

<style scoped>
/* ── Layout ── */
.page-content { max-width: 1200px; margin: 0 auto; padding: 24px; }

/* ── Status Banners ── */
.status-banner {
  padding: 10px 16px; border-radius: 8px; margin-bottom: 12px;
  font-size: 13px; text-align: center; font-weight: 500;
}
.status-closed { background: #fffbeb; border: 1px solid #fde68a; color: #92400e; }
.status-non-trading { background: #f3f4f6; border: 1px solid #d1d5db; color: #6b7280; }

/* ── Error / Success Banner ── */
.banner {
  padding: 10px 16px; border-radius: 8px; margin-bottom: 12px;
  font-size: 13px; cursor: pointer; text-align: center;
}
.banner.error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
.banner.success { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }

/* ── Account Card ── */
.account-card { border-left: 4px solid #f59e0b; }
.account-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  flex-wrap: wrap; gap: 12px; margin-bottom: 16px;
}
.account-meta { font-size: 12px; color: #6b7280; }
.account-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.account-metrics {
  display: flex; gap: 32px; flex-wrap: wrap; padding-top: 12px;
  border-top: 1px solid #f3f4f6;
}
.metric-item { display: flex; flex-direction: column; gap: 4px; }
.metric-label { font-size: 11px; color: #6b7280; }
.metric-value { font-size: 22px; font-weight: 700; line-height: 1.2; }
.metric-chg { font-size: 14px; font-weight: 400; }
.account-empty {
  display: flex; align-items: center; gap: 12px;
  padding: 20px 0 4px;
}

/* ── Tags ── */
.tag { display: inline-block; padding: 1px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.tag-open { background: #dcfce7; color: #166534; }
.tag-closed { background: #fef3c7; color: #92400e; }

/* ── Buttons ── */
.btn-init { background: #16a34a !important; color: #fff !important; border-color: #16a34a !important; }
.btn-gen { background: #7c3aed !important; color: #fff !important; border-color: #7c3aed !important; }
.btn-gen:disabled { opacity: .6 !important; cursor: default !important; }
.btn-reset { background: #f59e0b !important; color: #fff !important; border-color: #f59e0b !important; }
.btn-verify { background: #6b7280 !important; color: #fff !important; border-color: #6b7280 !important; }

/* ── Verify Result ── */
.verify-result {
  margin-top: 12px; padding: 10px 14px; border-radius: 8px;
  font-size: 13px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.verify-ok { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }
.verify-fail { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
.verify-toggle {
  margin-left: auto; cursor: pointer; font-size: 12px;
  text-decoration: underline; opacity: .7;
}
.verify-toggle:hover { opacity: 1; }
.verify-detail { width: 100%; margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(0,0,0,.08); }
.verify-check { display: flex; align-items: center; gap: 6px; padding: 3px 0; font-size: 12px; }
.verify-check .ok { color: #16a34a; font-weight: 700; }
.verify-check .fail { color: #dc2626; font-weight: 700; }
.verify-detail-text { color: #6b7280; font-size: 11px; margin-left: 4px; }
.verify-errors { margin-top: 6px; }
.verify-error-item { padding: 4px 8px; background: rgba(220,38,38,.06); border-radius: 4px; margin-bottom: 3px; font-size: 12px; }

/* ── Auto-Executor Status ── */
.auto-status-bar {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 14px; margin-bottom: 16px;
  background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px;
  font-size: 13px; color: #0369a1; flex-wrap: wrap;
}
.auto-status-dot {
  width: 8px; height: 8px; border-radius: 50%; display: inline-block;
}
.auto-status-dot.running { background: #16a34a; box-shadow: 0 0 4px rgba(22,163,74,.5); }
.auto-status-dot.stopped { background: #9ca3af; }
.auto-status-info { color: #6b7280; font-size: 12px; }
.auto-status-info.pending { color: #f59e0b; font-weight: 600; }
.auto-status-info.warn { color: #dc2626; font-weight: 600; }

/* ── Entry Zone (条件价) ── */
.entry-zone { font-size: 12px; color: #7c3aed; font-weight: 600; }
.entry-zone.none { color: #d1d5db; font-weight: 400; }

/* ── Stats Row ── */
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 20px; }
.stat-mini { background:#fff; border-radius:10px; padding:14px 16px; box-shadow:0 1px 3px rgba(0,0,0,.08); }
.stat-mini span { font-size:11px; color:#6b7280; display:block; margin-bottom:4px; }
.stat-mini b { font-size:18px; font-weight:700; }

/* ── Chart Area ── */
.chart-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 12px; margin-bottom: 12px;
}
.chart-tabs { display: flex; gap: 8px; }
.chart-controls { display: flex; gap: 8px; align-items: center; }
.chart-select, .chart-date {
  padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px;
}
.chart-info { font-size: 11px; color: #9ca3af; margin-top: 4px; }

/* ── Data Section ── */
.data-tabs { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.section-title {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 12px; font-size: 13px; color: #6b7280;
}

/* ── Trade Search ── */
.trade-search {
  display: flex; gap: 8px; margin-bottom: 12px;
  flex-wrap: wrap; align-items: center;
}

/* ── Pagination ── */
.pagination {
  display: flex; align-items: center; justify-content: center;
  gap: 12px; padding: 16px 0 4px;
}

/* ── Tables ── */
.paper-table { width: 100%; border-collapse: collapse; }
.paper-table thead { background: rgba(245,158,11,.08); }
.paper-table th, .paper-table td {
  padding: 8px 10px; text-align: left; font-size: 13px; white-space: nowrap;
}
.paper-table th { font-weight: 600; color: #4b5563; }
.paper-table tbody tr { border-bottom: 1px solid #f3f4f6; }
.paper-table tbody tr:last-child { border-bottom: none; }
.paper-table tbody tr:hover { background: rgba(245,158,11,.04); }
.code-sub { font-size: 11px; color: #9ca3af; }
.reason-cell { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ── Badges ── */
.badge { font-size: 11px; padding: 2px 10px; border-radius: 10px; font-weight: 600; display: inline-block; }
.badge.buy { background: #fecaca; color: #991b1b; }
.badge.sell { background: #bbf7d0; color: #166534; }
.badge.watch { background: #e5e7eb; color: #4b5563; }
.badge.hold { background: #e5e7eb; color: #4b5563; }

/* ── Icon Refresh Button ── */
.btn-icon-refresh {
  display: inline-flex; align-items: center; justify-content: center;
  width: 34px; height: 34px; border: 1px solid #d1d5db; border-radius: 8px;
  background: #fff; cursor: pointer; font-size: 16px; transition: all .15s;
}
.btn-icon-refresh:hover { background: #f3f4f6; border-color: #9ca3af; }
.btn-icon-refresh:disabled { opacity: .5; cursor: not-allowed; }
.btn-icon-refresh .refresh-icon { display: inline-block; }
.btn-icon-refresh .refresh-icon.spinning { animation: btnSpin 1s linear infinite; }
@keyframes btnSpin { to { transform: rotate(360deg); } }

/* ── Loading ── */
.loading { display: flex; justify-content: center; padding: 60px 0; }
.spinner {
  width: 32px; height: 32px; border: 3px solid #e5e7eb;
  border-top-color: #2563eb; border-radius: 50%; animation: spin .6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Empty state ── */
.empty {
  padding: 32px 0; text-align: center; color: #9ca3af; font-size: 14px;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .page-content { padding: 16px; }
  .account-metrics { gap: 16px; }
  .metric-value { font-size: 18px; }
  .chart-toolbar { flex-direction: column; align-items: flex-start; }
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
  .paper-table { font-size: 12px; }
  .paper-table th, .paper-table td { padding: 6px 8px; }
}
</style>
