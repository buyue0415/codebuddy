<template>
  <div class="overview-page">
    <!-- Loading State -->
    <div v-if="data.loading && !data.watchlist.length" class="loading">
      <div class="spinner"></div>
      <p>并行加载中 (15路API)...</p>
    </div>

    <div v-else-if="data.error && !data.watchlist.length" class="error-card">
      <h2>⚠️ 加载失败</h2>
      <p>{{ data.error }}</p>
      <button class="tab-btn primary" @click="data.fetchAll()">🔄 重试</button>
    </div>

    <template v-else>
      <!-- 刷新错误 Toast -->
      <Transition name="toast">
        <div v-if="data.refreshError" class="refresh-toast">
          <span class="toast-icon">⚠️</span>
          <span>{{ data.refreshError }}</span>
          <button class="toast-close" @click="data.refreshError = null">×</button>
        </div>
      </Transition>

      <div class="stat-grid">
        <div class="stat-item blue" :class="{ 'stat-pulse': data.refreshing }">
          <div class="label">总资产（持仓市值）</div>
          <div class="value">{{ overview.stats.totalAsset }}</div>
          <div class="sub">总成本 {{ overview.stats.totalCost }}</div>
        </div>
        <div class="stat-item" :class="[overview.stats.floatPnlClass, { 'stat-pulse': data.refreshing }]">
          <div class="label">浮动盈亏</div>
          <div class="value">{{ overview.stats.floatPnl }}</div>
          <div class="sub">{{ overview.stats.floatPnlPct }}</div>
        </div>
        <div class="stat-item profit" :class="{ 'stat-pulse': data.refreshing }">
          <div class="label">已实现盈亏+分红</div>
          <div class="value">{{ overview.stats.totalRealized }}</div>
          <div class="sub">含已清仓股票</div>
        </div>
        <div class="stat-item expense" :class="{ 'stat-pulse': data.refreshing }">
          <div class="label">累计手续费</div>
          <div class="value">{{ overview.stats.totalFees }}</div>
          <div class="sub">佣金+印花税+其他</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h2>当前持仓</h2>
          <span class="card-actions">
            <span class="refresh-time" :class="{ 'refresh-done': showRefreshDone }">
              {{ refreshLabel }}
            </span>
            <button
              class="tab-btn refresh-btn"
              :class="{ 'refresh-running': data.refreshing }"
              :disabled="data.refreshing"
              @click="handleRefresh"
            >
              <span class="btn-icon" :class="{ spinning: data.refreshing }">
                {{ data.refreshing ? '⏳' : '🔄' }}
              </span>
              <span>{{ data.refreshing ? '刷新中…' : '刷新股价' }}</span>
            </button>
          </span>
        </div>
        <table v-if="overview.positionRows.length">
          <thead>
            <tr><th>股票</th><th>持仓</th><th>成本价</th><th>现价</th><th>市值</th><th>浮盈亏</th><th>盈亏%</th><th>股息率<sup class="dy-hint">TTM</sup></th></tr>
          </thead>
          <tbody>
            <tr
              v-for="row in overview.positionRows"
              :key="row.code"
              :class="getRowFlash(row.code)"
            >
              <td><b>{{ row.name }}</b>({{ row.code }})</td>
              <td>{{ row.qty }}</td><td>{{ row.avgCost }}</td>
              <td :class="row.priceClass">{{ row.price }}</td><td>{{ row.marketValue }}</td>
              <td :class="row.pnlClass">{{ row.pnl }}</td><td :class="row.pnlClass">{{ row.pnlPct }}</td>
              <td class="up" :title="dyTooltip">{{ row.dy }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty">暂无持仓数据</div>
      </div>

      <div class="card" v-if="overview.closedRows.length">
        <h2>已清仓股票</h2>
        <table>
          <thead><tr><th>股票</th><th>交易盈亏</th><th>分红收入</th><th>合计收益</th></tr></thead>
          <tbody>
            <tr v-for="row in overview.closedRows" :key="row.code">
              <td>{{ row.name }}({{ row.code }})</td>
              <td :class="row.realizedClass">{{ row.realizedPnl }}</td>
              <td class="up">+{{ row.dividendsTotal }}</td>
              <td :class="row.totalClass" style="font-weight:700">{{ row.total }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card" v-if="overview.dividendRows.length">
        <h2>持仓分红收入明细 <span class="hint">· 对账单实际到账数据</span></h2>
        <table>
          <thead><tr><th>日期<sup class="hint">(派息日)</sup></th><th>股票</th><th>每股派息<sup class="hint" title="公式计算值 = 到账金额 ÷ 持仓股数">计</sup></th><th>持仓股数</th><th>分红金额</th></tr></thead>
          <tbody>
            <tr v-for="(d, i) in overview.dividendRows" :key="i">
              <td>{{ d.date }}</td><td>{{ d.name }}<span v-if="d.closed" class="closed-tag">已清仓</span></td>
              <td>{{ d.perShare }}</td><td>{{ d.qty }}</td><td class="div-amount">{{ d.amount }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { useOverviewStore } from '@/stores/overview.js'
import { useDataStore } from '@/stores/data.js'

const overview = useOverviewStore()
const data = useDataStore()

const dyTooltip = '公式计算值（TTM推算）\n基于最近12个月分红与当前股价推算\n与公司实际公布股息率可能存在差异'

// Track price changes per row for flash animation
const flashRows = ref({}) // { code: 'up' | 'down' | '' }
let flashTimers = {}

const showRefreshDone = ref(false)
let doneTimer = null

const refreshLabel = computed(() => {
  if (data.refreshing) return '正在获取实时行情…'
  if (data.lastRefresh) return `上次刷新 ${data.lastRefresh}`
  return ''
})

function getRowFlash(code) {
  const dir = flashRows.value[code]
  if (!dir) return ''
  return dir === 'up' ? 'row-flash-up' : 'row-flash-down'
}

async function handleRefresh() {
  if (data.refreshing) return

  // Clear previous flash states
  Object.keys(flashTimers).forEach(k => {
    clearTimeout(flashTimers[k])
    delete flashTimers[k]
  })
  flashRows.value = {}

  // Save old prices before refresh
  const oldPrices = {}
  for (const [code, q] of Object.entries(data.quotes)) {
    oldPrices[code] = q.price || 0
  }

  await data.refreshQuotesAndReload()

  // After data loaded, apply flash animations
  await nextTick()
  for (const code of Object.keys(data.quotes)) {
    const oldPrice = oldPrices[code]
    const newPrice = data.quotes[code]?.price
    if (oldPrice && newPrice && oldPrice !== newPrice) {
      const dir = newPrice > oldPrice ? 'up' : 'down'
      flashRows.value = { ...flashRows.value, [code]: dir }
      flashTimers[code] = setTimeout(() => {
        const next = { ...flashRows.value }
        delete next[code]
        flashRows.value = next
        delete flashTimers[code]
      }, 1200)
    }
  }

  // Show "refresh done" indicator
  if (!data.refreshError) {
    showRefreshDone.value = true
    if (doneTimer) clearTimeout(doneTimer)
    doneTimer = setTimeout(() => { showRefreshDone.value = false }, 2500)
  }
}

onMounted(() => {
  if (!data.watchlist.length) data.fetchAll()
})

onUnmounted(() => {
  Object.values(flashTimers).forEach(clearTimeout)
  if (doneTimer) clearTimeout(doneTimer)
})
</script>

<style scoped>
/* ─── Loading ─── */
.loading {
  text-align: center; padding: 60px; color: #6b7280;
}
.spinner {
  width: 36px; height: 36px;
  border: 3px solid #e5e7eb;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 16px;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ─── Error card ─── */
.error-card {
  background: #fef2f2; border: 1px solid #fca5a5;
  border-radius: 12px; padding: 32px; text-align: center;
}
.error-card h2 { color: #dc2626; margin-bottom: 8px; }
.error-card p { color: #6b7280; margin-bottom: 16px; }
.primary { background: #2563eb; color: #fff; border-color: #2563eb; }

/* ─── Toast (inline error) ─── */
.refresh-toast {
  display: flex; align-items: center; gap: 8px;
  background: #fef2f2; border: 1px solid #fca5a5;
  border-radius: 8px; padding: 10px 14px; margin-bottom: 12px;
  font-size: 13px; color: #dc2626;
}
.toast-icon { font-size: 16px; flex-shrink: 0; }
.toast-close {
  margin-left: auto; background: none; border: none;
  font-size: 18px; color: #9ca3af; cursor: pointer; padding: 0 4px;
}
.toast-enter-active { animation: toastIn 0.3s ease; }
.toast-leave-active { animation: toastIn 0.25s ease reverse; }
@keyframes toastIn {
  from { opacity: 0; transform: translateY(-8px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ─── Card header ─── */
.card-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.card-header h2 { margin-bottom: 0; }
.card-actions { display: flex; align-items: center; gap: 10px; }
.refresh-time { font-size: 12px; color: #6b7280; transition: color 0.3s; }
.refresh-time.refresh-done { color: #059669; }

/* ─── Refresh button ─── */
.refresh-btn {
  display: inline-flex; align-items: center; gap: 6px;
  transition: all 0.25s ease;
}
.refresh-btn:disabled {
  opacity: 0.7; cursor: not-allowed;
}
.refresh-btn:not(:disabled):hover {
  background: #dbeafe; border-color: #93c5fd; transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.15);
}
.refresh-btn:not(:disabled):active {
  transform: translateY(0);
}
.refresh-running {
  background: #eff6ff; border-color: #60a5fa; color: #2563eb;
}
.btn-icon {
  display: inline-block; font-size: 14px; line-height: 1;
}
.btn-icon.spinning {
  animation: btnSpin 1s linear infinite;
}
@keyframes btnSpin { to { transform: rotate(360deg); } }

/* ─── Stat grid pulse ─── */
.stat-pulse {
  animation: pulseBorder 1.5s ease-in-out infinite;
}
@keyframes pulseBorder {
  0%, 100% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0); }
  50%      { box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.08); }
}

/* ─── Row flash animations ─── */
.row-flash-up {
  animation: flashUp 1.2s ease;
}
.row-flash-down {
  animation: flashDown 1.2s ease;
}
@keyframes flashUp {
  0%   { background-color: rgba(22, 163, 74, 0.15); }
  60%  { background-color: rgba(22, 163, 74, 0.05); }
  100% { background-color: transparent; }
}
@keyframes flashDown {
  0%   { background-color: rgba(220, 38, 38, 0.12); }
  60%  { background-color: rgba(220, 38, 38, 0.04); }
  100% { background-color: transparent; }
}

/* ─── Misc ─── */
.hint { font-size: 12px; color: #6b7280; font-weight: 400; }
.dy-hint { font-size: 10px; color: #f59e0b; }
.div-amount { color: #dc2626; font-weight: 600; }
.closed-tag { color: #9ca3af; font-size: 11px; margin-left: 4px; }
.empty {
  text-align: center; padding: 40px; color: #9ca3af; font-size: 14px;
}
</style>
