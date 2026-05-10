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
- **严禁读取 `.py` 脚本源码** — 直接执行，不需要理解内部逻辑
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
                                     │ alpha_model.py (多因子融合+信号)   │
                                     │ portfolio.py (仓位/分散)          │
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

> **数据约束**: 所有数据通过下方脚本从 stock-data-crawl API 获取。本场景全程不允许使用 web_search 或 web_fetch。

当用户指定了一只或多只股票代码/名称时，跳过全市场筛选，直接拉 K 线做技术分析。

#### Step A1: 验证 bash 工具

先确认 bash 工具可用（这是唯一可用的数据获取方式，不要使用 web_search/web_fetch）：

```bash
echo "bash tool ready"
```

如果此命令执行失败，告知用户 **"bash 工具不可用，无法执行量化分析"**，然后停止。

#### Step A2: 获取 K 线数据

将用户提供的股票代码（如 `603345`）直接传入 `--codes` 参数：

```bash
python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
  --action klines \
  --codes "股票代码1,股票代码2,..." \
  --days 250 \
  --output /mnt/user-data/workspace/klines.json
```

#### Step A3: 计算技术指标

```bash
python /mnt/skills/public/stock-quant-trading/scripts/indicators.py \
  --klines /mnt/user-data/workspace/klines.json \
  --output /mnt/user-data/workspace/indicators.json
```

#### Step A4: 呈现技术分析结果

用 `read_file` 读取 `/mnt/user-data/workspace/indicators.json`，按以下格式输出：

```
股票: [代码] [名称]
───────────────────────────────────
最新价: XX | MA5: XX | MA20: XX | MA60: XX
MACD: DIF=XX DEA=XX 柱=XX (金叉/死叉)
RSI-14: XX (超买/中性/超卖)
KDJ: K=XX D=XX J=XX
布林带: 上轨=XX 中轨=XX 下轨=XX

技术面判断:
- 均线: 多头/空头排列
- MACD: 金叉/死叉/粘合
- RSI: 超买/超卖/中性
- 布林带: 价格在通道上/中/下轨
```

---

### 场景 B: 全市场量化选股

> **数据约束**: 所有数据通过下方脚本从 stock-data-crawl API 获取。本场景全程不允许使用 web_search 或 web_fetch。

#### Step B1: 验证 bash 工具

先确认 bash 工具可用（这是唯一可用的数据获取方式，不要使用 web_search/web_fetch）：

```bash
echo "bash tool ready"
```

#### Step B2: 多因子筛选

调用 stock-data-crawl 获取全市场 Top 50 股票：

```bash
python /mnt/skills/public/stock-quant-trading/scripts/fetch_data.py \
  --action screener \
  --output /mnt/user-data/workspace/screened.json
```

返回 Top 50 股票，包含 alpha 评分、8 因子暴露分、风险标签。

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

融合基本面因子（V/G/Q/M/LV/S/I 共 8 因子，各 12.5%）与技术指标调整（MACD/RSI/KDJ，占 10%），生成买卖信号：

```bash
python /mnt/skills/public/stock-quant-trading/scripts/alpha_model.py \
  --screened /mnt/user-data/workspace/screened.json \
  --indicators /mnt/user-data/workspace/indicators.json \
  --output /mnt/user-data/workspace/signals.json
```

#### Step B6: 组合优化

行业分散约束（单行业 ≤ 30%）、风险标签约束、仓位归一化：

```bash
python /mnt/skills/public/stock-quant-trading/scripts/portfolio.py \
  --signals /mnt/user-data/workspace/signals.json \
  --capital 1000000 \
  --output /mnt/user-data/workspace/portfolio.json
```

如果用户指定了资金量，替换 `--capital` 参数值。

#### Step B7: 呈现结果

用 `read_file` 读取 `/mnt/user-data/workspace/portfolio.json`，按以下格式输出：

```
[代码] [名称] | Alpha: XX | 信号: BUY/SELL | 建议仓位: X%
因子: V:XX G:XX Q:XX M:XX LV:XX S:XX I:XX
风险: [标签列表]

组合层面:
- 持仓股票数: N
- 行业分散度: N个行业
- 总仓位: X%
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

## Notes

- 脚本间有依赖关系，前一步成功后才能执行下一步
- 数据量大时（全市场 50 只股票 × 250 天 K 线），单次执行可能需要 30-60 秒

## References

- `references/factor_guide.md`: 8 因子详细定义、行业暴露、因子 IC/IR 参考
