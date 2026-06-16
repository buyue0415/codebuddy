<template>
  <div class="igt-wrapper">
    <!-- Level 1: Industry tabs (only industries present in watchlist) -->
    <div class="igt-industries">
      <button
        v-for="g in watchlistGroups" :key="g.industry"
        class="igt-ind-tab" :class="{ active: activeIndustry === g.industry }"
        @click="activeIndustry = g.industry">
        {{ g.industry }}<span class="igt-ind-count">{{ g.stocks.length }}</span>
      </button>
    </div>
    <!-- Level 2: Stock tabs for the active industry -->
    <div class="igt-stocks" v-if="activeIndustryStocks.length">
      <button
        v-for="s in activeIndustryStocks" :key="s.code"
        class="igt-stock-tab" :class="{ active: activeCode === s.code }"
        @click="onSelect(s)">
        {{ s.name }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useIndustryStore } from '@/stores/industry.js'

const props = defineProps({
  stocks: { type: Array, default: () => [] },
  activeCode: { type: String, default: '' },
  excludeCodes: { type: Array, default: () => [] },
})

const emit = defineEmits(['switch'])

const industryStore = useIndustryStore()
const activeIndustry = ref('')

// Build code→industry map from API data
const watchlistGroups = computed(() => {
  const map = {}
  for (const s of industryStore.flatStocks) {
    map[s.code] = s.industry
  }
  const groups = {}
  for (const s of props.stocks) {
    if (props.excludeCodes?.includes(s.code)) continue
    const ind = map[s.code] || '未分类'
    if (!groups[ind]) groups[ind] = { industry: ind, stocks: [] }
    groups[ind].stocks.push(s)
  }
  // Sort: "未分类" last
  const entries = Object.entries(groups)
  entries.sort((a, b) => a[0] === '未分类' ? 1 : b[0] === '未分类' ? -1 : a[0].localeCompare(b[0], 'zh'))
  return entries.map(([, g]) => g)
})

const activeIndustryStocks = computed(() => {
  const g = watchlistGroups.value.find(x => x.industry === activeIndustry.value)
  return g ? g.stocks : []
})

// Sync activeIndustry when activeCode changes externally
watch(() => props.activeCode, (code) => {
  if (!code) return
  const map = {}
  for (const s of industryStore.flatStocks) {
    map[s.code] = s.industry
  }
  const ind = map[code] || '未分类'
  if (ind !== activeIndustry.value) {
    activeIndustry.value = ind
  }
})

function onSelect(s) {
  if (props.excludeCodes?.includes(s.code)) return
  emit('switch', s.code)
}

onMounted(async () => {
  if (!industryStore.flatStocks.length) {
    await industryStore.fetchIndustries()
  }
  // Auto-select first industry
  if (!activeIndustry.value && watchlistGroups.value.length) {
    activeIndustry.value = watchlistGroups.value[0].industry
  }
  // Sync with current activeCode
  if (props.activeCode) {
    const map = {}
    for (const s of industryStore.flatStocks) map[s.code] = s.industry
    activeIndustry.value = map[props.activeCode] || watchlistGroups.value[0]?.industry || ''
  }
})
</script>

<style scoped>
.igt-wrapper { width: 100%; }

/* Industry tabs */
.igt-industries {
  display: flex;
  gap: 3px;
  flex-wrap: wrap;
  padding-bottom: 8px;
  border-bottom: 1px solid #e2e8f0;
  margin-bottom: 8px;
}
.igt-ind-tab {
  padding: 5px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-size: 12px;
  color: #475569;
  transition: all .12s;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 4px;
}
.igt-ind-tab:hover { background: #f8fafc; border-color: #93c5fd; }
.igt-ind-tab.active {
  background: #1e40af;
  color: #fff;
  border-color: #1e40af;
  font-weight: 500;
}
.igt-ind-count {
  font-size: 10px;
  background: rgba(255,255,255,.2);
  border-radius: 8px;
  padding: 0 5px;
  line-height: 16px;
}
.igt-ind-tab:not(.active) .igt-ind-count {
  background: #f1f5f9;
  color: #64748b;
}

/* Stock tabs */
.igt-stocks {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  padding-left: 2px;
}
.igt-stock-tab {
  padding: 6px 16px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  color: #374151;
  transition: all .12s;
  white-space: nowrap;
}
.igt-stock-tab:hover { background: #f3f4f6; }
.igt-stock-tab.active {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}
</style>
