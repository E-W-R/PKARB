import requests
import json


def get_polymarket():
    """
    Fetches all markets from Polymarket’s CLOB API and returns
    only those with active==True.
    """
    base_url = "https://clob.polymarket.com"
    all_live_markets = []
    next_cursor = ""  # empty string means “start at the beginning” :contentReference[oaicite:0]{index=0}

    while True:
        params = {}
        if next_cursor:
            params["next_cursor"] = next_cursor

        response = requests.get(f"{base_url}/markets", params=params)
        response.raise_for_status()
        payload = response.json()

        # Extract markets and filter for active/live ones :contentReference[oaicite:1]{index=1}
        markets = payload.get("data", [])
        live = [m for m in markets if m.get("active") and m.get("accepting_orders") and not (m.get("closed") or m.get("archived"))]
        all_live_markets.extend(live)

        # Prepare for next page; 'LTE=' signals “end of list” :contentReference[oaicite:2]{index=2}
        next_cursor = payload.get("next_cursor", "")
        if not next_cursor or next_cursor == "LTE=":
            break

    return all_live_markets

def get_kalshi():
    """
    Fetches all live (open) markets from Kalshi’s public API.
    """
    base_url = "https://api.elections.kalshi.com/trade-api/v2/markets"
    all_live_markets = []
    cursor = None

    while True:
        params = {
            "status": "open",    # only live markets
            "limit": 100         # max per page
        }
        if cursor:
            params["cursor"] = cursor

        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()

        # Collect markets from this page
        markets = data.get("markets", [])
        all_live_markets.extend(markets)

        # Prepare next cursor; stop if none
        cursor = data.get("cursor")
        if not cursor:
            break

    return all_live_markets


P = get_polymarket()
K = get_kalshi()


with open("p.json", "w") as file:
    json.dump(P, file, indent = 4)

with open("k.json", "w") as file:
    json.dump(K, file, indent = 4)