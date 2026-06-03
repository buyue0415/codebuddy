/**
 * 公共数据 store — 加载一次，多个页面共享
 * 替代旧版全局变量 DATA / trades / cp / cl / ...
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { loadAllData, clearCache } from '@/api/client.js'

export const useDataStore = defineStore('data', () => {
  const loading = ref(false)
  const error = ref(null)
  const watchlist = ref([])
  const quotes = ref({})
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

  async function fetchAll() {
    clearCache()
    loading.value = true
    error.value = null
    try {
      const { DATA, config: cfg, dividends: divs } = await loadAllData()
      watchlist.value = DATA.watchlist || []
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
    }
  }

  return {
    loading, error, watchlist, quotes,
    currentPositions, closedPositions, allTrades, allNews,
    allKlineDaily, allKlineMonthly, seasonal, allDividends, expertReports,
    predictions, accuracyStats, learningParams,
    config, lastRefresh,
    fetchAll,
  }
})
