# 14 — 形态规则

> **前端页面**: `deliverables/v2/src/pages/PatternRules.vue` (14KB)
> **路由**: `/pattern-rules` | **菜单**: 股票信息收集 → 形态规则

---

## 1. 业务需求说明书

### 1.1 业务背景

K线形态（如头肩顶/双底/锤子线等）是技术分析经典工具。系统内置33条标准K线形态规则，用户可查看规则定义并扫描自选股识别形态。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 33条标准规则 | 内置经典K线形态的检测逻辑 |
| 规则 CRUD | 支持查看/新增/编辑/删除规则 |
| 形态扫描 | 对各股票日K线执行规则匹配 |
| 结果可视化 | K线图上标注识别到的形态 |

---

## 2. 技术方案深度分析

### 2.1 规则数据结构

```sql
CREATE TABLE pattern_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,        -- 规则名称（如"头肩顶"）
    description TEXT,           -- 规则描述
    type TEXT,                  -- reversal(反转)/continuation(持续)
    code TEXT NOT NULL,         -- Python检测代码（eval执行）
    created_at TEXT,
    updated_at TEXT
);
```

### 2.2 检测流程

```python
# pattern_engine.py
def scan_pattern(code, rule):
    kdata = get_kline_daily(code)
    # 执行规则的 Python 代码（使用 kdata 作为上下文）
    # 返回匹配结果列表 [{date, pattern_name, confidence}]

# server_v2.py
@app.get("/api/v2/pattern-scan/{code}")
def api_pattern_scan(code):
    rules = get_pattern_rules()
    results = []
    for rule in rules:
        matches = scan_pattern(code, rule)
        results.extend(matches)
    return api_response(data=results)
```

### 2.3 内置规则类型

| 类型 | 示例 | 数量 |
|------|------|------|
| 反转形态 | 头肩顶/底、双顶/底、V形反转 | ~12 |
| 持续形态 | 旗形、三角形、楔形 | ~8 |
| 单K线 | 锤子线、倒锤子、十字星 | ~7 |
| 双K线 | 吞没形态、孕线、刺透 | ~6 |

---

## 3. 功能介绍和实现方式

### 3.1 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/pattern-rules` | 获取所有形态规则 |
| GET | `/api/v2/pattern-rules/{rule_id}` | 获取单条规则 |
| POST | `/api/v2/pattern-rules` | 新增规则 |
| PUT | `/api/v2/pattern-rules/{rule_id}` | 更新规则 |
| DELETE | `/api/v2/pattern-rules/{rule_id}` | 删除规则 |
| POST | `/api/v2/pattern-rules/init` | 初始化33条标准规则 |
| GET | `/api/v2/pattern-scan/{code}` | 扫描形态 |

### 3.2 启动初始化

```python
# server_v2.py 启动时自动调用
# init_pattern_rules.py → 写入33条标准规则到 pattern_rules 表
# 仅在表为空时执行（避免重复初始化）
```

### 3.3 前端实现

```vue
<!-- PatternRules.vue 核心结构 -->
<template>
  <!-- 规则列表 -->
  <section>
    <h3>形态规则（{{ rules.length }}条）</h3>
    <Button @click="initRules">🔄 重置为默认</Button>

    <DataTable :data="rules" :editable="true">
      <Column field="name" header="名称" />
      <Column field="type" header="类型" />
      <Column field="description" header="描述" />
      <Column field="code" header="检测代码" />
      <Column>
        <Button @click="editRule(rule)">编辑</Button>
        <Button @click="deleteRule(rule.id)">删除</Button>
      </Column>
    </DataTable>
  </section>

  <!-- 形态扫描 -->
  <section>
    <h3>形态扫描</h3>
    <Dropdown v-model="scanCode" :options="watchlist" />
    <Button @click="scanPatterns">🔍 扫描</Button>
    <ScanResults :results="scanResults" />
  </section>
</template>
```

---

## 4. 用户操作流程

### 4.1 查看规则列表

```
用户: 导航栏 "股票信息收集" → "形态规则"

页面显示:
┌───────────────────────────────────────────────┐
│  形态规则（33条）          [🔄 重置为默认]     │
│                                               │
│  ┌──────────┬────────┬──────────────────┐     │
│  │ 名称     │ 类型   │ 描述             │     │
│  │头肩顶    │ reversal│ 三峰中高...      │     │
│  │双底      │ reversal│ W形底部...       │     │
│  │锤子线    │ single  │ 长下影线小实体...│     │
│  └──────────┴────────┴──────────────────┘     │
└───────────────────────────────────────────────┘
```

### 4.2 扫描形态

```
用户: 选择股票 "601166 兴业银行" → 点击 [🔍 扫描]
  → GET /api/v2/pattern-scan/601166
  → 显示匹配结果:
    - 头肩底 (06-03, confidence: 0.82)
    - 双底 (05-15, confidence: 0.75)
    - 锤子线 (06-05, confidence: 0.68)
  → 点击某形态 → 跳转到K线页面高亮对应区域
```
