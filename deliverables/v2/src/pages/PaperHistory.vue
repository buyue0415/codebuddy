<template>
  <div class="page-content">
    <div style="text-align:center;padding:60px 24px;color:#6b7280">
      <div style="font-size:48px;margin-bottom:16px">📊</div>
      <h2>交易历史已合并到纸面交易页面</h2>
      <p style="margin:12px 0 24px;font-size:14px">资金曲线、绩效统计、交易记录等功能已整合到统一交易页面中</p>
      <button class="tab-btn" style="background:#2563eb;color:#fff;border-color:#2563eb;padding:10px 28px;font-size:15px"
        @click="goToPaper">前往统一交易页面 →</button>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
const router = useRouter()
function goToPaper() { router.push('/paper') }
</script>

<style scoped>
.tab-btn { padding: 8px 20px; border: 1px solid #d1d5db; border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; transition: all .2s; }
.tab-btn:hover { background: #f3f4f6; }
</style>
