---
name: prediction-module-refactor
overview: 重构智能预测模块：后端解耦三层架构并标准化接口，前端模块化并删除K线图和月度视图，提升可维护性和可测试性。
todos:
  - id: create-predict-package
    content: 创建 scripts/predict/ 包结构，将 optimize_predict.py 按职责拆分为 quality.py、signals.py、features.py、predictor.py、model.py、learning.py 六个模块，__init__.py 统一导出公共API
    status: completed
  - id: update-imports
    content: 更新 sync_all.py、optimize_predict.py（入口）、server.py 中所有预测相关 import 路径，确保向后兼容
    status: completed
    dependencies:
      - create-predict-package
  - id: remove-frontend-charts
    content: 删除 intelligence.js 中K线图（199-343行）和月度视图（345-418行）代码，删除季节性展望渲染（170-180行），移除 tab 切换相关变量和函数
    status: completed
  - id: update-html-layout
    content: 修改 bank-stock-system.html：删除6月价格展望卡片、走势图section、chartjs-chart-financial CDN，调整 .intel-top-row 为两列布局
    status: completed
    dependencies:
      - remove-frontend-charts
  - id: clean-css
    content: 清理 app.css：删除 .intel-seasonal-* 和 .intel-seas-* 样式，修改 .intel-top-row 为 1fr 1fr 两列布局
    status: completed
    dependencies:
      - remove-frontend-charts
  - id: add-predict-tests
    content: 新增 tests/test_predict/ 目录，编写 test_signals.py、test_features.py、test_predictor.py、test_learning.py、test_quality.py 五个测试文件
    status: completed
    dependencies:
      - create-predict-package
  - id: write-documentation
    content: 编写 docs/predict/ 目录下的 architecture.md、signals.md、api.md 三份文档
    status: completed
---

## 用户需求

重构智能预测模块，提升可维护性。

### 核心目标

- **后端模块化**：将 `optimize_predict.py`（979行）按职责拆分为6个独立模块
- **前端精简**：移除K线图（candlestick）和月度视图（6月季节性预测），保留核心功能
- **测试覆盖**：为预测模块增加完整单元测试
- **文档完善**：编写架构文档、信号说明、API文档

### 保留功能

- 次日预测卡片（价格区间、方向、置信度、建议）
- 技术信号详情网格（10项信号展示）
- 历史命中率网格（近20日）
- dropdown日历组件（历史日期切换）
- "刷新"触发按钮
- 综合操作建议
- 关键价位（现价、加仓/减仓线、股息率）

### 删除功能

- K线图（candlestick图表 + 预测支撑/阻力线叠加 + divider插件）
- 月度视图（6月季节性预测走势图）
- Tab切换按钮（"K线" / "月度"）
- 6月价格展望卡片
- chartjs-chart-financial CDN 依赖

## 技术栈

- **后端**：Python 3.12 + SQLite，遵循现有 `tests/` 中 `unittest` + `StockTestBase` 模式
- **前端**：原生 JavaScript + Chart.js（保留用于其他页面），CSS Grid + Flexbox
- **文档**：Markdown，遵循 `docs/specs/` 现有格式

## 实现方案

### 后端重构策略（模块化拆分）

将 `optimize_predict.py` 按**三层架构**拆分为 `scripts/predict/` 包：

```
scripts/predict/
├── __init__.py          # 公共导出：所有SIGNALS_V3常量、工厂函数
├── quality.py           # Layer 1: load_kline_data, analyze_data_quality, clean_kline_data
├── signals.py           # Layer 2: calc_signals_v3, _ema, SIGNALS_V3常量
├── features.py          # Layer 2: build_ml_features, build_ml_features_from_info
├── predictor.py         # Layer 2-3: gen_pred_v3 (规则投票), hybrid_predict (混合集成)
├── model.py             # Layer 3: build_meta_dataset, train_meta_model, save_to_db
└── learning.py          # MWU: improved_mwu_update, _get_or_init_lp, _get_seasonal_factor
```

**重构后的 `optimize_predict.py`** 转变为薄入口脚本（~50行），仅保留 `main()` + `argparse`，import 来自 `predict/` 包。

**关键兼容性保证**：

- `scripts/sync_all.py` 中的 `from optimize_predict import calc_signals_v3, gen_pred_v3, ...` 需改为 `from predict.signals import ...`
- `server.py` 中通过 `_build_init_data()` 提供的 `seasonal` 数据保持不变（预测引擎仍需季节因子）
- `db_helper.py` 中 `insert_daily_prediction` 等 CRUD 函数不做修改

### 前端重构策略（删除 + 调整布局）

**`intelligence.js` 变更**：

- 删除 L199-343：K线图渲染（candlestick + dividerPlugin + fallback）
- 删除 L345-418：月度视图渲染
- 删除 L170-180：6月季节性展望
- 删除 L4(`intelTab`), L11-17(`switchIntelTab`), L416-418(tab visibility)
- 删除 L3-4：不再需要的 `intelDailyInst`, `intelMonthlyInst`, `intelTab` 变量

**`bank-stock-system.html` 变更**：

- 删除 L216：6月价格展望卡片
- 删除 L220-227：整个走势图 section（tab + K线canvas + 月度canvas）
- 删除 L401：chartjs-chart-financial CDN `<script>` 标签
- 调整 L214-218 `.intel-top-row` 布局：从三列改为两列（次日预测 + 关键价位）

**`app.css` 变更**：

- 删除 `.intel-seasonal-grid`, `.intel-seas-item`, `.seas-m`, `.seas-p`, `.seas-chg` 样式
- 修改 `.intel-top-row` grid-template-columns 为 `1fr 1fr`（原 `1fr 1.2fr 1fr`）
- 修改响应式 `@media(max-width:800px)` 为 `1fr`

### 测试策略

新增 `tests/test_predict/` 目录，遵循现有 `unittest` + `StockTestBase` + `conftest` 模式：

| 测试文件 | 覆盖模块 | 测试重点 |
| --- | --- | --- |
| `test_signals.py` | predict/signals.py | 10信号计算正确性，边界条件(None/kdata不足) |
| `test_features.py` | predict/features.py | 30维ML特征向量构建、缺失值处理 |
| `test_predictor.py` | predict/predictor.py | 规则投票、置信度计算、方向判定 |
| `test_learning.py` | predict/learning.py | MWU更新逻辑、权重归一化、自适应衰减率 |
| `test_quality.py` | predict/quality.py | 数据加载、异常检测、清洗前后验证 |


### 文档

| 文档文件 | 内容 |
| --- | --- |
| `docs/predict/architecture.md` | 三层架构图、模块依赖关系、数据流 |
| `docs/predict/signals.md` | 10项信号定义、计算公式、方向判定规则 |
| `docs/predict/api.md` | gen_pred_v3/hybrid_predict 接口签名、参数说明 |


### 性能与风险控制

- **向后兼容**：`optimize_predict.py` 保留为入口，CLI 参数不变；`sync_all.py` import 路径更新
- **seasonal 数据保留**：预测引擎仍需季节因子，server.py 的 `_build_init_data()` 中 `seasonal` 不删除
- **Chart.js 主库保留**：仅在 intelligence 页删除图表，其他页面（如持仓分析）仍可能使用
- **CSS 命名空间**：`.dp-*` 样式保留（次日预测、信号、历史网格仍使用），仅删除 `.intel-seasonal-*` 和 `.intel-seas-*`

## Agent Extensions

### Skill

- **writing-plans**
- Purpose: 确认重构方案完整性，生成最终实施计划文档并输出到 `docs/plans/` 目录
- Expected outcome: 生成 `docs/plans/2026-06-03-predict-refactor.md` 实施计划

### SubAgent

- **code-explorer**
- Purpose: 在重构前验证所有 import 依赖关系，确保拆分后的模块引用路径正确，发现潜在的循环依赖
- Expected outcome: 输出完整的依赖关系图和所有需要更新 import 的文件清单