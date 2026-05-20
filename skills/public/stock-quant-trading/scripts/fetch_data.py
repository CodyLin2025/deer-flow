#!/usr/bin/env python3
"""
Data Fetcher — calls stock-data-crawl API

Usage:
    python fetch_data.py --action screener --api-base http://localhost:8000/api
    python fetch_data.py --action klines --codes "000001,600519" --days 250
    python fetch_data.py --action stocks --market all
    python fetch_data.py --action news --query "光模块 行业 景气"
"""

import argparse
import json
import os
import sys

import urllib.request
import urllib.error


API_BASE = os.environ.get("STOCK_API_BASE_URL", "http://localhost:8000/api")


def _post(url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return json.loads(body)
        except Exception:
            return {"code": e.code, "message": body}
    except Exception as e:
        return {"code": 500, "message": str(e)}


def _get(url: str) -> dict:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return json.loads(body)
        except Exception:
            return {"code": e.code, "message": body}
    except Exception as e:
        return {"code": 500, "message": str(e)}


def fetch_screened_stocks(api_base: str = API_BASE, market: str = "all", top_n: int = 50) -> dict:
    url = f"{api_base}/screener/run?market={market}&top_n={top_n}"
    return _post(url)


def fetch_klines(api_base: str = API_BASE, stock_code: str = "", days: int = 250) -> dict:
    url = f"{api_base}/kline/{stock_code}?limit={days}"
    return _get(url)


def fetch_klines_batch(api_base: str = API_BASE, codes: list[str] | None = None, days: int = 250) -> dict:
    url = f"{api_base}/kline/batch"
    return _post(url, {"codes": codes or [], "kline_type": "daily", "limit": days})


def fetch_benchmark_klines(api_base: str = API_BASE, index_code: str = "000300", days: int = 250) -> dict:
    url = f"{api_base}/kline/{index_code}"
    return _get(url)


def fetch_news(api_base: str = API_BASE, query: str = "", count: int = 10) -> dict:
    url = f"{api_base}/search/web"
    return _post(url, {"query": query, "count": count, "freshness": "oneMonth", "summary": True})


def fetch_stock_list(api_base: str = API_BASE, market: str = "all") -> dict:
    url = f"{api_base}/stocks/list?market={market}"
    return _get(url)


def fetch_quote(api_base: str = API_BASE, stock_code: str = "") -> dict:
    url = f"{api_base}/quote/{stock_code}"
    return _get(url)


def fetch_finance(api_base: str = API_BASE, stock_code: str = "") -> dict:
    url = f"{api_base}/finance/{stock_code}"
    return _get(url)


def fetch_report(api_base: str = API_BASE, stock_code: str = "") -> dict:
    url = f"{api_base}/report/{stock_code}"
    return _get(url)


def main():
    parser = argparse.ArgumentParser(description="Stock Data Fetcher")
    parser.add_argument("--action", required=True, choices=["screener", "klines", "stocks", "news", "quote", "finance", "report"])
    parser.add_argument("--api-base", default=API_BASE)
    parser.add_argument("--codes", default="")
    parser.add_argument("--code", default="")
    parser.add_argument("--market", default="all")
    parser.add_argument("--days", type=int, default=250)
    parser.add_argument("--top-n", type=int, default=50)
    parser.add_argument("--query", default="")
    parser.add_argument("--output", default="")

    args = parser.parse_args()

    if args.action == "screener":
        result = fetch_screened_stocks(args.api_base, args.market, args.top_n)
        stocks = result.get("top_stocks", result.get("data", []))
        regime_weights = result.get("regime_weights", {})
        if regime_weights:
            weights_file = args.output.replace(".json", "_weights.json") if args.output else "screened_weights.json"
            with open(weights_file, "w") as f:
                json.dump(regime_weights, f, ensure_ascii=False, indent=2)
    elif args.action == "klines":
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
        if len(codes) == 1:
            result = fetch_klines(args.api_base, codes[0], args.days)
            stocks = result.get("data", result)
            if isinstance(stocks, list) and stocks and "klines" not in stocks[0]:
                stocks = [{"security_code": codes[0], "klines": stocks}]
        else:
            result = fetch_klines_batch(args.api_base, codes, args.days)
            stocks = result.get("data", result)
    elif args.action == "stocks":
        result = fetch_stock_list(args.api_base, args.market)
        stocks = result.get("data", [])
    elif args.action == "news":
        result = fetch_news(args.api_base, args.query)
        stocks = result.get("data", result)
    elif args.action == "quote":
        code = args.code or args.codes.split(",")[0].strip()
        result = fetch_quote(args.api_base, code)
        stocks = result.get("data", result)
    elif args.action == "finance":
        code = args.code or args.codes.split(",")[0].strip()
        result = fetch_finance(args.api_base, code)
        stocks = result.get("data", result)
    elif args.action == "report":
        code = args.code or args.codes.split(",")[0].strip()
        result = fetch_report(args.api_base, code)
        stocks = result.get("data", result)

    output = args.output
    if not output:
        output = f"{args.action}_result.json"

    with open(output, "w") as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)

    print(f"{args.action} → {output} ({len(stocks) if isinstance(stocks, list) else 1} items)")


if __name__ == "__main__":
    main()
