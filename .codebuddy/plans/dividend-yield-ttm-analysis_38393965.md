---
name: dividend-yield-ttm-analysis
overview: 分析并修复股息率走势（TTM）计算方式的5个关键缺陷，同时建立"实际公布数据"与"公式计算值"的严格区分体系，确保前端清晰标注数据来源。
todos:
  - id: schema-migration
    content: 数据迁移：为dividends表新增ex_date列和source列，添加唯一索引(code,date,amount)，回填历史数据
    status: completed
  - id: unify-per-share
    content: 统一每股分红计算：提取_compute_per_share()公共函数，重构get_dividends()返回source字段，calc_dividend_yield()改为调用统一函数
    status: completed
    dependencies:
      - schema-migration
  - id: fix-ttm-and-exdate
    content: 修复TTM窗口锚定与除权日对齐：窗口锚定改为最近分红ex_date+5天缓冲，TTM判定使用ex_date，登记日从ex_date反推
    status: completed
    dependencies:
      - unify-per-share
  - id: api-source-metadata
    content: API层增加来源标识：/api/v2/dividends和/api/v2/dividend-yield-series返回增加source字段和顶层数据来源标识
    status: completed
    dependencies:
      - unify-per-share
  - id: add-dedup-protection
    content: 添加数据去重保护：upsert_positions使用事务包裹+INSERT OR REPLACE，div_timeline构建时按(code,date,amount)去重
    status: completed
    dependencies:
      - schema-migration
  - id: frontend-labels
    content: 使用[skill:subagent-driven-development]并行改造前端5处展示标签：持仓表格股息率列、股息率走势图表、分红明细表、智能建议面板、图表tooltip，全部标注数据来源
    status: completed
    dependencies:
      - api-source-metadata
  - id: verify-all
    content: 使用[skill:verification-before-completion]运行完整测试套件，验证股息率计算结果正确性、来源标识完整性、前后端数据一致性
    status: completed
    dependencies:
      - fix-ttm-and-exdate
      - add-dedup-protection
      - frontend-labels
---

## 用户需求

### 需求A：修复股息率（TTM）5个计算缺陷

1. **TTM窗口"悬崖效应"**：固定365天窗口锚定在"今天"，A股年度分红过期后股息率突然归零，走势图出现不真实的断崖式下跌
2. **派息日与除权日错位**：使用派息日（股息入账日）判定分红归属，但股价在除权日已下调，导致除权日到派息日之间股息率周期性偏低
3. **股权登记日估算粗糙**：硬编码`pay_date - 2天`（自然日而非交易日），且`date < record_date`可能错误计入登记日当天的买入
4. **前后端计算不一致**：`calc_dividend_yield()`与`get_dividend_yield_series()`独立计算每股分红，可能产生偏差
5. **分红数据重复风险**：dividends表仅靠AUTOINCREMENT主键，无业务唯一约束

### 需求B：严格区分数据来源与标识

在系统中建立清晰的数据来源分层：

- 对账单导入的分红数据 → 标注"对账单实际到账数据"
- 每股派息（金额÷持仓股数）→ 标注"计算值（到账金额÷持仓股数）"
- K线除权缺口估算 → 标注"公式估算值（K线除权缺口推算）"
- TTM股息率（quotes.dy）→ 标注"公式计算值（TTM滚动推算）"
- 股息率走势时间序列 → 标注"公式计算值（TTM推算走势）"

前端5处需添加标识：

1. 持仓表格"股息率"列 → 标注"TTM推算"+tooltip
2. 股息率走势(TTM)图表 → 标题含来源，分红事件区分实际vs估算
3. 分红明细表 → 标注"对账单实际到账"，每股派息标注"计算值"
4. 智能建议面板 → 股息率旁标注"TTM推算"
5. 图表hover tooltip → 显示数据来源标签

## 技术栈

- 后端：Python 3 + SQLite3
- 数据来源：广发证券对账单（xlsx解析） + 微证券K线接口
- 前端：原生HTML + Chart.js 4.4.1（CDN加载）
- 服务框架：Python http.server

## 数据库Schema变更

### dividends表新增字段

```sql
-- 新增 ex_date（除权日）和 source（数据来源标识）
ALTER TABLE dividends ADD COLUMN ex_date TEXT;
ALTER TABLE dividends ADD COLUMN source TEXT DEFAULT 'statement';

-- 新增唯一索引防重复
CREATE UNIQUE INDEX IF NOT EXISTS idx_div_unique ON dividends(code, date, amount);

-- 回填历史数据：ex_date = date - 3天, source = 'statement'
UPDATE dividends SET ex_date = date(date, '-3 days'), source = 'statement' WHERE ex_date IS NULL;
```

source字段枚举值：

- `statement`：对账单实际到账数据（默认）
- `kline_estimated`：K线除权缺口公式估算值

## 实现方案

### 1. 数据迁移：dividends表结构增强

**涉及文件**：`scripts/migrate_to_sqlite.py`

- CREATE TABLE时包含`ex_date TEXT`和`source TEXT DEFAULT 'statement'`
- 添加`CREATE UNIQUE INDEX IF NOT EXISTS idx_div_unique ON dividends(code, date, amount)`
- 历史数据回填：ex_date = date - 3天

同时更新`scripts/db_helper.py` `upsert_positions()`：

- INSERT dividends时写入ex_date（= date - 3天）和source='statement'
- 用事务包裹DELETE+INSERT确保原子性
- INSERT OR REPLACE防止重复

### 2. 统一每股分红计算

**涉及文件**：`scripts/db_helper.py`、`scripts/refresh_quotes.py`

在`db_helper.py`中新增`_compute_per_share()`公共函数：

```python
def _compute_per_share(code, pay_date, amount) -> float:
    pay_dt = datetime.strptime(pay_date[:10], '%Y-%m-%d')
    ex_dt = pay_dt - timedelta(days=3)
    record_dt = ex_dt - timedelta(days=1)
    record_str = record_dt.strftime('%Y-%m-%d')
    shares = _shares_before_date(code, record_str)
    return round(amount / shares, 4) if shares > 0 else 0.0
```

- `get_dividends()`改为调用`_compute_per_share()`
- `calc_dividend_yield()`从`db_helper`导入`_compute_per_share`，替换内联计算
- `get_dividends()`返回增加`ex_date`和`source`字段

### 3. 修复TTM窗口悬崖效应

**涉及文件**：`scripts/refresh_quotes.py`、`scripts/db_helper.py`

`calc_dividend_yield()`：窗口锚定从"今天"改为"最近分红日期+5天缓冲"

```python
# 取所有分红中最新的日期作为窗口右边界
valid_divs = [d for d in div_rows if d.get('ex_date')]
if valid_divs:
    latest_ex = max(d['ex_date'] for d in valid_divs)
    cutoff = latest_ex - timedelta(days=365)
else:
    cutoff = today - timedelta(days=365)
```

`get_dividend_yield_series()`同理，对每个K线日期的窗口锚定应用相同逻辑。

### 4. 修复除权日/登记日对齐

**涉及文件**：`scripts/refresh_quotes.py`、`scripts/db_helper.py`

- TTM窗口判定改用`ex_date`字段而非`date`（派息日）
- 股权登记日 = ex_date - 1天（A股规则：登记日为除权日前一个交易日）
- 历史数据无ex_date时回退为date - 3天

### 5. API层增加source元数据

**涉及文件**：`server.py`

- `GET /api/v2/dividends` 返回数据包含`source`字段
- `GET /api/v2/dividend-yield-series` 返回增加：
- `"source": "ttm_calculated"` 顶层标识
- `dividend_events`中每项含`source`字段区分`statement`/`kline_estimated`

### 6. 前端展示标签改造

**涉及文件**：`deliverables/bank-stock-system.html`、`scripts/render_intelligence.js`

各位置改造：

- **持仓表格股息率列**（第390、952行）：`"股息率<sup>TTM</sup>"`表头，数值添加`title`属性tooltip
- **股息率走势标题**（第429-431行）：`"股息率走势（TTM推算）"`，估算数据时追加"⚠基于除权缺口预估"
- **分红明细表**（第407行、955行）：表头改为"对账单实际到账"分组，每股派息列标注"计算值"
- **图表tooltip**（第1275行）：显示格式为`"股息率(TTM推算): X%"` + 来源后缀
- **智能建议面板**（render_intelligence.js 第57、124行）：股息率后追加`<sup>TTM</sup>`小标

### 7. 数据去重保护

**涉及文件**：`scripts/db_helper.py`、`scripts/migrate_to_sqlite.py`

- dividends表添加UNIQUE索引`(code, date, amount)`
- `upsert_positions()`改用事务+`INSERT OR REPLACE`
- `get_dividend_yield_series()`中div_timeline构建时按`(code, date, amount)`去重

## 性能考量

- 所有DB操作复用现有连接模式（`get_db()`），无额外开销
- `_compute_per_share()`使用已有的`_shares_before_date()`，时间复杂度O(1)
- 历史数据回填为一次性UPDATE操作，约O(n)
- 前端仅增加文本标签和title属性，不影响渲染性能

## 向后兼容性

- dividends表新增列有DEFAULT值，旧数据自动兼容
- API返回增加字段，前端使用`|| ''`安全访问，不影响旧逻辑
- 前端图表tooltip使用可选链`?.`访问新增字段

## Agent Extensions

### Skill

- **systematic-debugging**
- 目的：在修复过程中对每个缺陷进行根因验证，确保修复方案正确且不引入新问题
- 预期结果：每个缺陷修复有明确验证断言，通过前后数据对比确认修复效果

- **verification-before-completion**
- 目的：所有代码修改完成后运行现有测试套件，验证股息率计算结果正确且来源标识完整
- 预期结果：tests/目录下相关测试通过，股息率走势数据逻辑正确且来源标识清晰

- **subagent-driven-development**
- 目的：将前端HTML改造和后端Python修复拆分为独立子任务并行执行
- 预期结果：前端和后端修改互不阻塞，高效完成全部改造