<template>
  <div class="overview-page">
    <!-- Loading State -->
    <div v-if="data.loading" class="loading">
      <div class="spinner"></div>
      <p>并行加载中 (15路API)...</p>
    </div>

    <div v-else-if="data.error" class="error-card">
      <h2>⚠️ 加载失败</h2>
      <p>{{ data.error }}</p>
      <button class="tab-btn primary" @click="data.fetchAll()">🔄 重试</button>
    </div>

    <template v-else>
      <div class="stat-grid">
        <div class="stat-item blue">
          <div class="label">总资产（持仓市值）</div>
          <div class="value">{{ overview.stats.totalAsset }}</div>
          <div class="sub">总成本 {{ overview.stats.totalCost }}</div>
        </div>
        <div class="stat-item" :class="overview.stats.floatPnlClass">
          <div class="label">浮动盈亏</div>
          <div class="value">{{ overview.stats.floatPnl }}</div>
          <div class="sub">{{ overview.stats.floatPnlPct }}</div>
        </div>
        <div class="stat-item profit">
          <div class="label">已实现盈亏+分红</div>
          <div class="value">{{ overview.stats.totalRealized }}</div>
          <div class="sub">含已清仓股票</div>
        </div>
        <div class="stat-item expense">
          <div class="label">累计手续费</div>
          <div class="value">{{ overview.stats.totalFees }}</div>
          <div class="sub">佣金+印花税+其他</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h2>当前持仓</h2>
          <span class="card-actions">
            <span class="refresh-time">{{ data.lastRefresh }}</span>
            <button class="tab-btn" @click="data.fetchAll()">🔄 刷新股价</button>
          </span>
        </div>
        <table v-if="overview.positionRows.length">
          <thead>
            <tr><th>股票</th><th>持仓</th><th>成本价</th><th>现价</th><th>市值</th><th>浮盈亏</th><th>盈亏%</th><th>股息率<sup class="dy-hint">TTM</sup></th></tr>
          </thead>
          <tbody>
            <tr v-for="row in overview.positionRows" :key="row.code">
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
import { onMounted } from 'vue'
import { useOverviewStore } from '@/stores/overview.js'
import { useDataStore } from '@/stores/data.js'

const overview = useOverviewStore()
const data = useDataStore()

const dyTooltip = '公式计算值（TTM推算）\n基于最近12个月分红与当前股价推算\n与公司实际公布股息率可能存在差异'

onMounted(() => {
  if (!data.watchlist.length) data.fetchAll()
})
</script>

<style scoped>
.loading {
  text-align: center;
  padding: 60px;
  color: #6b7280;
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

.error-card {
  background: #fef2f2;
  border: 1px solid #fca5a5;
  border-radius: 12px;
  padding: 32px;
  text-align: center;
}
.error-card h2 { color: #dc2626; margin-bottom: 8px; }
.error-card p { color: #6b7280; margin-bottom: 16px; }

.primary { background: #2563eb; color: #fff; border-color: #2563eb; }

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.card-header h2 { margin-bottom: 0; }
.card-actions { display: flex; align-items: center; gap: 10px; }
.refresh-time { font-size: 12px; color: #6b7280; }

.hint { font-size: 12px; color: #6b7280; font-weight: 400; }
.dy-hint { font-size: 10px; color: #f59e0b; }

.div-amount { color: #dc2626; font-weight: 600; }
.closed-tag { color: #9ca3af; font-size: 11px; margin-left: 4px; }

.empty {
  text-align: center;
  padding: 40px;
  color: #9ca3af;
  font-size: 14px;
}
</style>
