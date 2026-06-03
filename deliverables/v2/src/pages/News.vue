<template>
  <div class="page-content">
    <div v-if="data.loading && !data.allNews.length" class="loading"><div class="spinner"></div></div>
    <div v-else-if="data.error && !data.allNews.length" class="error-card"><h2>加载失败</h2><p>{{ data.error }}</p></div>
    <template v-else>
      <!-- Tab bar -->
      <div class="top-bar">
        <div class="tab-bar">
          <button class="tab-btn" :class="{ active: filter === 'all' }" @click="setFilter('all')">全部</button>
          <button v-for="s in data.watchlist" :key="s.code" class="tab-btn" :class="{ active: filter === s.code }" @click="setFilter(s.code)">{{ s.name }}</button>
          <button class="tab-btn" :class="{ active: filter === 'major' }" @click="setFilter('major')">⚠️ 重大事件</button>
        </div>
        <div class="right-actions">
          <button class="tab-btn" @click="triggerNews" :disabled="refreshing">🔄 刷新新闻</button>
          <span class="status-text" v-if="newsStatus">{{ newsStatus }}</span>
        </div>
      </div>

      <!-- Date picker (per-stock only) -->
      <div v-if="filter !== 'all' && filter !== 'major'" class="date-bar">
        <div class="dp-wrapper" ref="dpRef">
          <button class="dp-trigger" @click="dpOpen = !dpOpen">
            <span>📅</span><span class="dp-text">{{ selDate || '选择日期' }}</span><span class="dp-arr">▾</span>
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
            <button class="dp-clear" @click="clearDate">清除筛选</button>
          </div>
        </div>
        <span class="dp-status" v-if="selDate">{{ filteredList.length }}条新闻 · 仅{{ selDate }}</span>
      </div>

      <!-- News list or detail -->
      <template v-if="!detailNews">
        <div class="card" v-if="filteredList.length">
          <h2>📰 近期新闻动态</h2>
          <div class="news-timeline">
            <div v-for="(n, i) in filteredList" :key="i"
              class="news-item" :class="{ major: n.major }" :style="{ animationDelay: (i * 0.04) + 's' }">
              <div class="news-date">{{ n.date }}</div>
              <div class="news-body">
                <div class="news-title">
                  <span class="stock-tag">{{ getStockName(n.code) }}</span>
                  <a href="#" @click.prevent="openDetail(n, i)">{{ n.title }}</a>
                </div>
                <div v-if="n.summary" class="news-summary">{{ n.summary }}</div>
                <div class="news-source">
                  {{ n.source || '综合' }}
                  <span v-if="n.major" class="major-tag">⚠ 重大事件</span>
                  <span class="sent-tag" :class="'sent-' + n.sentiment">
                    {{ {positive:'📈 利好',negative:'📉 利空',neutral:'➖ 中性'}[n.sentiment] || '中性' }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="card"><h2>📰 近期新闻动态</h2><div class="empty">暂无新闻数据</div></div>

        <!-- Sentiment chart -->
        <div class="card" v-if="sentimentData.length">
          <div class="chart-header">
            <h2 style="margin:0">📊 新闻情绪趋势</h2>
            <select v-model="sentimentMonth" @change="renderChart" class="month-select">
              <option v-for="m in sentimentMonths" :key="m" :value="m">
                {{ parseInt(m.substring(0,4)) }}年{{ parseInt(m.substring(5,7)) }}月
              </option>
            </select>
          </div>
          <div class="chart-box" style="height:280px"><canvas ref="sentCanvas"></canvas></div>
        </div>
      </template>

      <!-- News detail -->
      <template v-else>
        <div class="detail-page">
          <div class="detail-back"><button class="tab-btn" @click="closeDetail">← 返回新闻列表</button></div>
          <div class="nd-card">
            <div class="nd-header"><div class="nd-title">{{ detailNews.title }}</div></div>
            <div class="nd-badge-row">
              <span class="nd-badge stock">{{ getStockName(detailNews.code) }}({{ detailNews.code }})</span>
              <span class="nd-badge date">📅 {{ detailNews.date }}</span>
              <span class="nd-badge source">📰 {{ detailNews.source || '综合' }}</span>
              <span class="nd-badge" :class="'sent-' + detailNews.sentiment">{{ labels[detailNews.sentiment] || '中性' }}</span>
              <span v-if="detailNews.major" class="nd-badge major">⚠️ 重大事件</span>
            </div>
            <div class="nd-divider"></div>
            <div class="nd-body" v-if="detailNews.summary">
              <div class="nd-summary-label">📋 摘要</div>
              {{ detailNews.summary }}
            </div>
            <div class="nd-actions" v-if="detailNews.url && detailNews.url.startsWith('http')">
              <a :href="detailNews.url" target="_blank" class="nd-link primary">🔗 查看原文</a>
            </div>
          </div>
          <div v-if="relatedNews.length" class="nd-related">
            <h3>📌 {{ getStockName(detailNews.code) }} 更多新闻</h3>
            <div v-for="(n, i) in relatedNews" :key="i" class="nd-rel-item" @click="openDetail(n, i)">
              <div class="nd-rel-date">{{ n.date }}</div>
              <div class="nd-rel-title">{{ n.title }}</div>
              <div class="nd-rel-source">{{ n.source || '综合' }}</div>
            </div>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useDataStore } from '@/stores/data.js'
import { apiCall } from '@/api/client.js'

const data = useDataStore()
const filter = ref('all')
const selDate = ref('')
const dpOpen = ref(false)
const dpYear = ref(0)
const dpMonth = ref(0)
const detailNews = ref(null)
const detailIdx = ref(-1)
const sentCanvas = ref(null)
const sentimentMonth = ref('')
const refreshing = ref(false)
const newsStatus = ref('')
let sentChart = null

const weekdays = ['一','二','三','四','五','六','日']
const labels = { positive: '📈 利好', negative: '📉 利空', neutral: '➖ 中性' }

// Computed
const filteredList = computed(() => {
  let list = (data.allNews || []).filter(n => {
    if (filter.value === 'all') return true
    if (filter.value === 'major') return n.major
    return n.code === filter.value
  })
  if (selDate.value) list = list.filter(n => n.date === selDate.value)
  return list.sort((a, b) => b.date.localeCompare(a.date))
})

const sentimentData = computed(() => {
  if (filter.value === 'all') return data.allNews || []
  if (filter.value === 'major') return (data.allNews || []).filter(n => n.major)
  return (data.allNews || []).filter(n => n.code === filter.value)
})

const sentimentMonths = computed(() => {
  const months = [...new Set(sentimentData.value.map(n => n.date?.substring(0,7)).filter(Boolean))]
  months.sort().reverse()
  const cur = new Date().toISOString().substring(0,7)
  if (!months.includes(cur)) months.unshift(cur)
  return months
})

const relatedNews = computed(() => {
  if (!detailNews.value) return []
  return filteredList.value.filter((n, i) => i !== detailIdx.value && n.code === detailNews.value.code).slice(0, 5)
})

// Calendar
const calendarDays = computed(() => {
  const first = new Date(dpYear.value, dpMonth.value - 1, 1)
  const last = new Date(dpYear.value, dpMonth.value, 0)
  const startDay = first.getDay()
  const offset = startDay === 0 ? 6 : startDay - 1
  const days = []
  for (let i = 0; i < offset; i++) days.push({ cls: 'other' })
  const today = new Date().toISOString().substring(0, 10)
  const newsDates = new Set(sentimentData.value.map(n => n.date).filter(Boolean))
  for (let d = 1; d <= last.getDate(); d++) {
    const ds = `${dpYear.value}-${String(dpMonth.value).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    const cls = ['dp-day']
    if (ds === today) cls.push('today')
    if (newsDates.has(ds)) cls.push('has-news')
    if (selDate.value === ds) cls.push('selected')
    days.push({ day: d, dateStr: ds, cls: cls.join(' ') })
  }
  return days
})

// Methods
function getStockName(code) {
  const s = data.watchlist?.find(x => x.code === code)
  return s ? s.name : code
}

function setFilter(f) {
  filter.value = f
  selDate.value = ''
  dpOpen.value = false
  detailNews.value = null
  if (f !== 'all' && f !== 'major') initCalendar()
}

function selectDate(ds) { selDate.value = ds; dpOpen.value = false }
function clearDate() { selDate.value = ''; dpOpen.value = false }
function dpPrevMonth() { if (--dpMonth.value < 1) { dpMonth.value = 12; dpYear.value-- } }
function dpNextMonth() { if (++dpMonth.value > 12) { dpMonth.value = 1; dpYear.value++ } }

function initCalendar() {
  const d = new Date()
  dpYear.value = d.getFullYear()
  dpMonth.value = d.getMonth() + 1
}

function openDetail(n, i) { detailNews.value = n; detailIdx.value = i }
function closeDetail() { detailNews.value = null }

function escapeHtml(s) {
  if (!s) return ''
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

// Sentiment chart
function renderChart() {
  if (!sentCanvas.value) return
  if (sentChart) sentChart.destroy()
  const Chart = window.Chart
  if (!Chart) return
  const byDay = {}
  sentimentData.value.forEach(n => {
    if (!n.date || !n.date.startsWith(sentimentMonth.value)) return
    if (!byDay[n.date]) byDay[n.date] = { positive: 0, negative: 0, neutral: 0 }
    byDay[n.date][n.sentiment || 'neutral']++
  })
  const labels = Object.keys(byDay).sort()
  if (!labels.length) return
  sentChart = new Chart(sentCanvas.value, {
    type: 'bar',
    data: {
      labels: labels.map(d => parseInt(d.substring(8, 10)) + '日'),
      datasets: [
        { label: '利好', data: labels.map(l => byDay[l].positive), backgroundColor: '#dc2626' },
        { label: '利空', data: labels.map(l => byDay[l].negative), backgroundColor: '#16a34a' },
        { label: '中性', data: labels.map(l => byDay[l].neutral), backgroundColor: '#6b7280' },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top' }, title: { display: true, text: labels.length + '天 · 情绪分布', font: { size: 13 } } },
      scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } },
    },
  })
}

async function triggerNews() {
  refreshing.value = true; newsStatus.value = '刷新中...'
  try {
    const r = await apiCall('POST', '/api/trigger/news')
    newsStatus.value = r?.success ? '✅ 刷新完成' : '❌ ' + (r?.error || '')
    if (r?.success) await data.fetchAll()
  } catch (e) { newsStatus.value = '❌ ' + e.message }
  refreshing.value = false
}

// Init
onMounted(async () => {
  if (!data.watchlist.length) await data.fetchAll()
  if (sentimentData.value.length) {
    sentimentMonth.value = sentimentMonths.value[0] || ''
    await nextTick(); renderChart()
  }
})
watch(() => data.allNews, async () => {
  sentimentMonth.value = sentimentMonths.value[0] || ''
  await nextTick(); renderChart()
})
</script>

<style scoped>
.page-content { max-width: 1200px; margin: 0 auto; }
.loading { text-align: center; padding: 60px; }
.spinner { width: 36px; height: 36px; border: 3px solid #e5e7eb; border-top-color: #2563eb; border-radius: 50%; animation: spin .8s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-card { background: #fef2f2; border: 1px solid #fca5a5; border-radius: 12px; padding: 32px; text-align: center; }
.top-bar { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.top-bar .tab-bar { flex: 1; display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 0; }
.right-actions { display: flex; align-items: center; gap: 8px; white-space: nowrap; }
.status-text { font-size: 11px; color: #6b7280; }

/* Date picker */
.date-bar { display: flex; align-items: center; gap: 8px; margin: -4px 0 10px; }
.dp-wrapper { position: relative; }
.dp-trigger { display: flex; align-items: center; gap: 6px; padding: 5px 10px; border: 1px solid #d1d5db; border-radius: 6px; background: #fff; cursor: pointer; font-size: 13px; }
.dp-text { flex: 1; }
.dp-arr { font-size: 10px; color: #9ca3af; }
.dp-panel { position: absolute; top: 100%; left: 0; background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; box-shadow: 0 8px 24px rgba(0,0,0,.1); padding: 14px; width: 264px; z-index: 200; margin-top: 4px; }
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
.dp-day.has-news::after { content: ''; display: block; width: 4px; height: 4px; border-radius: 50%; background: #6366f1; margin: 2px auto 0; }
.dp-day.selected { background: #2563eb; color: #fff; font-weight: 600; }
.dp-clear { display: block; width: 100%; margin-top: 10px; padding: 5px; border: 1px solid #e5e7eb; border-radius: 6px; background: #fff; cursor: pointer; font-size: 11px; color: #9ca3af; }
.dp-status { font-size: 11px; color: #6b7280; }

/* News items */
.news-timeline { margin-top: 12px; }
.news-item { padding: 14px 0; border-bottom: 1px solid #f1f5f9; display: flex; gap: 14px; align-items: flex-start; animation: newsIn .25s ease-out both; }
@keyframes newsIn { 0% { opacity: 0; transform: translateY(10px) } 100% { opacity: 1; transform: translateY(0) } }
.news-item.major { background: #fffbeb; border-radius: 8px; padding: 14px; margin: 4px -8px; border-left: 3px solid #f59e0b; }
.news-date { min-width: 80px; font-size: 12px; color: #6b7280; padding-top: 2px; }
.news-body { flex: 1; }
.news-title { font-size: 14px; font-weight: 600; color: #1f2937; margin-bottom: 4px; }
.news-title a { color: inherit; text-decoration: none; }
.news-title a:hover { color: #2563eb; }
.stock-tag { font-size: 11px; padding: 1px 6px; border-radius: 3px; margin-right: 6px; font-weight: 600; background: #e0e7ff; color: #3730a3; }
.news-summary { font-size: 13px; color: #6b7280; margin-top: 4px; line-height: 1.5; }
.news-source { font-size: 11px; color: #9ca3af; margin-top: 4px; display: flex; align-items: center; gap: 8px; }
.major-tag { color: #dc2626; font-weight: 600; }
.sent-tag { font-size: 11px; padding: 1px 6px; border-radius: 4px; }
.sent-positive { background: #dcfce7; color: #166534; }
.sent-negative { background: #fee2e2; color: #991b1b; }
.sent-neutral { background: #f3f4f6; color: #6b7280; }
.empty { text-align: center; padding: 40px; color: #9ca3af; font-size: 14px; }
.chart-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
.month-select { padding: 4px 24px 4px 8px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 12px; appearance: none; background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10'%3E%3Cpath fill='%236b7280' d='M2 3l3 4 3-4'/%3E%3C/svg%3E") no-repeat right 6px center; }

/* Detail page */
.detail-page { max-width: 900px; margin: 0 auto; }
.detail-back { padding: 20px 0 16px; }
.nd-card { background: #fff; border-radius: 14px; box-shadow: 0 1px 4px rgba(0,0,0,.06); overflow: hidden; }
.nd-header { padding: 28px 28px 0; }
.nd-title { font-size: 22px; font-weight: 700; line-height: 1.5; color: #111827; }
.nd-badge-row { display: flex; flex-wrap: wrap; gap: 8px 12px; padding: 14px 28px 0; align-items: center; }
.nd-badge { display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; border-radius: 6px; font-size: 12px; font-weight: 500; }
.nd-badge.stock { background: #dbeafe; color: #1e40af; }
.nd-badge.date { background: #f3f4f6; color: #6b7280; }
.nd-badge.source { background: #fef3c7; color: #92400e; }
.nd-badge.major { background: #fef2f2; color: #dc2626; font-weight: 600; }
.nd-badge.sent-positive { background: #dcfce7; color: #166534; }
.nd-badge.sent-negative { background: #fee2e2; color: #991b1b; }
.nd-badge.sent-neutral { background: #f3f4f6; color: #6b7280; }
.nd-divider { height: 1px; background: linear-gradient(90deg,transparent,#e5e7eb,transparent); margin: 16px 28px; }
.nd-body { padding: 0 28px 28px; line-height: 1.9; font-size: 15px; color: #374151; white-space: pre-wrap; }
.nd-summary-label { font-size: 12px; font-weight: 600; color: #6366f1; margin-bottom: 8px; }
.nd-actions { padding: 0 28px 24px; }
.nd-link { display: inline-flex; align-items: center; gap: 6px; padding: 10px 24px; border-radius: 10px; font-size: 14px; font-weight: 500; text-decoration: none; }
.nd-link.primary { background: linear-gradient(135deg,#2563eb,#1d4ed8); color: #fff; }
.nd-related { background: #fff; border-radius: 14px; box-shadow: 0 1px 4px rgba(0,0,0,.06); margin-top: 16px; padding: 20px 24px; }
.nd-related h3 { font-size: 14px; font-weight: 600; margin: 0 0 12px; }
.nd-rel-item { display: flex; gap: 12px; padding: 10px 12px; border-radius: 8px; cursor: pointer; }
.nd-rel-item:hover { background: #f8fafc; }
.nd-rel-date { font-size: 11px; color: #9ca3af; min-width: 72px; padding-top: 2px; }
.nd-rel-title { font-size: 13px; font-weight: 500; color: #1f2937; }
.nd-rel-source { font-size: 11px; color: #9ca3af; margin-top: 2px; }
</style>
