"""Direction-agnostic analysis of LAFC home matches (no attacking-end labels yet).

Primary sample: MLS regular season at Banc of California / BMO Stadium with fans present,
half-time score known. 2020 no-crowd matches and playoffs are reported separately.
Once data/direction_labels.csv has verified ends, run this again: the four-group
split is computed automatically for every match whose status == 'verified'.
"""
import math, pathlib
import pandas as pd, numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
m = pd.read_csv(ROOT / "data/matches.csv")
g = pd.read_csv(ROOT / "data/goals.csv")
lab = pd.read_csv(ROOT / "data/direction_labels.csv")
m = m.merge(lab[["date", "attacking_end_1h", "status"]].rename(columns={"attacking_end_1h": "end_1h", "status": "dir_status"}), on="date", how="left")

def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"), float("nan"))
    p = k / n; d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d; h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (c-h, c+h)

def rate_line(label, k, n):
    lo, hi = wilson(k, n)
    return f"| {label} | {n} | {k} | {k/n:.1%} | {lo:.1%}–{hi:.1%} |"

out = []
P = out.append
reg = m[(m.competition == "MLS") & (m.venue.str.contains("BMO")) & (m.ht_lafc.notna())].copy()
fans = reg[reg.fans.astype(str) != "False"].copy()
nofans = reg[reg.fans.astype(str) == "False"].copy()
play = m[m.competition.str.contains("Playoff|Cup Final") & m.ht_lafc.notna()].copy()
for d in (fans, nofans, play, reg):
    d["h1_total"] = d.ht_lafc + d.ht_opp
    d["h2_total"] = d.h2_lafc + d.h2_opp
    d["ft_total"] = d.ft_lafc + d.ft_opp

P("# LAFC home matches: direction-agnostic results\n")
P(f"Matches in raw file: {len(m)}. MLS regular season at BMO with HT score known: {len(reg)} "
  f"(with fans {len(fans)}, 2020 no-crowd {len(nofans)}). Playoffs/finals: {len(play)}.\n")
P("Direction labels verified: " + str((m.dir_status == "verified").sum()) + " of " + str(len(m)) + ". "
  "The four-group direction × half comparison therefore cannot be run yet; see README.\n")

P("## Half-by-half goals, MLS regular season with fans (per match)\n")
P("| Metric | 1H | 2H | Ratio 2H/1H |\n|---|---|---|---|")
for lbl, a, b in [("LAFC goals", fans.ht_lafc.mean(), fans.h2_lafc.mean()),
                  ("Opponent goals", fans.ht_opp.mean(), fans.h2_opp.mean()),
                  ("Total goals", fans.h1_total.mean(), fans.h2_total.mean())]:
    P(f"| {lbl} | {a:.3f} | {b:.3f} | {b/a:.2f} |")
P("")
P("## First-half totals: under lines (MLS regular season with fans)\n")
P("| Outcome | n | hits | rate | 95% CI |\n|---|---|---|---|---|")
n = len(fans)
P(rate_line("1H total = 0 (under 0.5)", (fans.h1_total == 0).sum(), n))
P(rate_line("1H total ≤ 1 (under 1.5)", (fans.h1_total <= 1).sum(), n))
P(rate_line("1H total ≤ 2 (under 2.5)", (fans.h1_total <= 2).sum(), n))
P(rate_line("2H total ≤ 1 (under 1.5)", (fans.h2_total <= 1).sum(), n))
P(rate_line("Full match ≤ 2 (under 2.5)", (fans.ft_total <= 2).sum(), n))
P(rate_line("LAFC scoreless in 1H", (fans.ht_lafc == 0).sum(), n))
P(rate_line("Opponent scoreless in 1H", (fans.ht_opp == 0).sum(), n))
P("")
P("## By season (MLS regular season at BMO; 2020 rows are the no-crowd games)\n")
P("| Season | n | 1H goals/match | 2H goals/match | 1H ≤1 rate | 1H = 0 rate | LAFC 1H | LAFC 2H |\n|---|---|---|---|---|---|---|---|")
for s, d in reg.groupby("season"):
    P(f"| {s} | {len(d)} | {d.h1_total.mean():.2f} | {d.h2_total.mean():.2f} | {(d.h1_total<=1).mean():.0%} | {(d.h1_total==0).mean():.0%} | {d.ht_lafc.mean():.2f} | {d.h2_lafc.mean():.2f} |")
P("")
P("## No-crowd control (2020 regular-season home games without fans)\n")
P("| Sample | n | 1H total | 2H total | 1H ≤1 rate | LAFC 1H | LAFC 2H |\n|---|---|---|---|---|---|---|")
for lbl, d in [("With fans", fans), ("No fans (2020)", nofans), ("Playoffs / finals", play)]:
    if len(d):
        P(f"| {lbl} | {len(d)} | {d.h1_total.mean():.2f} | {d.h2_total.mean():.2f} | {(d.h1_total<=1).mean():.0%} | {d.ht_lafc.mean():.2f} | {d.h2_lafc.mean():.2f} |")
P("")

# 15-minute buckets from goals with known minutes, regular season with fans
gk = g[g.date.isin(fans.date) & g.total_minute.notna()].copy()
def bucket(r):
    mm, add = r.minute, (r.added or 0) if not pd.isna(r.added) else 0
    if mm <= 15: return "0-15"
    if mm <= 30: return "16-30"
    if mm <= 45: return "31-HT (incl. stoppage)"
    if mm <= 60: return "46-60"
    if mm <= 75: return "61-75"
    return "76-FT (incl. stoppage)"
gk["bucket"] = gk.apply(bucket, axis=1)
order = ["0-15","16-30","31-HT (incl. stoppage)","46-60","61-75","76-FT (incl. stoppage)"]
tab = gk.pivot_table(index="bucket", columns="team", values="date", aggfunc="count").reindex(order).fillna(0).astype(int)
tab["total"] = tab.sum(axis=1)
P(f"## Goals by 15-minute bucket (MLS regular season with fans; {len(gk)} goals with known minutes, "
  f"{int(fans.goal_minutes_missing.sum())} goals with unknown minute excluded)\n")
P("| Bucket | LAFC | Opponent | Total | per match |\n|---|---|---|---|---|")
for b in order:
    P(f"| {b} | {tab.loc[b,'LAFC']} | {tab.loc[b,'OPP']} | {tab.loc[b,'total']} | {tab.loc[b,'total']/len(fans):.2f} |")
P("")

# 60th-minute game state (matches with all minutes known)
full = fans[fans.goal_minutes_missing == 0].copy()
rows = []
for _, r in full.iterrows():
    gg = g[(g.date == r.date)]
    before = gg[gg.total_minute <= 60]
    after = gg[gg.total_minute > 60]
    l = (before.team == "LAFC").sum(); o = (before.team == "OPP").sum()
    state = "leading" if l > o else ("tied" if l == o else "trailing")
    rows.append({"date": r.date, "state60": state, "lafc_after": (after.team == "LAFC").sum() > 0,
                 "opp_after": (after.team == "OPP").sum() > 0, "any_after": len(after) > 0,
                 "lafc_goals_after": (after.team == "LAFC").sum(), "opp_goals_after": (after.team == "OPP").sum()})
s60 = pd.DataFrame(rows)
P(f"## Game state at 60' and what happened after (MLS regular season with fans, {len(s60)} matches with every goal minute known)\n")
P("| State at 60' | n | P(LAFC scores after 60') | P(opponent scores after 60') | P(any goal after 60') | LAFC goals after 60' per match |\n|---|---|---|---|---|---|")
for st in ["trailing", "tied", "leading"]:
    d = s60[s60.state60 == st]
    if len(d):
        P(f"| {st} | {len(d)} | {d.lafc_after.mean():.0%} | {d.opp_after.mean():.0%} | {d.any_after.mean():.0%} | {d.lafc_goals_after.mean():.2f} |")
d = s60[s60.state60 != "leading"]
P(f"| tied or trailing | {len(d)} | {d.lafc_after.mean():.0%} | {d.opp_after.mean():.0%} | {d.any_after.mean():.0%} | {d.lafc_goals_after.mean():.2f} |")
P("\nThese are the baselines the direction split must beat. Splitting them by attacking end requires the label file.\n")

# Four-group split if labels exist
ver = fans[fans.dir_status == "verified"]
if len(ver):
    P("## Four-group direction × half split (verified labels only)\n")
    P("| Half | LAFC attacking | n halves | LAFC goals/half | Opp goals/half | Total/half |\n|---|---|---|---|---|---|")
    for half in (1, 2):
        for end in ("north", "south"):
            d = ver[(ver.end_1h == end) if half == 1 else (ver.end_1h != end)]
            if len(d):
                lg = d.ht_lafc if half == 1 else d.h2_lafc; og = d.ht_opp if half == 1 else d.h2_opp
                P(f"| {half}H | {end} | {len(d)} | {lg.mean():.2f} | {og.mean():.2f} | {(lg+og).mean():.2f} |")
else:
    P("## Four-group direction × half split\n\nNot computable: zero verified direction labels. The table appears here automatically once labels are added.\n")

(ROOT / "out/summary.md").write_text("\n".join(out))
print("\n".join(out))
