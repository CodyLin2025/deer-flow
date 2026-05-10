#!/usr/bin/env python3
"""
Technical Indicators Calculator

Usage:
    python indicators.py --klines data/klines.json --output data/indicators.json

Input: JSON file with {"code": "000001", "klines": [{"close": ..., "high": ..., "low": ..., ...}]}

Output: JSON with indicators per stock
"""

import argparse
import json
import math


def calc_ma(closes: list[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        result[i] = sum(closes[i - period + 1:i + 1]) / period
    return result


def calc_ema(closes: list[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(closes)
    if not closes:
        return result
    multiplier = 2.0 / (period + 1)
    result[period - 1] = sum(closes[:period]) / period
    for i in range(period, len(closes)):
        if result[i - 1] is not None and closes[i] is not None:
            result[i] = (closes[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


def calc_macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = calc_ema(closes, fast)
    ema_slow = calc_ema(closes, slow)

    dif: list[float | None] = [None] * len(closes)
    for i in range(len(closes)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            dif[i] = ema_fast[i] - ema_slow[i]

    clean_dif = [d for d in dif if d is not None]
    dea = [None] * len(closes)
    if len(clean_dif) >= signal:
        for i in range(len(dif)):
            if i >= slow + signal - 2 and dif[i] is not None:
                back = [d for d in dif[max(0, i - signal + 1):i + 1] if d is not None]
                if back:
                    dea[i] = sum(back) / len(back)

    histogram: list[float | None] = [None] * len(closes)
    for i in range(len(closes)):
        if dif[i] is not None and dea[i] is not None:
            histogram[i] = (dif[i] - dea[i]) * 2

    return dif, dea, histogram


def calc_rsi(closes: list[float], period: int = 14) -> list[float | None]:
    result: list[float | None] = [None] * len(closes)
    if len(closes) < period + 1:
        return result

    gains = []
    losses = []
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    result[period] = 100 - 100 / (1 + avg_gain / avg_loss) if avg_loss != 0 else 100

    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain = max(change, 0)
        loss = max(-change, 0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        result[i] = 100 - 100 / (1 + avg_gain / avg_loss) if avg_loss != 0 else 100

    return result


def calc_kdj(highs: list[float], lows: list[float], closes: list[float], n: int = 9) -> tuple[list[float | None], list[float | None], list[float | None]]:
    k: list[float | None] = [None] * len(closes)
    d: list[float | None] = [None] * len(closes)
    j: list[float | None] = [None] * len(closes)

    for i in range(n - 1, len(closes)):
        h = max(highs[i - n + 1:i + 1])
        l = min(lows[i - n + 1:i + 1])
        if h == l:
            rsv = 100.0
        else:
            rsv = (closes[i] - l) / (h - l) * 100

        if i == n - 1:
            k[i] = 50.0
            d[i] = 50.0
        else:
            k[i] = 2 / 3 * (k[i - 1] or 50) + 1 / 3 * rsv
            d[i] = 2 / 3 * (d[i - 1] or 50) + 1 / 3 * (k[i] or 50)

        j[i] = 3 * (k[i] or 0) - 2 * (d[i] or 0)

    return k, d, j


def calc_bollinger(closes: list[float], period: int = 20, std_dev: int = 2) -> tuple[list[float | None], list[float | None], list[float | None]]:
    ma = calc_ma(closes, period)
    upper: list[float | None] = [None] * len(closes)
    lower: list[float | None] = [None] * len(closes)

    for i in range(period - 1, len(closes)):
        if ma[i] is None:
            continue
        window = closes[i - period + 1:i + 1]
        var = sum((v - ma[i]) ** 2 for v in window) / period
        sd = math.sqrt(var)
        upper[i] = ma[i] + std_dev * sd
        lower[i] = ma[i] - std_dev * sd

    return upper, ma, lower


def calc_atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float | None]:
    result: list[float | None] = [None] * len(closes)

    tr: list[float] = []
    tr.append(highs[0] - lows[0])
    for i in range(1, len(closes)):
        tr.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        ))

    if len(tr) < period:
        return result

    result[period - 1] = sum(tr[:period]) / period
    for i in range(period, len(tr)):
        result[i] = (result[i - 1] * (period - 1) + tr[i]) / period

    return result


def calc_beta(stock_returns: list[float], benchmark_returns: list[float], period: int = 60) -> float | None:
    n = min(len(stock_returns), len(benchmark_returns), period)
    if n < 2:
        return None

    x = benchmark_returns[:n]
    y = stock_returns[:n]
    mean_x = sum(x) / n
    mean_y = sum(y) / n

    cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n)) / n
    var = sum((xi - mean_x) ** 2 for xi in x) / n

    return cov / var if var != 0 else None


def calc_historical_volatility(closes: list[float], period: int = 60) -> float | None:
    if len(closes) < period + 1:
        return None

    returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(-period, 0)]
    mean_r = sum(returns) / len(returns)
    var = sum((r - mean_r) ** 2 for r in returns) / len(returns)
    return math.sqrt(var) * math.sqrt(250)


def compute_indicators(klines_data: list[dict]) -> dict:
    closes = [k["close"] for k in klines_data if k.get("close") is not None]
    highs = [k["high"] for k in klines_data if k.get("high") is not None]
    lows = [k["low"] for k in klines_data if k.get("low") is not None]

    if not closes:
        return {}

    ma5 = calc_ma(closes, 5)
    ma10 = calc_ma(closes, 10)
    ma20 = calc_ma(closes, 20)
    ma60 = calc_ma(closes, 60)

    dif, dea, hist = calc_macd(closes)
    rsi14 = calc_rsi(closes, 14)
    k, d, j = calc_kdj(highs, lows, closes)
    upper, mid, lower = calc_bollinger(closes)

    return {
        "latest": {
            "close": closes[-1] if closes else None,
            "ma5": ma5[-1],
            "ma10": ma10[-1],
            "ma20": ma20[-1],
            "ma60": ma60[-1],
            "macd_dif": dif[-1],
            "macd_dea": dea[-1],
            "macd_hist": hist[-1],
            "rsi_14": rsi14[-1],
            "kdj_k": k[-1],
            "kdj_d": d[-1],
            "kdj_j": j[-1],
            "boll_upper": upper[-1],
            "boll_mid": mid[-1],
            "boll_lower": lower[-1],
        },
        "full": {
            "closes": closes,
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "ma60": ma60,
            "dif": dif,
            "dea": dea,
            "histogram": hist,
            "rsi14": rsi14,
            "kdj_k": k,
            "kdj_d": d,
            "kdj_j": j,
            "boll_upper": upper,
            "boll_mid": mid,
            "boll_lower": lower,
        },
    }


def compute_all_indicators(all_klines: list[dict]) -> dict[str, dict]:
    result = {}
    for item in all_klines:
        code = item.get("security_code", item.get("code", ""))
        klines = item.get("klines", [])
        if klines:
            result[code] = compute_indicators(klines)
    return result


def main():
    parser = argparse.ArgumentParser(description="Technical Indicators Calculator")
    parser.add_argument("--klines", required=True, help="Path to klines JSON file")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    args = parser.parse_args()

    with open(args.klines) as f:
        all_klines = json.load(f)

    result = compute_all_indicators(all_klines)

    with open(args.output, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Computed indicators for {len(result)} stocks → {args.output}")


if __name__ == "__main__":
    main()
