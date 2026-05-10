#!/usr/bin/env python3
"""
Portfolio Optimizer

Usage:
    python portfolio.py --signals data/signals.json --capital 1000000 --output data/portfolio.json
"""

import argparse
import json
import math


def calc_position_size(alpha: float, volatility: float | None, max_single: float = 0.20) -> float:
    base = alpha / 200
    if volatility and volatility > 0:
        base = base / (volatility * 10)

    return min(max_single, max(0.02, base))


def diversify_sectors(
    selected: list[dict],
    max_per_sector: float = 0.30,
) -> list[dict]:
    sectors: dict[str, list[dict]] = {}
    for s in selected:
        ind = s.get("industry", "其他")
        if ind not in sectors:
            sectors[ind] = []
        sectors[ind].append(s)

    result = []
    sector_allocated: dict[str, float] = {}
    for s in selected:
        ind = s.get("industry", "其他")
        current = sector_allocated.get(ind, 0)
        pos = s.get("position", 0.05)
        if current + pos > max_per_sector:
            pos = max(0.02, max_per_sector - current)
            s = dict(s, position=round(pos, 4))
        sector_allocated[ind] = current + pos
        result.append(s)

    return result


def apply_risk_constraints(positions: list[dict], max_drawdown_limit: float = 0.15) -> list[dict]:
    result = []
    for p in positions:
        risk_flags = p.get("risk_flags", [])
        pos = p.get("position", 0.05)

        if "高杠杆" in risk_flags:
            pos = min(pos, 0.05)
        if "经营现金流为负" in risk_flags and "自由现金流为负" in risk_flags:
            pos = max(0.01, pos * 0.5)
        if "PE极端高" in risk_flags:
            pos = max(0.02, pos * 0.7)

        pos = min(pos, max_drawdown_limit)
        result.append(dict(p, position=round(pos, 4)))
    return result


def generate_portfolio(signals: list[dict], capital: float) -> dict:
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
        pos = calc_position_size(s["alpha_score"], None)
        positions.append(dict(s, position=round(pos, 4)))

    positions = diversify_sectors(positions)
    positions = apply_risk_constraints(positions)

    total_position = sum(p["position"] for p in positions)
    if total_position > 1.0:
        scale = 1.0 / total_position
        for p in positions:
            p["position"] = round(p["position"] * scale, 4)
    elif total_position < 0.3:
        for p in positions:
            p["position"] = round(p["position"] * 0.3 / total_position, 4)

    allocation = []
    for p in positions:
        alloc = p["position"] * capital
        allocation.append({
            "code": p["code"],
            "name": p["name"],
            "market": p["market"],
            "industry": p.get("industry", ""),
            "alpha_score": p["alpha_score"],
            "signal": p["signal"],
            "position_pct": round(p["position"] * 100, 2),
            "capital_allocation": round(alloc, 2),
            "risk_flags": p.get("risk_flags", []),
        })

    sectors = set(a["industry"] for a in allocation if a["industry"])
    return {
        "total_capital": capital,
        "stock_count": len(allocation),
        "sector_count": len(sectors),
        "total_position_pct": round(sum(a["position_pct"] for a in allocation), 2),
        "allocations": allocation,
    }


def main():
    parser = argparse.ArgumentParser(description="Portfolio Optimizer")
    parser.add_argument("--signals", required=True, help="Signals JSON")
    parser.add_argument("--capital", type=float, default=1000000, help="Capital amount")
    parser.add_argument("--output", required=True, help="Output portfolio JSON")
    args = parser.parse_args()

    with open(args.signals) as f:
        signals = json.load(f)

    portfolio = generate_portfolio(signals, args.capital)

    with open(args.output, "w") as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=2)

    print(f"Portfolio: {portfolio['stock_count']} stocks, {portfolio['sector_count']} sectors, "
          f"total position {portfolio['total_position_pct']}% → {args.output}")


if __name__ == "__main__":
    main()
