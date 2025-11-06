#!/usr/bin/env python3
"""Scan the Gamma API for tradeable markets with live CLOB order books."""

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


def fetch_midpoint(token_id: str):
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
        if best_bid is None and best_ask is None:
            return None
        if best_bid is None:
            return best_ask
        if best_ask is None:
            return best_bid
        return (best_bid + best_ask) / 2
    except (requests.RequestException, ValueError, KeyError):
        return None


def main():
    lookback = datetime.now(timezone.utc) - timedelta(days=45)
    params = {
        "active": True,
        "closed": False,
        "archived": False,
        "enableOrderBook": True,
        "limit": 50,
        "order": "id",
        "ascending": False,
        "start_date_min": lookback.isoformat().replace("+00:00", "Z"),
    }

    discovered = []
    offsets = [0, 50, 100]

    print("Scanning Gamma API for tradeable markets...")
    print("=" * 60)

    for offset in offsets:
        params['offset'] = offset
        try:
            resp = requests.get(GAMMA_URL, params=params, timeout=(5, 10))
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"❌ Request failed at offset {offset}: {exc}")
            continue

        payload = resp.json()
        markets = payload if isinstance(payload, list) else payload.get('data', [])
        print(f"Page offset {offset}: {len(markets)} markets returned")

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

            midpoint_prices = []
            for token_id in token_ids:
                price = fetch_midpoint(token_id)
                if price is not None and 0.01 <= price <= 0.99:
                    midpoint_prices.append(price)

            if not midpoint_prices:
                continue

            discovered.append((market, midpoint_prices))

            print(f"  ✓ {market.get('question', 'Unknown')[:90]}...")
            print(f"    Mid prices: {', '.join(f'{p:.3f}' for p in midpoint_prices)}")

            if len(discovered) >= 10:
                break

        if len(discovered) >= 10:
            break

    print("\n" + "=" * 60)
    print(f"Total tradeable markets found: {len(discovered)}")

    if discovered:
        market, prices = discovered[0]
        print("\nSample market snapshot:")
        print(json.dumps({
            "id": market.get('id'),
            "question": market.get('question'),
            "mid_prices": prices,
            "endDate": market.get('endDate'),
        }, indent=2))
    else:
        print("⚠️  No markets met the criteria. Consider broadening the search window.")


if __name__ == "__main__":
    main()
