"""
Match Cards: real FC ratings + Altitude FC physiology + the market.

    python3 match_cards.py --home "Utah Royals FC" --away "KC Current" --odds 2.60 3.40 2.60 --days 1
    python3 match_cards.py --home "Utah Royals FC" --away "KC Current" --odds 2.60 3.40 2.60 --away-out "Debinha"

For each side: best XI from fc_ratings_nwsl.json (formation-aware), team card =
XI averages of PAC/SHO/PAS/DRI/DEF/PHY and OVR; the visitor's card is adjusted
by the Altitude FC rating layer for the venue altitude vs its home altitude and
days since arrival (sensitivity = rating points per 1 % physiological change).
The adjusted-OVR gap vs the reference (unadjusted best XI) becomes a goal shift
through goals_per_point, exactly like the Lineup Desk, and is priced vs the 1X2.
Venue altitude comes from venues.py unless --venue-alt is given.
"""
import argparse
from lineup_desk import load_ratings, find_team, best_xi, FORMATIONS
from lineup_props import price_lineups, xi_rating, LINEUP_DEFAULT
from physio import card_deltas
from venues import lookup

FACE = ["pac", "sho", "pas", "dri", "def", "phy"]
# how the Altitude FC card categories map onto the six face stats of a real card
FACE_FROM_CARD = {"pac": "PAC", "def": "DEF", "phy": "PHY", "sho": None, "pas": None, "dri": None}
# how much each face stat contributes to team OVR change (ASSUMPTION: physical stats
# carry the altitude effect; OVR for an outfield XI moves ~0.6 of the STAMINA/PHY delta)
OVR_WEIGHTS = {"pac": 0.15, "sho": 0.0, "pas": 0.0, "dri": 0.0, "def": 0.15, "phy": 0.30, "STAMINA": 0.40}


def team_card(xi):
    card = {k: sum(p[k] for p in xi) / len(xi) for k in FACE}
    card["ovr"] = xi_rating(xi)
    return card


def adjusted_card(card, match_alt, home_alt, days, sensitivity):
    from altitude_model import RatingParams
    eff, deltas = card_deltas(match_alt, home_alt, days, None, RatingParams(sensitivity=sensitivity))
    adj = dict(card)
    for face, cat in FACE_FROM_CARD.items():
        if cat and deltas[cat]["delta"] is not None:
            adj[face] = card[face] + deltas[cat]["delta"]
    d_ovr = sum(OVR_WEIGHTS[f] * (adj[f] - card[f]) for f in ("pac", "def", "phy")) + OVR_WEIGHTS["STAMINA"] * (deltas["STAMINA"]["delta"] or 0)
    adj["ovr"] = card["ovr"] + d_ovr
    return adj, eff, deltas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", required=True); ap.add_argument("--away", required=True)
    ap.add_argument("--odds", nargs=3, type=float, metavar=("H", "D", "A"))
    ap.add_argument("--days", type=float, default=1); ap.add_argument("--venue-alt", type=float)
    ap.add_argument("--home-out", nargs="*", default=[]); ap.add_argument("--away-out", nargs="*", default=[])
    ap.add_argument("--formation", default="4-3-3", choices=list(FORMATIONS))
    ap.add_argument("--sensitivity", type=float, default=0.4)
    ap.add_argument("--gpp", type=float, default=LINEUP_DEFAULT["goals_per_point"])
    a = ap.parse_args()
    data = load_ratings()
    H, A = find_team(data, a.home), find_team(data, a.away)
    if not H or not A:
        raise SystemExit("unknown team; see lineup_desk.py --teams")
    vh, va = lookup(H), lookup(A)
    venue_alt = a.venue_alt if a.venue_alt is not None else (vh[2] if vh else 0)
    home_alt, away_alt = (vh[2] if vh else 0), (va[2] if va else 0)
    sides = {}
    for side, T, outs, res_alt in (("home", H, a.home_out, home_alt), ("away", A, a.away_out, away_alt)):
        sq = data["teams"][T]
        ref, proj = best_xi(sq, a.formation), best_xi(sq, a.formation, outs)
        card_ref, card_proj = team_card(ref), team_card(proj)
        adj, eff, deltas = adjusted_card(card_proj, venue_alt, res_alt, a.days, a.sensitivity)
        sides[side] = dict(team=T, ref=ref, proj=proj, card_ref=card_ref, card_proj=card_proj, card_adj=adj, eff=eff, deltas=deltas, res_alt=res_alt)
        print(f"{side.upper():4s} {T:18s} home {res_alt:.0f} m -> venue {venue_alt:.0f} m, day {a.days:.0f}")
        print("     " + " ".join(f"{k.upper()} {card_ref[k]:.1f}" for k in FACE) + f"  OVR {card_ref['ovr']:.2f}   (reference XI)")
        print("     " + " ".join(f"{k.upper()} {card_proj[k]:.1f}" for k in FACE) + f"  OVR {card_proj['ovr']:.2f}   (projected XI, out: {', '.join(outs) or 'none'})")
        print("     " + " ".join(f"{k.upper()} {adj[k]:.1f}" for k in FACE) + f"  OVR {adj['ovr']:.2f}   (altitude-adjusted: HIR {eff['high_intensity_running']['pct']:+.1f}%, STAMINA {deltas['STAMINA']['delta']:+.1f})")
    if not a.odds:
        return
    # price: projected+adjusted OVR vs reference OVR, through the lineup model
    params = dict(LINEUP_DEFAULT, goals_per_point=a.gpp)
    fake = lambda ovr: [{"rating": ovr}] * 11
    r = price_lineups(*a.odds, fake(sides["home"]["card_adj"]["ovr"]), fake(sides["home"]["card_ref"]["ovr"]),
                      fake(sides["away"]["card_adj"]["ovr"]), fake(sides["away"]["card_ref"]["ovr"]), params)
    print(f"d_ovr home {r['home']['d_rating']:+.2f} away {r['away']['d_rating']:+.2f} | market λ {r['market_lambda_home']:.2f}-{r['market_lambda_away']:.2f} -> model {r['model_lambda_home']:.2f}-{r['model_lambda_away']:.2f}")
    for k, e in r["edges"].items():
        print(f"  {k:5s} mkt {e['market_p']*100:5.1f}%  model {e['model_p']*100:5.1f}%  @ {e['odds']:.2f}  EV {e['ev']*100:+5.1f}%  kelly {e['kelly']*100:4.1f}%")


if __name__ == "__main__":
    main()
