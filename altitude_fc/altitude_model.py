"""
Altitude FC — physiological effect model + illustrative rating conversion.

TWO LAYERS, KEPT SEPARATE
  1. PHYSIOLOGY LAYER  -> % change in measurable quantities relative to the
     team's performance in ITS OWN USUAL ENVIRONMENT (home training altitude):
       vo2max, high_intensity_running, repeated_sprint_recovery,
       single_sprint_speed, technical_execution (None), decision_making (None)
     Inputs: match altitude, team's usual training altitude, days since arrival.
     Every parameter names the evidence row(s) in evidence_table.csv that
     motivate it, or is flagged ASSUMPTION.
  2. RATING LAYER -> FC-style card deltas from a fixed baseline of 80.
     Display convention only. A 10 % physiological change is NOT a 10 % rating
     change; the mapping is an adjustable 'points per 1 %' sensitivity with a cap.

BASELINE CONVENTION
  Both teams start at 80 in every category = 'equal ability, each measured in
  its own usual environment'. So an altitude-resident team playing at its home
  altitude shows ~0 change (smaller decline), NOT a bonus. Whether a resident
  team IMPROVES above baseline when descending to sea level is a separate
  question the evidence does not settle (E06, E12, E15) -> reported as
  'insufficient evidence', modelled as 0.

Nothing here is an official EA rating or a validated player measurement.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import math, json

# ---------------------------------------------------------------------------
# 1. PHYSIOLOGY LAYER
# ---------------------------------------------------------------------------
@dataclass
class PhysParams:
    # Aerobic ceiling. E18 (Wehrlin & Hallén 2006): -6.3 % VO2max per 1000 m,
    # linear, measurable from ~300 m upward; individual range 4.6-7.5 %/1000 m.
    vo2max_pct_per_1000m: float = 6.3
    vo2max_threshold_m: float = 300.0
    # ACUTE (day-0/1, unacclimatised) match high-intensity running deficit,
    # expressed as a fraction of the VO2max deficit. ASSUMPTION = 0.7, chosen so
    # the model sits between the two soccer anchors:
    #   E04 Nassis 2013: -3.1 % total distance at 1200-1750 m (pros, some days on site)
    #   E03 Garvican 2014 / E31: -9 % total, -15 % high-velocity at 1600 m on day 4 (youth)
    # With 0.7 the model gives about -3.5 % HIR at 1600 m on day 4 (see check()).
    hir_per_vo2_fraction: float = 0.7
    # Repeated-sprint recovery deficit as a fraction of VO2max deficit.
    # ASSUMPTION = 0.3, bounded by E24 (Townsend 2020: -2.6 % mean sprint distance
    # over 8 sprints at ~3600 m-equivalent, n.s. at ~1900 m-equivalent), E23
    # (Goods 2014: later-set power reduced at all simulated altitudes >= 2000 m),
    # E22 (Balsom 1994: greater fatigue at ~3000 m-equivalent). Matches accumulate
    # far more repeated efforts than an 8-sprint test, so 0.3 x 20.8 % = -6 % at
    # 3600 m acute is a deliberate middle estimate.
    rsa_per_vo2_fraction: float = 0.3
    # Single maximal sprint: air density. E26 (Linthorne 2016): 100 m ~1.9 %
    # faster at 2250 m; E27 (Hollings 2012) about half that. Soccer sprints are
    # 10-30 m (acceleration-dominated, less drag benefit), and E04 found no top-speed
    # change in matches. ASSUMPTION: +0.3 % top speed per 1000 m; no acclimatisation.
    sprint_pct_per_1000m: float = 0.3
    # Acclimatisation: fraction of the ACUTE deficit recovered after d days.
    # Fast phase (ventilation, plasma volume; E03 HR back to baseline ~day 5,
    # E06 CaO2 stabilises within days) + slow phase (Hb mass ~+3 % in 12 d, E06;
    # +4 % in 18 d, E09). Calibrated to E19 (Schuler 2007: VO2max -12.8 % day 1,
    # roughly half recovered by day 14, no further gain to day 21) and E02/E06
    # (2 weeks insufficient at 3600 m for sea-level natives). ASSUMPTION values:
    acclim_fast_tau_days: float = 3.5
    acclim_fast_fraction: float = 0.40
    acclim_slow_tau_days: float = 21.0
    acclim_slow_fraction: float = 0.25
    # -> residual 0.35 of the acute deficit is never recovered by a sea-level native
    #    at that altitude (consistent with E20: residents' VO2max still ~15 % lower
    #    at 2000 m than at sea level, and E01: lifelong residence does not remove
    #    the match-running deficit relative to sea level).
    # Individual spread: E18 individual slopes 4.6-7.5 %/1000 m around 6.3 -> about
    # +/-25 % of the mean; E08/E09/E30 show responder heterogeneity. Used only for
    # an illustrative 'typical spread' band, never a confidence interval.
    individual_spread_fraction: float = 0.25


def acclimatization_fraction(days: float, p: PhysParams) -> float:
    if days <= 0:
        return 0.0
    fast = p.acclim_fast_fraction * (1 - math.exp(-days / p.acclim_fast_tau_days))
    slow = p.acclim_slow_fraction * (1 - math.exp(-days / p.acclim_slow_tau_days))
    return fast + slow


def vo2_deficit_pct(alt_m: float, p: PhysParams) -> float:
    """VO2max at alt_m relative to sea level, in % (negative = lower). E18."""
    excess = max(0.0, alt_m - p.vo2max_threshold_m)
    return -p.vo2max_pct_per_1000m * excess / 1000.0


def phys_effects(match_alt_m: float, home_alt_m: float, days_since_arrival: float,
                 p: PhysParams | None = None) -> dict:
    """% changes relative to the SAME team's performance at its home altitude."""
    p = p or PhysParams()
    # Chronic aerobic ceiling at each altitude vs sea level (E18)
    vo2_match = vo2_deficit_pct(match_alt_m, p)
    vo2_home = vo2_deficit_pct(home_alt_m, p)
    # The NEW hypoxic load is the part of the match-altitude deficit the team is
    # not already adapted to. A fully adapted resident carries residual_fraction
    # of its home-altitude deficit as its 'normal' -> that is inside its baseline.
    residual = 1.0 - p.acclim_fast_fraction - p.acclim_slow_fraction
    if match_alt_m > home_alt_m + 1e-9:
        # ascending: acute deficit on the altitude difference, decaying with days
        delta_vo2_acute = vo2_match - vo2_home          # negative
        acclim = acclimatization_fraction(days_since_arrival, p)
        remaining = 1.0 - acclim                        # 1 -> 0.35 asymptotically
        vo2_eff = delta_vo2_acute * remaining
        status = "ascending"
    else:
        # descending or same altitude: no acute hypoxic penalty. A resident going
        # DOWN gains oxygen availability, but soccer evidence does not show a
        # performance gain (E06 [Hb] falls at sea level; E12/E15 match data) ->
        # modelled as 0 and flagged.
        acclim = 1.0
        vo2_eff = 0.0
        status = "descending_or_home" if match_alt_m < home_alt_m - 1e-9 else "home"
    hir = p.hir_per_vo2_fraction * vo2_eff
    rsa = p.rsa_per_vo2_fraction * vo2_eff
    sprint = p.sprint_pct_per_1000m * (match_alt_m - home_alt_m) / 1000.0  # physics, both directions

    spread = p.individual_spread_fraction
    def band(x):
        return None if x is None else (round(x * (1 + spread), 2), round(x * (1 - spread), 2))

    out = {
        "vo2max": {"pct": round(vo2_eff, 2), "spread": band(vo2_eff),
                   "label": "Aerobic ceiling (VO2max) vs home altitude",
                   "basis": "measured slope, endurance athletes (E18); acclimatisation curve calibrated to E19/E02/E06",
                   "evidence": ["E18", "E19", "E15", "E20"]},
        "high_intensity_running": {"pct": round(hir, 2), "spread": band(hir),
                   "label": "High-intensity running in matches",
                   "basis": "soccer match GPS anchors (E03, E04, E01) + ASSUMPTION hir_per_vo2_fraction",
                   "evidence": ["E01", "E03", "E04", "E31", "E02"]},
        "repeated_sprint_recovery": {"pct": round(rsa, 2), "spread": band(rsa),
                   "label": "Recovery between repeated sprints",
                   "basis": "team-sport / lab repeated-sprint studies, mostly SIMULATED altitude + ASSUMPTION rsa_per_vo2_fraction",
                   "evidence": ["E22", "E23", "E24", "E25", "E16"]},
        "single_sprint_speed": {"pct": round(sprint, 2), "spread": None,
                   "label": "Single maximal sprint / top speed",
                   "basis": "air density (E26, E27); soccer top speed unchanged in matches (E04)",
                   "evidence": ["E26", "E27", "E04", "E02"]},
        "technical_execution": {"pct": None, "spread": None,
                   "label": "Passing / first touch accuracy",
                   "basis": "insufficient evidence for a decline: pass completion ROSE (behavioural, E13); goals/GK errors unchanged (E04). Ball flight changes handled separately.",
                   "evidence": ["E13", "E04", "E16"]},
        "decision_making": {"pct": None, "spread": None,
                   "label": "Decision-making / reaction time",
                   "basis": "insufficient evidence in soccer; lab meta-analysis shows moderate cognitive impairment only when PaO2 is low (E28), mostly above ~3000 m; risk-averse passing observed (E13)",
                   "evidence": ["E28", "E13"]},
        "_meta": {"status": status, "acclim_fraction": round(acclim, 3),
                  "vo2_match_vs_sea_level": round(vo2_match, 2), "vo2_home_vs_sea_level": round(vo2_home, 2),
                  "residual_fraction": residual,
                  "sleep_recovery_flag": (status == "ascending" and match_alt_m - home_alt_m >= 1500 and days_since_arrival < 14),
                  "descent_bonus": "insufficient evidence" if status == "descending_or_home" else None},
    }
    return out


# ---------------------------------------------------------------------------
# 2. RATING LAYER (illustrative display convention)
# ---------------------------------------------------------------------------
@dataclass
class RatingParams:
    baseline: int = 80
    sensitivity: float = 0.4     # rating points per 1 % physiological change (ASSUMPTION)
    max_delta: float = 15.0
    weights: dict = field(default_factory=lambda: {
        "PAC": {"single_sprint_speed": 0.5, "repeated_sprint_recovery": 0.5},
        "SHO": {},
        "PAS": {},
        "DRI": {},
        "DEF": {"high_intensity_running": 0.5, "repeated_sprint_recovery": 0.5},
        "PHY": {"vo2max": 0.3, "high_intensity_running": 0.7},
        "STAMINA": {"vo2max": 0.4, "high_intensity_running": 0.6},
        "REPEATED_EFFORT": {"repeated_sprint_recovery": 1.0},
        "SPRINT_SPEED": {"single_sprint_speed": 1.0},
    })


def ratings_from_phys(eff: dict, rp: RatingParams | None = None) -> dict:
    rp = rp or RatingParams()
    cards = {}
    for cat, w in rp.weights.items():
        if not w:
            cards[cat] = {"baseline": rp.baseline, "adjusted": None, "delta": None,
                          "status": "insufficient evidence", "inputs": {}}
            continue
        pct, inputs = 0.0, {}
        for q, wt in w.items():
            v = eff[q]["pct"]
            if v is None:
                continue
            pct += wt * v
            inputs[q] = v
        delta = max(-rp.max_delta, min(rp.max_delta, rp.sensitivity * pct))
        cards[cat] = {"baseline": rp.baseline, "adjusted": int(round(rp.baseline + delta)),
                      "delta": round(delta, 1), "weighted_pct": round(pct, 2),
                      "status": "modelled", "inputs": inputs}
    return cards


def scenario(match_alt_m, home_alt_m, days, pp=None, rp=None):
    eff = phys_effects(match_alt_m, home_alt_m, days, pp)
    return {"match_alt_m": match_alt_m, "home_alt_m": home_alt_m, "days": days,
            "physiology": eff, "ratings": ratings_from_phys(eff, rp)}


# ---------------------------------------------------------------------------
# 3. BALL FLIGHT (physics, separate from physiology)
# ---------------------------------------------------------------------------
def air_density(alt_m: float) -> float:
    """ISA troposphere density, kg/m^3."""
    return 1.225 * (1 - 2.25577e-5 * alt_m) ** 4.2559


def ball_flight(alt_m: float, v0=25.0, angle_deg=20.0, spin_lift_coeff=0.0, cd=0.25,
                mass=0.43, diameter=0.22, dt=0.001) -> dict:
    """Simple point-mass trajectory with quadratic drag (and optional Magnus-like
    lift proportional to air density). Returns range (m) and flight time (s).
    Physics illustration only (E29, E16): drag and lift scale with air density."""
    rho = air_density(alt_m)
    A = math.pi * (diameter / 2) ** 2
    k = 0.5 * rho * A / mass
    x, y = 0.0, 0.0
    vx, vy = v0 * math.cos(math.radians(angle_deg)), v0 * math.sin(math.radians(angle_deg))
    t = 0.0
    while True:
        v = math.hypot(vx, vy)
        ax = -k * cd * v * vx - k * spin_lift_coeff * v * vy
        ay = -9.81 - k * cd * v * vy + k * spin_lift_coeff * v * vx
        vx += ax * dt; vy += ay * dt
        x += vx * dt; y += vy * dt; t += dt
        if y < 0:
            break
    return {"alt_m": alt_m, "rho": round(rho, 3), "range_m": round(x, 2), "flight_s": round(t, 2)}


def check():
    """Anchor checks used in the write-up."""
    p = PhysParams()
    return {
        "hir_1600m_day4_model_pct": round(phys_effects(1600, 0, 4, p)["high_intensity_running"]["pct"], 2),
        "hir_1500m_day3_model_pct": round(phys_effects(1500, 0, 3, p)["high_intensity_running"]["pct"], 2),
        "vo2_2340m_day1_model_pct": round(phys_effects(2340, 0, 1, p)["vo2max"]["pct"], 2),
        "vo2_2340m_day14_model_pct": round(phys_effects(2340, 0, 14, p)["vo2max"]["pct"], 2),
        "acclim_day14": round(acclimatization_fraction(14, p), 3),
        "hir_3600m_day1_model_pct": round(phys_effects(3600, 0, 1, p)["high_intensity_running"]["pct"], 2),
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=1))
