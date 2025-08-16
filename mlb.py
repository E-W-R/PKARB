import warnings
warnings.filterwarnings("ignore")
import requests
import json
import pandas as pd
from datetime import datetime, timezone, timedelta, time
import zoneinfo
from time import sleep
import os


pacific = zoneinfo.ZoneInfo("America/Los_Angeles")
current_date = datetime.now(pacific).strftime("%m-%d-%Y")
path = os.path.join("log", current_date)
if not os.path.exists(path):
    os.makedirs(path)


with open("p.json", "r") as file:
    P = json.loads(file.read())

with open("k.json", "r") as file:
    K = json.load(file)


def match():
    out = []
    seen = set()
    teams = pd.read_csv("csv/mlb.csv")
    loc, name = list(teams["City"]), list(teams["Team Name"])
    name_to_loc = dict(zip(name, loc))
    pacific = zoneinfo.ZoneInfo("America/Los_Angeles")
    today_wt = datetime.now(pacific).date()
    four_am_wt = datetime.combine(today_wt, time(4, 0), tzinfo=pacific)
    for p in P:
        if "MLB" in p["tags"] and "vs." in p["question"]:
            start = p["game_start_time"]
            dt = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ")
            dt = dt.replace(tzinfo=timezone.utc).astimezone(pacific)
            within_24h = four_am_wt <= dt <= four_am_wt + timedelta(hours=20)
            if within_24h:
                away_name, home_name = p["question"].split(" vs. ")
                away_loc, home_loc = name_to_loc[away_name], name_to_loc[home_name]
                k_title = away_loc + " at " + home_loc + ( " (Game 2)" if p["question"] in seen else "") + " Winner?"
                seen.add(p["question"])
                tickers = []
                for k in K:
                    if k["title"] == k_title:
                        month = dt.strftime("%b")
                        day = dt.day
                        if month + " " + str(day) not in k["rules_primary"]:
                            continue
                        tickers.append(k["ticker"])
                if tickers:
                    out.append([p["tokens"][1]["token_id"], tickers, p["question"]])
    for i in range(len(out)):
        _, k, _ = out[i]
        k1, k2 = k
        _, _, t1 = k1.split("-")
        _, _, t2 = k2.split("-")
        j = -1
        while k1[j] not in "1234567890":
            j -= 1
        s = k1[j+1:]
        out[i].append(s[:s.index("-")])
        i1 = s.index(t1)
        i2 = s.index(t2)
        if i1 > i2:
            out[i][1] = [k2, k1]
    return out

def arbitrage(common):
    print(f"\nScanning Markets: {datetime.now().strftime('%-I:%M%p')}\n")
    token_ids = [m[0] for m in common]
    url = "https://clob.polymarket.com/books"
    payload = [{"token_id": tid} for tid in token_ids]
    response = requests.post(url, json = payload)
    books = response.json()
    book_map = {book["asset_id"]: book for book in books}
    p_books = [book_map[tid] if tid in book_map else None for tid in token_ids]

    for i in range(len(p_books)):
        p = p_books[i]
        if not p:
            continue
        p_asks, p_bids = p["asks"], p["bids"]
        p_asks = [[round(float(D["price"]) * 100), int(float(D["size"]))] for D in p_asks]
        p_bids = [[round(float(D["price"]) * 100), int(float(D["size"]))] for D in p_bids]

        ticker = common[i][1][0]
        url = f"https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}/orderbook"
        response = requests.get(url)
        k_away = response.json()["orderbook"]
        ticker = common[i][1][1]
        url = f"https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}/orderbook"
        response = requests.get(url)
        k_home = response.json()["orderbook"]
        if not k_home["yes"] or not k_home["no"] or not k_away["yes"] or not k_away["no"]:
            continue
        def merge(L1, L2):
            D = dict(L1)
            for price, size in L2:
                if price in D:
                    D[price] += size
                else:
                    D[price] = size
            out = [list(t) for t in list(D.items())]
            return sorted(out, key = lambda t: t[0])
        k_asks = merge(k_home["no"], k_away["yes"])
        k_asks = [[100 - price, size] for price, size in k_asks]
        k_bids = merge(k_home["yes"], k_away["no"])

        header = "time,p_asks_size,p_asks_price,p_bids_size,p_bids_price,k_asks_size,k_asks_price,k_bids_size,k_bids_price,margin,units"
        pacific = zoneinfo.ZoneInfo("America/Los_Angeles")
        now_pacific = datetime.now(pacific)
        midnight_pacific = datetime.combine(now_pacific.date(), time(0, 0), tzinfo=pacific)
        seconds = int((now_pacific - midnight_pacific).total_seconds())
        try:
            row = [seconds, p_asks[-1][1], p_asks[-1][0], p_bids[-1][1], p_bids[-1][0], k_asks[-1][1], k_asks[-1][0], k_bids[-1][1], k_bids[-1][0]]
        except:
            continue
        row = [str(item) for item in row]
        line = ",".join(row)
        op = False

        # Buy Home on Polymarket, Buy Away on Kalshi
        units, cost = 0, 0
        while p_asks[-1][0] < k_bids[-1][0]:
            size = min(p_asks[-1][1], k_bids[-1][1])
            price = p_asks[-1][0] - k_bids[-1][0] + 100
            cost += price * size
            units += size
            p_asks[-1][1] -= size
            k_bids[-1][1] -= size
            if not p_asks[-1][1]:
                p_asks.pop()
            if not k_bids[-1][1]:
                k_bids.pop()
        if units:
            op = True
            cost = round(cost / 100, 2)
            margin = round((units - cost) / units * 100, 2)
            line += "," + str(margin) + "," + str(units)
            print(common[i][2])
            print(f"Buy Home on Polymarket, Buy Away on Kalshi: {units} units at ${cost} ({margin}% margin)\n")

        # Buy Away on Polymarket, Buy Home on Kalshi
        units, cost = 0, 0
        while k_asks[-1][0] < p_bids[-1][0]:
            size = min(k_asks[-1][1], p_bids[-1][1])
            price = k_asks[-1][0] - p_bids[-1][0] + 100
            cost += price * size
            units += size
            k_asks[-1][1] -= size
            p_bids[-1][1] -= size
            if not k_asks[-1][1]:
                k_asks.pop()
            if not p_bids[-1][1]:
                p_bids.pop()
        if units:
            op = True
            cost = round(cost / 100, 2)
            margin = round((units - cost) / units * 100, 2)
            line += "," + str(margin) + "," + str(units)
            print(common[i][2])
            print(f"Buy Away on Polymarket, Buy Home on Kalshi: {units} units at ${cost} ({margin}% margin)\n")

        if not op:
            line += ",,"
        current_date = datetime.now(pacific).strftime("%m-%d-%Y")
        path = f"log/{current_date}/{common[i][3]}.txt"
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write(header + "\n")
        with open(path, "a") as f:
            f.write(line + "\n")
        sleep(0.1)


common = match()
arbitrage(common)