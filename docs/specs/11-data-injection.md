# 模块 11: 数据注入模块（已废弃）

> **状态**: ⚠️ **已废弃** | **版本**: v2.0 (废弃标记)
> **废弃原因**: V2 前端使用 Vue API 动态获取数据，不再需要 HTML 静态数据注入

---

## 1. 废弃说明

**原模块功能**（`scripts/reinject_from_db.py`）已于 V2 迁移中彻底移除：

| 原功能 | 替代方案 | 移除版本 |
|--------|---------|---------|
| 将 SQLite 数据通过正则注入到 HTML `const DATA = {...}` 块 | Vue 前端通过 `GET /api/v2/init` + 15 个子 API 动态加载 | v3.0 |

### 1.1 移除的文件

| 文件 | 说明 |
|------|------|
| `scripts/reinject_from_db.py` | 核心注入脚本 |
| `scripts/reinject_data.py` | V0.5 遗留脚本 |
| `scripts/validate_data.py` | 注入验证脚本 |
| `scripts/verify_step2.py` | 迁移验证 |
| `scripts/verify_step3.py` | 迁移验证 |

### 1.2 移除的 API 调用

- ~~`POST /api/trigger/update_statement` 中的 `reinject_from_db.py` 调用~~
- ~~`POST /api/upload/statement` 中的 `reinject_from_db.py` 调用~~

当前上传流程：解析 → 写入 SQLite → 直接返回成功（前端自动刷新获取最新数据）

---

## 2. 历史背景（仅作参考）

旧版系统将前端 HTML 作为"页面模板"，后端通过 Python 脚本读取 SQLite 数据后，用正则替换写入 HTML 文件的 `const DATA = {...};` 区块。这种方式：

- 依赖精确的 JS 声明格式（`const DATA = {...};`）
- 重启服务或重新加载页面时需重新注入
- 无法实现实时数据更新
- 与 Vue 响应式架构不兼容

V2 系统完全基于 API 驱动，前端不再依赖静态数据嵌入。
