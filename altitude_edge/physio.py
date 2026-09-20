"""
Physiology layer: high-intensity running (HIR) decrement for a team playing
above its residence altitude.

Anchors (from the Altitude FC evidence table):
  * VO2max falls ~6.3% per 1000 m in trained athletes (Wehrlin & Hallen 2006).
  * Sea-level youth internationals at 1600 m, day 4: high-velocity running -15%,
    total distance -9% (Garvican et al. 2014).
  * Professionals at 1200-1750 m: total distance -3.1% (Nassis 2013).
  * Sea-level natives at 3600 m: large day-1 impairment; HIR not back to
    near-sea-level by day 13 (Buchheit et al. 2013, ISA3600).
  * Cyclists at 2340 m: VO2max -12.8% day 1, ~4%/week recovery to day 14,
    no further gain to day 21 (Schuler et al. 2007).
  * Bartsch/Saltin/Dvorak 2008: 500-2000 m 'minor, detectable' impairment.

Model:
  delta_eff = max(0, match_alt - residence_alt - threshold)
  hir_day0  = pct_per_1000 * delta_eff / 1000
  remaining(d) = never + fast * exp(-d / tau_fast) + slow * exp(-d / tau_slow)
  hir_dec(d) = hir_day0 * remaining(d)           (percent of HIR lost)

Calibration with defaults: sea-level team at 3600 m -> -12.6% on day 1,
-6.4% on day 14; at 1600 m on day 4 -> -4.5%; coastal club at Toluca, day
before -> -10.0%. Every number here is an ASSUMPTION calibrated to the
anchors above, not a measurement.
"""
import math

DEFAULT = {
    "threshold_m": 300,      # below this differential, no detectable effect
    "pct_per_1000": 5.4,     # % HIR lost per 1000 m of effective differential on arrival
    "never": 0.35,           # share not recovered within 2 weeks
    "fast": 0.40, "tau_fast": 2.0,
    "slow": 0.25, "tau_slow": 10.0,
    "max_pct": 30.0,
}


def remaining(days, p=DEFAULT):
    d = max(0.0, float(days))
    return p["never"] + p["fast"] * math.exp(-d / p["tau_fast"]) + p["slow"] * math.exp(-d / p["tau_slow"])


def hir_decrement(match_alt, residence_alt, days_since_arrival=1, p=DEFAULT):
    """Percent of high-intensity running lost (positive number = worse)."""
    delta = max(0.0, float(match_alt) - float(residence_alt) - p["threshold_m"])
    day0 = p["pct_per_1000"] * delta / 1000.0
    return min(p["max_pct"], day0 * remaining(days_since_arrival, p))


if __name__ == "__main__":
    for label, m, r, d in [
        ("sea level -> 3600 m, day 1", 3600, 430, 1),
        ("sea level -> 3600 m, day 14", 3600, 430, 14),
        ("sea level -> 1600 m, day 4", 1600, 0, 4),
        ("coast -> Toluca, day before", 2670, 10, 1),
        ("Monterrey -> Toluca, day before", 2670, 540, 1),
        ("Mexico City -> Toluca, day before", 2670, 2240, 1),
        ("Tijuana -> Pachuca, day before", 2430, 20, 1),
        ("Buenos Aires -> El Alto, same day", 4090, 25, 0),
        ("Buenos Aires -> El Alto, day 7", 4090, 25, 7),
    ]:
        print(f"{label:40s} HIR -{hir_decrement(m, r, d):5.1f}%")
