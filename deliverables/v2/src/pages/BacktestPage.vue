<template>
  <div class="page-content">
    <div v-if="loading" class="loading"><div class="spinner"></div></div>
    <template v-else>
      <!-- Controls -->
      <div class="card" style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
        <button class="tab-btn" style="background:#2563eb;color:#fff;border-color:#2563eb;padding:8px 20px"
          @click="startRun" :disabled="btStatus === 'running' || starting || stopping">
          {{ btStatus === 'running' ? '⏳ 运行中...' : starting ? '🔄 启动中...' : '▶ 运行回测' }}
        </button>
        <button class="tab-btn" style="padding:8px 20px"
          @click="stopRun" :disabled="btStatus !== 'running' || stopping"
          :style="stopBtnStyle">
          {{ stopping ? '⏳ 停止中...' : '■ 停止回测' }}
        </button>
        <label>训练窗口:
          <select v-model="trainWin" class="input" style="width:100px;margin-left:6px" :disabled="btStatus==='running'">
            <option :value="126">126天</option>
            <option :value="252">252天</option>
            <option :value="504">504天</option>
          </select>
        </label>
        <label>测试窗口:
          <select v-model="testWin" class="input" style="width:90px;margin-left:6px" :disabled="btStatus==='running'">
            <option :value="10">10天</option>
            <option :value="21">21天</option>
            <option :value="42">42天</option>
          </select>
        </label>
        <span v-if="btError" style="color:#dc2626;font-size:12px">{{ btError }}</span>
      </div>

      <!-- Progress bar -->
      <div v-if="btStatus==='running'" class="card" style="padding:16px 20px">
        <div style="display:flex;justify-content:space-between;margin-bottom:8px;font-size:13px">
          <span>● 正在处理 <b>{{ btProgress?.current_stock || '...' }}</b></span>
          <span style="color:#2563eb;font-weight:600">{{ pct }}%（{{ btProgress?.current||0 }}/{{ btProgress?.total||0 }}）</span>
        </div>
        <div style="background:#e5e7eb;border-radius:8px;height:10px;overflow:hidden">
          <div :style="{width: pct+'%', background:'linear-gradient(90deg,#2563eb,#3b82f6)', height:'100%', borderRadius:'8px', transition:'width .5s ease'}"></div>
        </div>
      </div>
      <div v-else-if="btStatus==='done'" class="card" style="background:#f0fdf4;border:1px solid #bbf7d0;padding:12px 16px;color:#166534;font-weight:600;font-size:14px">✓ 回测完成</div>
      <div v-else-if="btStatus==='cancelled'" class="card" style="background:#fffbeb;border:1px solid #fcd34d;padding:12px 16px;color:#92400e;font-size:13px">⚠ 回测已停止（用户取消）</div>
      <div v-else-if="btStatus==='error'" class="card" style="background:#fef2f2;border:1px solid #fecaca;padding:12px 16px;color:#991b1b;font-size:13px">✗ 回测失败，请查看下方历史记录或重试</div>

      <!-- Tip -->
      <div v-if="!btStatus || btStatus==='idle'" class="card" style="background:#fffbeb;border-left:4px solid #f59e0b;font-size:12px;color:#92400e;padding:10px 16px;margin-top:8px">
        💡 6 只股票全量回测约需 20 秒。处理中可切换页面，运行不受影响。
      </div>

      <!-- Aggregate Metrics -->
      <div v-if="results" class="stat-grid" style="margin-bottom:20px">
        <div class="stat-item blue">
          <div class="stat-label">夏普比率（均值）</div>
          <div class="stat-val">{{ fmtNum(avgMetrics.sharpe) }}</div>
        </div>
        <div class="stat-item neutral">
          <div class="stat-label">最大回撤（均值）</div>
          <div class="stat-val" :class="(avgMetrics.max_drawdown || 0) < -10 ? 'down' : ''">
            {{ fmtPct(avgMetrics.max_drawdown) }}
          </div>
        </div>
        <div class="stat-item blue">
          <div class="stat-label">胜率（均值）</div>
          <div class="stat-val">{{ fmtPct(avgMetrics.win_rate) }}</div>
        </div>
        <div class="stat-item profit">
          <div class="stat-label">年化收益（均值）</div>
          <div class="stat-val">{{ fmtPct(avgMetrics.annual_return) }}</div>
        </div>
      </div>

      <!-- Per-Stock Breakdown -->
      <div v-if="stockResults.length" class="card" style="margin-bottom:20px">
        <h2>📊 各股票回测明细</h2>
        <table>
          <thead>
            <tr>
              <th>股票</th>
              <th>夏普比率</th>
              <th>最大回撤</th>
              <th>胜率</th>
              <th>年化收益</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in stockResults" :key="row.code">
              <td><b>{{ row.name }}</b><span class="code-hint">{{ row.code }}</span></td>
              <td :class="row.sharpe >= 0 ? 'up' : 'down'">{{ fmtNum(row.sharpe) }}</td>
              <td class="down">{{ fmtPct(row.max_drawdown) }}</td>
              <td>{{ fmtPct(row.win_rate) }}</td>
              <td :class="row.annual_return >= 0 ? 'up' : 'down'">{{ fmtPct(row.annual_return) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- History -->
      <div class="card">
        <h2>📜 回测运行历史 <span class="hint">（点击行查看明细）</span></h2>
        <table v-if="history.length">
          <thead><tr><th>时间</th><th>状态</th><th>训练</th><th>测试</th><th>股票</th><th>夏普</th><th>最大回撤</th><th>胜率</th><th>年化</th></tr></thead>
          <tbody>
            <tr v-for="h in history" :key="h.id" style="cursor:pointer" @click="viewResult(h.id)"
              :class="{ 'row-selected': h.id === results?.run_id }">
              <td>{{ (h.started_at || '').slice(0,16) }}</td>
              <td><span :class="statusClass(h)">{{ statusText(h) }}</span></td>
              <td>{{ h.train_window }}天</td>
              <td>{{ h.test_window }}天</td>
              <td>{{ h.total_stocks }}</td>
              <td :class="tryParseField(h.summary_json, 'sharpe') >= 0 ? 'up' : 'down'">{{ fmtNum(tryParseField(h.summary_json, 'sharpe')) }}</td>
              <td class="down">{{ fmtPct(tryParseField(h.summary_json, 'max_drawdown')) }}</td>
              <td>{{ fmtPct(tryParseField(h.summary_json, 'win_rate')) }}</td>
              <td :class="tryParseField(h.summary_json, 'annual_return') >= 0 ? 'up' : 'down'">{{ fmtPct(tryParseField(h.summary_json, 'annual_return')) }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty">暂无回测记录，请先运行回测</div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { usePaperStore } from '@/stores/paper.js'
import { useDataStore } from '@/stores/data.js'

const store = usePaperStore()
const dataStore = useDataStore()
const {
  backtestStatus: btStatus, backtestProgress: btProgress,
  backtestResults: results, backtestHistory: history,
} = storeToRefs(store)
const {
  startBacktest, stopBacktest, pollBacktestStatus, loadBacktestResults, loadBacktestHistory,
} = store

const loading = ref(false)
const trainWin = ref(252)
const testWin = ref(21)
const btError = ref('')
const starting = ref(false)
const stopping = ref(false)

const pct = computed(() => {
  const p = btProgress.value
  if (!p || !p.total) return 0
  return Math.round(p.current / p.total * 100)
})

// Build per-stock rows with names from watchlist
const stockResults = computed(() => {
  const raw = results.value?.overall_metrics?.results
  if (!raw) return []
  const names = {}
  if (dataStore.watchlist) {
    dataStore.watchlist.forEach(s => { names[s.code] = s.name })
  }
  return Object.entries(raw).map(([code, r]) => ({
    code,
    name: names[code] || code,
    sharpe: r.sharpe ?? 0,
    max_drawdown: r.max_drawdown ?? 0,
    win_rate: r.win_rate ?? 0,
    annual_return: r.annual_return ?? 0,
  }))
})

// Aggregate metrics: use top-level avg_* fields, fallback to computing from per-stock results
const avgMetrics = computed(() => {
  const om = results.value?.overall_metrics || {}
  const computeFromResults = () => {
    const raw = om.results
    if (!raw) return null
    const entries = Object.values(raw)
    if (!entries.length) return null
    const avg = key => {
      const vals = entries.map(r => r[key]).filter(v => v != null && !isNaN(v))
      return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null
    }
    return {
      sharpe: avg('sharpe'),
      max_drawdown: avg('max_drawdown'),
      win_rate: avg('win_rate'),
      annual_return: avg('annual_return'),
    }
  }
  const fallback = computeFromResults()
  return {
    sharpe: om.avg_sharpe ?? fallback?.sharpe ?? null,
    max_drawdown: om.avg_max_drawdown ?? fallback?.max_drawdown ?? null,
    win_rate: om.avg_win_rate ?? fallback?.win_rate ?? null,
    annual_return: om.avg_annual_return ?? fallback?.annual_return ?? null,
  }
})

const stopBtnStyle = computed(() => {
  if (btStatus.value === 'running') {
    return { background: '#dc2626', color: '#fff', borderColor: '#dc2626' }
  }
  return { background: '#9ca3af', color: '#fff', borderColor: '#9ca3af', opacity: '0.5', cursor: 'not-allowed' }
})

let pollTimer = null

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    try {
      await pollBacktestStatus()
      if (btStatus.value === 'done' && btProgress.value?.run_id) {
        await loadBacktestResults(btProgress.value.run_id)
        await loadBacktestHistory()
        stopPolling()
      } else if (btStatus.value === 'error' || btStatus.value === 'cancelled') {
        await loadBacktestHistory()
        stopPolling()
      }
    } catch (e) {
      // Silently continue polling on network errors
      console.warn('Poll status error:', e.message)
    }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(async () => {
  loading.value = true
  await loadBacktestHistory()
  // Auto-load latest completed run so metrics + per-stock table are visible immediately
  const latestDone = history.value.find(h => h.status === 'done')
  if (latestDone) await loadBacktestResults(latestDone.id)
  loading.value = false
})

onUnmounted(() => stopPolling())

// Watch btStatus changes to start/stop polling
watch(btStatus, (newStatus, oldStatus) => {
  if (newStatus === 'running') {
    starting.value = false
    startPolling()
  } else if (oldStatus === 'running' && newStatus !== 'running') {
    stopping.value = false
    stopPolling()
  }
})

async function startRun() {
  btError.value = ''
  starting.value = true
  try {
    const rid = await startBacktest({ train_window: trainWin.value, test_window: testWin.value })
    if (!rid) {
      btError.value = '启动回测失败，请查看后端日志'
      starting.value = false
    }
  } catch (e) {
    btError.value = '启动回测异常: ' + (e.message || '网络错误')
    starting.value = false
  }
}

async function stopRun() {
  btError.value = ''
  stopping.value = true
  try {
    await stopBacktest()
  } catch (e) {
    btError.value = '停止回测失败: ' + (e.message || '网络错误')
    stopping.value = false
  }
}

async function viewResult(runId) {
  loading.value = true
  await loadBacktestResults(runId)
  loading.value = false
}

function fmtNum(v) { return v != null ? Number(v).toFixed(2) : '--' }
function fmtPct(v) { return v != null ? (Number(v) > 0 ? '+' : '') + Number(v).toFixed(1) + '%' : '--' }
function statusClass(h) {
  const s = typeof h === 'string' ? h : h?.status || ''
  const msg = typeof h === 'object' ? (h?.error_msg || '') : ''
  if (s === 'done') return 'up'
  if (s === 'running') return ''
  return 'down'
}
function statusText(h) {
  const s = typeof h === 'string' ? h : h?.status || ''
  const msg = typeof h === 'object' ? (h?.error_msg || '') : ''
  if (s === 'done') return '✓ 完成'
  if (s === 'running') return '● 运行中'
  if (msg && msg.includes('用户取消')) return '⚠ 已取消'
  if (msg && msg.includes('服务重启')) return '⚠ 服务中断'
  return '✗ 失败'
}
function tryParseField(s, key) {
  // Extract aggregate metric from summary_json.
  // Key map: sharpe→avg_sharpe, max_drawdown→avg_max_drawdown, etc.
  const keyMap = { sharpe: 'avg_sharpe', max_drawdown: 'avg_max_drawdown', win_rate: 'avg_win_rate', annual_return: 'avg_annual_return' }
  const aggKey = keyMap[key] || key
  if (!s) return null
  try {
    const j = JSON.parse(s)
    // New format: top-level avg_* field
    if (j[aggKey] != null) return j[aggKey]
    // Old format: compute average from per-stock results
    if (j.results) {
      const vals = Object.values(j.results).map(r => r[key]).filter(v => v != null)
      if (vals.length) return vals.reduce((a, b) => a + b, 0) / vals.length
    }
    return null
  } catch { return null }
}
</script>

<style scoped>
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }
.stat-item { background: #fff; border-radius: 12px; padding: 20px; text-align: center;
  box-shadow: 0 1px 3px rgba(0,0,0,.08); border-left: 4px solid; }
.stat-item.blue { border-left-color: #3b82f6; background: linear-gradient(135deg, #eff6ff, #fff); }
.stat-item.neutral { border-left-color: #6b7280; background: linear-gradient(135deg, #f9fafb, #fff); }
.stat-item.profit { border-left-color: #16a34a; background: linear-gradient(135deg, #f0fdf4, #fff); }
.stat-label { font-size: 12px; color: #6b7280; margin-bottom: 6px; }
.stat-val { font-size: 28px; font-weight: 700; color: #1e293b; }
.row-selected { background: #eff6ff; }
.code-hint { font-size: 11px; color: #9ca3af; margin-left: 6px; font-weight: 400; }
</style>
