<template>
  <div class="pattern-rules-page">
    <h2>K线形态规则管理</h2>

    <div class="toolbar">
      <div class="filters">
        <select v-model="filterCategory">
          <option value="">全部分类</option>
          <option value="single">单K线</option>
          <option value="double">双K线</option>
          <option value="triple">三K线</option>
          <option value="multi">多K线</option>
          <option value="special">特殊结构</option>
        </select>
        <select v-model="filterDirection">
          <option value="">全部方向</option>
          <option value="bullish">看涨</option>
          <option value="bearish">看跌</option>
          <option value="neutral">中性</option>
        </select>
      </div>
      <div class="actions">
        <button class="btn btn-init" @click="initRules" :disabled="initLoading">
          {{ initLoading ? '初始化中...' : '初始化33条规则' }}
        </button>
        <button class="btn btn-primary" @click="openAdd">+ 新增规则</button>
      </div>
    </div>

    <div v-if="loading" class="loading"><div class="spinner"></div></div>

    <div v-else class="table-wrap">
      <table class="rule-table">
        <thead>
          <tr>
            <th>规则ID</th>
            <th>名称</th>
            <th>分类</th>
            <th>方向</th>
            <th>强度</th>
            <th>天数</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in filteredRules" :key="r.id">
            <td class="id-cell">{{ r.rule_id }}</td>
            <td>
              <div class="name-cell">{{ r.name }}</div>
              <div class="name-en">{{ r.name_en }}</div>
            </td>
            <td>{{ categoryLabel(r.category) }}</td>
            <td><span :class="'dir-' + r.direction">{{ dirLabel(r.direction) }}</span></td>
            <td class="center">{{ '★'.repeat(r.strength) }}</td>
            <td class="center">{{ r.span_days }}</td>
            <td class="center">
              <label class="switch">
                <input type="checkbox" :checked="r.enabled" @change="toggleEnabled(r)" />
                <span class="slider"></span>
              </label>
            </td>
            <td class="actions-cell">
              <button class="btn-sm" @click="openEdit(r)">✏️</button>
              <button class="btn-sm btn-del" @click="confirmDelete(r)">🗑️</button>
            </td>
          </tr>
          <tr v-if="!filteredRules.length">
            <td colspan="8" class="empty">暂无规则</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Edit Dialog -->
    <div v-if="showDialog" class="dialog-overlay" @click.self="closeDialog">
      <div class="dialog">
        <h3>{{ isEditing ? '编辑规则' : '新增规则' }}</h3>
        <div class="form">
          <div class="field">
            <label>规则ID</label>
            <input v-model="editForm.rule_id" :disabled="isEditing" placeholder="如 C1-01" />
          </div>
          <div class="field">
            <label>名称</label>
            <input v-model="editForm.name" placeholder="如 长阳线" />
          </div>
          <div class="field">
            <label>英文名</label>
            <input v-model="editForm.name_en" placeholder="如 Long Bullish" />
          </div>
          <div class="field-half">
            <div class="field">
              <label>分类</label>
              <select v-model="editForm.category">
                <option value="single">单K线</option>
                <option value="double">双K线</option>
                <option value="triple">三K线</option>
                <option value="multi">多K线</option>
                <option value="special">特殊结构</option>
              </select>
            </div>
            <div class="field">
              <label>方向</label>
              <select v-model="editForm.direction">
                <option value="bullish">看涨</option>
                <option value="bearish">看跌</option>
                <option value="neutral">中性</option>
              </select>
            </div>
          </div>
          <div class="field-half">
            <div class="field">
              <label>强度 (1-10)</label>
              <input v-model.number="editForm.strength" type="number" min="1" max="10" />
            </div>
            <div class="field">
              <label>K线天数</label>
              <input v-model.number="editForm.span_days" type="number" min="1" />
            </div>
          </div>
          <div class="field">
            <label>备注</label>
            <input v-model="editForm.memo" placeholder="规则描述" />
          </div>
          <div class="field">
            <label>条件 (JSON)</label>
            <textarea v-model="editForm.conditions" rows="6" class="json-editor"></textarea>
          </div>
        </div>
        <div class="dialog-actions">
          <button class="btn" @click="closeDialog">取消</button>
          <button class="btn btn-primary" @click="saveRule" :disabled="saving">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Confirm -->
    <div v-if="deleteTarget" class="dialog-overlay" @click.self="deleteTarget = null">
      <div class="dialog confirm-dialog">
        <h3>确认删除</h3>
        <p>确定要删除规则 <strong>{{ deleteTarget.rule_id }} - {{ deleteTarget.name }}</strong> 吗？</p>
        <div class="dialog-actions">
          <button class="btn" @click="deleteTarget = null">取消</button>
          <button class="btn btn-danger" @click="doDelete">确认删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiCall } from '@/api/client.js'

const rules = ref([])
const loading = ref(true)
const saving = ref(false)
const initLoading = ref(false)
const showDialog = ref(false)
const isEditing = ref(false)
const deleteTarget = ref(null)
const filterCategory = ref('')
const filterDirection = ref('')

const defaultForm = {
  rule_id: '', name: '', name_en: '', category: 'single',
  direction: 'bullish', strength: 3, span_days: 1,
  conditions: '{}', memo: '',
  enabled: 1,
}
const editForm = ref({ ...defaultForm })

const categoryMap = {
  single: '单K线', double: '双K线', triple: '三K线',
  multi: '多K线', special: '特殊结构',
}
const dirMap = { bullish: '看涨 🔺', bearish: '看跌 🔻', neutral: '中性 ⬜' }

function categoryLabel(c) { return categoryMap[c] || c }
function dirLabel(d) { return dirMap[d] || d }

const filteredRules = computed(() => {
  return rules.value.filter(r => {
    if (filterCategory.value && r.category !== filterCategory.value) return false
    if (filterDirection.value && r.direction !== filterDirection.value) return false
    return true
  })
})

async function fetchRules() {
  loading.value = true
  const resp = await apiCall('GET', '/api/v2/pattern-rules')
  if (resp?.success) {
    rules.value = resp.data || []
  }
  loading.value = false
}

async function initRules() {
  initLoading.value = true
  const resp = await apiCall('POST', '/api/v2/pattern-rules/init')
  if (resp?.success) {
    await fetchRules()
  }
  initLoading.value = false
}

async function toggleEnabled(rule) {
  await apiCall('PUT', `/api/v2/pattern-rules/${rule.rule_id}`, { enabled: rule.enabled ? 0 : 1 })
  rule.enabled = rule.enabled ? 0 : 1
}

function openAdd() {
  isEditing.value = false
  editForm.value = { ...defaultForm }
  showDialog.value = true
}

function openEdit(rule) {
  isEditing.value = true
  editForm.value = {
    rule_id: rule.rule_id, name: rule.name, name_en: rule.name_en || '',
    category: rule.category, direction: rule.direction,
    strength: rule.strength, span_days: rule.span_days,
    conditions: rule.conditions, memo: rule.memo || '',
    enabled: rule.enabled,
  }
  showDialog.value = true
}

function closeDialog() {
  showDialog.value = false
}

async function saveRule() {
  saving.value = true
  const form = editForm.value
  // Validate JSON
  try {
    JSON.parse(form.conditions)
  } catch {
    alert('conditions 格式错误：请输入合法的 JSON')
    saving.value = false
    return
  }
  const payload = {
    ...form, strength: Number(form.strength), span_days: Number(form.span_days),
  }
  let resp
  if (isEditing.value) {
    resp = await apiCall('PUT', `/api/v2/pattern-rules/${form.rule_id}`, payload)
  } else {
    resp = await apiCall('POST', '/api/v2/pattern-rules', payload)
  }
  if (resp?.success) {
    await fetchRules()
    closeDialog()
  } else {
    alert('保存失败: ' + (resp?.error || '未知错误'))
  }
  saving.value = false
}

function confirmDelete(rule) {
  deleteTarget.value = rule
}

async function doDelete() {
  if (!deleteTarget.value) return
  const resp = await apiCall('DELETE', `/api/v2/pattern-rules/${deleteTarget.value.rule_id}`)
  if (resp?.success) {
    await fetchRules()
  }
  deleteTarget.value = null
}

onMounted(fetchRules)
</script>

<style scoped>
.pattern-rules-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}
.pattern-rules-page h2 {
  font-size: 20px;
  color: #1f2937;
  margin-bottom: 16px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}
.filters { display: flex; gap: 8px; }
.filters select {
  padding: 6px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 13px;
  background: #fff;
  color: #374151;
  cursor: pointer;
}
.actions { display: flex; gap: 8px; }
.btn {
  padding: 6px 16px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  color: #374151;
  cursor: pointer;
  font-size: 13px;
  transition: all .15s;
}
.btn:hover { background: #f3f4f6; }
.btn-primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.btn-primary:hover { background: #1d4ed8; }
.btn-init { background: #059669; color: #fff; border-color: #059669; }
.btn-init:hover { background: #047857; }
.btn-danger { background: #dc2626; color: #fff; border-color: #dc2626; }
.btn-danger:hover { background: #b91c1c; }
.loading { text-align: center; padding: 40px; }
.spinner { width: 32px; height: 32px; border: 3px solid #e5e7eb; border-top-color: #2563eb; border-radius: 50%; animation: spin .8s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }
.table-wrap { overflow-x: auto; }
.rule-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.rule-table th {
  background: #f3f4f6;
  padding: 10px 12px;
  text-align: left;
  font-weight: 600;
  color: #374151;
  border-bottom: 2px solid #e5e7eb;
  white-space: nowrap;
}
.rule-table td { padding: 8px 12px; border-bottom: 1px solid #f3f4f6; color: #4b5563; }
.rule-table tr:hover td { background: #f9fafb; }
.id-cell { font-family: monospace; font-weight: 600; color: #2563eb; white-space: nowrap; }
.name-cell { font-weight: 500; color: #1f2937; }
.name-en { font-size: 11px; color: #9ca3af; }
.center { text-align: center; }
.dir-bullish { color: #dc2626; font-weight: 600; }
.dir-bearish { color: #16a34a; font-weight: 600; }
.dir-neutral { color: #6b7280; }
.empty { text-align: center; padding: 30px; color: #9ca3af; }
.actions-cell { white-space: nowrap; }
.btn-sm {
  padding: 4px 8px; border: none; background: none; cursor: pointer;
  font-size: 14px; border-radius: 4px; transition: background .15s;
}
.btn-sm:hover { background: #f3f4f6; }
.btn-del:hover { background: #fee2e2; }
/* Toggle Switch */
.switch { position: relative; display: inline-block; width: 36px; height: 20px; }
.switch input { opacity: 0; width: 0; height: 0; }
.switch .slider {
  position: absolute; cursor: pointer; inset: 0;
  background: #d1d5db; border-radius: 20px; transition: .3s;
}
.switch .slider::before {
  content: ''; position: absolute; height: 16px; width: 16px;
  left: 2px; bottom: 2px; background: #fff; border-radius: 50%; transition: .3s;
}
.switch input:checked + .slider { background: #2563eb; }
.switch input:checked + .slider::before { transform: translateX(16px); }
/* Dialog */
.dialog-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.4);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.dialog {
  background: #fff; border-radius: 12px; padding: 24px;
  width: 560px; max-width: 90vw; max-height: 85vh; overflow-y: auto;
  box-shadow: 0 8px 30px rgba(0,0,0,.2);
}
.dialog h3 { font-size: 16px; color: #1f2937; margin-bottom: 16px; }
.form { display: flex; flex-direction: column; gap: 12px; }
.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 12px; color: #6b7280; font-weight: 500; }
.field input, .field select {
  padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px;
  font-size: 13px; color: #374151; background: #fff;
}
.field input:disabled { background: #f3f4f6; color: #9ca3af; }
.json-editor {
  font-family: 'Consolas', 'Monaco', monospace; font-size: 12px;
  padding: 8px; border: 1px solid #d1d5db; border-radius: 6px;
  resize: vertical; background: #f9fafb; color: #374151;
}
.field-half { display: flex; gap: 12px; }
.field-half .field { flex: 1; }
.dialog-actions {
  display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px;
}
.confirm-dialog { width: 400px; }
.confirm-dialog p { color: #4b5563; font-size: 14px; margin: 0 0 16px; }
</style>
