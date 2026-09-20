"""
Altitude discrepancy scanner.

    python3 scan.py --fixtures fixtures_demo.csv [--params params.json] [--residual 0.5]
                    [--k 0.3] [--min-diff 800] [--out scan_output]

Fixtures CSV columns (header required):
    date, league, home, away, odds_h, odds_d, odds_a, [odds_over25, odds_under25],
    [days_since_arrival], [venue_alt], [note]
Rows without odds are still scanned: the altitude adjustment is shown and the
row is flagged 'needs odds'.
"""
import argparse, csv, json, os, sys
from venues import lookup, is_habitual
from model import price_fixture, altitude_adjustment, DEFAULT_PARAMS


def load_params(path):
    p = json.loads(json.dumps(DEFAULT_PARAMS))
    if path and os.path.exists(path):
        with open(path) as fh:
            user = json.load(fh)
        for k, v in user.items():
            if k == "physio" and isinstance(v, dict):
                p["physio"].update(v)
            else:
                p[k] = v
    return p


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def scan_row(row, params, min_diff):
    home = lookup(row["home"]); away = lookup(row["away"])
    if not home or not away:
        return {"skip": f"unknown team: {row['home'] if not home else row['away']}"}
    hname, hcity, halt, hlg = home
    aname, acity, aalt, alg = away
    venue_alt = _f(row.get("venue_alt")) or halt
    days = _f(row.get("days_since_arrival"))
    days = 1 if days is None else days
    diff = venue_alt - aalt
    if abs(diff) < min_diff and abs(venue_alt - halt) < min_diff:
        return {"skip": f"altitude differential {diff:+.0f} m below {min_diff} m"}
    oh, od, oa = _f(row.get("odds_h")), _f(row.get("odds_d")), _f(row.get("odds_a"))
    o25, u25 = _f(row.get("odds_over25")), _f(row.get("odds_under25"))
    base = {
        "date": row["date"], "league": row.get("league", ""), "home": hname, "away": aname,
        "venue_alt": venue_alt, "home_res_alt": halt, "away_res_alt": aalt, "alt_diff": diff,
        "days_since_arrival": days, "note": row.get("note", ""),
    }
    if not (oh and od and oa):
        adj = altitude_adjustment(venue_alt, halt, aalt, days, is_habitual(hlg), is_habitual(alg), params)
        base.update({"needs_odds": True, "adjustment": adj})
        return base
    r = price_fixture(oh, od, oa, venue_alt, halt, aalt, days, is_habitual(hlg), is_habitual(alg), params, o25, u25)
    best = max(r["edges"].items(), key=lambda kv: kv[1]["ev"])
    base.update({"needs_odds": False, "result": r, "best_side": best[0], "best_ev": best[1]["ev"], "best_kelly": best[1]["kelly"]})
    return base


def fmt_table(rows):
    out = []
    hdr = f"{'date':10s} {'match':42s} {'diff':>6s} {'awayHIR':>7s} {'dλH':>6s} {'dλA':>6s} | {'H mkt→mod':>11s} {'D mkt→mod':>11s} {'A mkt→mod':>11s} | {'best':>6s} {'EV%':>6s} {'kelly':>5s}"
    out.append(hdr); out.append("-" * len(hdr))
    for r in rows:
        match = f"{r['home']} v {r['away']}"[:42]
        if r.get("needs_odds"):
            a = r["adjustment"]
            out.append(f"{r['date']:10s} {match:42s} {r['alt_diff']:+6.0f} {a['away_hir_dec_pct']:7.1f} {a['d_lambda_home']:+6.2f} {a['d_lambda_away']:+6.2f} | {'needs odds':>37s} |")
            continue
        res = r["result"]; a = res["adjustment"]; e = res["edges"]
        def pair(k):
            return f"{e[k]['market_p']*100:4.1f}→{e[k]['model_p']*100:4.1f}"
        out.append(f"{r['date']:10s} {match:42s} {r['alt_diff']:+6.0f} {a['away_hir_dec_pct']:7.1f} {a['d_lambda_home']:+6.2f} {a['d_lambda_away']:+6.2f} | {pair('home'):>11s} {pair('draw'):>11s} {pair('away'):>11s} | {r['best_side']:>6s} {r['best_ev']*100:+6.1f} {r['best_kelly']*100:5.1f}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", required=True)
    ap.add_argument("--params", default="params.json")
    ap.add_argument("--residual", type=float)
    ap.add_argument("--k", type=float)
    ap.add_argument("--min-diff", type=float, default=800)
    ap.add_argument("--out", default="scan_output")
    args = ap.parse_args()
    params = load_params(args.params)
    if args.residual is not None:
        params["residual_share"] = args.residual
    if args.k is not None:
        params["k_goals_per_10pct_hir"] = args.k

    with open(args.fixtures, newline="") as fh:
        rows = list(csv.DictReader(fh))
    scanned, skipped = [], []
    for row in rows:
        r = scan_row(row, params, args.min_diff)
        (skipped if "skip" in r else scanned).append((row, r))
    priced = sorted([r for _, r in scanned if not r["needs_odds"]], key=lambda r: -abs(r["best_ev"]))
    unpriced = sorted([r for _, r in scanned if r["needs_odds"]], key=lambda r: -abs(r["adjustment"]["d_lambda_away"]) - abs(r["adjustment"]["d_lambda_home"]))
    ordered = priced + unpriced

    print(f"params: residual_share={params['residual_share']} k={params['k_goals_per_10pct_hir']} habituation={params['habituation_discount']} descending={params['descending_goals']}")
    print(fmt_table(ordered))
    for row, r in skipped:
        print(f"skipped {row['home']} v {row['away']}: {r['skip']}")

    with open(args.out + ".json", "w") as fh:
        json.dump({"params": params, "rows": ordered}, fh, indent=1, default=str)
    with open(args.out + ".md", "w") as fh:
        fh.write("```\n" + fmt_table(ordered) + "\n```\n")
    with open(args.out + ".csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "league", "home", "away", "venue_alt", "away_res_alt", "alt_diff", "days", "away_hir_dec_pct",
                    "d_lambda_home", "d_lambda_away", "mkt_h", "mkt_d", "mkt_a", "mod_h", "mod_d", "mod_a", "best_side", "best_ev", "best_kelly", "note"])
        for r in ordered:
            if r["needs_odds"]:
                a = r["adjustment"]
                w.writerow([r["date"], r["league"], r["home"], r["away"], r["venue_alt"], r["away_res_alt"], r["alt_diff"], r["days_since_arrival"],
                            round(a["away_hir_dec_pct"], 2), round(a["d_lambda_home"], 3), round(a["d_lambda_away"], 3)] + [""] * 9 + [r["note"]])
            else:
                res = r["result"]; a = res["adjustment"]; e = res["edges"]
                w.writerow([r["date"], r["league"], r["home"], r["away"], r["venue_alt"], r["away_res_alt"], r["alt_diff"], r["days_since_arrival"],
                            round(a["away_hir_dec_pct"], 2), round(a["d_lambda_home"], 3), round(a["d_lambda_away"], 3),
                            round(e["home"]["market_p"], 4), round(e["draw"]["market_p"], 4), round(e["away"]["market_p"], 4),
                            round(e["home"]["model_p"], 4), round(e["draw"]["model_p"], 4), round(e["away"]["model_p"], 4),
                            r["best_side"], round(r["best_ev"], 4), round(r["best_kelly"], 4), r["note"]])


if __name__ == "__main__":
    main()
