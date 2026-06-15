/**
 * 公共数据 store — 加载一次，多个页面共享
 * 替代旧版全局变量 DATA / trades / cp / cl / ...
 */
import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'
import { loadAllData, clearCache, apiCall } from '@/api/client.js'

export const useDataStore = defineStore('data', () => {
  const loading = ref(false)
  const refreshing = ref(false)      // 仅刷新股价的轻量状态
  const fullRefreshing = ref(false)  // 全量刷新（采集+预测）状态
  const error = ref(null)
  const refreshError = ref(null)     // 刷新按钮的内联错误
  const watchlist = ref([])
  const quotes = ref({})
  const prevQuotes = shallowRef({})  // 上一轮行情，用于判断涨跌
  const currentPositions = ref({})
  const closedPositions = ref({})
  const allTrades = ref([])
  const allNews = ref([])
  const allKlineDaily = ref({})
  const allKlineMonthly = ref({})
  const seasonal = ref({})
  const allDividends = ref([])
  const expertReports = ref([])
  const predictions = ref([])
  const accuracyStats = ref({})
  const learningParams = ref({})
  const config = ref({})
  const lastRefresh = ref('')

  let _refreshTimer = null  // debounce
  let _fullRefreshTimer = null

  async function fetchAll() {
    clearCache()
    loading.value = true
    error.value = null
    try {
      const { DATA, config: cfg, dividends: divs } = await loadAllData()
      watchlist.value = DATA.watchlist || []
      prevQuotes.value = { ...quotes.value }
      quotes.value = DATA.quotes || {}
      currentPositions.value = DATA.positions?.current_positions || {}
      closedPositions.value = DATA.positions?.closed_positions || {}
      allTrades.value = DATA.positions?.all_trades || []
      allNews.value = DATA.news || []
      allKlineDaily.value = DATA.kline_daily || {}
      allKlineMonthly.value = DATA.kline || {}
      seasonal.value = DATA.seasonal || {}
      allDividends.value = divs || []
      expertReports.value = DATA.expert_reports || []
      predictions.value = DATA.daily_predictions || []
      accuracyStats.value = DATA.accuracy_stats || {}
      learningParams.value = DATA.learning_params || {}
      config.value = cfg || {}
      lastRefresh.value = new Date().toLocaleTimeString()
    } catch (e) {
      error.value = e.message
      console.error(e)
    } finally {
      loading.value = false
      refreshing.value = false
    }
  }

  /** Refresh real-time quotes via external API, then reload all data */
  async function refreshQuotesAndReload() {
    if (refreshing.value) return  // 防重复
    refreshing.value = true
    refreshError.value = null

    try {
      const res = await apiCall('POST', '/api/v2/quotes/refresh')
      if (!res.success) {
        refreshError.value = res.error || '刷新失败，请稍后重试'
        refreshing.value = false
        // 3秒后自动清除错误
        _refreshTimer = setTimeout(() => { refreshError.value = null }, 4000)
        return
      }
      await fetchAll()
      // 成功后也清理timer
      if (_refreshTimer) { clearTimeout(_refreshTimer); _refreshTimer = null }
    } catch (e) {
      refreshError.value = e.message || '网络请求失败'
      console.error(e)
      refreshing.value = false
      _refreshTimer = setTimeout(() => { refreshError.value = null }, 4000)
    }
  }

  /** Full refresh: trigger backend full pipeline (sync_all), then reload all data */
  async function triggerFullRefresh() {
    if (fullRefreshing.value) return
    fullRefreshing.value = true
    refreshError.value = null
    try {
      const r = await apiCall('POST', '/api/trigger/predict')
      if (r?.success) {
        await fetchAll()
        if (_fullRefreshTimer) { clearTimeout(_fullRefreshTimer); _fullRefreshTimer = null }
      } else {
        refreshError.value = r?.error || '全量刷新失败'
        fullRefreshing.value = false
        _fullRefreshTimer = setTimeout(() => { refreshError.value = null }, 4000)
        return
      }
    } catch (e) {
      refreshError.value = e.message || '网络请求失败'
      _fullRefreshTimer = setTimeout(() => { refreshError.value = null }, 4000)
    }
    fullRefreshing.value = false
  }

  /** Check if a stock's price changed since last fetch */
  function priceChangeDirection(code) {
    const prev = prevQuotes.value[code]?.price
    const curr = quotes.value[code]?.price
    if (!prev || !curr || prev === curr) return ''
    return curr > prev ? 'up' : 'down'
  }

  return {
    loading, refreshing, fullRefreshing, error, refreshError, watchlist, quotes, prevQuotes,
    currentPositions, closedPositions, allTrades, allNews,
    allKlineDaily, allKlineMonthly, seasonal, allDividends, expertReports,
    predictions, accuracyStats, learningParams,
    config, lastRefresh,
    fetchAll, refreshQuotesAndReload, triggerFullRefresh, priceChangeDirection,
  }
})
