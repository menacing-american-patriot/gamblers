#!/usr/bin/env python3
"""Test script to verify Polymarket connectivity and market availability."""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

import requests
from dotenv import load_dotenv
from py_clob_client.client import ClobClient

load_dotenv()

CLOB_HOST = "https://clob.polymarket.com"
GAMMA_MARKETS = "https://gamma-api.polymarket.com/markets"


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
        resp = requests.get(f"{CLOB_HOST}/book", params={"token_id": token_id}, timeout=(5, 10))
        if resp.status_code != 200:
            return None
        data = resp.json()
        bids = data.get('bids') or []
        asks = data.get('asks') or []
        if not bids and not asks:
            return None
        return {
            "best_bid": bids[0] if bids else None,
            "best_ask": asks[0] if asks else None,
        }
    except requests.RequestException:
        return None


def main():
    print("Testing Polymarket connectivity...")
    print("=" * 60)

    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        print("❌ PRIVATE_KEY not found. Populate .env before proceeding.")
        sys.exit(1)
    print(f"✓ PRIVATE_KEY loaded (length {len(private_key)})")

    try:
        client = ClobClient(CLOB_HOST, key=private_key, chain_id=137)
        print("✓ ClobClient initialized successfully")
    except Exception as exc:
        print(f"❌ Failed to initialize ClobClient: {exc}")
        sys.exit(1)

    lookback = datetime.now(timezone.utc) - timedelta(days=30)
    params = {
        "active": True,
        "closed": False,
        "archived": False,
        "enableOrderBook": True,
        "limit": 10,
        "order": "id",
        "ascending": False,
        "start_date_min": lookback.isoformat().replace("+00:00", "Z"),
    }

    try:
        resp = requests.get(GAMMA_MARKETS, params=params, timeout=(5, 10))
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"❌ Unable to fetch markets from Gamma API: {exc}")
        sys.exit(1)

    payload = resp.json()
    markets = payload if isinstance(payload, list) else payload.get('data', [])
    print(f"✓ Gamma API returned {len(markets)} markets for inspection")

    if not markets:
        print("⚠️  No markets returned. Verify API availability on the Polymarket status page.")
        sys.exit(0)

    market = markets[0]
    token_ids = parse_list(market.get('clobTokenIds'))
    outcomes = parse_list(market.get('outcomes'))

    print("\nSample market summary:")
    print(json.dumps({
        "id": market.get('id'),
        "question": market.get('question'),
        "acceptingOrders": market.get('acceptingOrders'),
        "endDate": market.get('endDate'),
        "tokenCount": len(token_ids),
    }, indent=2))

    if not token_ids:
        print("⚠️  Market lacks clobTokenIds; cannot inspect order book.")
        sys.exit(0)

    print("\nOrder book check:")
    for idx, token_id in enumerate(token_ids[:2]):
        outcome = outcomes[idx] if idx < len(outcomes) else f"Outcome {idx+1}"
        snapshot = fetch_orderbook(token_id)
        if not snapshot:
            print(f"  - {outcome}: No live order book")
            continue
        best_bid = snapshot['best_bid']['price'] if snapshot['best_bid'] else None
        best_ask = snapshot['best_ask']['price'] if snapshot['best_ask'] else None
        print(f"  - {outcome}: best bid={best_bid}, best ask={best_ask}")


if __name__ == "__main__":
    main()
