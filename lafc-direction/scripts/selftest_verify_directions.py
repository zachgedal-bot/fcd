#!/usr/bin/env python3
"""Offline self-test for verify_directions.py.

Builds synthetic broadcast-style clips with OpenCV (title card, kickoff wide shot with two
kits in their own halves, a close-up, open play) and runs the full pipeline on a scratch
copy of a tiny dataset through the video_overrides.csv path, so no network is needed.

    python scripts/selftest_verify_directions.py

Exits non-zero if any expectation fails.
"""
from __future__ import annotations

import csv
import pathlib
import random
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import verify_directions as vd  # noqa: E402

import cv2  # noqa: E402
import numpy as np  # noqa: E402

W, H, FPS = 640, 360, 25
GRASS = (40, 160, 40)


def draw_pitch(img):
    img[:] = (90, 90, 110)                       # stands
    cv2.rectangle(img, (0, 40), (W, H), GRASS, -1)  # pitch
    white = (245, 245, 245)
    cv2.rectangle(img, (20, 55), (W - 20, H - 15), white, 2)          # touch/goal lines
    cv2.line(img, (W // 2 - 3, 55), (W // 2 + 3, H - 15), white, 2)    # halfway line (slight slant)
    cv2.circle(img, (W // 2, 200), 40, white, 2)                      # centre circle
    cv2.rectangle(img, (20, 120), (80, 280), white, 2)                # penalty boxes
    cv2.rectangle(img, (W - 80, 120), (W - 20, 280), white, 2)


def draw_players(img, positions, colour):
    for x, y in positions:
        cv2.rectangle(img, (int(x) - 3, int(y) - 7), (int(x) + 3, int(y) + 7), colour, -1)


def make_clip(path: pathlib.Path, left_kit, right_kit, seconds=24, seed=1, mixed_only=False):
    rng = random.Random(seed)
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    left_base = [(rng.uniform(60, 290), rng.uniform(80, 330)) for _ in range(8)] + [(300, 200), (312, 190)]
    right_base = [(rng.uniform(350, 580), rng.uniform(80, 330)) for _ in range(10)]
    mixed = [(rng.uniform(60, 580), rng.uniform(80, 330)) for _ in range(20)]
    for i in range(seconds * FPS):
        t = i / FPS
        img = np.zeros((H, W, 3), np.uint8)
        jit = lambda pts: [(x + rng.uniform(-3, 3), y + rng.uniform(-3, 3)) for x, y in pts]  # noqa: E731
        if t < 3:                                     # title card
            img[:] = (30, 10, 10)
            cv2.putText(img, "HIGHLIGHTS", (150, 190), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (200, 200, 200), 3)
        elif t < 13 and not mixed_only:               # kickoff wide shot
            draw_pitch(img)
            draw_players(img, jit(left_base), left_kit)
            draw_players(img, jit(right_base), right_kit)
            draw_players(img, [(330, 230)], (0, 220, 220))            # referee
            draw_players(img, [(35, 200)], (0, 120, 255))             # left GK
            draw_players(img, [(W - 35, 200)], (200, 0, 200))         # right GK
        elif t < 18:                                  # close-up: huge blobs, no teams
            img[:] = GRASS
            cv2.rectangle(img, (150, 60), (260, 300), left_kit, -1)
            cv2.rectangle(img, (380, 70), (500, 310), right_kit, -1)
        else:                                         # open play, both kits everywhere
            draw_pitch(img)
            draw_players(img, jit(mixed[:10]), left_kit)
            draw_players(img, jit(mixed[10:]), right_kit)
        out.write(img)
    out.release()


def build_scratch(root: pathlib.Path, clips: dict[str, str], kits: dict[str, str]):
    (root / "data").mkdir(parents=True)
    rows = [
        ("2024-04-27", "2024", "Seattle Sounders", "MLS"),
        ("2024-05-11", "2024", "Vancouver Whitecaps", "MLS"),
        ("2024-06-01", "2024", "Portland Timbers", "MLS"),
        ("2024-06-15", "2024", "Houston Dynamo", "MLS"),
        ("2024-11-08", "2024", "Vancouver Whitecaps", "MLS Playoffs"),
    ]
    with open(root / "data/matches.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "season", "opponent", "competition", "venue", "attacking_end_1h", "direction_status"])
        for r in rows:
            w.writerow(list(r) + ["Banc of California / BMO Stadium", "unknown", "unavailable"])
    with open(root / "data/direction_labels.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "opponent", "competition", "attacking_end_1h", "status", "evidence_type", "video_url",
                    "video_timestamp", "landmark", "coder", "notes"])
        for r in rows:
            w.writerow([r[0], r[2], r[3], "", "unavailable", "", "", "", "", "", ""])
    with open(root / "data/video_overrides.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "video", "note"])
        for d, v in clips.items():
            w.writerow([d, v, "selftest"])
    with open(root / "data/kit_overrides.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "lafc_kit"])
        for d, k in kits.items():
            w.writerow([d, k])


def point_module_at(root: pathlib.Path):
    vd.ROOT = root
    vd.LABELS_CSV = root / "data/direction_labels.csv"
    vd.OVERRIDES_CSV = root / "data/video_overrides.csv"
    vd.KIT_CSV = root / "data/kit_overrides.csv"
    vd.OUT_DIR = root / "out"
    vd.FRAMES_DIR = root / "out/frames"
    vd.CACHE_DIR = root / "out/verify_cache"
    vd.LOG_JSONL = root / "out/verification_log.jsonl"
    vd.LOG_TXT = root / "out/verify_directions.log"
    vd.SUMMARY_MD = root / "out/direction_summary.md"


def read_rows(root):
    with open(root / "data/matches.csv", newline="") as f:
        return {r["date"]: r for r in csv.DictReader(f)}


def read_labels(root):
    with open(root / "data/direction_labels.csv", newline="") as f:
        return {r["date"]: r for r in csv.DictReader(f)}


def main() -> int:
    failures = []

    def expect(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            failures.append(msg)

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="vd_selftest_"))
    try:
        clips = tmp / "clips"
        clips.mkdir()
        make_clip(clips / "dark_left_white_right.mp4", (20, 20, 20), (240, 240, 240))
        make_clip(clips / "both_dark.mp4", (20, 20, 20), (30, 30, 30), seed=2)
        make_clip(clips / "open_play_only.mp4", (20, 20, 20), (240, 240, 240), seed=3, mixed_only=True)

        # --- direct frame check -------------------------------------------------------
        cap = cv2.VideoCapture(str(clips / "dark_left_white_right.mp4"))
        cap.set(cv2.CAP_PROP_POS_FRAMES, 6 * FPS)
        ok, frame = cap.read()
        cap.release()
        cfg = vd.FrameConfig(vd.build_parser().parse_args([]))
        fr = vd.analyse_frame(frame, cfg)
        print("frame features:", {k: v for k, v in fr.items() if k not in ("blobs",)})
        expect(fr["kind"] == "wide" and fr.get("kickoff_like"), "kickoff wide shot recognised")
        expect(fr.get("left_team") == "dark" and fr.get("right_team") == "light", "dark kit left, light kit right")
        expect(fr.get("mid_x") is not None and 0.45 < fr["mid_x"] < 0.55, "halfway line located near centre")

        root = tmp / "proj"
        build_scratch(root, {
            "2024-04-27": str(clips / "dark_left_white_right.mp4"),
            "2024-05-11": str(clips / "dark_left_white_right.mp4"),   # LAFC in light kit per override
            "2024-06-01": str(clips / "both_dark.mp4"),
            "2024-06-15": str(clips / "open_play_only.mp4"),
            "2024-11-08": str(clips / "does_not_exist.mp4"),
        }, {"2024-05-11": "light"})
        point_module_at(root)
        csv_path = root / "data/matches.csv"

        # --- run 1: camera side unknown -> screen side recorded, rows stay Unverified ---
        print("\n== run 1: camera side unknown")
        vd.main(["--csv", str(csv_path), "--no-install"])
        rows = read_rows(root)
        r = rows["2024-04-27"]
        expect(r["first_half_direction"] == "Unverified", "uncalibrated run keeps row Unverified")
        expect(r["first_half_screen_direction"] == "right", "dark LAFC defending left -> attacking screen-right")
        expect("camera_side_uncalibrated" in r["verification_note"], "note says camera side uncalibrated")
        expect(r["verification_source"].endswith("#t=3") or "#t=" in r["verification_source"], "source carries timestamp")
        expect(float(r["verification_confidence"] or 0) >= 0.7, f"confidence >= 0.7 (got {r['verification_confidence']})")
        expect(rows["2024-05-11"]["first_half_screen_direction"] == "left", "light-kit override flips LAFC to screen-left")
        expect(rows["2024-06-01"]["first_half_direction"] == "Unverified"
               and rows["2024-06-01"]["verification_note"].split(";")[0] in ("no_kickoff_frame", "kit_not_found"),
               f"both-dark clip is ambiguous ({rows['2024-06-01']['verification_note'].split(';')[0]})")
        expect(rows["2024-06-15"]["verification_note"].startswith("no_kickoff_frame"),
               f"open play only -> no_kickoff_frame ({rows['2024-06-15']['verification_note'].split(';')[0]})")
        expect(rows["2024-11-08"]["verification_note"] == "override_clip_missing", "missing clip -> override_clip_missing")
        expect((root / "out/frames/2024-04-27/contact_sheet.jpg").exists(), "contact sheet written")
        expect((root / "out/verification_log.jsonl").exists(), "jsonl evidence log written")

        # --- run 2: remap with camera on the west sideline --------------------------------
        print("\n== run 2: --remap-only --camera-side west")
        vd.main(["--csv", str(csv_path), "--no-install", "--remap-only", "--camera-side", "west"])
        rows = read_rows(root)
        labels = read_labels(root)
        expect(rows["2024-04-27"]["first_half_direction"] == "South", "west camera: attacking screen-right = South")
        expect(rows["2024-05-11"]["first_half_direction"] == "North", "west camera: attacking screen-left = North")
        expect(rows["2024-04-27"]["direction_status"] == "verified" and rows["2024-04-27"]["attacking_end_1h"] == "south",
               "legacy columns synced")
        expect(labels["2024-04-27"]["status"] == "verified" and labels["2024-04-27"]["attacking_end_1h"] == "south",
               "direction_labels.csv mirrored")
        expect(rows["2024-06-01"]["first_half_direction"] == "Unverified", "ambiguous row untouched by remap")

        # --- run 3: fresh run with camera side east flips the mapping ---------------------
        print("\n== run 3: --force --camera-side east")
        vd.main(["--csv", str(csv_path), "--no-install", "--force", "--camera-side", "east"])
        rows = read_rows(root)
        expect(rows["2024-04-27"]["first_half_direction"] == "North", "east camera: attacking screen-right = North")
        expect(rows["2024-05-11"]["first_half_direction"] == "South", "east camera: attacking screen-left = South")
        summary = (root / "out/direction_summary.md").read_text()
        expect("| 2024 | 4 | 1 | 1 | 2 |" in summary, "season summary counts Seq A / Seq B / Unverified")
        print("\n" + summary)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\nSELFTEST", "FAILED: " + "; ".join(failures) if failures else "PASSED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
