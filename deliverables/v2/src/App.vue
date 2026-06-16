<template>
  <div class="app">
    <!-- Top bar with logo + group tabs -->
    <nav class="nav-top">
      <div class="logo"><span>📊</span> 股票投资管理系统 <sup class="ver">V2</sup></div>
      <div class="nav-group-tabs">
        <button
          v-for="g in navGroups"
          :key="g.id"
          class="nav-gtab"
          :class="{ active: activeGroup === g.id }"
          @click="switchGroup(g.id)"
        >{{ g.label }}</button>
      </div>
      <div class="nav-global-actions">
        <button class="btn-global-refresh" @click="store.triggerFullRefresh()"
          :disabled="store.fullRefreshing" title="全量数据采集 + 重新计算预测">
          <span class="refresh-icon" :class="{ spinning: store.fullRefreshing }">&#x21bb;</span>
          <span>{{ store.fullRefreshing ? '刷新中...' : '全量刷新' }}</span>
        </button>
        <span v-if="store.refreshError" class="refresh-err">{{ store.refreshError }}</span>
        <span v-else-if="store.lastRefresh && !store.fullRefreshing" class="refresh-time">{{ store.lastRefresh }}</span>
      </div>
    </nav>

    <!-- Sub-tab bar for active group -->
    <div class="nav-sub-bar" v-if="currentGroup">
      <button
        v-for="item in currentGroup.items"
        :key="item.route"
        class="nav-stab"
        :class="{ active: route.path === item.route }"
        @click="router.push(item.route)"
      >{{ item.label }}</button>
    </div>

    <router-view />

    <div class="disclaimer">
      ⚠️ 本系统数据来源于广发证券对账单及NeoData金融数据服务（月度K线，非日K）。预测基于历史季节性模型推演，置信区间±8-10%，实际走势可能偏离中枢。以上内容不构成任何投资建议，投资有风险，决策需谨慎。
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDataStore } from '@/stores/data.js'

const route = useRoute()
const router = useRouter()
const store = useDataStore()

const navGroups = [
  { id: 'trade',  label: '个人交易数据', items: [
    { route: '/overview', label: '持仓总览' },
    { route: '/trades', label: '交易记录' },
    { route: '/fees', label: '手续费分析' },
    { route: '/manage', label: '管理设置' },
  ]},
  { id: 'analysis', label: '股票分析预测', items: [
    { route: '/intelligence', label: '智能预测' },
    { route: '/expert', label: '专家分析' },
  ]},
  { id: 'info',     label: '股票信息收集', items: [
    { route: '/news', label: '新闻动态' },
    { route: '/stock-data', label: '股票数据' },
    { route: '/kline', label: 'K线走势' },
    { route: '/pattern-rules', label: '形态规则' },
    { route: '/company-graph', label: '公司关系图谱' },
  ]},
  { id: 'paper',    label: '模拟交易', items: [
    { route: '/backtest', label: '回测分析' },
    { route: '/paper', label: '纸面交易' },
  ]},
]

const routeGroupMap = {
  '/overview': 'trade', '/trades': 'trade', '/fees': 'trade', '/manage': 'trade',
  '/intelligence': 'analysis', '/expert': 'analysis',
  '/news': 'info', '/stock-data': 'info', '/kline': 'info', '/pattern-rules': 'info', '/company-graph': 'info',
  '/backtest': 'paper', '/paper': 'paper',
}

const activeGroup = computed(() => routeGroupMap[route.path] || 'trade')
const currentGroup = computed(() => navGroups.find(g => g.id === activeGroup.value))

function switchGroup(id) {
  const firstItem = navGroups.find(g => g.id === id)?.items[0]
  if (firstItem) router.push(firstItem.route)
}
</script>

<style>
/* ===== Top Nav Bar ===== */
.nav-top {
  background: linear-gradient(135deg, #1a3a5c, #2563eb);
  padding: 0 24px;
  display: flex;
  align-items: center;
  height: 52px;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 2px 8px rgba(0,0,0,.15);
  user-select: none;
  gap: 24px;
}
.nav-top .logo {
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 1px;
  flex-shrink: 0;
}
.nav-top .logo span { color: #60a5fa; }
.ver {
  font-size: 10px;
  background: #f59e0b;
  color: #1a3a5c;
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: 700;
  vertical-align: super;
}

/* Group tabs */
.nav-group-tabs {
  display: flex;
  gap: 4px;
  height: 100%;
  align-items: stretch;
}
.nav-gtab {
  background: none;
  border: none;
  color: rgba(255,255,255,.7);
  font-size: 13px;
  padding: 0 16px;
  cursor: pointer;
  transition: all .15s;
  border-bottom: 3px solid transparent;
  white-space: nowrap;
}
.nav-gtab:hover { color: #fff; background: rgba(255,255,255,.06); }
.nav-gtab.active { color: #fff; border-bottom-color: #60a5fa; font-weight: 600; }

/* ===== Sub-tab Bar ===== */
.nav-sub-bar {
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  padding: 0 24px;
  display: flex;
  gap: 0;
  position: sticky;
  top: 52px;
  z-index: 99;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.nav-stab {
  background: none;
  border: none;
  color: #6b7280;
  font-size: 13px;
  padding: 12px 18px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all .15s;
  margin-bottom: -1px;
}
.nav-stab:hover { color: #2563eb; }
.nav-stab.active { color: #2563eb; border-bottom-color: #2563eb; font-weight: 600; }

/* Responsive */
@media (max-width: 700px) {
  .nav-top { padding: 0 12px; gap: 8px; }
  .nav-top .logo { font-size: 14px; }
  .nav-gtab { padding: 0 10px; font-size: 12px; }
  .nav-sub-bar { padding: 0 12px; }
  .nav-stab { padding: 10px 12px; font-size: 12px; }
  .btn-global-refresh { font-size: 11px; padding: 3px 8px; }
  .nav-global-actions { gap: 4px; }
}

/* ===== Global Refresh Button ===== */
.nav-global-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
}
.btn-global-refresh {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: rgba(255,255,255,.12);
  border: 1px solid rgba(255,255,255,.2);
  color: #fff;
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 6px;
  cursor: pointer;
  white-space: nowrap;
  transition: all .15s;
}
.btn-global-refresh:hover { background: rgba(255,255,255,.2); }
.btn-global-refresh:disabled { opacity: .5; cursor: not-allowed; }
.refresh-icon { display: inline-block; font-size: 14px; }
.refresh-icon.spinning { animation: btnSpin 1s linear infinite; }
@keyframes btnSpin { to { transform: rotate(360deg); } }
.refresh-err { font-size: 11px; color: #fca5a5; }
.refresh-time { font-size: 11px; color: rgba(255,255,255,.5); }
</style>
