---
name: dividend-yield-ttm-analysis
overview: 分析股息率走势（TTM）计算方式的5个关键缺陷，定位根本原因，并提供优化后的计算逻辑与修正步骤。
todos:
  - id: data-migration
    content: 数据迁移：为dividends表新增ex_date列和唯一索引(code, date, amount)，回填历史数据的ex_date
    status: pending
  - id: unify-per-share
    content: 统一每股分红计算：提取_compute_per_share()公共函数，重构calc_dividend_yield()和get_dividends()调用统一逻辑
    status: pending
    dependencies:
      - data-migration
  - id: fix-ttm-anchor
    content: 修复TTM窗口悬崖效应：将calc_dividend_yield()和get_dividend_yield_series()的窗口锚定从"今天"改为"最近分红日期+5天缓冲"
    status: pending
    dependencies:
      - unify-per-share
  - id: fix-ex-date-alignment
    content: 修复除权日与股权登记日对齐：TTM窗口使用ex_date判定分红归属，股权登记日从ex_date反推
    status: pending
    dependencies:
      - data-migration
      - unify-per-share
  - id: add-dedup-protection
    content: 添加数据去重保护：upsert_positions使用事务包裹+INSERT OR REPLACE，div_timeline构建时按(code,date,amount)去重
    status: pending
    dependencies:
      - data-migration
  - id: verify-and-regression
    content: 使用[skill:systematic-debugging]和[skill:verification-before-completion]运行测试套件，对比修复前后股息率走势，确认所有缺陷已修复
    status: pending
    dependencies:
      - fix-ttm-anchor
      - fix-ex-date-alignment
      - add-dedup-protection
---

## 用户需求

分析并修复系统中股息率走势（TTM）计算方式的明显缺陷，定位导致数据异常或逻辑错误的根本原因，并提供优化后的计算方案与修正步骤，确保股息率（TTM）走势准确反映最近四个季度的真实分红水平与股价关系。

## 核心缺陷列表

1. **TTM窗口"悬崖效应"**：固定365天窗口锚定在"今天"，年度分红过期后股息率断崖式归零，产生不真实的0%收益率走势
2. **派息日与除权日错位**：使用派息日（股息入账日）判定分红归属，但股价在除权日已调整，导致除权日到派息日之间股息率偏低
3. **股权登记日估算粗糙**：硬编码`pay_date - 2天`，不考虑交易日历，且`date < record_date`严格小于可能错误计入登记日当天买入的股数
4. **前后端计算不一致**：`calc_dividend_yield()`与`get_dividend_yield_series()`独立计算每股分红，可能产生不一致的结果
5. **分红数据重复风险**：dividends表缺少唯一约束，多路径写入存在重复插入的可能

## 技术栈

- 后端：Python 3 + SQLite3
- 数据来源：广发证券对账单（xlsx解析） + 微证券K线接口
- 现有文件：`scripts/refresh_quotes.py`、`scripts/db_helper.py`、`scripts/migrate_to_sqlite.py`

## 缺陷详细分析与修复方案

### 缺陷1：TTM窗口"悬崖效应"

**问题定位**：`scripts/refresh_quotes.py:101-103`和`scripts/db_helper.py:750`

```python
today = datetime.now()
cutoff = today - timedelta(days=365)
```

A股公司通常每年分红一次（年报分红，集中在5-7月到账）。假设某股票2025年6月10日派息0.50元/股，到2026年6月11日（366天后），365天窗口排除该笔分红，若2026年度分红尚未到账（通常也在6月），股息率从5%突然归零，走势图出现断崖式下跌，而公司基本面并未变化。

**修复方案**：将TTM窗口锚定从"今天"改为"最近一次分红日期"，配合"4季度滚动"的窗口逻辑：

```python
# 取最近一次分红日期作为窗口右边界
if div_rows:
    latest_div = max(d.date for d in div_rows)
    cutoff = latest_div - timedelta(days=365)
else:
    cutoff = today - timedelta(days=365)
```

这样确保只要最近分红在窗口内，TTM就能稳定反映分红水平。同时增加保护：若窗口内无分红但最近一次分红在370天以内（容忍5天缓冲），仍将其计入。

**文件变更**：

- `scripts/refresh_quotes.py` `calc_dividend_yield()` 第101-103行
- `scripts/db_helper.py` `get_dividend_yield_series()` 第748-751行

---

### 缺陷2：派息日与除权日错位

**问题定位**：`scripts/refresh_quotes.py:110-119`和`scripts/db_helper.py:758-762`

系统使用派息日（dividends表date字段，来自券商对账单"股息入账"交易日期）判断分红是否在TTM窗口内。但股价在除权日（通常比派息日早2-5个交易日）就已经下调整。在除权日到派息日之间：股价已除权（反映无分红状态），但TTM累计尚未计入该笔分红（因为用派息日判定），导致股息率呈现周期性"先低后正常"的锯齿形波动。

**修复方案**：为dividends表增加`ex_date`（除权日）字段，在TTM窗口判定中使用除权日替代派息日。除权日默认为派息日-3个自然日（相对保守，大于普遍间隔），同时对账单数据中如有`price`字段（登记日股价对应的除权日附近价格），可辅助推算。

1. 在`dividends`表中新增`ex_date TEXT`列（通过ALTER TABLE迁移）
2. `calc_dividend_yield()`和`get_dividend_yield_series()`的TTM窗口改用`ex_date`
3. 对于历史数据，`ex_date`回填为`date - 3天`

**文件变更**：

- `scripts/migrate_to_sqlite.py`：CREATE TABLE dividends增加ex_date列
- `scripts/db_helper.py` `upsert_positions()` 第571-572行：写入时计算ex_date
- `scripts/db_helper.py` `get_dividends()` 第300-314行：返回ex_date
- `scripts/refresh_quotes.py` `calc_dividend_yield()` 第110-119行：使用ex_date判定窗口
- `scripts/db_helper.py` `get_dividend_yield_series()` 第721-762行：使用ex_date判定窗口

---

### 缺陷3：股权登记日估算粗糙

**问题定位**：`scripts/refresh_quotes.py:133-134`和`scripts/db_helper.py:310`

```python
record_date_str = (div_date - timedelta(days=2)).strftime('%Y-%m-%d')
```

两个问题：

- **自然日vs交易日**：`timedelta(days=2)`减去的是自然日，但派息日到股权登记日间隔是交易日。若派息日在周一，减2天是周六，实际股权登记日可能在前一周的周四或周五，股数计算偏大
- **严格小于比较**：`date < record_date`（第277行）将登记日当天买入的股票也计入有权分红的股数范围。正确逻辑应为`date <= record_date`（含登记日当天持仓），但保守处理可维持严格小于

**修复方案**：将股权登记日估算改为`pay_date - timedelta(days=3)`（更保守的3自然日），并利用除权日（缺陷2新增的ex_date）反推股权登记日。A股规则：股权登记日 = 除权日前一个交易日。因此：

```python
# ex_date已知时，股权登记日为ex_date前一个自然日
# （已是日期比较，SQL中用 date < record_date 即含登记日）
record_date_str = (ex_date - timedelta(days=1)).strftime('%Y-%m-%d')
```

对历史数据（无ex_date），保持`div_date - timedelta(days=3)`作为保守估算。

**文件变更**：

- `scripts/refresh_quotes.py` `calc_dividend_yield()` 第133-134行
- `scripts/db_helper.py` `get_dividends()` 第308-312行

---

### 缺陷4：前后端计算不一致

**问题定位**：

- `calc_dividend_yield()`（refresh_quotes.py 第132-151行）内联计算每股分红
- `get_dividend_yield_series()`（db_helper.py 第717-718行）调用`get_dividends()`获取预计算的per_share
- 两者使用独立的DB连接和独立的计算逻辑，可能产生微小偏差

**修复方案**：统一每股分红计算为单一来源。引入`_compute_per_share(code, pay_date, amount)`公共函数，在`db_helper.py`中定义，两处均调用此函数。

```python
def _compute_per_share(code: str, pay_date: str, amount: float) -> float:
    """Compute per-share dividend amount based on holdings at record date."""
    # ex_date = pay_date - 3 days (conservative estimate)
    # record_date = ex_date - 1 day
    pay_dt = datetime.strptime(pay_date[:10], '%Y-%m-%d')
    ex_dt = pay_dt - timedelta(days=3)
    record_dt = ex_dt - timedelta(days=1)
    record_str = record_dt.strftime('%Y-%m-%d')
    shares = _shares_before_date(code, record_str)
    return round(amount / shares, 4) if shares > 0 else 0.0
```

**文件变更**：

- `scripts/db_helper.py`：新增`_compute_per_share()`函数，重构`get_dividends()`调用它
- `scripts/refresh_quotes.py`：导入`_compute_per_share`，替换内联计算（第132-151行）

---

### 缺陷5：分红数据重复风险

**问题定位**：

- `dividends`表仅有AUTOINCREMENT主键，无业务唯一约束
- `upsert_positions()`（db_helper.py 第567行）先`DELETE FROM dividends`再批量INSERT，单次同步安全
- 但`migrate_to_sqlite.py`（第149行）仅INSERT，多次迁移会产生重复
- 若程序异常中断在DELETE后INSERT前，数据丢失

**修复方案**：

1. 为dividends表添加UNIQUE约束`(code, date, amount)`，防止重复插入
2. `upsert_positions()`改用`INSERT OR REPLACE`或事务包裹
3. 在`get_dividend_yield_series()`中增加去重逻辑（以code+date+amount为键）

```sql
-- 新增唯一索引
CREATE UNIQUE INDEX IF NOT EXISTS idx_div_unique 
ON dividends(code, date, amount);
```

4. `upsert_positions()`中的DELETE+INSERT用事务包裹，确保原子性

**文件变更**：

- `scripts/migrate_to_sqlite.py`：CREATE UNIQUE INDEX
- `scripts/db_helper.py` `upsert_positions()` 第564-579行：事务包裹 + INSERT OR REPLACE
- `scripts/db_helper.py` `get_dividend_yield_series()` 第718-729行：构建div_timeline时按(code, date, amount)去重

---

## 实施步骤

### 步骤1：数据迁移 — dividends表结构增强

新增ex_date列和唯一约束，确保后续计算有准确的除权日期

### 步骤2：统一每股分红计算逻辑

提取公共函数`_compute_per_share()`，消除前后端计算不一致

### 步骤3：修复TTM窗口悬崖效应

将窗口锚定从"今天"改为"最近分红日期"，增加缓冲容差

### 步骤4：修复除权日/登记日时间点对齐

TTM窗口使用ex_date判定，股权登记日从ex_date反推

### 步骤5：添加数据去重保护

唯一索引 + INSERT OR REPLACE + div_timeline去重

### 步骤6：验证与回归测试

对比修复前后的股息率走势数据，确认走势平滑且准确

## Agent Extensions

### Skill

- **systematic-debugging**
- 目的：在修复过程中系统性验证每个缺陷的根因，确保修复方案正确且不引入新问题
- 预期结果：每个缺陷修复都有明确的验证断言（assertion），通过前后数据对比确认修复效果

- **verification-before-completion**
- 目的：在所有代码修改完成后，运行现有测试套件并手动验证股息率计算结果
- 预期结果：确认tests/目录下相关测试通过，股息率走势数据逻辑正确且走势平滑

- **writing-plans**
- 目的：本计划已用于生成结构化的实现方案，确保覆盖所有缺陷的根因分析和修复步骤
- 预期结果：当前生成的完整计划文档