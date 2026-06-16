<template>
  <div class="page-content">
    <div v-if="data.loading" class="loading"><div class="spinner"></div></div>
    <div v-else-if="data.error" class="error-card"><h2>加载失败</h2><p>{{ data.error }}</p></div>
    <template v-else>
      <!-- Watchlist Management -->
      <div class="card">
        <h2>📋 监控股票管理</h2>

        <!-- Search + Add bar -->
        <div class="mg-add-bar">
          <div class="mg-ac-wrap">
            <input v-model="searchQuery" @input="onSearchInput" @keydown="onSearchKeydown"
              placeholder="输入代码/名称搜索股票..." class="mg-input" autocomplete="off" />
            <div class="mg-ac-drop" v-if="searchResults.length && dropdownOpen">
              <div v-for="(s, i) in searchResults" :key="s.code" class="mg-ac-item"
                :class="{ active: i === highlightIdx }"
                @mousedown.prevent="addStock(s)">
                <span class="mg-ac-name">{{ s.name }}</span>
                <span class="mg-ac-code">{{ s.code }}</span>
                <span class="mg-ac-mkt">{{ s.market }}</span>
                <span v-if="s.industry" class="mg-ac-ind">{{ s.industry }}</span>
              </div>
            </div>
          </div>
          <button class="tab-btn mg-add-btn" @click="addStockFromInput" :disabled="adding">
            {{ adding ? (progressMsg || '添加中...') : '＋ 添加' }}
          </button>
          <span class="mg-count" v-if="data.watchlist.length">{{ data.watchlist.length }} 只自选股</span>
        </div>

        <!-- Progress bar -->
        <div class="mg-progress" v-if="progressCurrent >= 0">
          <div class="mg-pbar-track">
            <div class="mg-pbar-fill" :style="{ width: ((progressCurrent + 1) / progressSteps.length * 100) + '%' }"></div>
          </div>
          <div class="mg-psteps">
            <div v-for="(step, i) in progressSteps" :key="i" class="mg-pstep"
              :class="{
                'mg-pstep-done': i < progressCurrent,
                'mg-pstep-active': i === progressCurrent,
                'mg-pstep-pending': i > progressCurrent
              }">
              <span class="mg-pstep-icon">
                <span v-if="i < progressCurrent">✓</span>
                <span v-else-if="i === progressCurrent" class="mg-pstep-spin">◌</span>
                <span v-else>{{ i + 1 }}</span>
              </span>
              <span class="mg-pstep-label">{{ step }}</span>
            </div>
          </div>
          <div class="mg-pmsg">{{ progressMsg }}</div>
        </div>

        <div class="mg-status" v-if="status && progressCurrent < 0">{{ status }}</div>

        <!-- Watchlist grouped by industry -->
        <div class="mg-groups" v-if="watchlistGroups.length">
          <div v-for="group in watchlistGroups" :key="group.industry" class="mg-group">
            <div class="mg-group-head" :class="{ expanded: expandedMap[group.industry] }"
              @click="toggleGroup(group.industry)">
              <span class="mg-g-arrow">▸</span>
              <span class="mg-g-name">{{ group.industry }}</span>
              <span class="mg-g-count">{{ group.stocks.length }} 只</span>
            </div>
            <div class="mg-group-body" :class="{ expanded: expandedMap[group.industry] }">
              <div v-for="s in group.stocks" :key="s.code" class="mg-row">
                <span class="mg-r-name">{{ s.name }}</span>
                <span class="mg-r-code">{{ s.code }}</span>
                <span class="mg-r-mkt">{{ s.market }}</span>
                <span class="mg-r-kline" :style="{ color: klineInfo[s.code] ? '#16a34a' : '#dc2626' }">
                  {{ klineInfo[s.code] ? klineInfo[s.code] + '条' : '无K线' }}
                </span>
                <a class="mg-r-del" @click.prevent="removeStock(s.code)">删除</a>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="mg-empty">
          <div class="mg-empty-icon">📭</div>
          <div>暂无自选股</div>
          <div class="mg-empty-hint">在上方搜索并添加股票</div>
        </div>
      </div>

      <!-- Statement Upload -->
      <div class="card">
        <h2>📋 更新对账单数据</h2>
        <div class="add-row">
          <label class="tab-btn" style="background:#16a34a;color:#fff;border-color:#16a34a;cursor:pointer">
            📁 选择广发对账单文件
            <input type="file" accept=".xlsx,.xls" @change="handleFile" style="display:none">
          </label>
          <span class="file-name">{{ fileName || '未选择文件' }}</span>
        </div>
        <div class="status">{{ uploadStatus }}</div>
      </div>

      <!-- Expert Import -->
      <div class="card">
        <h2>🧠 导入专家分析报告</h2>
        <div class="add-row">
          <label class="tab-btn" style="background:#7c3aed;color:#fff;border-color:#7c3aed;cursor:pointer">
            📁 选择JSON报告
            <input type="file" accept=".json,.md" @change="handleExpertFile" style="display:none">
          </label>
          <span class="file-name">{{ expertFileName || '未选择文件' }}</span>
        </div>
        <div style="margin-top:10px">
          <textarea v-model="expertJson" placeholder="或直接粘贴JSON报告..." class="textarea"></textarea>
          <button class="tab-btn" style="background:#7c3aed;color:#fff;border-color:#7c3aed;margin-top:6px" @click="importReport">📤 导入报告</button>
        </div>
        <div class="status">{{ expertStatus }}</div>
      </div>

      <!-- Server Status -->
      <div class="card">
        <h2>📡 服务器状态</h2>
        <div class="server-status">
          <span class="dot" :class="serverOnline ? 'online' : 'offline'"></span>
          {{ serverStatus }}
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted } from 'vue'
import { useDataStore } from '@/stores/data.js'
import { useIndustryStore } from '@/stores/industry.js'
import { apiCall } from '@/api/client.js'

const data = useDataStore()
const industryStore = useIndustryStore()
const klineInfo = computed(() => {
  const info = {}
  for (const [code, klines] of Object.entries(data.allKlineDaily || {})) {
    info[code] = klines.length
  }
  return info
})

// Search and add
const searchQuery = ref('')
const searchResults = ref([])
const highlightIdx = ref(-1)
const dropdownOpen = ref(false)
const adding = ref(false)
const status = ref('')
let searchTimer = null

// Expand/collapse state (default all expanded)
const expandedMap = reactive({})
function toggleGroup(name) {
  expandedMap[name] = !expandedMap[name]
}

// Group watchlist by industry
const watchlistGroups = computed(() => {
  const map = {}
  for (const s of industryStore.flatStocks) {
    map[s.code] = s.industry
  }
  const groups = {}
  for (const s of data.watchlist) {
    const ind = map[s.code] || '未分类'
    if (!groups[ind]) groups[ind] = { industry: ind, stocks: [] }
    groups[ind].stocks.push(s)
  }
  const entries = Object.entries(groups)
  entries.sort((a, b) => a[0] === '未分类' ? 1 : b[0] === '未分类' ? -1 : a[0].localeCompare(b[0], 'zh'))
  return entries.map(([, g]) => g)
})

// Ensure all groups expanded by default
watchlistGroups.value // trigger computed
// But since computed is lazy, set expanded on first groups load
const initExpand = () => {
  for (const g of watchlistGroups.value) {
    if (expandedMap[g.industry] === undefined) {
      expandedMap[g.industry] = true
    }
  }
}

function onSearchInput() {
  clearTimeout(searchTimer)
  const q = searchQuery.value.trim()
  if (!q) { searchResults.value = []; dropdownOpen.value = false; return }
  searchTimer = setTimeout(async () => {
    const r = await apiCall('GET', '/api/search/stocks?q=' + encodeURIComponent(q))
    const list = (r?.data || []).slice(0, 10)
    // Attach industry info from store
    const map = {}
    for (const s of industryStore.flatStocks) map[s.code] = s.industry
    for (const s of list) {
      s.industry = map[s.code] || ''
      s.inWatchlist = data.watchlist.some(w => w.code === s.code)
    }
    searchResults.value = list
    dropdownOpen.value = list.length > 0
  }, 200)
}

function onSearchKeydown(e) {
  if (!searchResults.value.length) return
  if (e.key === 'ArrowDown') { e.preventDefault(); highlightIdx.value = Math.min(highlightIdx.value + 1, searchResults.value.length - 1) }
  else if (e.key === 'ArrowUp') { e.preventDefault(); highlightIdx.value = Math.max(highlightIdx.value - 1, 0) }
  else if (e.key === 'Enter') {
    e.preventDefault()
    if (highlightIdx.value >= 0) addStock(searchResults.value[highlightIdx.value])
    else addStockFromInput()
  }
  else if (e.key === 'Escape') { dropdownOpen.value = false }
}

async function addStockFromInput() {
  const q = searchQuery.value.trim()
  if (!q) { status.value = '请输入股票代码或名称'; return }
  // Search first
  const r = await apiCall('GET', '/api/search/stocks?q=' + encodeURIComponent(q))
  const list = r?.data || []
  const exact = list.find(s => s.code === q) || list[0]
  if (exact) {
    await addStock(exact)
  } else {
    // Fallback: use input as code
    await addStock({ code: q, name: q, market: 'sh' })
  }
}

// Progress tracking for stock add
const progressSteps = ref(['添加自选股', '行业分类', '行情数据', '新闻数据', '全量同步'])
const progressCurrent = ref(-1)
const progressMsg = ref('')

async function addStock(s) {
  if (s.inWatchlist) { status.value = s.name + ' 已在自选股中'; return }
  adding.value = true
  dropdownOpen.value = false
  progressCurrent.value = 0
  progressMsg.value = ''

  try {
    // Step 0: quick add
    progressCurrent.value = 0
    progressMsg.value = '添加自选股...'
    const r = await apiCall('POST', '/api/v2/watchlist', {
      code: s.code, name: s.name, market: s.market || 'sh',
    })
    if (!r?.success) {
      status.value = '❌ ' + (r?.error || '添加失败')
      adding.value = false; progressCurrent.value = -1; return
    }
    progressMsg.value = '✅ 已添加'
    searchQuery.value = ''
    searchResults.value = []

    // Step 1: industry
    progressCurrent.value = 1
    progressMsg.value = '获取行业分类...'
    await industryStore.refreshIndustries()
    await sleep(200)
    progressMsg.value = '✅ 行业分类完成'

    // Step 2: quotes
    progressCurrent.value = 2
    progressMsg.value = '获取行情数据...'
    try {
      await apiCall('POST', '/api/v2/quotes/refresh')
    } catch (_) {}
    progressMsg.value = '✅ 行情数据完成'

    // Step 3: news
    progressCurrent.value = 3
    progressMsg.value = '获取新闻...'
    try {
      await apiCall('POST', '/api/trigger/news')
    } catch (_) {}
    progressMsg.value = '✅ 新闻完成'

    // Step 4: full sync
    progressCurrent.value = 4
    progressMsg.value = '全量同步中（K线+预测，约1-3分钟）...'
    try {
      await apiCall('POST', '/api/trigger/predict')
    } catch (_) {}
    progressMsg.value = '✅ 全量同步完成'

    // Final refresh
    progressMsg.value = '更新数据...'
    await data.fetchAll()
    initExpand()
    progressCurrent.value = -1
    status.value = '✅ 已添加 ' + s.name + '，所有数据同步完成'
  } catch (e) {
    status.value = '❌ ' + e.message
    progressCurrent.value = -1
  }
  adding.value = false
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)) }

async function removeStock(code) {
  if (!confirm('确定删除自选股 ' + code + '？')) return
  status.value = '移除中...'
  try {
    const r = await apiCall('DELETE', '/api/v2/watchlist/' + code)
    if (r?.success) {
      status.value = '✅ 已移除'
      await data.fetchAll()
    } else {
      status.value = '❌ ' + (r?.error || '移除失败')
    }
  } catch (e) {
    status.value = '❌ ' + e.message
  }
}

// Statement upload
const fileName = ref('')
const uploadStatus = ref('')
function handleFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  fileName.value = file.name
  uploadFile(file)
}
async function uploadFile(file) {
  uploadStatus.value = '上传中...'
  const form = new FormData()
  form.append('file', file)
  try {
    const r = await fetch('/api/upload/statement', { method: 'POST', body: form })
    const j = await r.json()
    uploadStatus.value = j?.success ? '✅ 上传成功，数据已更新' : '❌ ' + (j?.error || '失败')
    if (j?.success) await data.fetchAll()
  } catch (e) { uploadStatus.value = '❌ ' + e.message }
}

// Expert import
const expertJson = ref('')
const expertStatus = ref('')
const expertFileName = ref('')
async function importReport() {
  const txt = expertJson.value.trim()
  if (!txt) { expertStatus.value = '请输入JSON报告'; return }
  expertStatus.value = '导入中...'
  try {
    const body = JSON.parse(txt)
    const r = await apiCall('POST', '/api/v2/expert/import', body)
    expertStatus.value = r?.success ? '✅ 导入成功' : '❌ ' + (r?.error || '失败')
    if (r?.success) { expertJson.value = ''; await data.fetchAll() }
  } catch (e) { expertStatus.value = '❌ ' + (e.message || 'JSON格式错误') }
}
function handleExpertFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  expertFileName.value = file.name
  const reader = new FileReader()
  reader.onload = (ev) => { expertJson.value = ev.target.result; importReport() }
  reader.readAsText(file)
}

// Server
const serverOnline = ref(false)
const serverStatus = ref('检测中...')
async function checkServer() {
  try {
    const r = await apiCall('GET', '/api/v2/config')
    serverOnline.value = r?.success
    serverStatus.value = r?.success ? '已连接 · 端口8766 · 监控' + data.watchlist.length + '只股票' : '服务异常'
  } catch (e) {
    serverOnline.value = false
    serverStatus.value = '连接失败: ' + e.message
  }
}

onMounted(async () => {
  if (!data.watchlist.length) await data.fetchAll()
  if (!industryStore.flatStocks.length) await industryStore.fetchIndustries()
  initExpand()
  checkServer()
})
</script>

<style scoped>
.page-content { max-width: 1200px; margin: 0 auto; }
.loading { text-align: center; padding: 60px; }
.spinner { width: 36px; height: 36px; border: 3px solid #e5e7eb; border-top-color: #2563eb; border-radius: 50%; animation: spin .8s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-card { background: #fef2f2; border: 1px solid #fca5a5; border-radius: 12px; padding: 32px; text-align: center; }
.add-row { display: flex; gap: 10px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
.input { padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; outline: none; }
.input:focus { border-color: #2563eb; }
.file-name { font-size: 13px; color: #6b7280; }
.textarea { width: 100%; height: 80px; padding: 8px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 12px; font-family: monospace; resize: vertical; box-sizing: border-box; }
.status { font-size: 12px; color: #6b7280; margin-top: 8px; }
.server-status { display: flex; align-items: center; gap: 8px; font-size: 14px; color: #374151; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot.online { background: #16a34a; }
.dot.offline { background: #dc2626; }

/* Search bar */
.mg-add-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.mg-ac-wrap { position: relative; flex: 1; min-width: 200px; }
.mg-input { width: 100%; padding: 7px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 13px; outline: none; box-sizing: border-box; }
.mg-input:focus { border-color: #2563eb; }
.mg-add-btn { flex-shrink: 0; }
.mg-count { font-size: 12px; color: #64748b; white-space: nowrap; }
.mg-status { font-size: 12px; color: #6b7280; margin-bottom: 10px; }

/* Autocomplete */
.mg-ac-drop {
  position: absolute; top: 100%; left: 0; right: 0; margin-top: 2px;
  background: #fff; border: 1px solid #e2e8f0;
  border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,.1);
  z-index: 100; max-height: 300px; overflow-y: auto;
}
.mg-ac-item {
  display: flex; align-items: center; gap: 8px; padding: 8px 12px;
  cursor: pointer; font-size: 13px; transition: background .1s;
}
.mg-ac-item:hover, .mg-ac-item.active { background: #eff6ff; }
.mg-ac-name { font-weight: 500; color: #1f2937; }
.mg-ac-code { font-family: monospace; font-size: 11px; color: #64748b; }
.mg-ac-mkt { font-size: 10px; color: #fff; background: #94a3b8; padding: 0 4px; border-radius: 3px; }
.mg-ac-ind { font-size: 11px; color: #94a3b8; margin-left: auto; }

/* Industry groups */
.mg-groups { border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }
.mg-group + .mg-group { border-top: 1px solid #f1f5f9; }
.mg-group-head {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; cursor: pointer; user-select: none;
  background: #fafbfc; transition: background .1s;
}
.mg-group-head:hover { background: #f1f5f9; }
.mg-g-arrow { font-size: 10px; color: #94a3b8; transition: transform .2s; width: 14px; text-align: center; flex-shrink: 0; }
.mg-group-head.expanded .mg-g-arrow { transform: rotate(90deg); }
.mg-g-name { flex: 1; font-size: 13px; font-weight: 600; color: #1e293b; }
.mg-g-count { font-size: 11px; color: #94a3b8; }
.mg-group-body {
  display: none; padding: 0 14px 4px 32px;
}
.mg-group-body.expanded { display: block; }

.mg-row {
  display: flex; align-items: center; gap: 10px;
  padding: 7px 8px; border-radius: 6px; font-size: 13px;
}
.mg-row:hover { background: #f8fafc; }
.mg-r-name { flex: 1; font-weight: 500; color: #1e293b; }
.mg-r-code { font-family: monospace; font-size: 11px; color: #64748b; }
.mg-r-mkt { font-size: 10px; color: #fff; background: #94a3b8; padding: 0 5px; border-radius: 3px; }
.mg-r-kline { font-size: 11px; white-space: nowrap; }
.mg-r-del { font-size: 12px; color: #dc2626; cursor: pointer; padding: 2px 6px; border-radius: 4px; }
.mg-r-del:hover { background: #fee2e2; }

/* Empty state */
.mg-empty { text-align: center; padding: 32px; color: #94a3b8; }
.mg-empty-icon { font-size: 32px; margin-bottom: 8px; }
.mg-empty-hint { font-size: 12px; margin-top: 4px; color: #cbd5e1; }

/* Progress bar */
.mg-progress { margin-bottom: 12px; padding: 10px 12px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; }
.mg-pbar-track { height: 4px; background: #e2e8f0; border-radius: 2px; overflow: hidden; margin-bottom: 10px; }
.mg-pbar-fill { height: 100%; background: linear-gradient(90deg, #2563eb, #3b82f6); border-radius: 2px; transition: width .4s ease; }
.mg-psteps { display: flex; gap: 0; margin-bottom: 6px; }
.mg-pstep { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 2px; font-size: 11px; position: relative; }
.mg-pstep + .mg-pstep::before { content: ''; position: absolute; left: -50%; top: 6px; width: 100%; height: 1px; background: #e2e8f0; z-index: 0; }
.mg-pstep-done + .mg-pstep::before { background: #2563eb; }
.mg-pstep-icon { width: 13px; height: 13px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 8px; font-weight: 700; position: relative; z-index: 1; }
.mg-pstep-pending .mg-pstep-icon { background: #e2e8f0; color: #94a3b8; }
.mg-pstep-active .mg-pstep-icon { background: #2563eb; color: #fff; }
.mg-pstep-done .mg-pstep-icon { background: #16a34a; color: #fff; }
.mg-pstep-spin { display: inline-block; animation: mgSpin .8s linear infinite; font-size: 11px; }
@keyframes mgSpin { to { transform: rotate(360deg); } }
.mg-pstep-label { color: #64748b; white-space: nowrap; }
.mg-pstep-active .mg-pstep-label { color: #2563eb; font-weight: 600; }
.mg-pstep-done .mg-pstep-label { color: #16a34a; }
.mg-pmsg { text-align: center; font-size: 12px; color: #64748b; }
</style>
