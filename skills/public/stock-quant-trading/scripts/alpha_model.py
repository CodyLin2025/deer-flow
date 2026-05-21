#!/usr/bin/env python3
"""
Multi-Factor Alpha Model (deer-flow端)

Fuses screener factor scores with risk flag adjustments
to produce final alpha scores and buy/sell signals.
Technical indicators are NOT part of the alpha score calculation,
but are used as a post-screening breakdown filter to detect
recent price deterioration that the momentum factor may miss
(momentum skips the most recent 20 trading days by design).

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


SIGNAL_ORDER = {
    "strong_buy": 0,
    "buy": 1,
    "hold": 2,
    "sell": 3,
    "strong_sell": 4,
}
SIGNAL_REVERSE = {v: k for k, v in SIGNAL_ORDER.items()}


def _degrade_signal(signal: str, steps: int) -> str:
    idx = SIGNAL_ORDER.get(signal, 2)
    new_idx = min(len(SIGNAL_ORDER) - 1, idx + steps)
    return SIGNAL_REVERSE[new_idx]


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

    def _check_recent_breakdown(self, code: str, ind: dict | None) -> tuple[list[str], int]:
        if ind is None:
            return [], 0
        latest = ind.get("latest", {}) if isinstance(ind, dict) else {}
        if not latest:
            return [], 0

        flags: list[str] = []

        close = latest.get("close")
        ma5 = latest.get("ma5")
        ma20 = latest.get("ma20")
        ma60 = latest.get("ma60")
        ma5_prev = latest.get("ma5_prev")
        ma20_prev = latest.get("ma20_prev")
        dif = latest.get("macd_dif")
        dea = latest.get("macd_dea")
        hist = latest.get("macd_hist")
        rsi = latest.get("rsi_14")
        change_5d = latest.get("change_5d")
        change_20d = latest.get("change_20d")

        if close is not None and ma20 is not None and close < ma20:
            flags.append("跌破MA20")
        if close is not None and ma60 is not None and close < ma60:
            flags.append("跌破MA60")

        if (ma5 is not None and ma20 is not None and ma5 < ma20
                and ma5_prev is not None and ma20_prev is not None
                and ma5_prev >= ma20_prev):
            flags.append("MA5/20死叉")

        if rsi is not None and rsi < 40:
            flags.append("RSI弱势")

        if (dif is not None and dea is not None and dif < dea
                and hist is not None and hist < 0):
            flags.append("MACD死叉")

        rapid_fall_threshold_20d = -20 if code.startswith(("688", "300", "301")) else -15
        rapid_fall_threshold_5d = -12 if code.startswith(("688", "300", "301")) else -8
        rapid_fall = False
        if change_20d is not None and change_20d < rapid_fall_threshold_20d:
            rapid_fall = True
        elif change_5d is not None and change_5d < rapid_fall_threshold_5d:
            rapid_fall = True
        if rapid_fall:
            flags.append("短期急跌")

        return flags, len(flags)

    def compute(self, screened: dict, indicators: dict[str, dict]) -> dict:
        factor_scores = screened.get("factor_scores", {})
        code = screened.get("code", "")

        precomputed_alpha = screened.get("alpha_score")
        if precomputed_alpha is not None:
            final_alpha = precomputed_alpha
        else:
            factor_sum = 0.0
            effective_weight = 0.0
            for k, v in factor_scores.items():
                w = self.weights.get(k, 0.125)
                factor_sum += v * w
                effective_weight += w
            if effective_weight > 0:
                final_alpha = max(0, min(100, factor_sum / effective_weight))
            else:
                final_alpha = 50.0

        dispersion = calc_factor_dispersion(factor_scores)
        signal, confidence = determine_signal(final_alpha, dispersion)

        risk_flags = list(screened.get("risk_flags", []))
        if "PE极端高" in risk_flags or "经营现金流为负" in risk_flags:
            if signal == "buy":
                signal = "hold"
            elif signal == "strong_buy":
                signal = "buy"
            confidence = max(0, confidence - 10)

        stock_ind = indicators.get(code)
        breakdown_flags, breakdown_count = self._check_recent_breakdown(code, stock_ind)

        if breakdown_count >= 4:
            signal = "sell"
            confidence = max(0, confidence - 30)
            risk_flags = risk_flags + ["近期破位风险(≥4)"]
        elif breakdown_count >= 3:
            signal = _degrade_signal(signal, 2)
            confidence = max(0, confidence - 20)
            risk_flags = risk_flags + ["近期破位风险(≥3)"]
        elif breakdown_count >= 2:
            signal = _degrade_signal(signal, 1)
            confidence = max(0, confidence - 15)
            risk_flags = risk_flags + ["近期破位风险(≥2)"]
        elif breakdown_count >= 1:
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
            "breakdown_flags": breakdown_flags,
            "breakdown_count": breakdown_count,
            "total_market_cap": screened.get("total_market_cap"),
            "vol_60d": screened.get("vol_60d"),
            "avg_turnover_20d": screened.get("avg_turnover_20d"),
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
        except FileNotFoundError:
            print(f"WARNING: Weights file not found ({args.weights}), using equal weights (0.125 each)", flush=True)
        except json.JSONDecodeError:
            print(f"WARNING: Weights file is invalid JSON ({args.weights}), using equal weights (0.125 each)", flush=True)
    else:
        print("WARNING: No --weights specified, using equal weights (0.125 each). "
              "Dynamic regime weights will be ignored. "
              "Alpha scores may differ from screener output. "
              "Pass --weights <screened_weights.json> to match regime weights.", flush=True)

    results = run_alpha_model(screened_list, indicators, weights=weights)

    with open(args.output, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    buy_count = sum(1 for r in results if r["signal"] in ("buy", "strong_buy"))
    print(f"Alpha model: {len(results)} stocks, {buy_count} buy signals → {args.output}")


if __name__ == "__main__":
    main()
