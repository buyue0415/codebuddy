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
    path: '/kline',
    name: 'kline',
    component: () => import('@/pages/Kline.vue'),
  },
  {
    path: '/manage',
    name: 'manage',
    component: () => import('@/pages/Management.vue'),
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
