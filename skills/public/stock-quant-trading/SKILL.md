---
name: stock-quant-trading
description: A股/港股量化交易分析技能。从 stock-data-crawl 获取多因子筛选结果，计算技术指标，生成买入/卖出信号和组合优化建议。禁止使用 web_search/web_fetch，所有数据必须通过 stock-data-crawl API + Python 脚本获取。适用场景：用户要求股票分析、量化选股、技术分析、买卖信号、持仓建议、行业轮动判断。
allowed-tools:
  - read_file
  - write_file
  - bash
---

# 股票量化交易分析 Skill

## CRITICAL — 读此段后再执行任何操作

- **所有数据通过 `stock-data-crawl` API + Python 脚本获取**，所有分析通过脚本计算
- **正常流程不读取 `.py` 脚本源码** — 直接执行，不需要理解内部逻辑。若脚本返回异常(如 0 结果、非预期错误)可读取脚本确认输入/输出格式
- **只能用 bash 工具依次执行下面的命令**，如果 bash 不可用则告知用户并停止，不要退化为搜索

## Overview

基于多因子 Alpha 模型的量化交易分析流水线。数据层由 stock-data-crawl 提供（全市场多因子筛选 + 博查搜索），本 Skill 负责候选池的深度技术分析、信号生成和组合优化。

## Architecture

```
stock-data-crawl (数据+筛选)            deer-flow Skill (分析+信号)
┌────────────────────────┐           ┌──────────────────────────────────┐
│ POST /api/screener/run │ ──→      │ fetch_data.py                     │
│ POST /api/kline/batch  │ ──→      │ fetch_data.py                     │
│ POST /api/search/web   │ ──→      │ fetch_data.py                     │
└────────────────────────┘           │                                    │
                                     │ indicators.py (MA/MACD/RSI/KDJ)   │
                                     │ alpha_model.py (纯8因子融合+信号)  │
                                     │ portfolio.py (3阶段仓位+风控建议)  │
                                     └────────────────────────────────────┘
```

## Prerequisites

- **stock-data-crawl 服务必须运行中**，API 地址通过 `STOCK_API_BASE_URL` 环境变量配置（在项目 `.env` 文件中设置），脚本会自动读取
- Python 3 需在 sandbox 内可用
## Workflow

### 判断走哪个流程

根据用户意图选择：

| 用户请求示例 | 走哪个流程 |
|-------------|-----------|
| "分析 安井食品 603345"、"600519 怎么样"、"帮我看看宁德时代的技术指标" | **场景 A: 单股分析** |
| "全市场选股"、"A股量化筛选"、"持仓建议"、"哪些股票有买入信号"、"行业轮动" | **场景 B: 全市场选股** |

---

### 场景 A: 单股 / 指定股票分析

> **数据约束**: 所有数据通过下方脚本从 stock-data-crawl API 获取。

当用户指定了一只或多只股票代码/名称时，进行完整的 **行情 + 技术 + 财务 + 研报 + 舆情** 多维度分析。

> **K 线数据排序说明**: stock-data-crawl API 的 `/api/kline/{code}` 和 `/api/kline/batch` 按 `trade_date` **倒序**返回(最新在前)。`indicators.py` 内部已自动反转为正序(最旧在前)再计算，调用方无需额外处理。

#### Step A1: 获取实时行情

```bash
python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
  --action quote \
  --code "600276" \
  --output /mnt/user-data/workspace/quote.json
```

返回字段: `latest_price`, `change_pct`, `change_amount`, `pe_dynamic`, `pe_ttm`, `pb`, `total_market_cap`, `circulating_market_cap`, `volume`, `turnover`, `turnover_rate`, `amplitude`, `open`, `high`, `low`, `prev_close`, `volume_ratio`, `main_net_inflow`, `change_60d`, `change_ytd`, `trade_time`

#### Step A2: 获取财务数据

```bash
python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
  --action finance \
  --code "600276" \
  --output /mnt/user-data/workspace/finance.json
```

返回字段: `report_date`, `report_type`, `eps_basic`, `bps`, `cash_flow_ps`, `total_operate_revenue`, `parent_net_profit`, `deducted_net_profit`, `revenue_yoy`, `net_profit_yoy`, `deducted_profit_yoy`, `roe`, `roa`, `roic`, `net_profit_margin`, `gross_margin`, `current_ratio`, `asset_liability_ratio`, `ocf_to_revenue`, `interest_coverage_ratio`, `fcff_forward`, `eps_yoy`, `roe_yoy`

#### Step A3: 获取研报数据

```bash
python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
  --action report \
  --code "600276" \
  --output /mnt/user-data/workspace/report.json
```

返回近 180 天最多 20 条研报: `title`, `org_name`, `em_rating_name`, `rating_change`, `publisher_date`, `researcher`, `predict_this_year_eps`, `predict_this_year_pe`, `predict_next_year_eps`, `predict_next_year_pe`, `predict_next_two_year_eps`, `predict_next_two_year_pe`

#### Step A4: 获取 K 线数据

```bash
python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
  --action klines \
  --codes "600276" \
  --days 250 \
  --output /mnt/user-data/workspace/klines.json
```

#### Step A5: 计算技术指标

```bash
python /mnt/skills/public/stock-quant-trading/scripts/indicators.py \
  --klines /mnt/user-data/workspace/klines.json \
  --output /mnt/user-data/workspace/indicators.json
```

#### Step A6: 获取新闻舆情

默认启用权威财经网站白名单(东方财富/同花顺/新浪财经/和讯/巨潮/中证/证券时报/财联社/中国证券网) + 正负面双向搜索：

```bash
python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
  --action news \
  --query "恒瑞医药 600276" \
  --output /mnt/user-data/workspace/news.json
```

输出格式：
```json
{
  "positive": [{...}],
  "negative": [{...}],
  "total": N
}
```

如 API Key 未配置导致失败，跳过此步骤，在报告中标注"舆情数据暂缺"。

#### Step A7: 呈现综合分析报告

依次用 `read_file` 读取所有 JSON 结果，按以下 6 个维度在回复中呈现报告：

---

**1. 实时行情**

| 指标 | 数值 |
|------|------|
| 最新价 | XX (涨跌幅 ±XX%) |
| 市盈率 (TTM) / 动态PE | XX / XX |
| 市净率 PB | XX |
| 总市值 / 流通市值 | XX亿 / XX亿 |
| 换手率 / 量比 | XX% / XX |
| 资金流向 (主力净流入) | XX |
| 60日涨跌幅 / 年初至今 | XX% / XX% |

**2. 技术分析**

| 指标 | 数值 | 判断 |
|------|------|------|
| 均线系统 | MA5/MA10/MA20/MA60 | 多头/空头排列 |
| MACD | DIF/DEA/柱 | 金叉/死叉 |
| RSI-14 | XX | 超买/中性/超卖 |
| KDJ | K/D/J | 状态描述 |
| 布林带 | 上/中/下轨 | 价格位置 |

**3. 财务分析**

| 指标 | 数值 | 评价 |
|------|------|------|
| 报告期 | XX | - |
| EPS / BPS | XX / XX | - |
| 营收 / 营收增速 YoY | XX亿 / ±XX% | - |
| 归母净利润 / 增速 YoY | XX亿 / ±XX% | - |
| ROE / ROA / ROIC | XX% / XX% / XX% | - |
| 毛利率 / 净利率 | XX% / XX% | - |
| 资产负债率 | XX% | - |
| 经营现金流 / 营收 | XX | - |
| 自由现金流 (前瞻) | XX | - |

**4. 研报分析**

| 维度 | 内容 |
|------|------|
| 近 180 天研报数 | N 份 |
| 评级分布 | 买入:N 增持:N 中性:N 减持:N |
| 评级变化趋势 | 上调:N 维持:N 下调:N |
| EPS 一致预测 (今/明/后年) | XX / XX / XX |
| 对应 PE (今/明/后年) | XX / XX / XX |
| 主要机构 | XX, XX, XX... |

**5. 舆情分析**

列出近期相关新闻摘要（如有）。舆情数据按正负面分向输出：
- **正面信息**（利好/业绩/研报推荐/突破）：列出`news.json → positive` 中的新闻标题及来源
- **负面信息**（利空/风险/监管/争议）：列出`news.json → negative` 中的新闻标题及来源
- 如无数据标注"舆情数据暂缺"

**6. 综合研判**

融合以上 5 个维度，给出投资价值判断：
- **行情面**: 估值水平(PE/PB 分位)、资金动向
- **技术面**: 趋势方向、关键支撑/压力位
- **财务面**: 盈利能力、成长性、财务健康度
- **研报面**: 分析师共识方向
- **舆情面**: 近期事件催化剂/风险

> **免责声明**: 以上分析基于公开数据，不构成投资建议。股市有风险，投资需谨慎。
> 
> **说明**: 以上为个股绝对估值和技术分析。全市场相对排名（8因子多空信号）可通过"全市场选股"（场景B）入口获得。两种场景口径不同：场景A为绝对值深度研究，场景B为全市场截面排序选股。

---

### 场景 B: 全市场量化选股

> **数据约束**: 所有数据通过下方脚本从 stock-data-crawl API 获取。

#### Step B1: 多因子筛选

调用 stock-data-crawl 获取全市场 Top 50 股票：

```bash
python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
  --action screener \
  --output /mnt/user-data/workspace/screened.json
```

返回 Top 50 股票，包含 alpha 评分、8 因子暴露分(value/growth/quality/momentum/low_vol/sentiment/industry/relative_strength)、所属基准指数(benchmark_code)、风险标签。同时产出 `screened_meta.json` 包含市场状态(regime/regime_details)、基准指数指标(benchmarks)。

#### Step B2: 获取 K 线数据

先用 `read_file` 读取 `/mnt/user-data/workspace/screened.json`，从中提取所有股票的 `code` 字段，用逗号拼接后传入 `--codes`：

```bash
python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
  --action klines \
  --codes "CODE1,CODE2,CODE3,..." \
  --days 250 \
  --output /mnt/user-data/workspace/klines.json
```

#### Step B3: 计算技术指标

```bash
python /mnt/skills/public/stock-quant-trading/scripts/indicators.py \
  --klines /mnt/user-data/workspace/klines.json \
  --output /mnt/user-data/workspace/indicators.json
```

#### Step B4: Alpha 多因子融合

融合 screener 端返回的市场状态动态权重（非等权），生成买卖信号。**技术指标(RSI/MA/MACD/KDJ)不参与多因子 Alpha 模型**，但会在此步骤进行**近期破位后置检测**（因 screener 动量因子跳过最近 20 天），命中破位项 ≥2 则降级信号：

```bash
python /mnt/skills/public/stock-quant-trading/scripts/alpha_model.py \
  --screened /mnt/user-data/workspace/screened.json \
  --indicators /mnt/user-data/workspace/indicators.json \
  --weights /mnt/user-data/workspace/screened_weights.json \
  --output /mnt/user-data/workspace/signals.json
```

#### Step B5: 组合优化

3阶段仓位流水线：阶段一(Alpha加权+波动率调整+风险惩罚)、阶段二(行业≤25%+科技/消费主题≤50%+指数成分上限+相关性惩罚)、阶段三(现金预留+归一化)。风控建议独立输出不参与仓位计算：

```bash
python /mnt/skills/public/stock-quant-trading/scripts/portfolio.py \
  --signals /mnt/user-data/workspace/signals.json \
  --indicators /mnt/user-data/workspace/indicators.json \
  --capital 1000000 \
  --regime $(python -c "import json; print(json.load(open('/mnt/user-data/workspace/screened_meta.json'))['regime'])") \
  --output /mnt/user-data/workspace/portfolio.json
```

如果用户指定了资金量，替换 `--capital` 参数值。`--regime` 从 Step B1 返回的 `screened_meta.json` 中 `regime` 字段获取。

#### Step B6: 在回复中呈现完整报告

> **⚠️ CRITICAL — REPORT INTEGRITY RULE**: 报告本身即为最终交付物。违反以下任一条即视为任务失败。
>
> 1. **禁止用总结/检查清单替代报告** — 不要输出 "✅ 已完成交付物" 表格或 "以上为完整报告" 的概述替代实际报告内容
> 2. **禁止在报告后追加总结消息** — 报告以 `免责声明` 结尾后立即停止，不要追加 "B6 全部完成！" 或类似结语
> 3. **6 个章节必须逐一完整呈现** — 每章必须包含实际数据表格和分析文字，不可跳过或用 "详见上述" 代过
> 4. **详细持仓表必须列出全部股票** — Chapter 4 必须完整列出 portfolio.json 中所有 allocations[]，不可只列前 N 只
> 5. **报告即回复** — 不要写入文件后再提示用户读取，必须在对话回复中直接呈现

##### B6a: 读取数据源

按顺序用 `read_file` 读取以下文件（每个文件都必须读取，不可跳过）：

```bash
read_file /mnt/user-data/workspace/screened_meta.json    # 市场状态、基准指标
read_file /mnt/user-data/workspace/screened_weights.json  # 8因子权重
read_file /mnt/user-data/workspace/signals.json            # 每只股票的因子分、信号、破位标记
read_file /mnt/user-data/workspace/portfolio.json          # 最终持仓、仓位、风险标记
```

##### B6b: 按以下 6 个章节顺序在回复中呈现报告

> **REPORT COMPLETENESS MANDATE**: 以下 6 个章节是强制性模板。每章必须用 B6a 读取到的 JSON 数据真实填充，不得留空或写占位符（如 `[regime]`、`XX`）。数据转换规则见下。

> **格式要求**:
> - 所有表格用 Markdown 表格，数值保留 2 位小数，百分比保留 1 位
> - 关键数值使用 **粗体** 高亮
> - 图表 URL 用 `![描述](URL)` 嵌入（如有生成）
> - 不要引用原始 JSON，必须转换为可读的表格/列表/段落
> - 报告以 `# 📊 全市场量化选股 — 完整报告` 开头

---

**一、市场总览**

从 `screened_meta.json` 提取数据，在回复中列出：

| 维度 | 状态 |
|------|------|
| 市场状态 | [regime] |
| 风格 | [regime_details.style] · [growth_style] |
| 筛选范围 | [screened_count] 只 → Top 50 → 优化为 [stock_count] 只 |

以及各基准指数 60 日表现：

| 指数 | 代码 | 60日涨跌幅 | 60日波动率 |
|------|------|:---------:|:---------:|
| 沪深300 | 000300 | +XX% | XX |
| 科创50 | 000688 | +XX% | XX |
| 中证1000 | 000852 | +XX% | XX |
| 创业板指 | 399006 | +XX% | XX |

---

**二、因子权重配置**

从 `screened_weights.json` 提取权重，降序排列展示：

| 因子 | 权重 | 说明 |
|------|:----:|------|
| 成长 (Growth) | **XX%** | 核心驱动：高营收/利润增速 |
| 动量 (Momentum) | **XX%** | 核心驱动：价格趋势延续 |
| 质量 (Quality) | XX% | 盈利能力和财务健康 |
| 情绪 (Sentiment) | XX% | 市场关注度和资金流向 |
| 行业 (Industry) | XX% | 行业暴露和轮动 |
| 相对强度 (RS) | XX% | 相对基准的超额表现 |
| 价值 (Value) | XX% | 低估值保护 |
| 低波 (Low Vol) | XX% | 波动率控制 |

> **可选增强**: 可调用 chart-visualization 技能生成雷达图展示因子权重分布。方法：
> 1. 加载 `chart-visualization` 技能: `read_file /mnt/skills/public/chart-visualization/SKILL.md`
> 2. 读取参考: `read_file /mnt/skills/public/chart-visualization/references/generate_radar_chart.md`
> 3. 生成: `node /mnt/skills/public/chart-visualization/scripts/generate.js '{"tool":"generate_radar_chart","args":{"data":[{"name":"Growth","value":XX},...],"title":"8因子权重配置","width":600,"height":400}}'`
> 4. 用 `read_file` 确认成功后在回复中用 `![](URL)` 嵌入
> 如果 chart-visualization 不可用，跳过图表，只展示表格。

---

**三、组合配置方案**

从 `portfolio.json` 提取总览数据：

| 指标 | 数值 |
|------|:----:|
| 总资金 | ¥[total_capital] |
| 持仓股票 | **[stock_count] 只** |
| 覆盖行业 | **[sector_count] 个** |
| 总仓位 | **[total_position_pct]%** |
| 闲置资金 | ¥[actual_idle_cash] |

> **仓位构成**: model 预设最低现金保留 X% → Alpha 加权分配 → 波动率调整(vol_adj = 1/(1 + ann_vol × k)) → 风险标签惩罚(高杠杆/PE极端/现金流为负等) → 最终仓位。核心压缩来自 `vol_adj` 因子：以 vol_60d=5%、k=4 为例，年化波动 ~79%，vol_adj ≈ 0.24，即单股仓位被压缩至流程计算的 24%。如果总仓位 < 30%，应在报告中解释原因（市场状态 k 值、个股波动率水平、风险标签触发数量）。

> **可选增强**: 生成以下图表并在回复中嵌入：
> - **行业分布饼图**: 统计 `allocations[].industry` 后传入 chart-visualization
> - **个股仓位条形图**: 提取 `name` + `position_pct`
> - **Alpha评分 vs 波动率散点图**: 提取 `alpha_score` + `vol_60d`
> 
> 方法同上。如果 chart-visualization 不可用，跳过图表，只展示数据表格。

---

**四、组合详细持仓**（核心章节，必须完整展示）

从 `portfolio.json` 的 `allocations[]` 逐只在回复中列出表格，包含：代码、名称、行业、基准、Alpha评分、信号、仓位%、配置金额、vol_60d、风险标记。

> **因子分补充**: 每只股票下方另起一行用小字列出因子分值（从 `signals.json` 中按 code 匹配 `factor_scores`）和破位标记（如有）。格式：`因子: V:XX G:XX Q:XX M:XX LV:XX S:XX I:XX RS:XX | 破位: [列表]`

表格格式：

| # | 代码 | 名称 | 行业 | 基准 | Alpha | 信号 | 仓位% | 配置金额 | 风险标记 |
|:-:|:----:|:----:|:----:|:----:|:-----:|:----:|:-----:|:--------:|:--------:|
| 1 | XXXXXX | XX | XX | XXXX | **XX.XX** | BUY | X.XX% | ¥XX,XXX | 标签 |

展示完所有持股后，再展示**信号为 sell 的股票**（从 `signals.json` 中筛选 `signal == "sell"`），提示用户规避风险。

---

**五、风控参考**

按风险类型汇总 `allocations[].risk_flags`，统计：
- 哪些股票有 PE 极端/异常标记
- 哪些股票有自由现金流为负的财务风险
- 哪些股票有高杠杆风险
- 哪些股票有近期破位风险（从 `signals.json` 的 `breakdown_flags` 字段）
- 总仓位预警：如 < 30% 则说明模型在当前市场状态下偏保守

> 注意: 本阶段仅输出基于风险标记的统计信息，不输出止盈/止损操作建议。止盈/止损属于持仓管理阶段（Phase 2）的规则引擎职责。

---

**六、总结**

融合以上 5 个章节，用 2-3 段文字总结：

- **模型判断**: 当前市场状态下模型的倾向（积极/中性/保守），核心配置主线（行业主题）
- **仓位逻辑**: 为什么当前仓位是这个水平（市场波动、个股风险评分、行业分散度等）
- **核心风险**: 需要关注的系统性风险和个股风险

> 结尾必须附上:
> **免责声明**: 以上分析基于量化模型和公开数据，不构成投资建议。股市有风险，投资需谨慎。

---

##### B6c: 完整性自检（回复前强制验证）

在发送回复前，必须在回复正文中逐项确认以下内容均已呈现，缺一不可：

| # | 检查项 | 必须包含 |
|:-:|--------|----------|
| 1 | 市场总览 | regime、regime_details、screened_count、4 个基准指数表（含实值，非占位符） |
| 2 | 因子权重 | 8 个因子降序排列表（含实值，非占位符） |
| 3 | 组合配置 | total_capital、stock_count、sector_count、total_position_pct、actual_idle_cash |
| 4 | 详细持仓 | **全部** allocations[]（不可只列前 N 只）+ 每只股票因子分 + sell 信号列表 |
| 5 | 风控参考 | PE极端标记统计、自由现金流为负统计、破位标记统计、总仓位预警说明 |
| 6 | 总结 | 2-3 段论述（模型判断、仓位逻辑、核心风险）+ 免责声明 |

> **严禁**: 用 "✅" 或 "已完成" 清单跳过实际报告内容。完整性自检是验证手段，不是报告的替代品。

---

## Output Handling

- 所有中间结果（JSON 文件）保存到 `/mnt/user-data/workspace/`
- 单股分析 → 读取 `indicators.json` + `finance.json` + `report.json`，按场景 A7 的 6 维度模板在回复中呈现报告
- 全市场选股 → 读取 `screened_meta.json` + `screened_weights.json` + `signals.json` + `portfolio.json`，按场景 B6 的 6 章节模板在回复中呈现报告
- 图表生成 → 可选调用 `chart-visualization` 技能，如技能不可用则只展示数据表格
- **不要引用原始 JSON**，必须转换为可读的 Markdown 表格/列表/段落
- 所有数值保留 2 位小数，百分比保留 1 位，金额保留整数（如 ¥14,500）
- **报告不应有尾部总结**：报告以 `免责声明` 结尾即止。禁止在报告后追加 "B6 全部完成"、"✅ 已完成交付物" 等总结消息或交付物清单
- **覆盖所有持股**：详细持仓表必须列出组合中全部股票，禁止只列前 10 只或 "等 N 只" 等缩写

## Error Handling

如果脚本执行失败（API 不可达）：

1. 告知用户 **stock-data-crawl 服务可能未启动**，请检查服务状态
2. **禁止退化为 web_search / web_fetch** — 搜索新闻无法替代结构化量化数据，不要尝试用搜索填补数据缺失
3. 如果单个步骤失败，输出已成功步骤的结果并标注失败步骤，然后停止

### 脚本返回 0 结果或空 JSON

若脚本 bash 退出码为 0 但结果为空(如 `indicators.py` 输出空 `{}`)：

1. 这通常是输入数据格式不匹配导致。`fetch_data.py` 输出是分组格式 `[{code, klines: [...]}]`，确认 klines.json 第一层元素有 `klines` 字段
2. 可读取脚本源码(`indicators.py` 的 `compute_all_indicators` 函数)查看期望格式，对比实际 JSON 排查差异
3. 修复后重新运行失败步骤

### 股票名称为空

若输出中股票名称显示为 `None`：

1. 尝试调用 API 获取名称：
   ```bash
   python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
     --action stocks --market all \
     --output /mnt/user-data/workspace/stock_names.json
   ```
2. 读取 `/mnt/user-data/workspace/stock_names.json`，从 `security_name` 字段查找对应代码的名称
3. 或在最终呈现时代码只输出代码，不显示名称

## Notes

- 脚本间有依赖关系，前一步成功后才能执行下一步
- 数据量大时（全市场 50 只股票 × 250 天 K 线），单次执行可能需要 30-60 秒
- 股票名称会自动从行情数据补全；若仍为空，见 Error Handling → 股票名称为空
- 单股 K 线支持通过 `--days` 参数控制返回天数（默认 250，最快在 500 条以内）

## References

- `references/factor_guide.md`: 8 因子详细定义(value/growth/quality/momentum/low_vol/sentiment/industry/relative_strength)，动量剔除最近1月，硬性剔除规则，行业暴露，因子 IC/IR 参考
