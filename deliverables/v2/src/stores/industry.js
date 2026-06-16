/**
 * 行业数据 store — 按行业分组的股票列表，含缓存和状态管理
 * 多个页面共享，避免重复请求
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiCall } from '@/api/client.js'

export const useIndustryStore = defineStore('industry', () => {
  const loading = ref(false)
  const error = ref(null)
  const industries = ref([])       // IndustryGroup[]
  const loadedAt = ref(null)       // 加载时间戳

  // 行业名称列表（用于搜索提示）
  const industryNames = computed(() =>
    industries.value.map(g => g.industry)
  )

  // 展平的股票列表（含 industry 字段）
  const flatStocks = computed(() => {
    const result = []
    for (const group of industries.value) {
      for (const stock of group.stocks) {
        result.push({ ...stock, industry: group.industry })
      }
    }
    return result
  })

  // 总股票数
  const totalStocks = computed(() =>
    industries.value.reduce((sum, g) => sum + g.stock_count, 0)
  )

  async function fetchIndustries() {
    if (loading.value) return
    loading.value = true
    error.value = null
    try {
      const r = await apiCall('GET', '/api/v2/industries')
      if (r && r.success) {
        industries.value = r.data || []
        loadedAt.value = Date.now()
      } else {
        error.value = r?.error || '加载行业数据失败'
      }
    } catch (e) {
      error.value = e.message || '网络错误'
      console.error(e)
    } finally {
      loading.value = false
    }
  }

  /** 强制刷新（添加/删除自选股后调用） */
  async function refreshIndustries() {
    industries.value = []
    loadedAt.value = null
    await fetchIndustries()
  }

  /** 更新 in_watchlist 状态（本地乐观更新，避免全量重取） */
  function markWatchlistStocks(codes, inWatchlist) {
    const codeSet = new Set(codes)
    for (const group of industries.value) {
      for (const stock of group.stocks) {
        if (codeSet.has(stock.code)) {
          stock.in_watchlist = inWatchlist
        }
      }
    }
  }

  return {
    loading, error, industries, loadedAt,
    industryNames, flatStocks, totalStocks,
    fetchIndustries, refreshIndustries, markWatchlistStocks,
  }
})
