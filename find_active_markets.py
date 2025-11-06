#!/usr/bin/env python3
"""Find and display currently tradeable Polymarket markets using the Gamma API."""

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
        data = resp.json()
        bids = data.get('bids') or []
        asks = data.get('asks') or []
        if not bids and not asks:
            return None
        best_bid = float(bids[0]['price']) if bids else None
        best_ask = float(asks[0]['price']) if asks else None
        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "book": {
                "bids": bids[:5],
                "asks": asks[:5],
            },
        }
    except (requests.RequestException, ValueError, KeyError):
        return None


def is_future_date(value: str) -> bool:
    if not value:
        return True
    try:
        cleaned = value.replace('Z', '+00:00')
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt > datetime.now(timezone.utc)
    except ValueError:
        return False


def main():
    print("Finding CURRENT Polymarket markets...")
    print("=" * 60)

    lookback = datetime.now(timezone.utc) - timedelta(days=45)
    params = {
        "active": True,
        "closed": False,
        "archived": False,
        "enableOrderBook": True,
        "limit": 100,
        "order": "id",
        "ascending": False,
        "start_date_min": lookback.isoformat().replace("+00:00", "Z"),
    }

    try:
        resp = requests.get(GAMMA_URL, params=params, timeout=(5, 10))
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"❌ Failed to reach Gamma API: {exc}")
        return

    payload = resp.json()
    markets = payload if isinstance(payload, list) else payload.get('data', [])
    print(f"Gamma returned {len(markets)} markets before filtering")

    tradeable = []

    for market in markets:
        if not isinstance(market, dict):
            continue

        if market.get('archived') or market.get('closed'):
            continue
        if market.get('acceptingOrders') is False:
            continue

        token_ids = parse_list(market.get('clobTokenIds'))
        if not token_ids:
            continue

        end_date = market.get('endDateIso') or market.get('endDate')
        if not is_future_date(end_date):
            continue

        outcome_labels = parse_list(market.get('outcomes'))
        tokens_display = []
        valid_orderbooks = 0

        for idx, token_id in enumerate(token_ids[:4]):
            ob = fetch_orderbook(token_id)
            if not ob:
                continue
            valid_orderbooks += 1
            midpoint = None
            if ob['best_bid'] is not None and ob['best_ask'] is not None:
                midpoint = (ob['best_bid'] + ob['best_ask']) / 2
            elif ob['best_bid'] is not None:
                midpoint = ob['best_bid']
            elif ob['best_ask'] is not None:
                midpoint = ob['best_ask']

            label = outcome_labels[idx] if idx < len(outcome_labels) else f"Outcome {idx+1}"
            tokens_display.append((label, midpoint, ob['best_bid'], ob['best_ask']))

        if valid_orderbooks == 0:
            continue

        tradeable.append((market, tokens_display))

        print(f"\n✓ {market.get('question', 'Unknown')[:90]}...")
        print(f"  Market ID: {market.get('id')} | Accepting Orders: {market.get('acceptingOrders')}")
        print(f"  End date: {end_date}")
        for label, mid, bid, ask in tokens_display:
            if mid is None:
                continue
            print(f"    - {label}: mid={mid:.3f} (bid={bid}, ask={ask})")

        if len(tradeable) >= 10:
            break

    print("\n" + "=" * 60)
    print(f"Identified {len(tradeable)} tradeable markets with live order books")

    if not tradeable:
        print("⚠️  No tradeable markets met the criteria. Try adjusting lookback or check manually.")


if __name__ == "__main__":
    main()
