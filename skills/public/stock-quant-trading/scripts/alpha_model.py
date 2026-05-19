#!/usr/bin/env python3
"""
Multi-Factor Alpha Model (deer-flow端)

Fuses screener factor scores with risk flag adjustments
to produce final alpha scores and buy/sell signals.
Technical indicators are NOT part of the alpha model —
they are used independently in single-stock analysis (Scenario A).

Usage:
    python alpha_model.py --screened data/screened.json --indicators data/indicators.json --output data/signals.json
"""

import argparse
import json
from enum import Enum


class SignalStrength(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


SIGNAL_THRESHOLDS = {
    "strong_buy": 80,
    "buy": 65,
    "hold": 35,
    "sell": 20,
}


def determine_signal(alpha_score: float, factor_dispersion: float) -> tuple[str, float]:
    if alpha_score >= 80:
        signal = "strong_buy"
    elif alpha_score >= 65:
        signal = "buy"
    elif alpha_score >= 35:
        signal = "hold"
    elif alpha_score >= 20:
        signal = "sell"
    else:
        signal = "strong_sell"

    confidence = min(100, max(0, 100 - factor_dispersion * 2))
    return signal, confidence


def calc_factor_dispersion(factor_scores: dict[str, float]) -> float:
    if not factor_scores:
        return 0
    vals = list(factor_scores.values())
    mean = sum(vals) / len(vals)
    variance = sum((v - mean) ** 2 for v in vals) / len(vals)
    return variance ** 0.5


class AlphaModel:
    DEFAULT_WEIGHTS = {
        "value": 0.125,
        "growth": 0.125,
        "quality": 0.125,
        "momentum": 0.125,
        "low_vol": 0.125,
        "sentiment": 0.125,
        "industry": 0.125,
        "relative_strength": 0.125,
    }

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or self.DEFAULT_WEIGHTS

    def compute(self, screened: dict, indicators: dict[str, dict]) -> dict:
        factor_scores = screened.get("factor_scores", {})
        code = screened.get("code", "")

        factor_sum = sum(
            self.weights.get(k, 0.125) * v
            for k, v in factor_scores.items()
        )

        final_alpha = max(0, min(100, factor_sum))

        dispersion = calc_factor_dispersion(factor_scores)
        signal, confidence = determine_signal(final_alpha, dispersion)

        risk_flags = screened.get("risk_flags", [])
        if "PE极端高" in risk_flags or "经营现金流为负" in risk_flags:
            if signal == "buy":
                signal = "hold"
            elif signal == "strong_buy":
                signal = "buy"
            confidence = max(0, confidence - 10)

        return {
            "code": code,
            "name": screened.get("name", ""),
            "market": screened.get("market", ""),
            "industry": screened.get("industry", ""),
            "benchmark": screened.get("benchmark_code", ""),
            "alpha_score": round(final_alpha, 2),
            "factor_scores": factor_scores,
            "signal": signal,
            "confidence": round(confidence, 2),
            "risk_flags": risk_flags,
            "total_market_cap": screened.get("total_market_cap"),
            "vol_60d": screened.get("vol_60d"),
        }


def run_alpha_model(screened_list: list[dict], indicators: dict[str, dict], weights: dict[str, float] | None = None) -> list[dict]:
    model = AlphaModel(weights=weights)
    results = []
    for s in screened_list:
        result = model.compute(s, indicators)
        results.append(result)
    results.sort(key=lambda r: r["alpha_score"], reverse=True)
    return results


def main():
    parser = argparse.ArgumentParser(description="Alpha Model")
    parser.add_argument("--screened", required=True, help="Screened stocks JSON")
    parser.add_argument("--indicators", required=True, help="Indicators JSON")
    parser.add_argument("--weights", required=False, default=None, help="Regime weights JSON (optional, overrides defaults)")
    parser.add_argument("--output", required=True, help="Output signals JSON")
    args = parser.parse_args()

    with open(args.screened) as f:
        screened_list = json.load(f)

    with open(args.indicators) as f:
        indicators = json.load(f)

    weights = None
    if args.weights:
        try:
            with open(args.weights) as f:
                weights = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    results = run_alpha_model(screened_list, indicators, weights=weights)

    with open(args.output, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    buy_count = sum(1 for r in results if r["signal"] in ("buy", "strong_buy"))
    print(f"Alpha model: {len(results)} stocks, {buy_count} buy signals → {args.output}")


if __name__ == "__main__":
    main()
