"""
Courtsiding EV model v2: NWSL on a continuous order book (Polymarket US LiveTrade).

Per attended match:
  gross = G * f * L * r * (1 - fee)
  net   = gross - T - R

  G   goals per match
  f   fraction of goals captured: right side available, your fill lands before
      the makers cancel/reprice, trade not voided
  L   $ of stale resting liquidity within reach per goal
  r   return per $ filled (stale price -> fair price after the goal)
  fee taker fee on Polymarket US live markets
  T   travel per match
  R   amortised risk cost (account restriction, voids, ejection, legal)

Parameters are read from params.json if present (written from the research
synthesis), else from the defaults below.
"""
import json, os, itertools, sys

DEFAULTS = {
  "goals_per_match": 2.8,
  "f_capture": {"low": 0.05, "base": 0.20, "high": 0.50},
  "L_stale_usd": {"low": 50, "base": 300, "high": 2000},
  "r_edge": {"low": 0.25, "base": 0.45, "high": 0.70},
  "fees": {"value": 0.02},
  "risk_cost_per_match_usd": {"low": 25, "base": 100, "high": 400},
}
TRAVEL = {"fly": 700, "drive_regional": 200, "local": 60}

p = DEFAULTS
if os.path.exists("params.json"):
    with open("params.json") as fh:
        p = json.load(fh)

G = p["goals_per_match"]
fee = p["fees"]["value"]

def net(f, L, r, R, T):
    gross = G * f * L * r * (1 - fee)
    return gross, gross - T - R

def be_L(f, r, R, T):
    return (T + R) / (G * f * r * (1 - fee))

print(f"G={G}  fee={fee}")
print(f"{'case':10s} {'f':>5s} {'L':>7s} {'r':>5s} {'R':>5s} | {'gross':>7s} {'net fly':>8s} {'net reg':>8s} {'net loc':>8s} | {'BE L fly':>9s}")
for case in ["low", "base", "high"]:
    f = p["f_capture"][case]; L = p["L_stale_usd"][case]; r = p["r_edge"][case]
    R = p["risk_cost_per_match_usd"][case if case != "high" else "low"]  # high case = low risk
    g, nf = net(f, L, r, R, TRAVEL["fly"])
    _, nr = net(f, L, r, R, TRAVEL["drive_regional"])
    _, nl = net(f, L, r, R, TRAVEL["local"])
    print(f"{case:10s} {f:5.2f} {L:7.0f} {r:5.2f} {R:5.0f} | {g:7.0f} {nf:8.0f} {nr:8.0f} {nl:8.0f} | {be_L(f, r, R, TRAVEL['fly']):9.0f}")

# Mixed: best-case fill and price, base liquidity (the "you're right about mechanics, but the book is thin" case)
f = p["f_capture"]["high"]; L = p["L_stale_usd"]["base"]; r = p["r_edge"]["high"]; R = p["risk_cost_per_match_usd"]["base"]
g, nf = net(f, L, r, R, TRAVEL["fly"])
print(f"{'mech-high':10s} {f:5.2f} {L:7.0f} {r:5.2f} {R:5.0f} | {g:7.0f} {nf:8.0f} {'':8s} {'':8s} | {be_L(f, r, R, TRAVEL['fly']):9.0f}")

print("\nSeason (40 flown matches), base case net:")
f = p["f_capture"]["base"]; L = p["L_stale_usd"]["base"]; r = p["r_edge"]["base"]; R = p["risk_cost_per_match_usd"]["base"]
print(f"  {40*net(f, L, r, R, TRAVEL['fly'])[1]:,.0f}")

print("\nSensitivity, net/match flying, base r and R, over f x L:")
fs = [0.1, 0.25, 0.5, 0.75]
Ls = [100, 250, 500, 1000, 2500, 5000]
print("        " + "".join(f"{L:>8d}" for L in Ls))
for f in fs:
    print(f"f={f:.2f} " + "".join(f"{net(f, L, r, R, TRAVEL['fly'])[1]:8.0f}" for L in Ls))
