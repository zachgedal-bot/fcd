"""
Does the closing line already price altitude? Estimate the RESIDUAL altitude
effect after the market, from historical results with closing odds.

For each match:
    (lh, la)   = goal expectancies implied by the de-vigged closing 1X2
    resid      = (HG - AG) - (lh - la)            # what the market got wrong, in goals
    x_up       = max(0, venue_alt - away_res_alt - 300) / 1000    # visitor climbing, km
    x_down     = max(0, away_res_alt - venue_alt - 1500) / 1000   # visitor descending, km
    resid = a + b_up * x_up + b_down * x_down + e

b_up is the residual goals-per-km the market leaves on the table for the home
side when a low-altitude visitor climbs. If b_up ~ 0 (t < 2), the market has
it priced; the scanner's residual_share should then be near 0.

Input: football-data.co.uk 'new' format (Country,League,Season,Date,Time,Home,
Away,HG,AG,Res,PH,PD,PA,...). Mexico file: https://www.football-data.co.uk/new/MEX.csv
Other columns names can be mapped with --cols.

    python3 backtest.py --results MEX.csv
    python3 backtest.py --synthetic 3000 --true-b-up 0.15     # recovery test, no data needed
"""
import argparse, csv, math, random
from venues import lookup
from model import devig, implied_lambdas


def ols(X, y):
    """Plain OLS with intercept; returns coefs, standard errors, n."""
    n, k = len(X), len(X[0]) + 1
    A = [[1.0] + row for row in X]
    # normal equations
    XtX = [[sum(A[i][r] * A[i][c] for i in range(n)) for c in range(k)] for r in range(k)]
    Xty = [sum(A[i][r] * y[i] for i in range(n)) for r in range(k)]
    # invert XtX (Gauss-Jordan)
    M = [row[:] + [1.0 if i == j else 0.0 for j in range(k)] for i, row in enumerate(XtX)]
    for c in range(k):
        piv = max(range(c, k), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        p = M[c][c]
        M[c] = [v / p for v in M[c]]
        for r in range(k):
            if r != c:
                f = M[r][c]
                M[r] = [a - f * b for a, b in zip(M[r], M[c])]
    inv = [row[k:] for row in M]
    beta = [sum(inv[r][c] * Xty[c] for c in range(k)) for r in range(k)]
    resid = [y[i] - sum(A[i][c] * beta[c] for c in range(k)) for i in range(n)]
    s2 = sum(e * e for e in resid) / max(1, n - k)
    se = [math.sqrt(max(0.0, s2 * inv[j][j])) for j in range(k)]
    return beta, se, n


def rows_from_results(path, cols):
    out = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            try:
                oh, od, oa = float(r[cols["ph"]]), float(r[cols["pd"]]), float(r[cols["pa"]])
                hg, ag = int(float(r[cols["hg"]])), int(float(r[cols["ag"]]))
            except (KeyError, ValueError):
                continue
            h, a = lookup(r[cols["home"]]), lookup(r[cols["away"]])
            if not h or not a:
                continue
            out.append({"home": h[0], "away": a[0], "venue_alt": h[2], "away_alt": a[2], "hg": hg, "ag": ag, "oh": oh, "od": od, "oa": oa})
    return out


def features(venue_alt, away_alt):
    return [max(0.0, venue_alt - away_alt - 300) / 1000.0, max(0.0, away_alt - venue_alt - 1500) / 1000.0]


def run(rows, rho=-0.05):
    X, y = [], []
    for r in rows:
        ph, pd, pa = devig(r["oh"], r["od"], r["oa"])
        lh, la = implied_lambdas(ph, pd, pa, rho)
        X.append(features(r["venue_alt"], r["away_alt"]))
        y.append((r["hg"] - r["ag"]) - (lh - la))
    beta, se, n = ols(X, y)
    names = ["intercept", "b_up (goals/km, visitor climbing)", "b_down (goals/km, visitor descending)"]
    print(f"n = {n} matches")
    for nm, b, s in zip(names, beta, se):
        t = b / s if s > 0 else float("nan")
        print(f"  {nm:42s} {b:+.3f}  se {s:.3f}  t {t:+.2f}")
    up = [x[0] for x in X if x[0] > 0]
    print(f"  matches with visitor climbing >300 m: {len(up)}; mean climb {sum(up)/max(1,len(up)):.2f} km")
    return beta, se


def synthetic(n, true_b_up, seed=1):
    random.seed(seed)
    teams = ["Toluca", "Pachuca", "Puebla", "America", "Cruz Azul", "Pumas UNAM", "Queretaro", "Leon", "Guadalajara", "Atlas",
             "Atletico San Luis", "Necaxa", "Juarez", "Santos Laguna", "Monterrey", "Tigres UANL", "Tijuana", "Mazatlan"]
    strength = {t: random.gauss(0, 0.25) for t in teams}
    rows = []
    for _ in range(n):
        h, a = random.sample(teams, 2)
        H, A = lookup(h), lookup(a)
        lh_true = math.exp(0.35 + strength[h] - strength[a] + 0.15)   # market's view incl. generic HA
        la_true = math.exp(0.35 + strength[a] - strength[h] - 0.15)
        fx = features(H[2], A[2])
        # reality: extra residual effect the market ignores
        lh_real = lh_true + true_b_up * fx[0] * 0.5
        la_real = max(0.05, la_true - true_b_up * fx[0] * 0.5)
        hg = sum(1 for _ in range(60) if random.random() < lh_real / 60)
        ag = sum(1 for _ in range(60) if random.random() < la_real / 60)
        # market odds from lh_true/la_true with 5% vig
        from model import outcome_probs
        p = outcome_probs(lh_true, la_true, -0.05)
        rows.append({"home": h, "away": a, "venue_alt": H[2], "away_alt": A[2], "hg": hg, "ag": ag,
                     "oh": 0.95 / p["home"], "od": 0.95 / p["draw"], "oa": 0.95 / p["away"]})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results")
    ap.add_argument("--cols", default="home=Home,away=Away,hg=HG,ag=AG,ph=PH,pd=PD,pa=PA")
    ap.add_argument("--synthetic", type=int)
    ap.add_argument("--true-b-up", type=float, default=0.15)
    a = ap.parse_args()
    cols = dict(kv.split("=") for kv in a.cols.split(","))
    if a.synthetic:
        print(f"synthetic recovery test: true b_up = {a.true_b_up}")
        run(synthetic(a.synthetic, a.true_b_up))
    elif a.results:
        run(rows_from_results(a.results, cols))
    else:
        ap.error("give --results or --synthetic")


if __name__ == "__main__":
    main()
