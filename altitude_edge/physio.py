"""
Physiology layer for the edge model = the Altitude FC model (altitude_fc/altitude_model.py).

phys_effects(match_alt, home_alt, days) gives % changes vs the same team at its
home altitude: vo2max, high_intensity_running, repeated_sprint_recovery,
single_sprint_speed (technical/decision = insufficient evidence). The rating
layer (ratings_from_phys) turns those into FC-style card deltas with an
adjustable sensitivity. Parameters and evidence IDs live in altitude_model.py
and altitude_fc/evidence_table.csv.

hir_decrement() keeps the old signature used by model.py: positive percent of
high-intensity running lost.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "altitude_fc"))
from altitude_model import PhysParams, RatingParams, phys_effects, ratings_from_phys, acclimatization_fraction, ball_flight  # noqa: F401

DEFAULT = PhysParams()


def hir_decrement(match_alt, residence_alt, days_since_arrival=1, p=None):
    p = p if isinstance(p, PhysParams) else (PhysParams(**p) if isinstance(p, dict) else DEFAULT)
    return -phys_effects(match_alt, residence_alt, days_since_arrival, p)["high_intensity_running"]["pct"]


def card_deltas(match_alt, residence_alt, days_since_arrival=1, p=None, rp=None):
    """FC-style category deltas (STAMINA, PAC, DEF, PHY, ...) for a team at this venue."""
    p = p if isinstance(p, PhysParams) else (PhysParams(**p) if isinstance(p, dict) else DEFAULT)
    eff = phys_effects(match_alt, residence_alt, days_since_arrival, p)
    return eff, ratings_from_phys(eff, rp or RatingParams())


if __name__ == "__main__":
    for label, m, r, d in [("sea level -> 3600 m, day 1", 3600, 0, 1), ("sea level -> 3600 m, day 14", 3600, 0, 14), ("sea level -> 1600 m, day 4", 1600, 0, 4),
                           ("coast -> Toluca, day before", 2670, 10, 1), ("Monterrey -> Toluca, day before", 2670, 540, 1), ("Mexico City -> Toluca, day before", 2670, 2240, 1),
                           ("Tijuana -> Pachuca, day before", 2430, 20, 1), ("Buenos Aires -> El Alto, same day", 4090, 25, 0), ("Buenos Aires -> El Alto, day 7", 4090, 25, 7)]:
        eff, cards = card_deltas(m, r, d)
        print(f"{label:36s} HIR {eff['high_intensity_running']['pct']:6.1f}%  RSA {eff['repeated_sprint_recovery']['pct']:5.1f}%  STA {cards['STAMINA']['adjusted']} PHY {cards['PHY']['adjusted']} PAC {cards['PAC']['adjusted']}")
