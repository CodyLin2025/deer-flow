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

- **严禁使用 `web_search` / `web_fetch` 获取任何数据** — 搜索引擎结果无法替代结构化量化数据
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
- **Python 依赖**: `numpy` 必须可用。在每个 scenario 的 Step 1 中用以下命令验证：

```bash
python -c "import numpy; print('numpy ok')"
```

## Workflow

### 判断走哪个流程

根据用户意图选择：

| 用户请求示例 | 走哪个流程 |
|-------------|-----------|
| "分析 安井食品 603345"、"600519 怎么样"、"帮我看看宁德时代的技术指标" | **场景 A: 单股分析** |
| "全市场选股"、"A股量化筛选"、"持仓建议"、"哪些股票有买入信号"、"行业轮动" | **场景 B: 全市场选股** |

---

### 场景 A: 单股 / 指定股票分析

> **数据约束**: 所有数据通过下方脚本从 stock-data-crawl API 获取。本场景全程不允许使用 web_search 或 web_fetch。

当用户指定了一只或多只股票代码/名称时，进行完整的 **行情 + 技术 + 财务 + 研报 + 舆情** 多维度分析。

> **K 线数据排序说明**: stock-data-crawl API 的 `/api/kline/{code}` 和 `/api/kline/batch` 按 `trade_date` **倒序**返回(最新在前)。`indicators.py` 内部已自动反转为正序(最旧在前)再计算，调用方无需额外处理。

#### Step A1: 验证环境

先确认 bash 工具、Python、numpy 依赖可正常使用（不要使用 web_search/web_fetch）：

```bash
echo "bash tool ready"
python -c "import numpy; print('numpy ok')"
```

如果任何命令执行失败：
- bash 失败 → 告知用户 **"bash 工具不可用，无法执行量化分析"**，然后停止
- numpy 失败 → 告知用户 **"numpy 未安装，请运行 pip install numpy"**，然后停止

#### Step A2: 获取实时行情

```bash
python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
  --action quote \
  --code "600276" \
  --output /mnt/user-data/workspace/quote.json
```

返回字段: `latest_price`, `change_pct`, `change_amount`, `pe_dynamic`, `pe_ttm`, `pb`, `total_market_cap`, `circulating_market_cap`, `volume`, `turnover`, `turnover_rate`, `amplitude`, `open`, `high`, `low`, `prev_close`, `volume_ratio`, `main_net_inflow`, `change_60d`, `change_ytd`, `trade_time`

#### Step A3: 获取财务数据

```bash
python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
  --action finance \
  --code "600276" \
  --output /mnt/user-data/workspace/finance.json
```

返回字段: `report_date`, `report_type`, `eps_basic`, `bps`, `cash_flow_ps`, `total_operate_revenue`, `parent_net_profit`, `deducted_net_profit`, `revenue_yoy`, `net_profit_yoy`, `deducted_profit_yoy`, `roe`, `roa`, `roic`, `net_profit_margin`, `gross_margin`, `current_ratio`, `asset_liability_ratio`, `ocf_to_revenue`, `interest_coverage_ratio`, `fcff_forward`, `eps_yoy`, `roe_yoy`

#### Step A4: 获取研报数据

```bash
python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
  --action report \
  --code "600276" \
  --output /mnt/user-data/workspace/report.json
```

返回近 180 天最多 20 条研报: `title`, `org_name`, `em_rating_name`, `rating_change`, `publisher_date`, `researcher`, `predict_this_year_eps`, `predict_this_year_pe`, `predict_next_year_eps`, `predict_next_year_pe`, `predict_next_two_year_eps`, `predict_next_two_year_pe`

#### Step A5: 获取 K 线数据

```bash
python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
  --action klines \
  --codes "600276" \
  --days 250 \
  --output /mnt/user-data/workspace/klines.json
```

#### Step A6: 计算技术指标

```bash
python /mnt/skills/public/stock-quant-trading/scripts/indicators.py \
  --klines /mnt/user-data/workspace/klines.json \
  --output /mnt/user-data/workspace/indicators.json
```

#### Step A7: 获取新闻舆情

```bash
python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
  --action news \
  --query "恒瑞医药 600276 最新消息" \
  --output /mnt/user-data/workspace/news.json
```

如 API Key 未配置导致失败，跳过此步骤，在报告中标注"舆情数据暂缺"。

#### Step A8: 呈现综合分析报告

依次用 `read_file` 读取所有 JSON 结果，按以下 6 个维度输出综合报告：

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

列出近期相关新闻摘要（如有），标注正/中/负面倾向。

**6. 综合研判**

融合以上 5 个维度，给出投资价值判断：
- **行情面**: 估值水平(PE/PB 分位)、资金动向
- **技术面**: 趋势方向、关键支撑/压力位
- **财务面**: 盈利能力、成长性、财务健康度
- **研报面**: 分析师共识方向
- **舆情面**: 近期事件催化剂/风险

> **免责声明**: 以上分析基于公开数据，不构成投资建议。股市有风险，投资需谨慎。

---

### 场景 B: 全市场量化选股

> **数据约束**: 所有数据通过下方脚本从 stock-data-crawl API 获取。本场景全程不允许使用 web_search 或 web_fetch。

#### Step B1: 验证环境

先确认 bash 工具、Python、numpy 依赖可正常使用（不要使用 web_search/web_fetch）：

```bash
echo "bash tool ready"
python -c "import numpy; print('numpy ok')"
```

如果任何命令执行失败：
- bash 失败 → 告知用户 **"bash 工具不可用，无法执行量化分析"**，然后停止
- numpy 失败 → 告知用户 **"numpy 未安装，请运行 pip install numpy"**，然后停止

#### Step B2: 多因子筛选

调用 stock-data-crawl 获取全市场 Top 50 股票：

```bash
python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
  --action screener \
  --output /mnt/user-data/workspace/screened.json
```

返回 Top 50 股票，包含 alpha 评分、8 因子暴露分(value/growth/quality/momentum/low_vol/sentiment/industry/relative_strength)、所属基准指数(benchmark_code)、风险标签、市场状态(regime/regime_details)、基准指数指标(benchmarks)。

#### Step B3: 获取 K 线数据

先用 `read_file` 读取 `/mnt/user-data/workspace/screened.json`，从中提取所有股票的 `code` 字段，用逗号拼接后传入 `--codes`：

```bash
python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
  --action klines \
  --codes "CODE1,CODE2,CODE3,..." \
  --days 250 \
  --output /mnt/user-data/workspace/klines.json
```

#### Step B4: 计算技术指标

```bash
python /mnt/skills/public/stock-quant-trading/scripts/indicators.py \
  --klines /mnt/user-data/workspace/klines.json \
  --output /mnt/user-data/workspace/indicators.json
```

#### Step B5: Alpha 多因子融合

融合 8 因子（value/growth/quality/momentum/low_vol/sentiment/industry/relative_strength，各 12.5% 等权），生成买卖信号。**技术指标(RSI/MA/MACD/KDJ)不参与多因子 Alpha 模型**，技术分析仅在单股分析场景(A6)中独立使用：

```bash
python /mnt/skills/public/stock-quant-trading/scripts/alpha_model.py \
  --screened /mnt/user-data/workspace/screened.json \
  --indicators /mnt/user-data/workspace/indicators.json \
  --output /mnt/user-data/workspace/signals.json
```

#### Step B6: 组合优化

3阶段仓位流水线：阶段一(Alpha加权+波动率调整+风险惩罚)、阶段二(行业≤25%+科技/消费主题≤50%+指数成分上限+相关性惩罚)、阶段三(现金预留+归一化)。风控建议独立输出不参与仓位计算：

```bash
python /mnt/skills/public/stock-quant-trading/scripts/portfolio.py \
  --signals /mnt/user-data/workspace/signals.json \
  --capital 1000000 \
  --regime "震荡市" \
  --output /mnt/user-data/workspace/portfolio.json
```

如果用户指定了资金量，替换 `--capital` 参数值。`--regime` 从 Step B2 返回的 `regime` 字段获取。

#### Step B7: 呈现结果

用 `read_file` 读取 `/mnt/user-data/workspace/portfolio.json`，按以下格式输出：

```
市场状态: [regime] — [regime_details.style]
现金预留: [cash_reserve_pct]%

[代码] [名称] | 行业: [industry] | 基准: [benchmark] | Alpha: XX | 信号: BUY/SELL | 仓位: X%
因子: V:XX G:XX Q:XX M:XX LV:XX S:XX I:XX RS:XX
风险: [标签列表]

组合层面:
- 持仓股票数: N
- 行业分散度: N个行业
- 总仓位: X%
- 风控参考: 见 risk_advisory 字段
```

## Output Handling

- 所有中间结果输出到 `/mnt/user-data/workspace/`
- 单股分析 → 读取 `indicators.json`，格式化技术指标
- 全市场选股 → 读取 `portfolio.json`，列出持仓建议
- 用 `read_file` 读取 JSON 结果，以表格/结构化文本呈现

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
