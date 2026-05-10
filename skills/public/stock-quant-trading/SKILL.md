---
name: stock-quant-trading
description: A股/港股量化交易分析技能。自动从 stock-data-crawl 获取多因子筛选结果，计算技术指标，生成买入/卖出信号和组合优化建议。适用场景：用户要求股票分析、量化选股、技术分析、买卖信号、持仓建议、行业轮动判断。
---

# 股票量化交易分析 Skill

## Overview

基于多因子 Alpha 模型的量化交易分析流水线。数据层由 stock-data-crawl 提供（全市场多因子筛选 + 博查搜索），本 Skill 负责候选池的深度技术分析、信号生成和组合优化。

## Architecture

```
stock-data-crawl (数据+筛选)          deer-flow Skill (分析+信号)
┌──────────────────────┐         ┌──────────────────────────┐
│ POST /api/screener/run│ ──→    │ fetch_screened_stocks()     │
│ POST /api/kline/batch │ ──→    │ fetch_klines_batch()       │
│ POST /api/search/web  │ ──→    │ fetch_news()              │
└──────────────────────┘         │                            │
                                 │ indicators.py (MA/MACD/RSI) │
                                 │ alpha_model.py (融合/市场状态) │
                                 │ portfolio.py (仓位/分散)    │
                                 └────────────────────────────┘
```

## Workflow

### Step 1: Get Screened Candidates

Call stock-data-crawl's screener API to get the top-ranked stocks:

```bash
STOCK_API_BASE_URL=http://localhost:8000/api
python scripts/fetch_data.py --action screener --api-base $STOCK_API_BASE_URL
```

Returns top 50 stocks with alpha scores, factor exposures, and risk flags.

### Step 2: Fetch K-line Data

```bash
python scripts/fetch_data.py --action klines --codes "000001,600519,300750" --days 250
```

### Step 3: Calculate Technical Indicators

```bash
python scripts/indicators.py --klines data/klines.json --output data/indicators.json
```

### Step 4: Run Alpha Model (Multi-Factor Fusion)

```bash
python scripts/alpha_model.py --screened data/screened.json --indicators data/indicators.json --output data/signals.json
```

### Step 5: Portfolio Optimization

```bash
python scripts/portfolio.py --signals data/signals.json --capital 1000000 --output data/portfolio.json
```

### Step 6: Present Results

Output format for each stock:
```
[代码] [名称] | Alpha: XX | 信号: BUY/SELL | 建议仓位: X%
因子: V:XX G:XX Q:XX M:XX LV:XX S:XX I:XX
风险: [标签列表]

组合层面:
- 持仓股票数: N
- 行业分散度: N个行业
- 预期最大回撤: X%
```

## Expected Output Structure

For each stock in the portfolio:
- **Alpha Score** (0-100): Multi-factor composite
- **Signal**: strong_buy / buy / hold / sell / strong_sell
- **Confidence**: 0-100%
- **Position Size**: Percentage of capital
- **Factor Radar**: 8-factor exposure breakdown
- **Risk Flags**: Valuation risk, liquidity risk, etc.

## References

- `references/factor_guide.md`: 8因子详细定义、行业暴露、因子IC/IR参考
