<template>
  <div class="page-content">
    <div v-if="data.loading" class="loading"><div class="spinner"></div></div>
    <div v-else-if="data.error" class="error-card"><h2>加载失败</h2><p>{{ data.error }}</p></div>
    <template v-else>
      <!-- Watchlist Management -->
      <div class="card">
        <h2>📋 监控股票管理</h2>
        <div class="add-row">
          <div class="ac-wrapper">
            <input v-model="searchQuery" @input="onSearch" @keydown="onKeydown" @focus="onSearch" @blur="onBlur"
              placeholder="如 601398 或 工商" class="input" style="width:180px" autocomplete="off" ref="searchInput">
            <div class="ac-dropdown" :class="{ show: searchResults.length > 0 && dropdownOpen }">
              <div v-for="(s, i) in searchResults" :key="s.code"
                class="ac-item" :class="{ active: i === highlightIdx }"
                @mousedown.prevent="selectStock(s)">
                <span class="ac-name" v-html="highlightMatch(s.name)"></span>
                <span class="ac-code">{{ s.code }} <span class="ac-mkt">{{ s.market }}</span></span>
              </div>
            </div>
          </div>
          <select v-model="market" class="input" style="width:100px">
            <option value="sh">沪市</option><option value="sz">深市</option>
          </select>
          <button class="tab-btn" style="background:#2563eb;color:#fff;border-color:#2563eb" @click="addStock" :disabled="adding">➕ 添加</button>
        </div>
        <table class="wl-table" v-if="data.watchlist.length">
          <thead><tr><th>代码</th><th>名称</th><th>市场</th><th>日K线</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="s in data.watchlist" :key="s.code">
              <td>{{ s.code }}</td><td><a href="#" @click.prevent="$router.push('/kline')">{{ s.name }}</a></td>
              <td>{{ s.market }}</td>
              <td><span :style="{color: klineInfo[s.code] ? '#16a34a' : '#dc2626', fontSize:'11px'}">
                {{ klineInfo[s.code] ? klineInfo[s.code] + '条' : '无' }}</span></td>
              <td><a href="#" @click.prevent="removeStock(s.code)" style="color:#dc2626;font-size:12px">删除</a></td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty">暂无自选股</div>
        <div class="status">{{ status }}</div>
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
import { ref, computed, onMounted } from 'vue'
import { useDataStore } from '@/stores/data.js'
import { apiCall } from '@/api/client.js'

const data = useDataStore()
const searchInput = ref(null)
const searchQuery = ref('')
const market = ref('sh')
const fileName = ref('')
const status = ref('')
const uploadStatus = ref('')
const expertJson = ref('')
const expertStatus = ref('')
const adding = ref(false)
const searchResults = ref([])
const expertFileName = ref('')
const serverOnline = ref(false)
const serverStatus = ref('检测中...')
const highlightIdx = ref(-1)
const dropdownOpen = ref(false)
let searchTimer = null

// K-line stats per stock (from data.kline_daily loaded in data store)
const klineInfo = computed(() => {
  // We need kline_daily — but data store doesn't store it. Let's add it.
  return {}
})

function onSearch() {
  clearTimeout(searchTimer)
  highlightIdx.value = -1
  searchTimer = setTimeout(async () => {
    const q = searchQuery.value.trim()
    if (!q) { searchResults.value = []; dropdownOpen.value = false; return }
    const r = await apiCall('GET', '/api/search/stocks?q=' + encodeURIComponent(q))
    searchResults.value = (r?.data || []).slice(0, 12)
    dropdownOpen.value = searchResults.value.length > 0
  }, 200)
}

function onKeydown(e) {
  if (!searchResults.value.length) return
  if (e.key === 'ArrowDown') { e.preventDefault(); highlightIdx.value = Math.min(highlightIdx.value + 1, searchResults.value.length - 1) }
  else if (e.key === 'ArrowUp') { e.preventDefault(); highlightIdx.value = Math.max(highlightIdx.value - 1, -1) }
  else if (e.key === 'Enter') {
    e.preventDefault()
    if (highlightIdx.value >= 0) selectStock(searchResults.value[highlightIdx.value])
    else if (searchQuery.value.trim()) addStock()
  }
  else if (e.key === 'Escape') { dropdownOpen.value = false }
}

function onBlur() { setTimeout(() => { dropdownOpen.value = false }, 200) }

const selectedStock = ref(null)

function selectStock(s) {
  selectedStock.value = s
  searchQuery.value = s.name + ' (' + s.code + ')'
  market.value = s.market || 'sh'
  dropdownOpen.value = false
  searchInput.value?.focus()
}

function highlightMatch(name) {
  if (!name) return ''
  const q = searchQuery.value.trim()
  if (!q) return name
  const re = new RegExp('(' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig')
  return name.replace(re, '<b class="hl">$1</b>')
}

async function addStock() {
  let code, name
  if (selectedStock.value) {
    code = selectedStock.value.code
    name = selectedStock.value.name
    market.value = selectedStock.value.market || 'sh'
  } else {
    code = searchQuery.value.trim()
    if (!code || code.length !== 6) { status.value = '请输入6位股票代码或从下拉选择'; return }
    name = code
    const sr = await apiCall('GET', '/api/search/stocks?q=' + code)
    if (sr?.data) { const found = sr.data.find(s => s.code === code); if (found) name = found.name }
  }
  adding.value = true; status.value = '添加中...'
  try {
    const r = await apiCall('POST', '/api/v2/watchlist', { code, name, market: market.value })
    if (r?.success) {
      status.value = '✅ 已添加 ' + name
      searchQuery.value = ''; selectedStock.value = null
      await data.fetchAll()
    } else status.value = '❌ ' + (r?.error || '添加失败')
  } catch (e) { status.value = '❌ ' + e.message }
  adding.value = false
}

async function removeStock(code) {
  if (!confirm('确定删除自选股 ' + code + '？')) return
  status.value = '移除中...'
  try {
    const r = await apiCall('DELETE', '/api/v2/watchlist/' + code)
    if (r?.success) { status.value = '✅ 已移除 ' + code; await data.fetchAll() }
    else status.value = '❌ ' + (r?.error || '移除失败')
  } catch (e) { status.value = '❌ ' + e.message }
}

function handleFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  fileName.value = file.name
  uploadFile(file)
}

async function uploadFile(file) {
  uploadStatus.value = '上传中...'
  const form = new FormData()
  form.append('statement', file)
  try {
    const r = await fetch('/api/upload/statement', { method: 'POST', body: form })
    const j = await r.json()
    uploadStatus.value = j?.success ? '✅ 上传成功，数据已更新' : '❌ ' + (j?.error || '失败')
    if (j?.success) await data.fetchAll()
  } catch (e) { uploadStatus.value = '❌ ' + e.message }
}

async function importReport() {
  const txt = expertJson.value.trim()
  if (!txt) { expertStatus.value = '请输入JSON报告'; return }
  expertStatus.value = '导入中...'
  try {
    const body = JSON.parse(txt)
    const r = await apiCall('POST', '/api/v2/expert/import', body)
    expertStatus.value = r?.success ? '✅ 导入成功' : '❌ ' + (r?.error || '失败')
    if (r?.success) expertJson.value = ''
  } catch (e) { expertStatus.value = '❌ ' + (e.message || 'JSON格式错误') }
}

function handleExpertFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  expertFileName.value = file.name
  const reader = new FileReader()
  reader.onload = (ev) => {
    expertJson.value = ev.target.result
    importReport()
  }
  reader.readAsText(file)
}

async function checkServer() {
  try {
    const r = await apiCall('GET', '/api/v2/config')
    serverOnline.value = r?.success
    serverStatus.value = r?.success
      ? '已连接 · 端口8765 · 监控' + data.watchlist.length + '只股票'
      : '服务异常'
  } catch (e) {
    serverOnline.value = false
    serverStatus.value = '连接失败: ' + e.message
  }
}

onMounted(async () => {
  if (!data.watchlist.length) await data.fetchAll()
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
.empty { text-align: center; padding: 24px; color: #9ca3af; }
.wl-table { margin-top: 12px; }
.wl-table a { text-decoration: none; }

/* Autocomplete */
.ac-wrapper { position: relative; }
.ac-dropdown { position: absolute; top: 100%; left: 0; right: 0; background: #fff; border: 1px solid #d1d5db; border-radius: 0 0 8px 8px; box-shadow: 0 4px 12px rgba(0,0,0,.1); z-index: 200; max-height: 260px; overflow-y: auto; display: none; }
.ac-dropdown.show { display: block; }
.ac-item { padding: 9px 12px; cursor: pointer; font-size: 13px; display: flex; justify-content: space-between; align-items: center; transition: background .1s; }
.ac-item:hover, .ac-item.active { background: #eff6ff; }
.ac-name { color: #1f2937; font-weight: 500; }
.ac-code { color: #6b7280; font-size: 12px; margin-left: 12px; white-space: nowrap; }
.ac-mkt { color: #9ca3af; font-size: 11px; margin-left: 4px; }
:deep(.hl) { color: #2563eb; font-weight: 600; }
.server-status { display: flex; align-items: center; gap: 8px; font-size: 14px; color: #374151; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot.online { background: #16a34a; }
.dot.offline { background: #dc2626; }
</style>
