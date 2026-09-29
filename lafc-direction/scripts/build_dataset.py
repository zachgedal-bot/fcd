"""Build matches.csv and goals.csv from data/raw_events.jsonl.

raw_events.jsonl: one JSON object per LAFC home match, hand-collected from
match reports (ESPN / lafc.com / opponent sites / FOX box scores) via web search.
Fields: date, opp, comp, ft [lafc, opp], ht [lafc, opp] or nulls, goals (m=minute,
a=added stoppage minutes, t='LAFC'|'OPP', s=scorer, k='pen'|'og'), reds, att, ko,
src (URLs), conf ('high'|'medium'|'low'), optional fans / exclude / venue / et.
"""
import json, csv, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
rows = [json.loads(l) for l in open(ROOT / "data/raw_events.jsonl")]

def half_of(g, ht):
    """Return 1 or 2 for a goal, using the minute when known, else the note/HT score."""
    m = g.get("m")
    if m is not None:
        return 1 if m <= 45 else 2
    note = (g.get("note") or "").lower()
    if "1h" in note or "before ht" in note or "before half" in note or "first half" in note:
        return 1
    if "2h" in note or "late" in note or "stoppage" in note and "1h" not in note:
        return 2
    return None

matches, goals = [], []
for r in rows:
    if r.get("exclude"):
        continue
    ht = r.get("ht") or [None, None]
    lafc1 = opp1 = 0
    unknown_half = 0
    for g in r.get("goals", []):
        h = half_of(g, ht)
        if h is None:
            unknown_half += 1
        goals.append({
            "date": r["date"], "opponent": r["opp"], "competition": r["comp"],
            "team": "LAFC" if g["t"] == "LAFC" else "OPP", "minute": g.get("m"),
            "added": g.get("a"), "half": h, "scorer": g.get("s"), "kind": g.get("k", "open"),
            "total_minute": (g["m"] + (g.get("a") or 0)) if g.get("m") is not None else None,
            "note": g.get("note"),
        })
        if h == 1:
            if g["t"] == "LAFC": lafc1 += 1
            else: opp1 += 1
    # prefer the reported HT score when present
    ht_l, ht_o = ht[0], ht[1]
    if ht_l is None and unknown_half == 0:
        ht_l, ht_o = lafc1, opp1
    ft_l, ft_o = r["ft"]
    matches.append({
        "date": r["date"], "season": int(r["date"][:4]), "opponent": r["opp"],
        "competition": r["comp"], "venue": r.get("venue", "Banc of California / BMO Stadium"),
        "kickoff_local": r.get("ko"), "attendance": r.get("att"),
        "fans": r.get("fans", True), "extra_time_played": bool(r.get("et")),
        "ft_lafc": ft_l, "ft_opp": ft_o, "ht_lafc": ht_l, "ht_opp": ht_o,
        "h1_total": (ht_l + ht_o) if ht_l is not None else None,
        "h2_lafc": (ft_l - ht_l) if (ht_l is not None and ft_l is not None) else None,
        "h2_opp": (ft_o - ht_o) if (ht_o is not None and ft_o is not None) else None,
        "red_cards": len(r.get("reds", [])),
        "red_lafc": sum(1 for x in r.get("reds", []) if x["t"] == "LAFC"),
        "red_opp": sum(1 for x in r.get("reds", []) if x["t"] == "OPP"),
        "goal_minutes_missing": sum(1 for g in r.get("goals", []) if g.get("m") is None),
        "confidence": r.get("conf"), "todo": r.get("todo"), "note": r.get("note"),
        "attacking_end_1h": "unknown", "direction_status": "unavailable",
        "sources": " | ".join(r.get("src", [])),
    })

matches.sort(key=lambda x: x["date"])
goals.sort(key=lambda x: (x["date"], x["total_minute"] if x["total_minute"] is not None else 999))
with open(ROOT / "data/matches.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(matches[0].keys())); w.writeheader(); w.writerows(matches)
with open(ROOT / "data/goals.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(goals[0].keys())); w.writeheader(); w.writerows(goals)
# direction label template: one row per match, to be filled from kickoff footage
with open(ROOT / "data/direction_labels.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["date", "opponent", "competition", "attacking_end_1h", "status", "evidence_type", "video_url", "video_timestamp", "landmark", "coder", "notes"])
    for m in matches:
        w.writerow([m["date"], m["opponent"], m["competition"], "", "unavailable", "", "", "", "", "", ""])
print(len(matches), "matches,", len(goals), "goals")
