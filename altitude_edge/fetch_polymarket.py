"""
Pull live 3-way prices for a league's games from Polymarket's public Gamma API
into a scanner-ready CSV. Prices are mid-market probabilities; the scanner treats
1/price as decimal odds (so 'EV' here is vs. the mid, before the spread and fees).
Run on your own machine.

    python3 fetch_polymarket.py --tags liga-mx col1 --out fixtures_polymarket.csv

Tag slugs change; check https://polymarket.com/sports for the league you want.
"""
import argparse, csv, json, sys, urllib.request

URL = "https://gamma-api.polymarket.com/events?tag_slug={tag}&active=true&closed=false&limit=200"


def fetch(tag):
    req = urllib.request.Request(URL.format(tag=tag), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def parse_event(ev, tag):
    """Moneyline events carry one market per outcome (team A / Draw / team B), each
    binary with outcomePrices ['yes','no']. Map by groupItemTitle."""
    prices = {}
    vol = 0.0
    for m in ev.get("markets", []):
        try:
            yes = float(json.loads(m.get("outcomePrices", "[]"))[0])
        except Exception:
            continue
        title = (m.get("groupItemTitle") or m.get("question") or "").strip()
        prices[title] = yes
        vol += float(m.get("volumeNum") or m.get("volume") or 0)
    if not prices:
        return None
    draw_key = next((k for k in prices if k.lower() == "draw"), None)
    teams = [k for k in prices if k != draw_key]
    if len(teams) != 2 or draw_key is None:
        return None
    title = ev.get("title", "")
    # Polymarket titles are '<away> vs. <home>' for US sports but '<home> vs. <away>' for soccer; trust order in title
    parts = title.replace(" vs. ", " vs ").split(" vs ")
    home, away = (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else (teams[0], teams[1])
    ph = prices.get(home) or prices.get(teams[0]); pa = prices.get(away) or prices.get(teams[1]); pd = prices[draw_key]
    if not (ph and pa and pd):
        return None
    return {
        "date": (ev.get("startDate") or ev.get("gameStartTime") or "")[:10], "league": tag, "home": home, "away": away,
        "odds_h": round(1 / ph, 3), "odds_d": round(1 / pd, 3), "odds_a": round(1 / pa, 3),
        "odds_over25": "", "odds_under25": "", "days_since_arrival": 1,
        "note": f"polymarket mid; event volume ${vol:,.0f}; liquidity {ev.get('liquidityNum', ev.get('liquidity', ''))}",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", nargs="+", required=True)
    ap.add_argument("--out", default="fixtures_polymarket.csv")
    a = ap.parse_args()
    rows = []
    for tag in a.tags:
        try:
            for ev in fetch(tag):
                r = parse_event(ev, tag)
                if r:
                    rows.append(r)
        except Exception as e:  # noqa
            print(f"{tag}: {e}", file=sys.stderr)
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["date", "league", "home", "away", "odds_h", "odds_d", "odds_a", "odds_over25", "odds_under25", "days_since_arrival", "note"])
        w.writeheader(); w.writerows(rows)
    print(f"wrote {len(rows)} fixtures to {a.out}")


if __name__ == "__main__":
    main()
