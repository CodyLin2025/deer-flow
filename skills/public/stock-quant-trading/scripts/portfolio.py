#!/usr/bin/env python3
"""
Portfolio Optimizer (3-phase pipeline)

Phase 1: Position initialization (alpha-weighted, volatility-adjusted, risk-capped)
Phase 2: Diversification constraints (sector, theme, index, correlation)
Phase 3: Final adjustment (cash reserve, normalization)

Usage:
    python portfolio.py --signals data/signals.json --capital 1000000 --output data/portfolio.json
"""

import argparse
import json
import math


TECH_THEME = {"电子", "计算机", "通信", "军工", "传媒"}
CONSUME_THEME = {"食品饮料", "家用电器", "汽车", "商贸零售", "社会服务"}


def _vol_k_for_regime(regime: str) -> float:
    if regime in ("趋势上涨",):
        return 3.0
    elif regime in ("趋势下跌", "高波动",):
        return 5.0
    else:
        return 4.0


def phase1_init_positions(signals: list[dict], cash_pct: float, regime: str) -> list[dict]:
    k = _vol_k_for_regime(regime)

    buy_signals = [s for s in signals if s["signal"] in ("strong_buy", "buy")]
    hold_signals = [s for s in signals if s["signal"] == "hold"]
    candidates = buy_signals + hold_signals
    if len(candidates) > 20:
        candidates = candidates[:20]

    total_alpha = sum(s["alpha_score"] for s in candidates)
    if total_alpha == 0:
        total_alpha = len(candidates)

    positions = []
    for s in candidates:
        weight = s["alpha_score"] / total_alpha
        raw_pos = weight * (1.0 - cash_pct)
        raw_pos = max(0.02, min(0.20, raw_pos))

        vol_60d = s.get("vol_60d")
        if vol_60d is not None and vol_60d > 0:
            vol_adj = 1.0 / (1.0 + vol_60d * k)
        else:
            vol_adj = 1.0
        pos = raw_pos * vol_adj

        risk_flags = s.get("risk_flags", [])
        market_cap = s.get("total_market_cap", 0) or 0

        if "高杠杆" in risk_flags:
            pos = min(pos, 0.05)
        if "经营现金流为负" in risk_flags and "自由现金流为负" in risk_flags:
            pos = max(0.01, pos * 0.5)
        if "PE极端高" in risk_flags:
            pos = max(0.02, pos * 0.7)
        if "小市值风险" in risk_flags:
            pos = min(pos, 0.03)
        if "上市不足1年" in risk_flags:
            pos = min(pos, 0.03)

        positions.append({
            **s,
            "position": round(pos, 4),
        })

    return positions


def phase2_diversify(positions: list[dict]) -> list[dict]:
    result = list(positions)

    sector_totals: dict[str, float] = {}
    for p in result:
        ind = p.get("industry", "其他") or "其他"
        sector_totals[ind] = sector_totals.get(ind, 0) + p["position"]

    for p in result:
        ind = p.get("industry", "其他") or "其他"
        over = sector_totals.get(ind, 0) - 0.25
        if over > 0:
            scale = min(1.0, 0.25 / sector_totals[ind])
            p["position"] = round(p["position"] * scale, 4)

    theme_totals: dict[str, float] = {"tech": 0, "consume": 0}
    for p in result:
        ind = p.get("industry", "其他") or "其他"
        if ind in TECH_THEME:
            theme_totals["tech"] += p["position"]
        if ind in CONSUME_THEME:
            theme_totals["consume"] += p["position"]

    for theme, limit in [("tech", 0.50), ("consume", 0.50)]:
        total = theme_totals[theme]
        if total > limit:
            scale = limit / total
            for p in result:
                ind = p.get("industry", "其他") or "其他"
                if (theme == "tech" and ind in TECH_THEME) or (theme == "consume" and ind in CONSUME_THEME):
                    p["position"] = round(p["position"] * scale, 4)

    benchmark_totals: dict[str, float] = {}
    index_limits = {"000300": 0.40, "000852": 0.40, "399006": 0.30, "000688": 0.25}
    for p in result:
        bm = p.get("benchmark", "") or "000852"
        benchmark_totals[bm] = benchmark_totals.get(bm, 0) + p["position"]

    for bm, total in benchmark_totals.items():
        limit = index_limits.get(bm, 0.40)
        if total > limit:
            scale = limit / total
            for p in result:
                if (p.get("benchmark", "") or "000852") == bm:
                    p["position"] = round(p["position"] * scale, 4)

    sector_benchmark: dict[tuple, list] = {}
    for i, p in enumerate(result):
        key = (p.get("industry", "其他") or "其他", p.get("benchmark", "") or "000852")
        if key not in sector_benchmark:
            sector_benchmark[key] = []
        sector_benchmark[key].append(i)

    for indices in sector_benchmark.values():
        if len(indices) > 2:
            for idx in indices[2:]:
                result[idx]["position"] = round(result[idx]["position"] * 0.7, 4)

    return result


def phase3_finalize(positions: list[dict], capital: float, cash_pct: float) -> dict:
    total_pos = sum(p["position"] for p in positions)
    if total_pos > 1.0:
        scale = 1.0 / total_pos
        for p in positions:
            p["position"] = round(p["position"] * scale, 4)
    elif total_pos < 0.30:
        if total_pos > 0:
            scale = 0.30 / total_pos
            for p in positions:
                p["position"] = round(p["position"] * scale, 4)

    stock_count = len(positions)
    if stock_count < 5:
        for p in positions:
            p["position"] = min(0.25, p["position"])

    allocation = []
    for p in positions:
        alloc = p["position"] * capital
        allocation.append({
            "code": p["code"],
            "name": p["name"],
            "market": p["market"],
            "industry": p.get("industry", ""),
            "benchmark": p.get("benchmark", ""),
            "alpha_score": p["alpha_score"],
            "signal": p["signal"],
            "position_pct": round(p["position"] * 100, 2),
            "capital_allocation": round(alloc, 2),
            "vol_60d": p.get("vol_60d"),
            "risk_flags": p.get("risk_flags", []),
        })

    sectors = set(a["industry"] for a in allocation if a["industry"])
    return {
        "total_capital": capital,
        "cash_reserve": round(capital * cash_pct, 2),
        "cash_reserve_pct": round(cash_pct * 100, 1),
        "stock_count": len(allocation),
        "sector_count": len(sectors),
        "total_position_pct": round(sum(a["position_pct"] for a in allocation), 2),
        "allocations": allocation,
    }


def compute_risk_advisory(allocations: list[dict], indicators: dict, total_capital: float) -> dict:
    advisory: dict = {
        "note": "以下建议仅供参考，不参与仓位计算，请独立判断",
        "portfolio_level": None,
        "per_stock": {},
    }

    for a in allocations:
        code = a["code"]
        ind = indicators.get(code, {})
        latest = ind.get("latest", {}) if isinstance(ind, dict) else {}
        close = latest.get("close")
        high_60d = latest.get("high_60d")
        low_60d = latest.get("low_60d")

        stock_adv = {}
        if close and high_60d and high_60d > 0:
            drawdown = (close - high_60d) / high_60d * 100
            if drawdown < -15:
                stock_adv["stop_loss"] = f"距60日高点回落{abs(drawdown):.1f}%, 参考减仓50%"

        if close and low_60d and low_60d > 0:
            gain = (close - low_60d) / low_60d * 100
            if gain > 30:
                stock_adv["take_profit"] = f"60日涨幅{gain:.1f}%, 参考止盈至70%仓位"

        advisory["per_stock"][code] = stock_adv if stock_adv else {}

    return advisory


def generate_portfolio(signals: list[dict], capital: float, regime: str = "默认") -> dict:
    cash_map = {"趋势上涨": 0.10, "震荡市": 0.20, "趋势下跌": 0.40, "高波动": 0.30}
    cash_pct = cash_map.get(regime, 0.20)

    positions = phase1_init_positions(signals, cash_pct, regime)
    positions = phase2_diversify(positions)
    portfolio = phase3_finalize(positions, capital, cash_pct)

    return portfolio


def main():
    parser = argparse.ArgumentParser(description="Portfolio Optimizer")
    parser.add_argument("--signals", required=True, help="Signals JSON")
    parser.add_argument("--indicators", required=False, default=None, help="Indicators JSON (for advisory)")
    parser.add_argument("--capital", type=float, default=1000000, help="Capital amount")
    parser.add_argument("--regime", type=str, default="默认", help="Market regime label")
    parser.add_argument("--output", required=True, help="Output portfolio JSON")
    args = parser.parse_args()

    with open(args.signals) as f:
        signals = json.load(f)

    indicators = {}
    if args.indicators:
        try:
            with open(args.indicators) as f:
                indicators = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    portfolio = generate_portfolio(signals, args.capital, args.regime)

    advisory = compute_risk_advisory(portfolio["allocations"], indicators, args.capital)
    portfolio["risk_advisory"] = advisory

    with open(args.output, "w") as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=2)

    print(f"Portfolio: {portfolio['stock_count']} stocks, {portfolio['sector_count']} sectors, "
          f"total position {portfolio['total_position_pct']}% → {args.output}")


if __name__ == "__main__":
    main()
