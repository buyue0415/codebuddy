<template>
  <div class="page-content">
    <div v-if="data.loading && !data.watchlist.length" class="loading"><div class="spinner"></div></div>
    <template v-else>
      <div class="top-bar">
        <div class="tab-bar">
          <IndustryGroupTabs :stocks="data.watchlist" :activeCode="activeCode"
            @switch="switchStock" />
        </div>
      </div>

      <div v-if="!stockReports.length" class="empty-card">
        <div class="expert-empty">暂无专家分析报告<br><span style="font-size:12px;margin-top:8px;display:block">每周一 9:00 自动生成</span></div>
      </div>

      <div v-else class="expert-layout">
        <!-- Sidebar -->
        <div class="expert-sidebar">
          <div v-for="(r, i) in stockReports" :key="i"
            class="rpt-item" :class="{ active: i === activeIdx }"
            @click="activeIdx = i">
            <div class="rpt-date">{{ r.date }}</div>
            <div class="rpt-decision">{{ decIcon(r.stocks[activeCode]) }} {{ r.stocks[activeCode]?.decision || 'N/A' }}</div>
          </div>
        </div>

        <!-- Detail -->
        <div class="expert-content" v-if="currentReport">
          <!-- Decision Card -->
          <div class="decision-card" :class="decClass">
            <h1>{{ currentStock?.decision || 'HOLD' }}</h1>
            <div class="sub-info">
              <span>信心：{{ currentStock?.confidence || '中' }}</span>
              <span>风险：{{ currentStock?.risk_level || '中' }}</span>
              <span>建议仓位：{{ currentStock?.position_pct || 0 }}%</span>
            </div>
            <div class="price-grid">
              <div class="price-item"><div class="plabel">入场价</div><div class="pval">{{ fmt(currentStock?.entry_price) }}</div></div>
              <div class="price-item"><div class="plabel">目标价</div><div class="pval">{{ fmt(currentStock?.target_price) }}</div></div>
              <div class="price-item"><div class="plabel">止损价</div><div class="pval">{{ fmt(currentStock?.stop_loss) }}</div></div>
              <div class="price-item"><div class="plabel">现价</div><div class="pval">{{ fmt(data.quotes[activeCode]?.price) }}</div></div>
            </div>
          </div>

          <!-- Radar chart -->
          <div class="card">
            <h2>综合评分雷达图</h2>
            <div class="chart-box" style="height:320px"><canvas ref="radarCanvas"></canvas></div>
          </div>

          <!-- Bull vs Bear -->
          <div class="card">
            <h2>多空论点对比</h2>
            <div class="chart-box" style="height:300px"><canvas ref="bullBearCanvas"></canvas></div>
          </div>

          <!-- Risk triangle -->
          <div class="card">
            <h2>风险评估三角图</h2>
            <div class="chart-box" style="height:280px"><canvas ref="riskCanvas"></canvas></div>
          </div>

          <!-- Collapsible sections -->
          <div class="collapse-section" v-for="sec in collapseSections" :key="sec.label">
            <div class="collapse-header" @click="toggleSection(sec.label)">
              <span>{{ sec.icon }} {{ sec.label }}</span><span class="arrow" :class="{ open: openSections[sec.label] }">▶</span>
            </div>
            <div class="collapse-body" :class="{ open: openSections[sec.label] }" v-html="sec.content"></div>
          </div>

          <!-- Catalysts & Risks -->
          <div class="card" v-if="currentStock?.catalysts?.length || currentStock?.risks?.length" style="margin-top:12px">
            <h2>🔑 催化剂 & 风险事件</h2>
            <div><b>催化剂</b><div class="tag-list"><span v-for="c in currentStock.catalysts" :key="c" class="etag catalyst">{{ c }}</span></div></div>
            <div style="margin-top:8px"><b>风险事件</b><div class="tag-list"><span v-for="r in currentStock.risks" :key="r" class="etag risk">{{ r }}</span></div></div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useDataStore } from '@/stores/data.js'
import { useIndustryStore } from '@/stores/industry.js'
import IndustryGroupTabs from '@/components/IndustryGroupTabs.vue'
import { fmt } from '@/api/client.js'

const data = useDataStore()
const industryStore = useIndustryStore()
const activeCode = ref('')
const activeIdx = ref(0)
const radarCanvas = ref(null)
const bullBearCanvas = ref(null)
const riskCanvas = ref(null)

let radarChart = null, bullBearChart = null, riskChart = null

const openSections = ref({})
function toggleSection(label) {
  openSections.value[label] = !openSections.value[label]
}

const stockReports = computed(() => {
  const reports = (data.expertReports || []).filter(r => r.stocks && r.stocks[activeCode.value])
  return reports.sort((a, b) => b.date.localeCompare(a.date))
})

const currentReport = computed(() => stockReports.value[activeIdx.value] || null)
const currentStock = computed(() => currentReport.value?.stocks?.[activeCode.value] || null)
const decClass = computed(() => (currentStock.value?.decision || 'hold').toLowerCase())

function decIcon(s) {
  const d = s?.decision
  return d === 'BUY' ? '🟢' : d === 'SELL' ? '🔴' : '🟡'
}

function switchStock(code) {
  activeCode.value = code; activeIdx.value = 0
}

const collapseSections = computed(() => {
  const s = currentStock.value
  if (!s) return []
  const p1 = s.phase1 || {}
  const p2 = s.phase2 || {}
  const p4 = s.phase4 || {}
  const bull = p2.bull_args || [], bear = p2.bear_args || []

  return [
    { label: '技术面分析', icon: '📈', content: p1.technical || '暂无', open: false },
    { label: '基本面分析', icon: '📊', content: p1.fundamental || '暂无', open: false },
    { label: '新闻面分析', icon: '📰', content: p1.news || '暂无', open: false },
    { label: '情绪面分析', icon: '💭', content: p1.sentiment || '暂无', open: false },
    { label: '多空辩论结论', icon: '⚖️', open: false, content:
      '<b>多头论点：</b><ul class="arg-list">' + bull.map(a => `<li><span class="arg-weight bull">${a.weight}</span>${a.point}</li>`).join('') + '</ul>' +
      '<b>空头论点：</b><ul class="arg-list">' + bear.map(a => `<li><span class="arg-weight bear">${a.weight}</span>${a.point}</li>`).join('') + '</ul>' +
      '<b style="margin-top:8px;display:block">裁决：' + (p2.verdict || '暂无') + '</b>'
    },
    { label: '风险评估结论', icon: '🛡️', content: p4.final_risk_note || '暂无', open: false },
  ]
})

function renderCharts() {
  const s = currentStock.value
  if (!s) return
  const Chart = window.Chart
  if (!Chart) return
  const name = data.watchlist.find(x => x.code === activeCode.value)?.name || activeCode.value

  // Radar
  if (radarChart) radarChart.destroy()
  const scores = s.scores || {}
  radarChart = new Chart(radarCanvas.value, {
    type: 'radar',
    data: {
      labels: ['技术面', '基本面', '新闻面', '情绪面', '风险面'],
      datasets: [{ label: name, data: [scores.technical||0, scores.fundamental||0, scores.news||0, scores.sentiment||0, scores.risk||0], backgroundColor: 'rgba(37,99,235,.15)', borderColor: '#2563eb', borderWidth: 2, pointBackgroundColor: '#2563eb', pointRadius: 4 }],
    },
    options: { responsive: true, maintainAspectRatio: false, scales: { r: { min: 0, max: 10, ticks: { stepSize: 2, font: { size: 10 } }, pointLabels: { font: { size: 12 } } } }, plugins: { legend: { display: false } } },
  })

  // Bull vs Bear
  if (bullBearChart) bullBearChart.destroy()
  const p2 = s.phase2 || {}
  const bull = p2.bull_args || [], bear = p2.bear_args || []
  const maxLen = Math.max(bull.length, bear.length, 1)
  const bbLabels = [], bullData = [], bearData = []
  for (let i = 0; i < maxLen; i++) { bbLabels.push('论点' + (i + 1)); bullData.push(bull[i]?.weight || 0); bearData.push(bear[i]?.weight || 0) }
  bullBearChart = new Chart(bullBearCanvas.value, {
    type: 'bar',
    data: { labels: bbLabels, datasets: [{ label: '多头(看涨)', data: bullData, backgroundColor: '#dc2626' }, { label: '空头(看跌)', data: bearData, backgroundColor: '#16a34a' }] },
    options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, scales: { x: { max: 10, ticks: { font: { size: 10 } } }, y: { ticks: { font: { size: 10 } } } }, plugins: { legend: { position: 'top' } } },
  })

  // Risk triangle
  if (riskChart) riskChart.destroy()
  const p4 = s.phase4 || {}
  riskChart = new Chart(riskCanvas.value, {
    type: 'radar',
    data: { labels: ['激进', '保守', '中性'], datasets: [{ label: '风险评分', data: [p4.aggressive_score||0, p4.conservative_score||0, p4.neutral_score||0], backgroundColor: 'rgba(245,158,11,.15)', borderColor: '#f59e0b', borderWidth: 2, pointBackgroundColor: '#f59e0b', pointRadius: 5 }] },
    options: { responsive: true, maintainAspectRatio: false, scales: { r: { min: 0, max: 10, ticks: { stepSize: 2, font: { size: 10 } }, pointLabels: { font: { size: 13 } } } }, plugins: { legend: { display: false } } },
  })
}

onMounted(async () => {
  await data.fetchAll()
  activeCode.value = data.watchlist[0]?.code || ''
  await nextTick()
  renderCharts()
})
watch(activeIdx, async () => { await nextTick(); renderCharts() })
watch(activeCode, async () => { activeIdx.value = 0; await nextTick(); renderCharts() })
</script>

<style scoped>
.page-content { max-width: 1200px; margin: 0 auto; }
.loading { text-align: center; padding: 60px; }
.spinner { width: 36px; height: 36px; border: 3px solid #e5e7eb; border-top-color: #2563eb; border-radius: 50%; animation: spin .8s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }
.top-bar { margin-bottom: 12px; }
.empty-card { text-align: center; padding: 60px; }
.expert-empty { text-align: center; color: #9ca3af; padding: 60px 20px; font-size: 14px; }

/* Layout */
.expert-layout { display: flex; gap: 20px; min-height: 500px; }
.expert-sidebar { width: 220px; flex-shrink: 0; }
.rpt-item { padding: 10px 14px; border-radius: 8px; cursor: pointer; margin-bottom: 6px; border: 1px solid #e2e8f0; transition: all .2s; }
.rpt-item:hover { background: #f0f7ff; border-color: #93c5fd; }
.rpt-item.active { background: #eff6ff; border-color: #2563eb; }
.rpt-date { font-size: 13px; font-weight: 600; color: #1f2937; }
.rpt-decision { font-size: 12px; margin-top: 2px; }
.expert-content { flex: 1; min-width: 0; }

/* Decision card */
.decision-card { padding: 28px; border-radius: 14px; color: #fff; margin-bottom: 20px; }
.decision-card.buy { background: linear-gradient(135deg,#047857,#10b981); }
.decision-card.sell { background: linear-gradient(135deg,#991b1b,#dc2626); }
.decision-card.hold { background: linear-gradient(135deg,#b45309,#f59e0b); }
.decision-card h1 { font-size: 42px; margin: 0; line-height: 1; }
.sub-info { display: flex; gap: 20px; margin-top: 12px; font-size: 13px; opacity: .9; }
.price-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 16px; }
.price-item { background: rgba(255,255,255,.15); padding: 10px; border-radius: 8px; text-align: center; }
.plabel { font-size: 11px; opacity: .8; }
.pval { font-size: 22px; font-weight: 700; }

/* Collapse */
.collapse-section { border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 10px; overflow: hidden; }
.collapse-header { padding: 12px 16px; background: #f8fafc; cursor: pointer; font-size: 14px; font-weight: 600; display: flex; justify-content: space-between; }
.collapse-header:hover { background: #f0f7ff; }
.collapse-header .arrow { transition: transform .2s; font-size: 12px; color: #6b7280; }
.collapse-header .arrow.open { transform: rotate(90deg); }
.collapse-body { padding: 14px 16px; font-size: 13px; line-height: 1.7; color: #374151; display: none; border-top: 1px solid #e2e8f0; }
.collapse-body.open { display: block; }
.arg-list { list-style: none; padding: 0; margin: 6px 0; }
.arg-list li { padding: 4px 0; display: flex; align-items: center; gap: 8px; }
.arg-weight { display: inline-block; width: 28px; height: 28px; border-radius: 6px; text-align: center; line-height: 28px; font-size: 12px; font-weight: 700; color: #fff; flex-shrink: 0; }
.arg-weight.bull { background: #dc2626; }
.arg-weight.bear { background: #16a34a; }
.tag-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.etag { padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 500; }
.etag.catalyst { background: #dcfce7; color: #166534; }
.etag.risk { background: #fee2e2; color: #991b1b; }
</style>
