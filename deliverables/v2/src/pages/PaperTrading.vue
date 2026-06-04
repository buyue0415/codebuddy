<template>
  <div class="page-content">
    <!-- Error banner -->
    <div v-if="errorText" class="error-banner" @click="errorText=''">
      ⚠️ {{ errorText }} (点击关闭)
    </div>

    <div v-if="loading" class="loading"><div class="spinner"></div></div>
    <template v-else>
      <!-- Account Card -->
      <div class="card account-card" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px">
        <div>
          <h2 style="margin:0 0 8px;font-size:16px">💼 虚拟账户</h2>
          <div v-if="account?.initialized" style="font-size:12px;color:#6b7280">
            初始资金: ¥{{ fmtMoney(account.initial_capital) }} &nbsp;|&nbsp;
            {{ (account.created_at || '').slice(0,16) }}
          </div>
        </div>
        <div v-if="account?.initialized" style="display:flex;gap:24px;flex-wrap:wrap">
          <div><div style="font-size:11px;color:#6b7280">当前总资产</div>
            <div style="font-size:22px;font-weight:700" :class="pnlClass(account.cumulative_return_pct)">
              ¥{{ fmtMoney(account.total_asset) }}
              <span style="font-size:14px">({{ pnlSign(account.cumulative_return_pct) }}{{ fmtPct(account.cumulative_return_pct) }})</span>
            </div>
          </div>
          <div><div style="font-size:11px;color:#6b7280">可用现金</div>
            <div style="font-size:18px;font-weight:600">¥{{ fmtMoney(account.cash) }}</div>
          </div>
          <div><div style="font-size:11px;color:#6b7280">持仓市值</div>
            <div style="font-size:18px;font-weight:600">¥{{ fmtMoney(account.position_value) }}</div>
          </div>
        </div>
        <div v-else style="color:#dc2626;display:flex;align-items:center;gap:12px">
          <span>虚拟账户未初始化</span>
          <button class="tab-btn" style="background:#16a34a;color:#fff;border-color:#16a34a;padding:6px 16px"
            @click="initAccount" :disabled="initLoading">
            {{ initLoading ? '初始化中...' : '初始化 ¥100,000' }}
          </button>
        </div>
        <button v-if="account?.initialized" class="tab-btn" style="background:#f59e0b;color:#fff;border-color:#f59e0b"
          @click="confirmReset">🔄 重置</button>
      </div>

      <!-- Suggestions -->
      <div class="card" v-if="suggestions.length">
        <h2>📋 今日交易结果</h2>
        <div style="font-size:11px;color:#6b7280;margin-bottom:12px">
          交易由算法自动执行，以下为已执行的交易结果
        </div>
        <div v-for="sug in suggestions" :key="sug.code" class="sug-card" :class="sugCardClass(sug)">
          <div class="sug-header">
            <span class="sug-name">{{ sug.name || sug.code }} <span class="sug-code">{{ sug.code }}</span></span>
            <span class="sug-badge" :class="sug.action">
              {{ actionText(sug.action) }}
            </span>
          </div>
          <div class="sug-body">
            <div class="sug-row">
              <span>方向: <b :class="dirClass(sug.direction)">{{ dirText(sug.direction) }}</b></span>
              <span>置信度: <b>{{ pct(sug.confidence) }}%</b></span>
              <span v-if="sug.qty">数量: <b>{{ sug.qty }}股</b></span>
            </div>
            <div class="sug-row" v-if="sug.price">
              <span>执行价: <b>¥{{ fmt(sug.price) }}</b></span>
              <span v-if="sug.entry_zone">入场位: ¥{{ fmt(sug.entry_zone) }}</span>
            </div>
            <div class="sug-reason" v-if="sug.reason">{{ sug.reason }}</div>
          </div>
        </div>
      </div>
      <div class="card" v-else>
        <h2>📋 今日交易结果</h2>
        <div class="empty">今日暂无自动交易结果</div>
      </div>

      <!-- Positions -->
      <div class="card">
        <h2>📦 虚拟持仓 <span style="font-size:12px;color:#f59e0b;font-weight:400">(橙色标识)</span></h2>
        <table v-if="positions.length" class="paper-table">
          <thead><tr><th>股票</th><th>代码</th><th>持仓量</th><th>成本价</th><th>现价</th><th>市值</th><th>浮盈亏</th></tr></thead>
          <tbody>
            <tr v-for="p in positions" :key="p.code">
              <td>{{ p.name || p.code }}</td>
              <td>{{ p.code }}</td>
              <td>{{ p.qty }}股</td>
              <td>¥{{ fmt(p.avg_cost) }}</td>
              <td>¥{{ p.last_price ? fmt(p.last_price) : '--' }}</td>
              <td>¥{{ fmtMoney(p.market_value) }}</td>
              <td :class="pnlClass(p.unrealized_pnl)">
                {{ pnlSign(p.unrealized_pnl) }}¥{{ fmtMoney(Math.abs(p.unrealized_pnl||0)) }}
                <span v-if="p.unrealized_pnl_pct">({{ pnlSign(p.unrealized_pnl_pct) }}{{ fmtPct(p.unrealized_pnl_pct) }})</span>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty">暂无虚拟持仓</div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { usePaperStore } from '@/stores/paper.js'

const store = usePaperStore()
const { account, positions, suggestions } = storeToRefs(store)
const { loadAccount, loadPositions, loadSuggestions, resetAccount } = store

const loading = ref(false)
const errorText = ref('')
const initLoading = ref(false)

onMounted(async () => {
  loading.value = true
  errorText.value = ''
  try {
    // Load suggestions first — they may auto-execute trades and create positions
    await Promise.all([loadAccount(), loadSuggestions()])
    await loadPositions()
  } catch (e) {
    errorText.value = '加载数据失败: ' + (e.message || '网络错误，请确认后端服务已启动(端口8766)')
  }
  loading.value = false
})

async function initAccount() {
  initLoading.value = true
  errorText.value = ''
  try {
    const r = await resetAccount(100000)
    if (!r?.success) {
      errorText.value = '初始化失败: ' + (r?.error || 'API返回异常，请确认后端已启动')
      return
    }
    // Load suggestions first — they auto-execute trades and create positions
    await loadSuggestions()
    await loadPositions()
  } catch (e) {
    errorText.value = '初始化异常: ' + (e.message || '未知错误')
  } finally {
    initLoading.value = false
  }
}

async function confirmReset() {
  if (!confirm('确认重置虚拟账户？所有持仓将被清空，现金恢复为 ¥100,000。交易历史记录将保留。')) return
  loading.value = true
  errorText.value = ''
  try {
    await resetAccount(100000)
    // Load suggestions first — they auto-execute trades and create positions
    await loadSuggestions()
    await loadPositions()
  } catch (e) {
    errorText.value = '重置失败: ' + (e.message || '未知错误')
  }
  loading.value = false
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
function pct(v) { return v != null ? Math.round(v * 100) : '--' }
function pnlClass(v) { return Number(v) > 0 ? 'up' : Number(v) < 0 ? 'down' : 'flat' }
function pnlSign(v) { return Number(v) > 0 ? '+' : Number(v) < 0 ? '-' : '' }
function dirClass(d) { return d === 'bullish' ? 'up' : d === 'bearish' ? 'down' : '' }
function dirText(d) { return d === 'bullish' ? '看涨 ↑' : d === 'bearish' ? '看跌 ↓' : '中性 →' }
function sugCardClass(s) { return s.action === 'buy' ? 'buy' : s.action === 'sell' ? 'sell' : 'hold' }
function actionText(a) { return a === 'buy' ? '已买入' : a === 'sell' ? '已卖出' : a === 'watch' ? '关注' : '观望' }
</script>

<style scoped>
.error-banner {
  background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px;
  padding: 10px 16px; margin-bottom: 16px; color: #991b1b;
  font-size: 13px; cursor: pointer;
}
.account-card {
  border-left: 4px solid #f59e0b;
}
.sug-card {
  border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px 18px;
  margin-bottom: 10px; transition: box-shadow .15s;
}
.sug-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,.06); }
.sug-card.buy { border-left: 4px solid #dc2626; background: #fef2f2; }
.sug-card.sell { border-left: 4px solid #16a34a; background: #f0fdf4; }
.sug-card.hold { border-left: 4px solid #9ca3af; background: #f9fafb; }
.sug-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.sug-name { font-weight: 600; font-size: 15px; }
.sug-code { font-size: 11px; color: #9ca3af; font-weight: 400; margin-left: 6px; }
.sug-badge { font-size: 11px; padding: 2px 10px; border-radius: 10px; font-weight: 600; }
.sug-badge.buy { background: #fecaca; color: #991b1b; }
.sug-badge.sell { background: #bbf7d0; color: #166534; }
.sug-badge.hold { background: #e5e7eb; color: #4b5563; }
.sug-row { display: flex; gap: 20px; font-size: 13px; color: #4b5563; margin-top: 4px; flex-wrap: wrap; }
.sug-reason { margin-top: 8px; font-size: 12px; color: #6b7280; padding-top: 8px; border-top: 1px dashed #e5e7eb; }
.paper-table { width: 100%; border-collapse: collapse; }
.paper-table thead { background: rgba(245,158,11,.08); }
</style>
