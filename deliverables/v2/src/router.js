import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/overview',
  },
  {
    path: '/overview',
    name: 'overview',
    component: () => import('@/pages/Overview.vue'),
  },
  // Placeholder routes for other pages — show "coming soon"
  {
    path: '/trades',
    name: 'trades',
    component: () => import('@/pages/Trades.vue'),
  },
  {
    path: '/fees',
    name: 'fees',
    component: () => import('@/pages/Fees.vue'),
  },
  {
    path: '/intelligence',
    name: 'intelligence',
    component: () => import('@/pages/Intelligence.vue'),
  },
  {
    path: '/expert',
    name: 'expert',
    component: () => import('@/pages/Expert.vue'),
  },
  {
    path: '/news',
    name: 'news',
    component: () => import('@/pages/News.vue'),
  },
  {
    path: '/stock-data',
    name: 'stock-data',
    component: () => import('@/pages/StockData.vue'),
  },
  {
    path: '/kline',
    name: 'kline',
    component: () => import('@/pages/Kline.vue'),
  },
  {
    path: '/pattern-rules',
    name: 'pattern-rules',
    component: () => import('@/pages/PatternRules.vue'),
  },
  {
    path: '/company-graph',
    name: 'company-graph',
    component: () => import('@/pages/CompanyGraph.vue'),
  },
  {
    path: '/manage',
    name: 'manage',
    component: () => import('@/pages/Management.vue'),
  },
  // V0.9: 模拟交易
  {
    path: '/backtest',
    name: 'backtest',
    component: () => import('@/pages/BacktestPage.vue'),
  },
  {
    path: '/paper',
    name: 'paper-trading',
    component: () => import('@/pages/PaperTrading.vue'),
  },
  {
    path: '/paper/history',
    redirect: '/paper',
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
