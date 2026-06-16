<template>
  <div class="ss-wrap">
    <!-- Search bar -->
    <div class="ss-search">
      <input v-model="query" @input="onQueryInput" placeholder="搜索行业/股票..." class="ss-input" />
      <span class="ss-count" v-if="industryStore.totalStocks">{{ industryStore.totalStocks }} 只</span>
      <span class="ss-msg" :class="msgCls" v-if="msg">{{ msg }}</span>
    </div>

    <!-- Loading / Error -->
    <div v-if="industryStore.loading" class="ss-loading"><div class="mini-spinner"></div> 加载中...</div>
    <div v-else-if="industryStore.error" class="ss-err">{{ industryStore.error }}</div>

    <!-- Industry groups -->
    <template v-else-if="filteredGroups.length">
      <!-- First selected industry when searching -->
      <div v-if="!activeInd && filteredGroups.length" class="ss-hint">请选择一个行业</div>

      <!-- Level 1: Industry tabs -->
      <div class="ss-inds">
        <button v-for="g in filteredGroups" :key="g.industry"
          class="ss-ind-tab" :class="{ active: activeInd === g.industry }"
          @click="activeInd = g.industry">
          {{ g.industry }}<span class="ss-ind-cnt">{{ g.stocks.length }}</span>
        </button>
      </div>

      <!-- Level 2: Stocks in selected industry -->
      <div class="ss-stocks" v-if="activeIndStocks.length">
        <div v-for="s in activeIndStocks" :key="s.code" class="ss-row"
          :class="{ disabled: s.inWatchlist && mode === 'watchlist-add' }"
          @click="onStockClick(s)">
          <span class="ss-r-name">{{ s.name }}</span>
          <span class="ss-r-code">{{ s.code }}</span>
          <span class="ss-r-mkt">{{ s.market }}</span>
          <span class="ss-r-btn" :class="{ added: s.in_watchlist || s.inWatchlist }">
            {{ mode === 'watchlist-add'
              ? (s.inWatchlist ? '✓ 已添加' : (addingCode === s.code ? '添加中...' : '＋ 添加'))
              : '选择' }}
          </span>
        </div>
      </div>
      <div v-else class="ss-empty-sm">该行业暂无匹配股票</div>
    </template>

    <div v-else class="ss-empty">
      <div class="ss-empty-icon">📭</div>
      <div v-if="query">未匹配"{{ query }}"</div>
      <div v-else>暂无行业数据</div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useIndustryStore } from '@/stores/industry.js'
import { apiCall } from '@/api/client.js'

const props = defineProps({
  mode: { type: String, default: 'watchlist-add' },
  modelValue: { type: Object, default: null },
  watchlistOnly: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'add-to-watchlist'])

const industryStore = useIndustryStore()
const query = ref('')
const activeInd = ref('')
const addingCode = ref('')
const msg = ref('')
const msgCls = ref('')
let qTimer = null
let msgTimer = null

const filteredGroups = computed(() => {
  const q = query.value.trim().toLowerCase()
  const all = industryStore.industries
  // Filter to watchlist stocks only when watchlistOnly prop is true
  const filtered = props.watchlistOnly
    ? all.map(g => {
        const wlStocks = g.stocks.filter(s => s.in_watchlist || s.inWatchlist)
        if (!wlStocks.length) return null
        return { ...g, stocks: wlStocks, stock_count: wlStocks.length }
      }).filter(Boolean)
    : all
  if (!q) return filtered
  return filtered.map(g => {
    const matched = g.stocks.filter(s =>
      s.name?.toLowerCase().includes(q) || s.code.includes(q) || g.industry.toLowerCase().includes(q)
    )
    if (!matched.length && !g.industry.toLowerCase().includes(q)) return null
    return { ...g, stocks: matched, stock_count: matched.length }
  }).filter(Boolean)
})

const activeIndStocks = computed(() => {
  const g = filteredGroups.value.find(x => x.industry === activeInd.value)
  return g ? g.stocks : []
})

function onQueryInput() {
  clearTimeout(qTimer)
  qTimer = setTimeout(() => {
    // Auto-select first group when search has results in grouped mode
    const q = query.value.trim().toLowerCase()
    if (q && filteredGroups.value.length) {
      activeInd.value = filteredGroups.value[0].industry
    }
  }, 300)
}

async function onStockClick(s) {
  if (props.mode === 'watchlist-add') {
    if ((s.in_watchlist || s.inWatchlist) || addingCode.value) return
    addingCode.value = s.code
    try {
      const r = await apiCall('POST', '/api/v2/watchlist', {
        code: s.code, name: s.name, market: s.market || 'sh',
      })
      if (r?.success) {
        industryStore.markWatchlistStocks([s.code], true)
        emit('add-to-watchlist', { code: s.code, name: s.name, market: s.market })
        showMsg('ss-ok', '✅ 已添加 ' + s.name)
      } else {
        showMsg('ss-err', '❌ ' + (r?.error || '添加失败'))
      }
    } catch (e) {
      showMsg('ss-err', '❌ ' + e.message)
    }
    addingCode.value = ''
  } else {
    // selector mode
    emit('update:modelValue', { code: s.code, name: s.name, market: s.market })
  }
}

function showMsg(cls, text) {
  msg.value = text
  msgCls.value = cls
  clearTimeout(msgTimer)
  msgTimer = setTimeout(() => { msg.value = '' }, 3000)
}

onMounted(async () => {
  if (!industryStore.industries.length) {
    await industryStore.fetchIndustries()
  }
  if (filteredGroups.value.length) {
    activeInd.value = filteredGroups.value[0].industry
  }
})
</script>

<style scoped>
.ss-wrap { display: flex; flex-direction: column; gap: 0; }

/* Search */
.ss-search { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-bottom: 1px solid #e2e8f0; background: #fafbfc; flex-wrap: wrap; }
.ss-input { flex: 1; min-width: 100px; padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; outline: none; }
.ss-input:focus { border-color: #2563eb; }
.ss-count { font-size: 11px; color: #94a3b8; white-space: nowrap; }
.ss-msg { font-size: 11px; padding: 0 4px; }
.ss-ok { color: #16a34a; }
.ss-err { color: #dc2626; }
.ss-hint { padding: 12px; text-align: center; font-size: 12px; color: #94a3b8; }

/* Loading/Error */
.ss-loading { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 24px; font-size: 13px; color: #6b7280; }
.mini-spinner { width: 14px; height: 14px; border: 2px solid #e5e7eb; border-top-color: #2563eb; border-radius: 50%; animation: ssSpin .8s linear infinite; }
@keyframes ssSpin { to { transform: rotate(360deg); } }
.ss-err { padding: 16px; text-align: center; font-size: 12px; color: #dc2626; }

/* Industry tabs */
.ss-inds { display: flex; gap: 3px; flex-wrap: wrap; padding: 8px 12px; border-bottom: 1px solid #e2e8f0; }
.ss-ind-tab { padding: 4px 10px; border: 1px solid #d1d5db; border-radius: 5px; background: #fff; cursor: pointer; font-size: 11px; color: #475569; transition: all .12s; display: flex; align-items: center; gap: 3px; white-space: nowrap; }
.ss-ind-tab:hover { background: #f8fafc; border-color: #93c5fd; }
.ss-ind-tab.active { background: #1e40af; color: #fff; border-color: #1e40af; font-weight: 500; }
.ss-ind-cnt { font-size: 9px; background: rgba(255,255,255,.2); border-radius: 6px; padding: 0 4px; line-height: 14px; }
.ss-ind-tab:not(.active) .ss-ind-cnt { background: #f1f5f9; color: #64748b; }

/* Stock rows */
.ss-stocks { max-height: 280px; overflow-y: auto; }
.ss-row { display: flex; align-items: center; gap: 8px; padding: 8px 12px 8px 14px; border-bottom: 1px solid #f8fafc; cursor: pointer; transition: background .1s; min-height: 34px; }
.ss-row:hover { background: #eff6ff; }
.ss-row.disabled { cursor: not-allowed; opacity: .6; }
.ss-row.disabled:hover { background: transparent; }
.ss-r-name { flex: 1; font-size: 13px; font-weight: 500; color: #1e293b; }
.ss-r-code { font-size: 11px; color: #64748b; font-family: monospace; }
.ss-r-mkt { font-size: 10px; color: #fff; background: #94a3b8; padding: 1px 5px; border-radius: 3px; }
.ss-r-btn { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; white-space: nowrap; background: #dbeafe; color: #2563eb; }
.ss-r-btn.added { background: #dcfce7; color: #166534; }

/* Empty */
.ss-empty { text-align: center; padding: 32px 16px; font-size: 13px; color: #6b7280; }
.ss-empty-icon { font-size: 28px; margin-bottom: 8px; }
.ss-empty-sm { text-align: center; padding: 16px; font-size: 12px; color: #94a3b8; }
</style>
