<template>
  <div class="page-content">
    <div v-if="data.loading" class="loading"><div class="spinner"></div></div>
    <div v-else-if="data.error" class="error-card"><h2>加载失败</h2><p>{{ data.error }}</p></div>
    <template v-else>
      <!-- Stats -->
      <div class="stat-grid" style="grid-template-columns:repeat(4,1fr)">
        <div class="stat-item expense"><div class="label">总佣金</div><div class="value">{{ fmtMoney(stats.allCommission) }}</div><div class="sub">净佣金合计</div></div>
        <div class="stat-item expense"><div class="label">总印花税</div><div class="value">{{ fmtMoney(stats.allStamp) }}</div><div class="sub">卖出时收取</div></div>
        <div class="stat-item expense"><div class="label">其他费用</div><div class="value">{{ fmtMoney(stats.allOther) }}</div><div class="sub">过户费+证管费+经手费</div></div>
        <div class="stat-item expense"><div class="label">费用合计</div><div class="value">{{ fmtMoney(stats.allCommission + stats.allStamp + stats.allOther) }}</div><div class="sub">三项合计</div></div>
      </div>
      <!-- Stock Fee Table -->
      <div class="card">
        <h2>各股票费用明细</h2>
        <table>
          <thead><tr><th>股票</th><th>佣金</th><th>印花税</th><th>其他费用</th><th>合计</th><th>费率估算</th></tr></thead>
          <tbody>
            <tr v-for="row in feeRows" :key="row.code">
              <td>{{ row.name }}({{ row.code }})</td><td>{{ fmt(row.commission) }}</td><td>{{ fmt(row.stamp) }}</td>
              <td>{{ fmt(row.other) }}</td><td style="font-weight:600">{{ fmt(row.total) }}</td>
              <td>{{ row.estRate }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <!-- Pie Chart -->
      <div class="card">
        <h2>费用构成图</h2>
        <div class="chart-box"><canvas ref="pieCanvas"></canvas></div>
      </div>
      <!-- Monthly Trend -->
      <div class="card">
        <h2>逐月费用趋势</h2>
        <div class="chart-box" style="height:280px"><canvas ref="trendCanvas"></canvas></div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch, nextTick } from 'vue'
import { useDataStore } from '@/stores/data.js'
import { fmt, fmtMoney } from '@/api/client.js'

const data = useDataStore()
const pieCanvas = ref(null)
const trendCanvas = ref(null)
let pieChart = null
let trendChart = null

// Stock fee breakdown
const feeByStock = computed(() => {
  const map = {}
  for (const [code, p] of Object.entries(data.currentPositions)) {
    const c = p.total_commission || 0, s = p.total_stamp_tax || 0, o = p.total_other_fees || 0
    let buyAmt = 0, sellAmt = 0
    ;(p.trades || []).forEach(t => {
      const amt = Math.abs(t.qty) * t.price
      if (t.type === '证券买入') buyAmt += amt; else if (t.type === '证券卖出') sellAmt += amt
    })
    map[code] = { name: p.name, commission: c, stamp: s, other: o, total: c + s + o, buyAmount: buyAmt, sellAmount: sellAmt }
  }
  for (const [code, p] of Object.entries(data.closedPositions)) {
    const c = p.total_commission || 0, s = p.total_stamp_tax || 0, o = p.total_other_fees || 0
    let buyAmt2 = 0, sellAmt2 = 0
    ;(p.trades || []).forEach(t => {
      const amt = Math.abs(t.qty) * t.price
      if (t.type === '证券买入') buyAmt2 += amt; else if (t.type === '证券卖出') sellAmt2 += amt
    })
    if (map[code]) {
      map[code].commission += c; map[code].stamp += s; map[code].other += o; map[code].total += c + s + o
      map[code].buyAmount += buyAmt2; map[code].sellAmount += sellAmt2
    } else {
      map[code] = { name: p.name, commission: c, stamp: s, other: o, total: c + s + o, buyAmount: buyAmt2, sellAmount: sellAmt2 }
    }
  }
  return map
})

const feeRows = computed(() =>
  Object.entries(feeByStock.value).map(([code, f]) => ({
    code, name: f.name,
    commission: f.commission, stamp: f.stamp, other: f.other, total: f.total,
    estRate: f.buyAmount > 0 ? '佣金率≈' + (f.commission / (f.buyAmount + f.sellAmount) * 100).toFixed(4) + '%' : '--',
  }))
)

const stats = computed(() => {
  let allCommission = 0, allStamp = 0, allOther = 0
  for (const [, f] of Object.entries(feeByStock.value)) {
    allCommission += f.commission; allStamp += f.stamp; allOther += f.other
  }
  return { allCommission, allStamp, allOther }
})

function renderPieChart() {
  const s = stats.value
  if (!pieCanvas.value) return
  if (pieChart) pieChart.destroy()
  const Chart = window.Chart
  if (!Chart) return
  pieChart = new Chart(pieCanvas.value, {
    type: 'doughnut',
    data: {
      labels: ['佣金', '印花税', '其他费用'],
      datasets: [{ data: [s.allCommission, s.allStamp, s.allOther], backgroundColor: ['#3b82f6', '#f59e0b', '#10b981'] }],
    },
    options: { responsive: true, maintainAspectRatio: false,
      plugins: { tooltip: { callbacks: { label: ctx => ctx.label + ': ' + fmtMoney(ctx.raw) } } } },
  })
}

function renderTrendChart() {
  if (!trendCanvas.value || !data.allTrades.length) return
  if (trendChart) trendChart.destroy()
  const Chart = window.Chart
  if (!Chart) return

  const monthly = {}
  data.allTrades.forEach(t => {
    const m = t.date.substring(0, 7)
    if (!monthly[m]) monthly[m] = { commission: 0, stamp: 0 }
    monthly[m].commission += Math.abs(t.commission || 0)
    monthly[m].stamp += Math.abs(t.stamp_tax || 0)
  })
  const months = Object.keys(monthly).sort()
  trendChart = new Chart(trendCanvas.value, {
    type: 'bar',
    data: {
      labels: months,
      datasets: [
        { label: '佣金', data: months.map(m => monthly[m].commission), backgroundColor: '#3b82f6', stack: 'fee' },
        { label: '印花税', data: months.map(m => monthly[m].stamp), backgroundColor: '#f59e0b', stack: 'fee' },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + fmtMoney(ctx.raw) } } },
      scales: { x: { stacked: true }, y: { stacked: true, title: { display: true, text: '费用' } } },
    },
  })
}

function renderAll() {
  renderPieChart()
  renderTrendChart()
}

onMounted(async () => {
  if (!data.watchlist.length) await data.fetchAll()
  await nextTick()
  renderAll()
})
watch(() => data.loading, async (v) => { if (!v) { await nextTick(); renderAll() } })
</script>

<style scoped>
.page-content { max-width: 1200px; margin: 0 auto; }
.loading { text-align: center; padding: 60px; }
.spinner { width: 36px; height: 36px; border: 3px solid #e5e7eb; border-top-color: #2563eb; border-radius: 50%; animation: spin .8s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-card { background: #fef2f2; border: 1px solid #fca5a5; border-radius: 12px; padding: 32px; text-align: center; }
.chart-box { position: relative; height: 300px; }
</style>
