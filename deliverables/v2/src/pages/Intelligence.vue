<template>
  <div class="page-content">
    <div v-if="data.loading && !data.watchlist.length" class="loading"><div class="spinner"></div></div>
    <template v-else>
      <div class="top-bar">
        <div class="tab-bar">
          <button v-for="s in data.watchlist" :key="s.code" class="tab-btn" :class="{ active: activeCode === s.code }" @click="switchStock(s.code)">{{ s.name }}</button>
        </div>
        <span class="right-actions">
          <button class="tab-btn refresh-btn" :class="{ 'refresh-running': refreshing }" @click="triggerPredict" :disabled="refreshing">
            <span class="btn-icon" :class="{ spinning: refreshing }">{{ refreshing ? '⏳' : '🔄' }}</span>
            <span>{{ refreshing ? '刷新中…' : '刷新' }}</span>
          </button>
          <span class="status-text" :class="{ 'status-ok': status === '✅ 完成', 'status-err': status?.startsWith('❌') }">{{ status }}</span>
        </span>
      </div>

      <template v-if="activeCode">
        <!-- Next Day + Key Levels -->
        <div class="top-grid">
          <div class="dp-card dp-next-card">
            <h3>🔮 次日预测</h3>
            <div v-if="todayPred">
              <div style="font-size:13px;color:#6b7280">预测 {{ todayPred.date }} 次日
                <span v-if="todayPred.actual?.next_day_direction_hit===true" style="color:#16a34a">✓ 命中</span>
                <span v-else-if="todayPred.actual?.next_day_direction_hit===false" style="color:#dc2626">✗ 未命中</span>
              </div>
              <div class="dp-next-dir" :class="todayPred.next_day?.direction">{{ dirIcon(todayPred.next_day?.direction) }} {{ dirText(todayPred.next_day?.direction) }}</div>
              <div class="dp-next-range">{{ fmt(todayPred.next_day?.low) }} ~ {{ fmt(todayPred.next_day?.high) }}</div>
              <div class="dp-confidence" :class="confLevel(todayPred.next_day?.confidence)">信心 {{ pct(todayPred.next_day?.confidence) }}%</div>
              <div style="font-size:12px;color:#6b7280;margin-top:10px;text-align:left">{{ todayPred.next_day?.advice }}</div>
              <div v-if="todayPred.actual?.close!=null" class="actual-box">
                <b>实际:</b> 开 {{ fmt(todayPred.actual.open) }} 高 {{ fmt(todayPred.actual.high) }} 低 {{ fmt(todayPred.actual.low) }} 收 {{ fmt(todayPred.actual.close) }}
              </div>
            </div>
            <div v-else class="dp-empty">暂无预测</div>
          </div>
          <div class="dp-card">
            <h3>🎯 关键价位</h3>
            <div class="key-levels">
              <div>现价: <b :class="data.quotes[activeCode]?.change>=0?'up':'down'">{{ fmt(data.quotes[activeCode]?.price) }}</b></div>
              <div>加仓 ≤ <span class="down">{{ fmt(curPrice * cfg.buy_multiplier) }}</span></div>
              <div>减仓 ≥ <span class="up">{{ fmt(curPrice * cfg.sell_multiplier) }}</span></div>
              <div>股息率 <span class="up">{{ fmt(data.quotes[activeCode]?.dy) }}%</span></div>
            </div>
          </div>
        </div>

        <!-- 10-Day chart -->
        <div class="card">
          <h2>📈 10日预测走势</h2>
          <div class="chart-box" style="height:360px"><canvas ref="predChartCanvas"></canvas></div>
        </div>

        <!-- Advice -->
        <div class="card" v-if="todayPred">
          <h2>💡 综合操作建议</h2>
          <div class="advice" v-html="adviceText"></div>
        </div>

        <!-- Signals collapse -->
        <div class="card">
          <div class="collapse-header" @click="showSignals = !showSignals">
            <span>📡 技术信号 · 学习统计</span><span class="arrow" :class="{ open: showSignals }">▶</span>
          </div>
          <div v-if="showSignals" class="collapse-body open">
            <div class="sig-grid" v-if="todayPred">
              <div v-for="s in signalList" :key="s.key" class="sig-item">
                <div class="sig-name">{{ s.label }}</div>
                <div class="sig-val" :class="'dir-'+s.dir">{{ s.val }}</div>
              </div>
            </div>
            <div v-if="accStats" class="acc-row">
              <b>准确率(近20):</b> 方向 {{ accStats.last_20?.direction?.rate != null ? Number(accStats.last_20.direction.rate).toFixed(0) : '--' }}%<span class="acc-detail">({{ accStats.last_20?.direction?.correct || 0 }}/{{ accStats.last_20?.direction?.total || 0 }}命中)</span> | 区间 {{ accStats.last_20?.range?.rate != null ? Number(accStats.last_20.range.rate).toFixed(0) : '--' }}%<span class="acc-detail">({{ accStats.last_20?.range?.correct || 0 }}/{{ accStats.last_20?.range?.total || 0 }}命中)</span>
            </div>
          </div>
        </div>

        <!-- History timeline -->
        <div class="card">
          <h2>📅 预测 vs 实际</h2>
          <div class="dp-timeline" v-if="timelineItems.length">
            <div v-for="(p, i) in timelineItems" :key="i"
              class="dp-tl-item" :class="tlClass(p)">
              <div class="dp-tl-date">{{ p.date?.substring(5) }}</div>
              <div class="dp-tl-dir" :class="p.next_day?.direction">{{ dirIcon(p.next_day?.direction) }}</div>
              <div class="dp-tl-range">{{ p.next_day?.low != null ? fmt(p.next_day.low)+'~'+fmt(p.next_day.high) : '--' }}</div>
              <div class="dp-tl-status" :class="tlStatus(p)">{{ tlLabel(p) }}</div>
            </div>
          </div>
          <div v-else class="dp-empty">暂无预测数据</div>
          <div class="tl-legend">
            <span class="tl-dot hit"></span> 命中 <span class="tl-dot miss"></span> 未命中 <span class="tl-dot pending"></span> 待验证 <span class="tl-bar today"></span> 今天
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useDataStore } from '@/stores/data.js'
import { fmt, apiCall } from '@/api/client.js'

const data = useDataStore()
const activeCode = ref('')
const showSignals = ref(true)
const predChartCanvas = ref(null)
const refreshing = ref(false)
const status = ref('')
let predChart = null
let statusTimer = null

const today = new Date().toISOString().substring(0, 10)
const curPrice = computed(() => data.quotes[activeCode.value]?.price || 0)
const cfg = computed(() => data.config?.price_strategy || { buy_multiplier: 0.95, sell_multiplier: 1.10 })

const allPreds = computed(() =>
  (data.predictions || []).filter(p => p.code === activeCode.value).sort((a, b) => b.date.localeCompare(a.date))
)

const todayPred = computed(() => allPreds.value.find(p => p.date === today))

const adviceText = computed(() => {
  const nd = todayPred.value?.next_day
  if (!nd) return '暂无预测'
  const dy = data.quotes[activeCode.value]?.dy || 0
  if (nd.direction === 'bearish') return '<b style="color:#dc2626">短期看跌</b> → <b>等待下月加仓窗口</b>'
  if (nd.direction === 'bullish') return '<b style="color:#16a34a">短期看涨</b> → <b>耐心持有，选择最佳月份高位兑现</b>'
  return `<b style="color:#f59e0b">信号中性</b> → 股息率${fmt(dy)}%提供安全垫，<b>持有收息为主</b>`
})

const signalList = computed(() => {
  const sig = todayPred.value?.signals || {}
  const names = { macd:'MACD', rsi:'RSI', bollinger:'布林带', kdj:'KDJ', seasonal:'季节', atr:'ATR', money_flow:'资金', adx_trend:'ADX', obv_divergence:'OBV', vol_convergence:'波动率' }
  return Object.entries(names).map(([k, label]) => {
    const s = sig[k] || {}
    // Prefer formatted value string (e.g. "+0.52%", "K50 D50 J50"), fallback to raw/factor
    const displayVal = s.value || s.raw || s.factor
    const val = displayVal != null ? (typeof displayVal === 'number' ? displayVal.toFixed(2) : String(displayVal)) : '--'
    return { key: k, label, dir: s.direction || 'neutral', val }
  }).filter(s => s.val !== '--')
})

const accStats = computed(() => data.accuracyStats[activeCode.value] || null)

const timelineItems = computed(() => {
  const sorted = [...allPreds.value].sort((a, b) => a.date.localeCompare(b.date))
  const past = sorted.filter(p => p.actual?.next_day_direction_hit != null && p.date < today).slice(-10)
  const future = sorted.filter(p => p.date >= today).slice(0, 11)
  return past.concat(future)
})

function confLevel(c) { return c >= 0.7 ? 'high' : c >= 0.5 ? 'mid' : 'low' }
function pct(v) { return v != null ? (v * 100).toFixed(0) : '--' }
function dirIcon(d) { return d === 'bullish' ? '↑' : d === 'bearish' ? '↓' : '➡' }
function dirText(d) { return d === 'bullish' ? '看涨' : d === 'bearish' ? '看跌' : '中性' }
function tlClass(p) {
  const a = p.actual || {}
  if (a.next_day_direction_hit != null) return a.next_day_direction_hit ? 'hit' : 'miss'
  return p.date === today ? 'today pending' : 'pending'
}
function tlStatus(p) {
  const a = p.actual || {}
  if (a.next_day_direction_hit != null) return a.next_day_direction_hit ? 'hit' : 'miss'
  return p.date === today ? 'pending' : 'pending'
}
function tlLabel(p) {
  const a = p.actual || {}
  if (a.next_day_direction_hit != null) return a.next_day_direction_hit ? '命中' : '未命中'
  return p.date === today ? '预测中' : '待验证'
}

function switchStock(code) { activeCode.value = code }

function renderChart() {
  if (!predChartCanvas.value || !activeCode.value) return
  if (predChart) predChart.destroy()
  const Chart = window.Chart
  if (!Chart) return

  const klRaw = data.allKlineDaily[activeCode.value] || []
  const kl = klRaw.slice().reverse()
  const histSlice = kl.slice(-180)
  const histLabels = histSlice.map(k => k[0])
  const histClose = histSlice.map(k => k[2])

  const futurePreds = allPreds.value.filter(p => p.date >= today).sort((a, b) => a.date.localeCompare(b.date)).slice(0, 10)
  const predLabels = [], predClose = [], predHigh = [], predLow = []
  const lastClose = histClose[histClose.length - 1]
  futurePreds.forEach(p => {
    const nd = p.next_day || {}
    let ec = lastClose
    if (nd.direction === 'bullish') ec = nd.low + (nd.high - nd.low) * 0.55
    else if (nd.direction === 'bearish') ec = nd.high - (nd.high - nd.low) * 0.55
    else ec = (nd.high + nd.low) / 2
    predLabels.push(p.date); predClose.push(ec); predHigh.push(nd.high || ec); predLow.push(nd.low || ec)
  })

  const allLabels = histLabels.concat(predLabels)
  const predArr = new Array(histClose.length).fill(null)
  predArr[histClose.length - 1] = lastClose
  for (let i = 0; i < predClose.length; i++) predArr.push(predClose[i])

  const bandH = new Array(histClose.length).fill(null), bandL = new Array(histClose.length).fill(null)
  bandH[histClose.length - 1] = lastClose; bandL[histClose.length - 1] = lastClose
  for (let i = 0; i < predHigh.length; i++) { bandH.push(predHigh[i]); bandL.push(predLow[i]) }

  predChart = new Chart(predChartCanvas.value, {
    type: 'line',
    data: {
      labels: allLabels,
      datasets: [
        { label: '历史收盘', data: histClose.concat(new Array(predLabels.length).fill(null)), borderColor: '#2563eb', borderWidth: 2, pointRadius: 0, fill: false, order: 0 },
        ...(predClose.length ? [
          { label: '预测收盘', data: predArr, borderColor: '#f59e0b', borderWidth: 2.5, borderDash: [6, 3], pointRadius: 0, fill: false, order: 0 },
          { label: '预测上限', data: bandH, borderColor: 'rgba(245,158,11,.3)', borderWidth: 1, borderDash: [2,4], pointRadius: 0, fill: false, order: 1 },
          { label: '预测下限', data: bandL, borderColor: 'rgba(245,158,11,.3)', borderWidth: 1, borderDash: [2,4], pointRadius: 0, fill: '-1', backgroundColor: 'rgba(245,158,11,.08)', order: 1 },
        ] : []),
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 500 },
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { position: 'top', labels: { font: { size: 11 }, usePointStyle: true, filter: item => item.datasetIndex < 2 } } },
      scales: { x: { ticks: { font: { size: 9 }, maxTicksLimit: 20 } }, y: { ticks: { callback: v => '¥' + v.toFixed(2), font: { size: 10 } } } },
    },
  })
}

async function triggerPredict() {
  if (refreshing.value) return
  refreshing.value = true; status.value = '刷新中…'
  try {
    const r = await apiCall('POST', '/api/trigger/predict')
    if (r?.success) {
      await data.fetchAll()
      status.value = '✅ 完成'
    } else {
      status.value = '❌ ' + (r?.error || '预测失败')
    }
  } catch (e) { status.value = '❌ ' + (e.message || '网络错误') }
  refreshing.value = false
  if (statusTimer) clearTimeout(statusTimer)
  statusTimer = setTimeout(() => { status.value = '' }, 3000)
}

onMounted(async () => {
  if (!data.watchlist.length) await data.fetchAll()
  activeCode.value = data.watchlist[0]?.code || ''
  await nextTick()
  renderChart()
})
watch(activeCode, async () => { await nextTick(); renderChart() })

onUnmounted(() => { if (statusTimer) clearTimeout(statusTimer) })
</script>

<style scoped>
.page-content { max-width: 1200px; margin: 0 auto; }
.loading { text-align: center; padding: 60px; }
.spinner { width: 36px; height: 36px; border: 3px solid #e5e7eb; border-top-color: #2563eb; border-radius: 50%; animation: spin .8s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }
.top-bar { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.top-bar .tab-bar { margin-bottom: 0; flex: 1; }
.right-actions { display: flex; align-items: center; gap: 6px; white-space: nowrap; }
.status-text { font-size: 11px; color: #6b7280; transition: color 0.3s; }
.status-text.status-ok { color: #059669; }
.status-text.status-err { color: #dc2626; }
.top-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
.refresh-btn {
  display: inline-flex; align-items: center; gap: 6px;
  transition: all 0.25s ease;
}
.refresh-btn:disabled { opacity: 0.7; cursor: not-allowed; }
.refresh-btn:not(:disabled):hover {
  background: #dbeafe; border-color: #93c5fd; transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.15);
}
.refresh-btn:not(:disabled):active { transform: translateY(0); }
.refresh-running { background: #eff6ff; border-color: #60a5fa; color: #2563eb; }
.btn-icon { display: inline-block; font-size: 14px; line-height: 1; }
.btn-icon.spinning { animation: btnSpin 1s linear infinite; }
@keyframes btnSpin { to { transform: rotate(360deg); } }
@media (max-width: 800px) { .top-grid { grid-template-columns: 1fr; } }
.dp-card { background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.dp-card h3 { font-size: 14px; color: #6b7280; margin-bottom: 8px; font-weight: 500; }
.dp-next-card { text-align: center; padding: 24px; }
.dp-next-dir { font-size: 32px; font-weight: 700; margin: 8px 0; }
.dp-next-dir.bullish { color: #dc2626; }
.dp-next-dir.bearish { color: #16a34a; }
.dp-next-dir.neutral { color: #6b7280; }
.dp-next-range { font-size: 18px; font-weight: 600; color: #1f2937; margin: 4px 0; }
.dp-confidence { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; margin-top: 6px; }
.dp-confidence.high { background: #dcfce7; color: #166534; }
.dp-confidence.mid { background: #fef3c7; color: #92400e; }
.dp-confidence.low { background: #fee2e2; color: #991b1b; }
.actual-box { margin-top: 8px; padding: 6px 10px; background: #f0fdf4; border-radius: 6px; font-size: 12px; }
.key-levels { font-size: 13px; line-height: 2.2; }
.advice { line-height: 2; font-size: 13px; }
.dp-empty { text-align: center; color: #9ca3af; padding: 20px; font-size: 13px; }

/* Signals */
.collapse-header { padding: 0; background: none; cursor: pointer; font-size: 14px; font-weight: 600; display: flex; justify-content: space-between; }
.collapse-header .arrow { transition: transform .2s; font-size: 12px; color: #6b7280; }
.collapse-header .arrow.open { transform: rotate(90deg); }
.collapse-body { padding-top: 12px; }
.sig-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 12px; }
.sig-item { padding: 8px; background: #f8fafc; border-radius: 6px; font-size: 12px; text-align: center; }
.sig-name { font-weight: 600; margin-bottom: 2px; }
.sig-val { font-size: 16px; font-weight: 700; }
.sig-val.dir-bullish { color: #dc2626; }
.sig-val.dir-bearish { color: #16a34a; }
.sig-val.dir-neutral { color: #6b7280; }
.acc-row { margin-top: 8px; font-size: 12px; }
.acc-detail { font-size: 10px; color: #9ca3af; margin-left: 1px; }

/* Timeline */
.dp-timeline { display: flex; gap: 4px; overflow-x: auto; padding: 4px 0 8px; scrollbar-width: thin; }
.dp-tl-item { flex: 0 0 auto; width: 72px; padding: 8px 6px; border-radius: 8px; text-align: center; font-size: 11px; border: 2px solid #e5e7eb; background: #f9fafb; }
.dp-tl-item.today { border-color: #2563eb; background: #eff6ff; }
.dp-tl-item.hit { border-color: #86efac; background: #f0fdf4; }
.dp-tl-item.miss { border-color: #fca5a5; background: #fef2f2; }
.dp-tl-date { font-weight: 600; color: #374151; margin-bottom: 3px; }
.dp-tl-item.today .dp-tl-date { color: #2563eb; }
.dp-tl-dir { font-size: 18px; margin: 2px 0; }
.dp-tl-dir.bullish { color: #dc2626; }
.dp-tl-dir.bearish { color: #16a34a; }
.dp-tl-dir.neutral { color: #6b7280; }
.dp-tl-range { font-size: 10px; color: #6b7280; margin: 2px 0; }
.dp-tl-status { font-size: 10px; font-weight: 600; margin-top: 3px; padding: 1px 4px; border-radius: 3px; }
.dp-tl-status.hit { background: #dcfce7; color: #16a34a; }
.dp-tl-status.miss { background: #fee2e2; color: #dc2626; }
.dp-tl-status.pending { background: #f3f4f6; color: #6b7280; }
.tl-legend { display: flex; gap: 12px; font-size: 11px; color: #6b7280; margin-top: 4px; align-items: center; }
.tl-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.tl-dot.hit { background: #16a34a; }
.tl-dot.miss { background: #dc2626; }
.tl-dot.pending { background: #d1d5db; }
.tl-bar { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
.tl-bar.today { background: #2563eb; }
</style>
