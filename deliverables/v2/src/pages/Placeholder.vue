<template>
  <div class="placeholder-page">
    <div class="card">
      <h2>🚧 {{ pageTitle }}</h2>
      <div class="info">
        <p>此页面正在迁移中，即将完成。</p>
        <p class="hint">Phase 2-3 计划迁移内容</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const pageTitleMap = {
  trades: '交易记录',
  fees: '手续费分析',
  intelligence: '智能预测',
  expert: '专家分析',
  news: '新闻动态',
  kline: 'K线走势',
  manage: '管理设置',
}

const pageTitle = computed(() => {
  const name = route.name
  return pageTitleMap[name] ? pageTitleMap[name] + ' — 迁移中' : '页面迁移中'
})
</script>

<style scoped>
.placeholder-page {
  max-width: 1200px;
  margin: 24px auto;
  padding: 0 24px;
}
.info {
  text-align: center;
  padding: 24px;
  color: #6b7280;
  line-height: 2;
}
.info a { color: #2563eb; }
.hint { font-size: 12px; color: #9ca3af; margin-top: 8px; }
</style>
