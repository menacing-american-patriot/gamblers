#!/usr/bin/env python3
"""Inspect the structure of Polymarket markets via the Gamma and CLOB APIs."""

import json
from datetime import datetime, timezone, timedelta

import requests

GAMMA_URL = "https://gamma-api.polymarket.com/markets"
CLOB_URL = "https://clob.polymarket.com/book"


def parse_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return []
    return []


def fetch_orderbook(token_id: str):
    try:
        resp = requests.get(CLOB_URL, params={"token_id": token_id}, timeout=(5, 10))
        if resp.status_code != 200:
            return None
        return resp.json()
    except requests.RequestException:
        return None


def main():
    lookback = datetime.now(timezone.utc) - timedelta(days=30)
    params = {
        "active": True,
        "closed": False,
        "archived": False,
        "enableOrderBook": True,
        "limit": 5,
        "order": "id",
        "ascending": False,
        "start_date_min": lookback.isoformat().replace("+00:00", "Z"),
    }

    try:
        resp = requests.get(GAMMA_URL, params=params, timeout=(5, 10))
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"❌ Unable to fetch markets: {exc}")
        return

    payload = resp.json()
    markets = payload if isinstance(payload, list) else payload.get('data', [])

    print(f"Gamma returned {len(markets)} markets for inspection")

    if not markets:
        print("⚠️  No markets available to inspect")
        return

    market = markets[0]
    print("\nSample market JSON (truncated):")
    print(json.dumps(market, indent=2)[:2000])

    token_ids = parse_list(market.get('clobTokenIds'))
    outcomes = parse_list(market.get('outcomes'))

    if not token_ids:
        print("⚠️  Market does not contain clobTokenIds")
        return

    print("\nOrder book snapshots:")
    for idx, token_id in enumerate(token_ids):
        outcome = outcomes[idx] if idx < len(outcomes) else f"Outcome {idx+1}"
        print(f"\nToken {idx} ({outcome}) -> {token_id}")
        book = fetch_orderbook(token_id)
        if not book:
            print("  No order book available")
            continue
        bids = book.get('bids') or []
        asks = book.get('asks') or []
        print(f"  Bids: {bids[:3]}")
        print(f"  Asks: {asks[:3]}")


if __name__ == "__main__":
    main()
