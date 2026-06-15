<template>
  <div class="page-content">
    <div v-if="data.loading" class="loading"><div class="spinner"></div></div>
    <div v-else-if="data.error" class="error-card"><h2>加载失败</h2><p>{{ data.error }}</p></div>
    <template v-else>
      <div class="card">
        <h2>全部交易流水（广发证券 {{ data.config?.account || '51312640' }}）</h2>
        <div class="table-wrap">
          <table>
            <thead><tr><th>日期</th><th>时间</th><th>股票</th><th>类型</th><th>数量</th><th>价格</th><th>佣金</th><th>印花税</th><th>清算金额</th></tr></thead>
            <tbody>
              <tr v-for="(t, i) in data.allTrades" :key="i">
                <td>{{ t.date }}</td><td>{{ t.time }}</td><td>{{ t.name }}</td>
                <td><span class="tag" :class="typeClass(t.type)">{{ t.type }}</span></td>
                <td>{{ Math.abs(t.qty).toLocaleString() }}</td>
                <td>{{ fmt(t.price) }}</td><td>{{ fmt(t.commission) }}</td>
                <td>{{ fmt(t.stamp_tax) }}</td>
                <td :class="t.settlement >= 0 ? 'up' : 'down'">{{ fmt(t.settlement) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="card">
        <h2>交易时间线</h2>
        <div class="chart-box"><canvas ref="chartCanvas"></canvas></div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref, watch, nextTick } from 'vue'
import { useDataStore } from '@/stores/data.js'
import { fmt } from '@/api/client.js'

const data = useDataStore()
const chartCanvas = ref(null)
let chartInst = null

function typeClass(type) {
  return type === '证券买入' ? 'tag-buy' : type === '证券卖出' ? 'tag-sell' : 'tag-div'
}

function renderTimeline() {
  if (!chartCanvas.value || !data.allTrades.length) return
  if (chartInst) chartInst.destroy()

  // Aggregate by month
  const monthly = {}
  data.allTrades.forEach(t => {
    const m = t.date.substring(0, 7)
    if (!monthly[m]) monthly[m] = { buy: 0, sell: 0, div: 0 }
    if (t.type === '证券买入') monthly[m].buy += t.settlement
    else if (t.type === '证券卖出') monthly[m].sell += Math.abs(t.settlement)
    else monthly[m].div += Math.abs(t.settlement)
  })
  const months = Object.keys(monthly).sort()
  const toWan = v => Math.abs(v) / 10000

  const Chart = window.Chart
  if (!Chart) return
  chartInst = new Chart(chartCanvas.value, {
    type: 'bar',
    data: {
      labels: months,
      datasets: [
        { label: '买入', data: months.map(m => toWan(monthly[m].buy)), backgroundColor: '#3b82f6' },
        { label: '卖出', data: months.map(m => toWan(monthly[m].sell)), backgroundColor: '#f59e0b' },
        { label: '分红', data: months.map(m => toWan(monthly[m].div)), backgroundColor: '#dc2626' },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + ctx.raw.toFixed(2) + '万' } },
      },
      scales: { y: { title: { display: true, text: '万元' } } },
    },
  })
}

onMounted(async () => {
  if (!data.watchlist.length) await data.fetchAll()
  await nextTick()
  renderTimeline()
})
watch(() => data.allTrades.length, async () => {
  await nextTick()
  renderTimeline()
})
</script>

<style scoped>
.page-content { max-width: 1200px; margin: 0 auto; }
.table-wrap { overflow-x: auto; }
.loading { text-align: center; padding: 60px; }
.spinner {
  width: 36px; height: 36px; border: 3px solid #e5e7eb;
  border-top-color: #2563eb; border-radius: 50%; animation: spin .8s linear infinite;
  margin: 0 auto;
}
@keyframes spin { to { transform: rotate(360deg); } }
.error-card { background: #fef2f2; border: 1px solid #fca5a5; border-radius: 12px; padding: 32px; text-align: center; }
</style>
