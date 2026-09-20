"""
Lineup desk and props desk. Same math as the browser port in after-hours.js.

LINEUP DESK
  Rate each side's projected XI (any 0-100 scale: EA FC overall, your own FCD
  score, whatever). Compare with the XI the market is assumed to be pricing
  (default: the squad's best XI). A team that is fielding a weaker XI than the
  market assumes scores less and concedes more:
      d_rating   = mean(projected XI) - mean(reference XI)
      d_lambda_own = goals_per_point * d_rating * own_share * (1 - market_awareness)
      d_lambda_opp = -goals_per_point * d_rating * (1 - own_share) * (1 - market_awareness)
  goals_per_point is the calibration constant: how many goals of expectancy one
  point of average-XI rating is worth. Default 0.10 is an ASSUMPTION (a league's
  spread of ~8 rating points between best and worst average XI mapping to ~0.8
  goals of xG difference). Fit it from results before trusting it.

PROPS DESK
  Player shot lines -> expected shots (Poisson mean that reproduces the de-vigged
  over probability) -> xG (shots x xG-per-shot by position, or per-player) ->
  team xG (listed xG divided by the share of team xG the listed players carry) -> Poisson score matrix -> 1X2,
  totals, anytime-scorer probabilities -> EV vs the main-market odds.
  Props are themselves market prices, so a book's own props rarely contradict
  its own main line; the desk blends props-implied lambdas with the market's
  implied lambdas (blend = weight on props) and is most useful cross-book or
  when props lag lineup news.
"""
import math
from model import devig, implied_lambdas, outcome_probs

XG_PER_SHOT = {"FW": 0.12, "AM": 0.10, "MF": 0.08, "WB": 0.06, "DF": 0.05, "GK": 0.01}

LINEUP_DEFAULT = {"goals_per_point": 0.10, "own_share": 0.6, "market_awareness": 0.0, "skew_flag_points": 1.5}
PROPS_DEFAULT = {"coverage": None, "blend": 0.5, "rho": -0.05}


def default_coverage(n_listed):
    """Share of a team's xG carried by the n players who have props. ASSUMPTION:
    the top shooter carries ~25% of shots and each extra listed player adds ~12%,
    capped at 95%. Override with params['coverage'] when you know it."""
    return min(0.95, 0.13 + 0.12 * max(0, n_listed))


# ---------------- lineup ----------------

def xi_rating(players):
    """players: list of dicts with 'rating' (and optional 'weight')."""
    if not players:
        return None
    w = [float(p.get("weight", 1.0)) for p in players]
    return sum(float(p["rating"]) * wi for p, wi in zip(players, w)) / sum(w)


def best_xi(squad, n=11):
    return sorted(squad, key=lambda p: -float(p["rating"]))[:n]


def lineup_adjustment(projected, reference, params=LINEUP_DEFAULT):
    d = xi_rating(projected) - xi_rating(reference)
    g = params["goals_per_point"] * (1 - params["market_awareness"])
    return {"d_rating": d, "d_lambda_own": g * d * params["own_share"], "d_lambda_opp": -g * d * (1 - params["own_share"]),
            "skewed": abs(d) >= params["skew_flag_points"]}


def price_lineups(oh, od, oa, home_proj, home_ref, away_proj, away_ref, params=LINEUP_DEFAULT, rho=-0.05):
    ph, pd, pa = devig(oh, od, oa)
    lh, la = implied_lambdas(ph, pd, pa, rho)
    H = lineup_adjustment(home_proj, home_ref, params)
    A = lineup_adjustment(away_proj, away_ref, params)
    lh2 = max(0.05, lh + H["d_lambda_own"] + A["d_lambda_opp"])
    la2 = max(0.05, la + A["d_lambda_own"] + H["d_lambda_opp"])
    pm = outcome_probs(lh2, la2, rho)
    odds = {"home": oh, "draw": od, "away": oa}
    mkt = {"home": ph, "draw": pd, "away": pa}
    edges = {k: {"model_p": pm[k], "market_p": mkt[k], "odds": o, "ev": pm[k] * o - 1, "kelly": max(0.0, (pm[k] * o - 1) / (o - 1))} for k, o in odds.items()}
    return {"market_lambda_home": lh, "market_lambda_away": la, "model_lambda_home": lh2, "model_lambda_away": la2,
            "home": H, "away": A, "model_probs": pm, "edges": edges}


# ---------------- props ----------------

def _pois_cdf(mu, k):
    return sum(math.exp(-mu) * mu ** i / math.factorial(i) for i in range(int(k) + 1))


def shots_mean_from_line(line, o_over, o_under):
    """Poisson mean mu such that P(X > line) equals the de-vigged over probability."""
    q = [1 / o_over, 1 / o_under]
    p_over = q[0] / sum(q)
    k = math.floor(line)          # over 2.5 -> X >= 3 -> 1 - CDF(2)
    lo, hi = 0.01, 15.0
    for _ in range(60):
        mu = (lo + hi) / 2
        if 1 - _pois_cdf(mu, k) < p_over:
            lo = mu
        else:
            hi = mu
    return (lo + hi) / 2


def player_xg(p):
    """p: {'name','pos', and either 'shots' or ('line','o_over','o_under'), optional 'xg_per_shot'}"""
    shots = p.get("shots")
    if shots is None:
        shots = shots_mean_from_line(float(p["line"]), float(p["o_over"]), float(p["o_under"]))
    xps = p.get("xg_per_shot") or XG_PER_SHOT.get(p.get("pos", "MF"), 0.08)
    xg = float(shots) * float(xps)
    return {"name": p.get("name", "?"), "shots": shots, "xg_per_shot": xps, "xg": xg, "p_score": 1 - math.exp(-xg)}


def team_xg(players, params=PROPS_DEFAULT):
    rows = [player_xg(p) for p in players]
    listed = sum(r["xg"] for r in rows)
    cov = params.get("coverage") or default_coverage(len(rows))
    return {"players": rows, "listed_xg": listed, "coverage": cov, "team_xg": listed / cov if cov > 0 else listed}


def price_props(oh, od, oa, home_players, away_players, params=PROPS_DEFAULT, o_over25=None, o_under25=None, scorer_odds=None):
    rho = params["rho"]
    ph, pd, pa = devig(oh, od, oa)
    lh, la = implied_lambdas(ph, pd, pa, rho)
    H, A = team_xg(home_players, params), team_xg(away_players, params)
    b = params["blend"]
    lh2 = b * H["team_xg"] + (1 - b) * lh
    la2 = b * A["team_xg"] + (1 - b) * la
    pm = outcome_probs(lh2, la2, rho)
    odds = {"home": oh, "draw": od, "away": oa}
    mkt = {"home": ph, "draw": pd, "away": pa}
    if o_over25 and o_under25:
        odds["over25"], odds["under25"] = o_over25, o_under25
        q = [1 / o_over25, 1 / o_under25]
        mkt["over25"], mkt["under25"] = q[0] / sum(q), q[1] / sum(q)
    edges = {k: {"model_p": pm[k], "market_p": mkt[k], "odds": o, "ev": pm[k] * o - 1, "kelly": max(0.0, (pm[k] * o - 1) / (o - 1))} for k, o in odds.items()}
    scorers = []
    for side, T in (("home", H), ("away", A)):
        for r in T["players"]:
            o = (scorer_odds or {}).get(r["name"])
            scorers.append({"side": side, **r, "odds": o, "ev": (r["p_score"] * o - 1) if o else None})
    return {"market_lambda_home": lh, "market_lambda_away": la, "props_xg_home": H["team_xg"], "props_xg_away": A["team_xg"],
            "model_lambda_home": lh2, "model_lambda_away": la2, "model_probs": pm, "edges": edges, "scorers": scorers}


if __name__ == "__main__":
    # Illustrative only: ratings and lines are placeholders, not real NWSL data.
    home_ref = [{"rating": r} for r in [84, 82, 81, 80, 79, 79, 78, 78, 77, 76, 75]]
    home_proj = [{"rating": r} for r in [82, 81, 80, 79, 79, 78, 78, 77, 76, 73, 71]]   # two starters out
    away_ref = [{"rating": r} for r in [80, 79, 78, 78, 77, 77, 76, 76, 75, 74, 73]]
    r = price_lineups(1.80, 3.60, 4.20, home_proj, home_ref, away_ref, away_ref)
    print("LINEUP  d_rating home %.2f -> dλ own %+.3f opp %+.3f skewed=%s" % (r["home"]["d_rating"], r["home"]["d_lambda_own"], r["home"]["d_lambda_opp"], r["home"]["skewed"]))
    for k, e in r["edges"].items():
        print(f"  {k:5s} mkt {e['market_p']:.3f} model {e['model_p']:.3f} EV {e['ev']:+.3f}")
    hp = [{"name": "H9", "pos": "FW", "line": 2.5, "o_over": 1.95, "o_under": 1.85}, {"name": "H10", "pos": "AM", "line": 1.5, "o_over": 1.80, "o_under": 2.00},
          {"name": "H7", "pos": "FW", "line": 1.5, "o_over": 2.10, "o_under": 1.72}, {"name": "H8", "pos": "MF", "line": 0.5, "o_over": 1.50, "o_under": 2.50}]
    ap = [{"name": "A9", "pos": "FW", "line": 1.5, "o_over": 2.20, "o_under": 1.65}, {"name": "A11", "pos": "FW", "line": 1.5, "o_over": 2.40, "o_under": 1.55},
          {"name": "A8", "pos": "MF", "line": 0.5, "o_over": 1.70, "o_under": 2.10}]
    r = price_props(1.80, 3.60, 4.20, hp, ap, o_over25=1.90, o_under25=1.90, scorer_odds={"H9": 2.6, "A9": 4.0})
    print("PROPS   props xG %.2f v %.2f ; market λ %.2f v %.2f ; blended %.2f v %.2f" % (r["props_xg_home"], r["props_xg_away"], r["market_lambda_home"], r["market_lambda_away"], r["model_lambda_home"], r["model_lambda_away"]))
    for k, e in r["edges"].items():
        print(f"  {k:7s} mkt {e['market_p']:.3f} model {e['model_p']:.3f} EV {e['ev']:+.3f}")
    for s in r["scorers"]:
        print(f"  {s['side']:4s} {s['name']:4s} shots {s['shots']:.2f} xG {s['xg']:.2f} P(score) {s['p_score']:.3f}" + (f" odds {s['odds']} EV {s['ev']:+.3f}" if s['odds'] else ""))
