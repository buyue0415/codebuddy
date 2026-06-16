<template>
  <div class="page-content">
    <!-- Loading -->
    <div v-if="store.loading && !store.graphData.nodes.length" class="loading">
      <div class="spinner"></div>
    </div>
    <!-- Error -->
    <div v-else-if="store.error && !store.graphData.nodes.length" class="error-card">
      <h2>加载失败</h2><p>{{ store.error }}</p>
    </div>
    <template v-else>
      <!-- Top bar: title + refresh -->
      <div class="cg-topbar">
        <h1 class="cg-title">🔹 公司关系图谱</h1>
        <div class="cg-topbar-right">
          <button class="cg-btn cg-btn-refresh" :class="{ refreshing: store.refreshing }"
            @click="doRefresh" :disabled="store.refreshing">
            <span class="cg-btn-icon" :class="{ spin: store.refreshing }">{{ store.refreshing ? '⏳' : '🔄' }}</span>
            <span>{{ store.refreshing ? '刷新中' : '刷新数据' }}</span>
          </button>
          <span class="cg-meta" v-if="store.lastRefresh && !store.refreshing">上次 {{ store.lastRefresh }}</span>
        </div>
      </div>

      <!-- Stock switcher -->
      <div class="cg-tab-row">
        <button
          v-for="s in data.watchlist" :key="s.code"
          class="cg-tab" :class="{ active: activeCode === s.code }"
          @click="switchCode(s.code)">{{ s.name }}</button>
      </div>

      <!-- Type filter + stats -->
      <div class="cg-type-row">
        <div class="cg-type-tabs">
          <button
            v-for="t in typeTabs" :key="t.key"
            class="cg-tab cg-tab-sm" :class="{ active: activeType === t.key }"
            @click="switchType(t.key)">{{ t.label }}</button>
        </div>
        <div class="cg-stats">
          <span v-for="s in statsList" :key="s.key" class="cg-stat-item">
            <span class="cg-dot" :style="{ background: s.color }"></span>
            {{ s.label }}<em class="cg-stat-num">{{ s.count }}</em>
          </span>
        </div>
      </div>

      <!-- Graph -->
      <div class="cg-graph-wrap">
        <div v-if="store.graphData.nodes.length === 0 && !store.loading" class="cg-empty">
          <p>📊 暂无关系数据</p>
          <p class="cg-empty-hint">点击 [刷新数据] 从东方财富采集企业关系数据</p>
        </div>
        <div ref="graphRef" class="cg-canvas"></div>
      </div>
    </template>

    <!-- Node detail side panel -->
    <transition name="slide">
      <div v-if="selectedNode" class="cg-detail">
        <div class="cg-detail-head">
          <span class="cg-detail-name">{{ selectedNode.label }}</span>
          <button class="cg-detail-close" @click="closeDetail">✕</button>
        </div>
        <div class="cg-detail-body">
          <div class="cg-detail-info">
            <div class="cg-detail-row" v-if="selectedNode.code"><span class="cg-dl">代码</span>{{ selectedNode.code }}</div>
            <div class="cg-detail-row" v-if="selectedNode.industry"><span class="cg-dl">行业</span>{{ selectedNode.industry }}</div>
            <div class="cg-detail-row"><span class="cg-dl">类型</span>{{ typeLabel(selectedNode.type) }}</div>
          </div>
          <div class="cg-detail-sec" v-if="selectedNode.business">
            <div class="cg-detail-sectitle">📋 主营业务</div>
            <p class="cg-detail-biz">{{ selectedNode.business }}</p>
          </div>
          <div class="cg-detail-sec">
            <div class="cg-detail-sectitle">关联关系 ({{ nodeRelations.length }})</div>
            <div v-if="nodeRelations.length === 0" class="cg-detail-empty">暂无关联关系</div>
            <div v-for="(rel, i) in nodeRelations" :key="i" class="cg-detail-rel">
              <div class="cg-rel-name">
                <span class="cg-rel-dot" :style="{ background: relColor(rel.type) }"></span>
                {{ rel.related_name || rel.code }}
              </div>
              <div class="cg-rel-meta">
                <span class="cg-rel-tag" :class="'t-' + rel.type">{{ rel.typeLabel }}</span>
                <span class="cg-rel-desc">{{ rel.relation_detail }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useCompanyGraphStore } from '@/stores/companyGraph.js'
import { useDataStore } from '@/stores/data.js'

const store = useCompanyGraphStore()
const data = useDataStore()
const graphRef = ref(null)
const activeType = ref('')
const activeCode = ref('')
const selectedNode = ref(null)
let graphInstance = null

const typeTabs = [
  { key: '', label: '全部' },
  { key: 'equity', label: '股权' },
  { key: 'executive', label: '高管' },
  { key: 'supply', label: '供应链' },
  { key: 'competition', label: '竞争' },
]

const statsList = computed(() => [
  { key: 'equity', label: '股权', count: store.stats.equity, color: '#3b82f6' },
  { key: 'executive', label: '高管', count: store.stats.executive, color: '#8b5cf6' },
  { key: 'supply', label: '供应链', count: store.stats.supply, color: '#f59e0b' },
  { key: 'competition', label: '竞争', count: store.stats.competition, color: '#ef4444' },
])

function typeLabel(t) {
  return { stock: '自选股', company: '外部公司', person: '人员' }[t] || t
}
function relColor(type) {
  return { equity: '#3b82f6', executive: '#8b5cf6', supply: '#f59e0b', competition: '#ef4444' }[type] || '#94a3b8'
}
function typeTabLabel(t) {
  return { equity: '股权', executive: '高管', supply: '供应链', competition: '竞争' }[t] || t
}

const nodeRelations = computed(() => {
  if (!selectedNode.value) return []
  const id = selectedNode.value.id
  const all = store.graphData.edges || []
  const rels = []
  for (const e of all) {
    if (e.source === id) {
      rels.push({ ...e, code: e.target, related_name: e.target, typeLabel: typeTabLabel(e.type) })
    } else if (e.target === id) {
      rels.push({ ...e, code: e.source, related_name: e.source, typeLabel: typeTabLabel(e.type) })
    }
  }
  return rels
})

async function switchCode(code) {
  activeCode.value = code
  await store.fetchData(code, activeType.value)
  await store.fetchStats(code)
  await nextTick()
  renderGraph()
}

async function switchType(key) {
  activeType.value = key
  await store.fetchData(activeCode.value, key)
  await store.fetchStats(activeCode.value)
  await nextTick()
  await renderGraph()
}

async function doRefresh() {
  await store.triggerRefresh()
  await nextTick()
  renderGraph()
}

function closeDetail() {
  selectedNode.value = null
  if (graphInstance) {
    graphInstance.setElementVisibility({ nodes: [], edges: [] })
    graphInstance.setElementState({ nodes: [], edges: [] })
  }
}

async function renderGraph() {
  const container = graphRef.value
  if (!container) return
  console.log('[CG] renderGraph called, nodes:', store.graphData.nodes.length)

  if (!store.graphData.nodes.length) {
    if (graphInstance) {
      graphInstance.destroy()
      graphInstance = null
    }
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#94a3b8;font-size:14px">暂无关系图谱数据</div>'
    return
  }

  if (graphInstance) {
    graphInstance.destroy()
    graphInstance = null
  }
  container.innerHTML = ''

  // Wait for container to have actual dimensions
  let tries = 0
  while (tries < 5) {
    await new Promise(r => requestAnimationFrame(r))
    if (container.clientWidth > 0 && container.clientHeight > 0) break
    tries++
  }

  const { Graph } = await import('@antv/g6')
  console.log('[CG] G6 loaded, container dims:', container.clientWidth, container.clientHeight)

  const wrap = container.parentElement
  const w = wrap ? wrap.clientWidth : container.clientWidth || 800
  const h = wrap ? wrap.clientHeight : container.clientHeight || 500

  graphInstance = new Graph({
    container,
    width: Math.max(w, 400),
    height: Math.max(h, 300),
    autoResize: true,
    layout: {
      type: 'd3-force',
      preventOverlap: true,
      nodeSize: 50,
      linkDistance: 200,
      nodeStrength: -800,
      manyBodyStrength: -600,
      linkStrength: 0.2,
      alpha: 0.5,
      alphaMin: 0.001,
      alphaDecay: 0.02,
      velocityDecay: 0.3,
      animation: true,
    },
    node: {
      style: (model) => {
        const d = model.data || {}
        return {
          size: d.type === 'stock' ? 42 : d.type === 'person' ? 30 : 32,
          fill: d.type === 'stock' ? '#2563eb' : d.type === 'person' ? '#8b5cf6' : '#94a3b8',
          labelText: d.label || '',
          labelFill: '#1e293b',
          labelFontSize: d.type === 'stock' ? 13 : 11,
          labelPlacement: 'bottom',
          labelOffsetY: 4,
          labelBackground: true,
          labelBackgroundFill: '#fff',
          labelBackgroundOpacity: 0.85,
          stroke: d.type === 'stock' ? '#fff' : 'none',
          lineWidth: d.type === 'stock' ? 3 : 0,
          shadowColor: d.type === 'stock' ? 'rgba(37,99,235,0.3)' : 'none',
          shadowBlur: 8,
          cursor: 'pointer',
        }
      },
    },
    edge: {
      style: (model) => {
        const d = model.data || {}
        const t = d.type || ''
        const w = d.weight || 1
        let lineDash
        if (t === 'executive') lineDash = [5, 5]
        else if (t === 'competition') lineDash = [4, 4, 4, 4]
        else lineDash = undefined
        return {
          stroke: relColor(t),
          lineWidth: t === 'equity' ? Math.max(1, w * 0.3) : 1.5,
          lineDash,
          labelText: d.label || '',
          labelFontSize: 10,
          labelFill: '#64748b',
          labelBackground: true,
          labelBackgroundFill: '#fff',
          labelBackgroundOpacity: 0.8,
          endArrow: t === 'supply',
          cursor: 'pointer',
        }
      },
    },
    behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
    plugins: [
      {
        type: 'tooltip',
        getContent: (event, items) => {
          const item = items && items[0]
          if (item) {
            const d = item.data || {}
            let text = `<strong>${d.label || ''}</strong>`
            if (d.code) text += `<br>代码: ${d.code}`
            if (d.industry) text += `<br>行业: ${d.industry}`
            if (d.business) text += `<br>主营: ${d.business.substring(0, 30)}...`
            return text
          }
          return ''
        },
      },
    ],
  })

  // G6 v5 格式: id 在顶层, data 里不能有 id
  const g6Nodes = store.graphData.nodes.map(n => {
    const { id, ...rest } = n
    return { id, data: rest }
  })
  const g6Edges = store.graphData.edges.map(e => {
    const { source, target, ...rest } = e
    return { source, target, data: rest }
  })

  graphInstance.setData({ nodes: g6Nodes, edges: g6Edges })
  await graphInstance.render()
  // Wait a frame before fitting view to ensure layout has settled
  await new Promise(r => requestAnimationFrame(r))
  graphInstance.fitView()

  graphInstance.on('node:click', (event) => {
    const d = event.item?.data
    if (d) selectedNode.value = d
  })

  graphInstance.on('canvas:click', () => closeDetail())
}

function handleResize() {
  if (graphInstance && graphRef.value) graphInstance.resize()
}

onMounted(async () => {
  // Load watchlist via simple API call (not the heavy fetchAll)
  if (!data.watchlist.length) {
    try {
      await data.fetchAll()
    } catch (_e) { /* ignore, fallback below */ }
  }
  // Load graph data
  if (data.watchlist.length > 0) {
    const first = data.watchlist[0].code
    activeCode.value = first
    await store.fetchData(first)
    await store.fetchStats(first)
  } else {
    // Fallback: try loading all relations without watchlist
    console.warn('[CG] Watchlist empty, loading all data')
    await store.fetchData()
    await store.fetchStats()
  }
  await nextTick()
  renderGraph()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (graphInstance) {
    graphInstance.destroy()
    graphInstance = null
  }
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
/* ── Layout ── */
.cg-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}
.cg-title {
  font-size: 17px;
  font-weight: 600;
  margin: 0;
  color: #1e293b;
}
.cg-topbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* ── Stock tabs ── */
.cg-tab-row {
  display: flex;
  gap: 4px;
  padding: 8px 20px;
  background: #fff;
  border-bottom: 1px solid #f1f5f9;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.cg-tab-row::-webkit-scrollbar { height: 0; }

/* ── Type + Stats row ── */
.cg-type-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 20px;
  background: #fff;
  border-bottom: 1px solid #f1f5f9;
}
.cg-type-tabs {
  display: flex;
  gap: 4px;
}
.cg-stats {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-shrink: 0;
}

/* ── Tabs ── */
.cg-tab {
  padding: 5px 14px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-size: 12px;
  color: #374151;
  white-space: nowrap;
  transition: all .15s;
  flex-shrink: 0;
}
.cg-tab:hover { background: #f3f4f6; }
.cg-tab.active {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}
.cg-tab-sm { padding: 4px 10px; font-size: 12px; }

/* ── Stats ── */
.cg-stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #64748b;
}
.cg-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}
.cg-stat-num {
  font-style: normal;
  font-weight: 600;
  color: #1e293b;
  margin-left: 2px;
}

/* ── Refresh ── */
.cg-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-size: 12px;
  color: #374151;
  transition: all .15s;
}
.cg-btn:hover { background: #f3f4f6; }
.cg-btn.refreshing { opacity: .7; cursor: not-allowed; }
.cg-btn-icon { display: inline-block; font-size: 13px; }
.cg-btn-icon.spin { animation: cg-spin 1s linear infinite; }
@keyframes cg-spin { to { transform: rotate(360deg); } }
.cg-meta { font-size: 11px; color: #94a3b8; white-space: nowrap; }

/* ── Graph ── */
.cg-graph-wrap {
  position: relative;
  height: calc(100vh - 155px);
  min-height: 350px;
  background: #f8fafc;
  overflow: hidden;
}
.cg-canvas { width: 100%; height: 100%; min-height: 350px; }
.cg-empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 15px;
}
.cg-empty-hint { font-size: 12px; margin-top: 6px; color: #94a3b8; }

/* ── Detail panel ── */
.cg-detail {
  position: fixed;
  top: 52px;
  right: 0;
  width: 300px;
  height: calc(100vh - 52px);
  background: #fff;
  border-left: 1px solid #e5e7eb;
  box-shadow: -2px 0 8px rgba(0,0,0,.08);
  z-index: 90;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.cg-detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid #f1f5f9;
  background: #f8fafc;
}
.cg-detail-name { font-size: 15px; font-weight: 600; color: #1e293b; }
.cg-detail-close {
  background: none;
  border: none;
  font-size: 15px;
  cursor: pointer;
  color: #94a3b8;
  padding: 4px 8px;
  border-radius: 4px;
}
.cg-detail-close:hover { background: #f1f5f9; color: #1e293b; }
.cg-detail-body { flex: 1; overflow-y: auto; padding: 14px 18px; }
.cg-detail-info { margin-bottom: 14px; }
.cg-detail-row {
  font-size: 12px;
  margin-bottom: 6px;
  color: #64748b;
  display: flex;
}
.cg-dl { color: #1e293b; font-weight: 500; width: 44px; flex-shrink: 0; }
.cg-detail-sec { margin-bottom: 14px; }
.cg-detail-sectitle {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid #f1f5f9;
}
.cg-detail-biz { font-size: 12px; color: #64748b; line-height: 1.6; margin: 0; }
.cg-detail-empty { font-size: 12px; color: #94a3b8; text-align: center; padding: 12px 0; }
.cg-detail-rel { padding: 6px 0; border-bottom: 1px solid #f8fafc; }
.cg-rel-name {
  font-size: 12px;
  font-weight: 500;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 5px;
}
.cg-rel-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.cg-rel-meta { display: flex; align-items: center; gap: 6px; margin-top: 3px; margin-left: 11px; }
.cg-rel-tag { font-size: 10px; padding: 1px 5px; border-radius: 3px; font-weight: 500; }
.t-equity { background: #dbeafe; color: #1e40af; }
.t-executive { background: #f3e8ff; color: #6d28d9; }
.t-supply { background: #fef3c7; color: #92400e; }
.t-competition { background: #fee2e2; color: #991b1b; }
.cg-rel-desc { font-size: 11px; color: #94a3b8; }

/* ── Transition ── */
.slide-enter-active, .slide-leave-active { transition: transform .2s ease; }
.slide-enter-from, .slide-leave-to { transform: translateX(100%); }
</style>
