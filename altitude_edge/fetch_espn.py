"""
Pull upcoming fixtures (and ESPN BET 3-way odds where ESPN publishes them) from
ESPN's public scoreboard endpoint into a scanner-ready CSV. Run this on your own
machine; it needs open internet access.

    python3 fetch_espn.py --from 20260920 --to 20261005 --out fixtures_espn.csv
    python3 fetch_espn.py --leagues mex.1 bol.1 --from 20260920 --to 20260927

Odds coverage varies by league; rows without odds still scan (flagged 'needs odds').
"""
import argparse, csv, json, sys, urllib.request

LEAGUES = {
    "mex.1": "Liga MX", "bol.1": "Bolivia Division Profesional", "ecu.1": "LigaPro Ecuador",
    "col.1": "Liga BetPlay", "per.1": "Liga 1 Peru", "conmebol.libertadores": "Copa Libertadores",
    "conmebol.sudamericana": "Copa Sudamericana", "fifa.worldq.conmebol": "CONMEBOL WCQ",
}
URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/scoreboard?dates={d1}-{d2}&limit=300"


def american_to_decimal(ml):
    if ml is None:
        return None
    ml = float(ml)
    return round(1 + (ml / 100 if ml > 0 else 100 / abs(ml)), 3)


def fetch(lg, d1, d2):
    req = urllib.request.Request(URL.format(lg=lg, d1=d1, d2=d2), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def parse(lg, data):
    rows = []
    for ev in data.get("events", []):
        comp = ev["competitions"][0]
        home = away = None
        for c in comp["competitors"]:
            if c.get("homeAway") == "home":
                home = c["team"]["displayName"]
            else:
                away = c["team"]["displayName"]
        odds = (comp.get("odds") or [{}])[0]
        oh = american_to_decimal((odds.get("homeTeamOdds") or {}).get("moneyLine"))
        oa = american_to_decimal((odds.get("awayTeamOdds") or {}).get("moneyLine"))
        od = american_to_decimal((odds.get("drawOdds") or {}).get("moneyLine"))
        rows.append({
            "date": ev["date"][:10], "league": LEAGUES.get(lg, lg), "home": home, "away": away,
            "odds_h": oh or "", "odds_d": od or "", "odds_a": oa or "",
            "odds_over25": "", "odds_under25": "", "days_since_arrival": 1,
            "note": f"{(odds.get('provider') or {}).get('name', '')} {odds.get('details', '')} venue={(comp.get('venue') or {}).get('fullName', '')}".strip(),
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", nargs="*", default=list(LEAGUES))
    ap.add_argument("--from", dest="d1", required=True)
    ap.add_argument("--to", dest="d2", required=True)
    ap.add_argument("--out", default="fixtures_espn.csv")
    a = ap.parse_args()
    rows = []
    for lg in a.leagues:
        try:
            rows += parse(lg, fetch(lg, a.d1, a.d2))
        except Exception as e:  # noqa
            print(f"{lg}: {e}", file=sys.stderr)
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["date", "league", "home", "away", "odds_h", "odds_d", "odds_a", "odds_over25", "odds_under25", "days_since_arrival", "note"])
        w.writeheader(); w.writerows(rows)
    print(f"wrote {len(rows)} fixtures to {a.out}")


if __name__ == "__main__":
    main()
