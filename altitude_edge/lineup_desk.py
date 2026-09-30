"""
Lineup desk CLI on EA FC ratings.

    python3 lineup_desk.py --home "KC Current" --away "Orlando Pride" --odds 1.60 4.00 5.20
    python3 lineup_desk.py --home "KC Current" --away "Orlando Pride" --odds 1.60 4.00 5.20 --home-out "Temwa Chawinga" "Debinha"
    python3 lineup_desk.py --teams        # list squads

The reference XI (what the market is assumed to price) is the club's best XI by
formation from fc_ratings_nwsl.json. The projected XI is the best XI after
removing the players you mark out. Same math as after-hours.js.
"""
import argparse, json, os, unicodedata
from lineup_props import price_lineups, xi_rating, LINEUP_DEFAULT

GROUPS = {"GK": "GK", "CB": "DF", "LB": "DF", "RB": "DF", "LWB": "DF", "RWB": "DF",
          "CDM": "MF", "CM": "MF", "CAM": "MF", "LM": "MF", "RM": "MF",
          "ST": "FW", "CF": "FW", "LW": "FW", "RW": "FW"}
FORMATIONS = {"4-3-3": {"GK": 1, "DF": 4, "MF": 3, "FW": 3}, "4-4-2": {"GK": 1, "DF": 4, "MF": 4, "FW": 2},
              "4-2-3-1": {"GK": 1, "DF": 4, "MF": 5, "FW": 1}, "3-5-2": {"GK": 1, "DF": 3, "MF": 5, "FW": 2}, "3-4-3": {"GK": 1, "DF": 3, "MF": 4, "FW": 3}}


def _norm(s):
    return " ".join(unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().split())


def load_ratings(path=os.path.join(os.path.dirname(__file__), "fc_ratings_nwsl.json")):
    return json.load(open(path, encoding="utf-8"))


def find_team(data, name):
    key = _norm(name)
    for t in data["teams"]:
        if _norm(t) == key or key in _norm(t):
            return t
    aliases = {"kansas city current": "KC Current", "gotham": "NJ/NY Gotham", "gotham fc": "NJ/NY Gotham", "racing louisville": "Rac. Louisville",
               "north carolina courage": "NC Courage", "chicago stars": "Chicago Red Stars", "utah royals": "Utah Royals FC", "angel city": "Angel City FC"}
    return aliases.get(key)


def player_group(p):
    return GROUPS.get(p["p"], "MF")


def best_xi(squad, formation="4-3-3", out=()):
    """Best XI by rating within each positional group; short groups borrow the best remaining player."""
    outn = {_norm(n) for n in out}
    pool = [dict(p, rating=p["ovr"], name=p["n"], pos=p["p"]) for p in squad if _norm(p["n"]) not in outn]
    need = dict(FORMATIONS[formation]); xi = []
    for g, k in need.items():
        cands = sorted([p for p in pool if player_group(p) == g and p not in xi], key=lambda p: -p["ovr"])[:k]
        xi += cands; need[g] = k - len(cands)
    short = sum(need.values())
    if short:
        rest = sorted([p for p in pool if p not in xi and player_group(p) != "GK"], key=lambda p: -p["ovr"])[:short]
        xi += rest
    return xi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teams", action="store_true")
    ap.add_argument("--home"); ap.add_argument("--away")
    ap.add_argument("--odds", nargs=3, type=float, metavar=("H", "D", "A"))
    ap.add_argument("--home-out", nargs="*", default=[]); ap.add_argument("--away-out", nargs="*", default=[])
    ap.add_argument("--formation", default="4-3-3", choices=list(FORMATIONS))
    ap.add_argument("--gpp", type=float, default=LINEUP_DEFAULT["goals_per_point"])
    ap.add_argument("--awareness", type=float, default=LINEUP_DEFAULT["market_awareness"])
    a = ap.parse_args()
    data = load_ratings()
    if a.teams:
        for t, sq in data["teams"].items():
            xi = best_xi(sq, a.formation)
            print(f"{t:20s} squad {len(sq):2d}  best XI {xi_rating(xi):.1f}  top: {', '.join(p['n'] + ' ' + str(p['ovr']) for p in sq[:3])}")
        return
    H, A = find_team(data, a.home), find_team(data, a.away)
    if not H or not A:
        raise SystemExit(f"unknown team: {a.home if not H else a.away}; try --teams")
    hs, as_ = data["teams"][H], data["teams"][A]
    href, hproj = best_xi(hs, a.formation), best_xi(hs, a.formation, a.home_out)
    aref, aproj = best_xi(as_, a.formation), best_xi(as_, a.formation, a.away_out)
    params = dict(LINEUP_DEFAULT, goals_per_point=a.gpp, market_awareness=a.awareness)
    print(f"{H}: reference XI {xi_rating(href):.2f} -> projected {xi_rating(hproj):.2f} (out: {', '.join(a.home_out) or 'none'})")
    print(f"{A}: reference XI {xi_rating(aref):.2f} -> projected {xi_rating(aproj):.2f} (out: {', '.join(a.away_out) or 'none'})")
    for side, xi in ((H, hproj), (A, aproj)):
        print(f"  {side} XI: " + ", ".join(f"{p['n']} ({p['p']} {p['ovr']})" for p in xi))
    if not a.odds:
        return
    r = price_lineups(*a.odds, hproj, href, aproj, aref, params)
    print(f"d_rating home {r['home']['d_rating']:+.2f} away {r['away']['d_rating']:+.2f}  | market λ {r['market_lambda_home']:.2f}-{r['market_lambda_away']:.2f} -> model {r['model_lambda_home']:.2f}-{r['model_lambda_away']:.2f}")
    for k, e in r["edges"].items():
        print(f"  {k:5s} mkt {e['market_p']*100:5.1f}%  model {e['model_p']*100:5.1f}%  @ {e['odds']:.2f}  EV {e['ev']*100:+5.1f}%  kelly {e['kelly']*100:4.1f}%")


if __name__ == "__main__":
    main()
