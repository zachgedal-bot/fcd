"""
Market-anchored Poisson model with an altitude overlay.

Idea: the closing 1X2 line already encodes team quality, the generic home
edge and whatever altitude allowance the market makes. We (1) strip the vig,
(2) back out the goal expectancies (lambda_home, lambda_away) that reproduce
the market's 1X2, (3) apply OUR altitude adjustment scaled by `residual_share`
(the fraction of the physiological effect we believe the market has NOT
priced), and (4) re-price 1X2 and totals. The gap between step 4 and the
market is the discrepancy the scanner ranks.

residual_share = 1.0 means "the market prices altitude like any other home
game"; 0.0 means "the market prices it perfectly". The backtest estimates it.
"""
import math
from dataclasses import asdict
from physio import hir_decrement, card_deltas, DEFAULT as _PP
PHYSIO_DEFAULT = asdict(_PP)

MAX_GOALS = 10

DEFAULT_PARAMS = {
    "k_goals_per_10pct_hir": 0.35,   # total goal swing per 10% HIR lost by the visitor
    "conceded_share": 0.5,           # share of the swing that shows up as extra home goals
    "residual_share": 0.25,          # fraction of the effect the market has NOT priced
    "habituation_discount": 0.5,     # multiplier for teams whose league routinely plays at altitude
    "descending_goals": 0.15,        # extra penalty (goals) for an altitude team playing >1500 m below home
    "descending_threshold_m": 1500,
    "rho": -0.05,                    # Dixon-Coles low-score correction
    "physio": PHYSIO_DEFAULT,
}


# ---------- Poisson / Dixon-Coles machinery ----------

def _pois(lmb, k):
    return math.exp(-lmb) * lmb ** k / math.factorial(k)


def _dc_tau(x, y, lh, la, rho):
    if x == 0 and y == 0:
        return 1 - lh * la * rho
    if x == 0 and y == 1:
        return 1 + lh * rho
    if x == 1 and y == 0:
        return 1 + la * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def score_matrix(lh, la, rho=0.0):
    m = [[_pois(lh, x) * _pois(la, y) * _dc_tau(x, y, lh, la, rho) for y in range(MAX_GOALS + 1)] for x in range(MAX_GOALS + 1)]
    s = sum(sum(r) for r in m)
    return [[v / s for v in r] for r in m]


def outcome_probs(lh, la, rho=0.0):
    m = score_matrix(lh, la, rho)
    ph = sum(m[x][y] for x in range(MAX_GOALS + 1) for y in range(MAX_GOALS + 1) if x > y)
    pd = sum(m[x][x] for x in range(MAX_GOALS + 1))
    pa = 1 - ph - pd
    over25 = sum(m[x][y] for x in range(MAX_GOALS + 1) for y in range(MAX_GOALS + 1) if x + y > 2.5)
    return {"home": ph, "draw": pd, "away": pa, "over25": over25, "under25": 1 - over25}


def devig(oh, od, oa, method="power"):
    """Return fair probabilities from decimal odds. 'power' fits p_i = q_i^k with sum 1
    (handles favourite-longshot bias better than proportional)."""
    q = [1 / oh, 1 / od, 1 / oa]
    if method == "proportional":
        s = sum(q)
        return [x / s for x in q]
    lo, hi = 0.5, 2.0
    for _ in range(60):
        k = (lo + hi) / 2
        s = sum(x ** k for x in q)
        if s > 1:
            lo = k
        else:
            hi = k
    k = (lo + hi) / 2
    return [x ** k for x in q]


def implied_lambdas(ph, pd, pa, rho=0.0):
    """Find (lh, la) whose Dixon-Coles 1X2 matches (ph, pd, pa). Newton with finite
    differences from a heuristic start; falls back to a grid if it fails to converge."""
    lh = max(0.2, 1.35 + 1.2 * (ph - pa))
    la = max(0.2, 1.35 - 1.2 * (ph - pa))
    h = 1e-4
    for _ in range(40):
        p = outcome_probs(lh, la, rho)
        f1, f2 = p["home"] - ph, p["away"] - pa
        if abs(f1) < 1e-7 and abs(f2) < 1e-7:
            return lh, la
        p1 = outcome_probs(lh + h, la, rho)
        p2 = outcome_probs(lh, la + h, rho)
        j11, j12 = (p1["home"] - p["home"]) / h, (p2["home"] - p["home"]) / h
        j21, j22 = (p1["away"] - p["away"]) / h, (p2["away"] - p["away"]) / h
        det = j11 * j22 - j12 * j21
        if abs(det) < 1e-12:
            break
        dh = (-f1 * j22 + f2 * j12) / det
        da = (-f2 * j11 + f1 * j21) / det
        # damp big steps
        scale = max(1.0, abs(dh) / 0.5, abs(da) / 0.5)
        lh = max(0.05, lh + dh / scale)
        la = max(0.05, la + da / scale)
    # grid fallback
    best = (1e9, lh, la)
    for i in range(2, 45):
        for j in range(2, 45):
            gh, ga = i / 10, j / 10
            p = outcome_probs(gh, ga, rho)
            e = (p["home"] - ph) ** 2 + (p["away"] - pa) ** 2
            if e < best[0]:
                best = (e, gh, ga)
    return best[1], best[2]


# ---------- Altitude overlay ----------

def altitude_adjustment(match_alt, home_res_alt, away_res_alt, days_since_arrival,
                        home_habitual, away_habitual, params=DEFAULT_PARAMS):
    """Return dict with HIR decrements and goal adjustments for each side."""
    P = params
    phys = P.get("physio", PHYSIO_DEFAULT)
    away_dec = hir_decrement(match_alt, away_res_alt, days_since_arrival, phys)
    home_dec = hir_decrement(match_alt, home_res_alt, 1000, phys)  # home side fully adapted to own venue
    if away_habitual:
        away_dec *= P["habituation_discount"]
    if home_habitual:
        home_dec *= P["habituation_discount"]

    swing_from_away = P["k_goals_per_10pct_hir"] * away_dec / 10.0
    swing_from_home = P["k_goals_per_10pct_hir"] * home_dec / 10.0

    d_home = swing_from_away * P["conceded_share"] - swing_from_home * (1 - P["conceded_share"])
    d_away = -swing_from_away * (1 - P["conceded_share"]) + swing_from_home * P["conceded_share"]

    desc_away = away_res_alt - match_alt > P["descending_threshold_m"]
    desc_home = home_res_alt - match_alt > P["descending_threshold_m"]
    if desc_away:
        d_away -= P["descending_goals"]
    if desc_home:
        d_home -= P["descending_goals"]

    r = P["residual_share"]
    return {
        "away_hir_dec_pct": away_dec, "home_hir_dec_pct": home_dec,
        "d_lambda_home_full": d_home, "d_lambda_away_full": d_away,
        "d_lambda_home": d_home * r, "d_lambda_away": d_away * r,
        "away_descending": desc_away, "home_descending": desc_home,
    }


def price_fixture(oh, od, oa, match_alt, home_res_alt, away_res_alt, days_since_arrival=1,
                  home_habitual=False, away_habitual=False, params=DEFAULT_PARAMS,
                  o_over25=None, o_under25=None):
    rho = params["rho"]
    ph, pd, pa = devig(oh, od, oa)
    lh, la = implied_lambdas(ph, pd, pa, rho)
    adj = altitude_adjustment(match_alt, home_res_alt, away_res_alt, days_since_arrival,
                              home_habitual, away_habitual, params)
    lh2 = max(0.05, lh + adj["d_lambda_home"])
    la2 = max(0.05, la + adj["d_lambda_away"])
    pm = outcome_probs(lh2, la2, rho)
    mkt = {"home": ph, "draw": pd, "away": pa}
    odds = {"home": oh, "draw": od, "away": oa}
    if o_over25 and o_under25:
        odds["over25"], odds["under25"] = o_over25, o_under25
        q = [1 / o_over25, 1 / o_under25]
        mkt["over25"], mkt["under25"] = q[0] / sum(q), q[1] / sum(q)
    edges = {}
    for k, o in odds.items():
        ev = pm[k] * o - 1
        kelly = max(0.0, (pm[k] * o - 1) / (o - 1)) if o > 1 else 0.0
        edges[k] = {"model_p": pm[k], "market_p": mkt.get(k), "odds": o, "ev": ev, "kelly": kelly}
    return {
        "market_lambda_home": lh, "market_lambda_away": la,
        "model_lambda_home": lh2, "model_lambda_away": la2,
        "model_probs": pm, "market_probs": mkt, "edges": edges, "adjustment": adj,
    }


if __name__ == "__main__":
    # Pachuca (2430 m) v Tijuana (20 m), ML -135/+280/+350 -> 1.74/3.80/4.50
    r = price_fixture(1.74, 3.80, 4.50, 2430, 2430, 20, 1, True, True)
    print("market lambdas", round(r["market_lambda_home"], 2), round(r["market_lambda_away"], 2))
    print("model  lambdas", round(r["model_lambda_home"], 2), round(r["model_lambda_away"], 2))
    for k, e in r["edges"].items():
        print(f"{k:7s} model {e['model_p']:.3f} market {e['market_p']:.3f} odds {e['odds']:.2f} EV {e['ev']:+.3f} kelly {e['kelly']:.3f}")
