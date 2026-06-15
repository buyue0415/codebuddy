<template>
  <div class="page-content">
    <div v-if="loading" class="loading"><div class="spinner"></div></div>
    <template v-else>
      <!-- Equity Curve -->
      <div class="card">
        <h2>📈 资金曲线</h2>
        <div style="display:flex;gap:8px;margin-bottom:12px">
          <button v-for="d in [30,90,180]" :key="d" class="tab-btn"
            :class="{ active: activeDays === d }" @click="switchDays(d)">
            {{ d }}天
          </button>
        </div>
        <div v-if="perf?.equity_curve?.length" class="chart-box" style="height:300px">
          <canvas ref="chartCanvas"></canvas>
        </div>
        <div v-else class="empty">暂无资金曲线数据</div>
      </div>

      <!-- Stats -->
      <div class="stat-grid" v-if="perf">
        <div class="stat-mini"><span>总收益</span><b :class="pnlClass(perf.total_return_pct)">{{ pnlSign(perf.total_return_pct) }}{{ fmtPct(perf.total_return_pct) }}</b></div>
        <div class="stat-mini"><span>最大回撤</span><b>{{ fmtPct(perf.max_drawdown_pct) }}</b></div>
        <div class="stat-mini"><span>胜率</span><b>{{ fmtPct(perf.win_rate_pct) }}</b></div>
        <div class="stat-mini"><span>盈亏比</span><b>{{ fmtNum(perf.profit_factor) }}</b></div>
        <div class="stat-mini"><span>总交易</span><b>{{ perf.total_trades || 0 }}次</b></div>
        <div class="stat-mini"><span>最大盈利</span><b class="up">+¥{{ fmtMoney(perf.max_single_win) }}</b></div>
      </div>

      <!-- Trade History -->
      <div class="card">
        <h2>📜 交易记录</h2>
        <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;align-items:center">
          <input v-model="filterCode" placeholder="搜索代码..." class="input" style="width:140px"
            @keyup.enter="searchTrades">
          <button class="tab-btn" @click="searchTrades" :disabled="tradesLoading">🔍 查询</button>
          <span v-if="tradesLoading" style="font-size:12px;color:#6b7280">加载中...</span>
          <span v-else style="font-size:12px;color:#6b7280">共 {{ tradesTotal }} 条</span>
        </div>
        <table v-if="trades.length">
          <thead><tr><th>日期</th><th>代码</th><th>方向</th><th>数量</th><th>价格</th><th>手续费</th><th>发生金额</th><th>盈亏</th></tr></thead>
          <tbody>
            <tr v-for="t in trades" :key="t.id">
              <td>{{ t.date }}</td>
              <td>{{ t.name || t.code }}<br><span style="font-size:11px;color:#9ca3af">{{ t.code }}</span></td>
              <td :class="t.direction==='buy'?'up':'down'">{{ t.direction==='buy'?'买入':'卖出' }}</td>
              <td>{{ t.qty }}</td>
              <td>¥{{ fmt(t.price) }}</td>
              <td>¥{{ fmt((t.commission||0)+(t.stamp_tax||0)) }}</td>
              <td :class="t.settlement>0?'up':'down'">{{ pnlSign(t.settlement) }}¥{{ fmtMoney(Math.abs(t.settlement||0)) }}</td>
              <td v-if="t.realized_pnl!=null" :class="pnlClass(t.realized_pnl)">
                {{ pnlSign(t.realized_pnl) }}¥{{ fmtMoney(Math.abs(t.realized_pnl)) }}
              </td>
              <td v-else>—</td>
            </tr>
          </tbody>
        </table>
        <div v-else-if="searched" class="empty">无匹配交易记录</div>
        <div v-else class="empty">点击"查询"加载交易记录</div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { usePaperStore } from '@/stores/paper.js'

const store = usePaperStore()
const { performance: perf, equityCurve, trades, tradesTotal } = storeToRefs(store)
const { loadPerformance, loadTrades } = store

const loading = ref(false)
const tradesLoading = ref(false)
const activeDays = ref(90)
const filterCode = ref('')
const searched = ref(false)
const chartCanvas = ref(null)
let chartInst = null

onMounted(() => { loadData() })

// Auto-draw chart whenever equityCurve data changes (after DOM is ready)
watch([equityCurve, chartCanvas], () => {
  nextTick(() => {
    try { drawChart() } catch (e) { console.warn('drawChart:', e) }
  })
})

async function loadData() {
  loading.value = true
  searched.value = true
  try {
    await loadTrades(filterCode.value || '')
  } catch (e) {
    console.warn('loadTrades failed:', e)
  }
  try {
    await loadPerformance(activeDays.value)
  } catch (e) {
    console.warn('loadPerformance failed:', e)
  }
  loading.value = false
}

async function searchTrades() {
  tradesLoading.value = true
  searched.value = true
  try {
    await loadTrades(filterCode.value || '')
  } catch (e) {
    console.warn('searchTrades failed:', e)
  }
  tradesLoading.value = false
}

function switchDays(d) {
  activeDays.value = d
  loadData()
}

function drawChart() {
  if (!chartCanvas.value || !equityCurve.value?.length) return
  const C = window.Chart
  if (!C) { console.warn('Chart.js not loaded'); return }
  if (chartInst) chartInst.destroy()
  const data = equityCurve.value
  const labels = data.map(e => e.date)
  const values = data.map(e => e.value)
  const benchmark = data.map(() => data[0].value)
  chartInst = new C(chartCanvas.value, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: '纸面账户', data: values, borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,.1)', fill: true, tension: .3, pointRadius: values.length > 1 ? 0 : 4 },
        { label: '买入持有', data: benchmark, borderColor: '#9ca3af', borderDash: [5,5], fill: false, tension: .3, pointRadius: 0 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
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
            title: items => {
              const i = items[0]?.dataIndex
              return labels[i] || ''
            },
            label: ctx => {
              const v = ctx.raw
              const init = data[0]?.value || 1
              const pct = ((v - init) / init * 100)
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
function pnlClass(v) { return Number(v) > 0 ? 'up' : Number(v) < 0 ? 'down' : 'flat' }
function pnlSign(v) { return Number(v) > 0 ? '+' : Number(v) < 0 ? '' : '' }
</script>

<style scoped>
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 20px; }
.stat-mini { background:#fff; border-radius:10px; padding:14px 16px; box-shadow:0 1px 3px rgba(0,0,0,.08); }
.stat-mini span { font-size:11px; color:#6b7280; display:block; margin-bottom:4px; }
.stat-mini b { font-size:18px; font-weight:700; }
.chart-box { background:#fff; border-radius:10px; }
</style>
