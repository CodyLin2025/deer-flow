---
name: stock-quant-trading
description: A股/港股量化交易分析技能。从 stock-data-crawl 获取多因子筛选结果，计算技术指标，生成买入/卖出信号和组合优化建议。适用场景：用户要求股票分析、量化选股、技术分析、买卖信号、持仓建议、行业轮动判断。
---

# 股票量化交易分析 Skill

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
                                     │ alpha_model.py (多因子融合+信号)   │
                                     │ portfolio.py (仓位/分散)          │
                                     └────────────────────────────────────┘
```

## Prerequisites

- **stock-data-crawl 服务必须运行中**，API 地址通过 `STOCK_API_BASE_URL` 环境变量配置（在项目 `.env` 文件中设置），脚本会自动读取
- Python 3 需在 sandbox 内可用

## Workflow

**IMPORTANT: Do NOT read the Python scripts. Do NOT use web_fetch or web_search to call the API. Just execute the commands below with the bash tool in order.**

### Step 1: Get Screened Candidates

调用 stock-data-crawl 的多因子筛选 API，获取全市场 Top 50 股票：

```bash
python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
  --action screener \
  --output /mnt/user-data/workspace/screened.json
```

返回 Top 50 股票，包含 alpha 评分、8 因子暴露分、风险标签。

### Step 2: Fetch K-line Data

先用 `read_file` 读取 `/mnt/user-data/workspace/screened.json`，从中提取所有股票的 `code` 字段，用逗号拼接后传入 `--codes` 参数：

```bash
python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
  --action klines \
  --codes "CODE1,CODE2,CODE3,..." \
  --days 250 \
  --output /mnt/user-data/workspace/klines.json
```

### Step 3: Calculate Technical Indicators

计算 MA(5/10/20/60)、MACD、RSI(14)、KDJ、布林带、ATR 等技术指标：

```bash
python /mnt/skills/public/stock-quant-trading/scripts/indicators.py \
  --klines /mnt/user-data/workspace/klines.json \
  --output /mnt/user-data/workspace/indicators.json
```

### Step 4: Run Alpha Model (Multi-Factor Fusion)

融合基本面因子（V/G/Q/M/LV/S/I 共 8 因子，各 12.5%）与技术指标调整（MACD/RSI/KDJ，占 10%），生成最终信号：

```bash
python /mnt/skills/public/stock-quant-trading/scripts/alpha_model.py \
  --screened /mnt/user-data/workspace/screened.json \
  --indicators /mnt/user-data/workspace/indicators.json \
  --output /mnt/user-data/workspace/signals.json
```

### Step 5: Portfolio Optimization

行业分散约束（单行业 ≤ 30%）、风险标签约束、仓位归一化：

```bash
python /mnt/skills/public/stock-quant-trading/scripts/portfolio.py \
  --signals /mnt/user-data/workspace/signals.json \
  --capital 1000000 \
  --output /mnt/user-data/workspace/portfolio.json
```

如果用户指定了资金量，替换 `--capital` 参数值。

### Step 6: Present Results

用 `read_file` 读取 `/mnt/user-data/workspace/portfolio.json`，按以下格式输出给用户：

```
[代码] [名称] | Alpha: XX | 信号: BUY/SELL | 建议仓位: X%
因子: V:XX G:XX Q:XX M:XX LV:XX S:XX I:XX
风险: [标签列表]

组合层面:
- 持仓股票数: N
- 行业分散度: N个行业
- 预期最大回撤: X%
```

## Output Handling

- 所有中间结果输出到 `/mnt/user-data/workspace/`
- 最终组合建议输出到 `/mnt/user-data/workspace/portfolio.json`
- 用 `read_file` 读取 portfolio.json，直接格式化呈现给用户
- 以表格形式列出每只股票的 Alpha 评分、信号、仓位比例

## Error Handling

如果 Step 1 的 `fetch_data.py` 执行失败（API 不可达）：

1. 告知用户 **stock-data-crawl 服务可能未启动**，请检查服务状态
2. 建议执行：`curl $STOCK_API_BASE_URL/screener/result` 验证连通性
3. **不要退化为 web_search / web_fetch** 去搜索新闻替代 — 这无法替代量化筛选数据

## Notes

- 脚本间有严格依赖关系，**必须按 Step 1 → 6 顺序执行**，前一步成功后才能执行下一步
- 不要读取 `.py` 脚本源码，直接用上述命令执行
- 数据量大时（全市场 50 只股票 × 250 天 K 线），单次执行可能需要 30-60 秒
- 如果用户只要求分析特定股票，可以跳过 Step 1，直接从 Step 2 开始传入指定 codes

## References

- `references/factor_guide.md`: 8 因子详细定义、行业暴露、因子 IC/IR 参考
