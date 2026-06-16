/**
 * 公司关系图谱数据 Store
 * 管理图谱节点/边数据、统计信息和刷新状态，支持按股票代码切换
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiCall } from '@/api/client.js'

export const useCompanyGraphStore = defineStore('companyGraph', () => {
  const loading = ref(false)
  const refreshing = ref(false)
  const error = ref(null)
  const graphData = ref({ nodes: [], edges: [] })
  const stats = ref({ equity: 0, executive: 0, supply: 0, competition: 0, total: 0 })
  const lastRefresh = ref('')
  const selectedCode = ref('')

  function buildQuery(code, type) {
    const params = []
    if (code) params.push(`code=${encodeURIComponent(code)}`)
    if (type) params.push(`type=${encodeURIComponent(type)}`)
    return params.length ? `?${params.join('&')}` : ''
  }

  async function fetchData(code = '', type = '') {
    loading.value = true
    error.value = null
    selectedCode.value = code
    try {
      const q = buildQuery(code, type)
      const r = await apiCall('GET', `/api/v2/company-relations${q}`)
      if (r && r.success) {
        graphData.value = r.data || { nodes: [], edges: [] }
      } else {
        error.value = r?.error || '加载失败'
      }
    } catch (e) {
      error.value = e.message || '网络请求失败'
      console.error('companyGraph fetchData error:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchStats(code = '') {
    try {
      const q = code ? `?code=${encodeURIComponent(code)}` : ''
      const r = await apiCall('GET', `/api/v2/company-relations/stats${q}`)
      if (r && r.success && r.data) {
        stats.value = r.data
      }
    } catch (e) {
      console.error('companyGraph fetchStats error:', e)
    }
  }

  async function triggerRefresh() {
    if (refreshing.value) return
    refreshing.value = true
    error.value = null
    try {
      const r = await apiCall('POST', '/api/v2/company-relations/refresh')
      if (r && r.success) {
        lastRefresh.value = new Date().toLocaleTimeString()
        await fetchData(selectedCode.value)
        await fetchStats(selectedCode.value)
        return { success: true, output: r.output }
      } else {
        error.value = r?.error || '刷新失败'
        return { success: false, error: error.value }
      }
    } catch (e) {
      error.value = e.message || '网络请求失败'
      console.error('companyGraph refresh error:', e)
      return { success: false, error: error.value }
    } finally {
      refreshing.value = false
    }
  }

  function clearError() {
    error.value = null
  }

  return {
    loading, refreshing, error, graphData, stats, lastRefresh, selectedCode,
    fetchData, fetchStats, triggerRefresh, clearError,
  }
})
