#!/usr/bin/env python3
"""verify_directions.py - empirical first-half attacking direction for LAFC home matches.

For every row of data/matches.csv this script:

  1. searches YouTube (through yt-dlp) for the official MLS / LAFC highlight package of
     that match, validating the candidate on channel, upload date and title before use;
  2. downloads only the opening seconds of the clip (default 0-90 s), where the official
     packages open on the kickoff / line-up wide shot;
  3. samples frames with OpenCV, keeps the wide pitch shots, locates the halfway line and
     the two kits on the pitch, and reads which screen side LAFC is defending at kickoff
     (so which screen side LAFC is attacking);
  4. converts the screen side to a physical end of BMO Stadium (North = the 3252 terrace,
     South = the scoreboard end) using the camera-side calibration (--camera-side);
  5. writes first_half_direction / verification_source (+ note, confidence, screen side)
     back into matches.csv, mirrors the label into data/direction_labels.csv, appends a
     full evidence record to out/verification_log.jsonl and saves an annotated contact
     sheet of the frames it looked at under out/frames/<date>/ for manual review;
  6. prints the Sequence A (1H North -> 2H South) vs Sequence B (1H South -> 2H North)
     count per season and writes it to out/direction_summary.md.

Nothing is ever guessed: a match is written as Unverified whenever the video is missing,
restricted, the wrong match, the frames are ambiguous, or the camera side has not been
calibrated. The reason is stored in verification_note so the row can be reviewed by hand.

Camera-side calibration (one-time, venue constant)
--------------------------------------------------
The main broadcast camera sits on one sideline for every match at BMO. If it is on the
WEST sideline (looking east) the North End / 3252 terrace is on the LEFT of the screen; if
it is on the EAST sideline the 3252 is on the RIGHT. Open any contact sheet in out/frames/
(or the clip itself), find the goal with the steep safe-standing terrace and the open
north-east "keyhole" corner beside it, and run once:

    python scripts/verify_directions.py --remap-only --camera-side west   # or east

That re-maps every already-analysed screen side to North/South without re-downloading.
Until that flag is given, rows keep their screen side but stay Unverified.

Kit assumption
--------------
LAFC are identified on the pitch by kit class (default: dark = the black home kit).
Matches in which LAFC wore a light or grey kit must be listed in data/kit_overrides.csv
(columns: date,lafc_kit) with lafc_kit in {dark,light,grey}; otherwise those rows would be
read for the wrong team. Any match whose two detected kit classes do not include the
expected LAFC class is written as Unverified (kit_not_found).

Offline / manual path
---------------------
data/video_overrides.csv (columns: date,video,note) lets you point a match at a specific
YouTube URL or a local clip. A local clip skips the search and download steps entirely,
which is also how the self-test (selftest_verify_directions.py) exercises the pipeline.

Network requirements
--------------------
Needs outbound access to www.youtube.com, youtube.com, *.googlevideo.com and i.ytimg.com.
When those are blocked (as in the cloud environment this was written in) every row is
written Unverified with note network_blocked and the run stops searching after three
consecutive network failures, so it never hammers a closed proxy.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import importlib
import json
import logging
import os
import pathlib
import random
import re
import shutil
import subprocess
import sys
import time
from collections import Counter

# --------------------------------------------------------------------------------------
# Paths and constants
# --------------------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "data" / "matches.csv"
LABELS_CSV = ROOT / "data" / "direction_labels.csv"
OVERRIDES_CSV = ROOT / "data" / "video_overrides.csv"
KIT_CSV = ROOT / "data" / "kit_overrides.csv"
OUT_DIR = ROOT / "out"
FRAMES_DIR = OUT_DIR / "frames"
CACHE_DIR = OUT_DIR / "verify_cache"
LOG_JSONL = OUT_DIR / "verification_log.jsonl"
LOG_TXT = OUT_DIR / "verify_directions.log"
SUMMARY_MD = OUT_DIR / "direction_summary.md"

NORTH, SOUTH, UNVERIFIED = "North", "South", "Unverified"
SCRIPT_TAG = "verify_directions.py"

NEW_COLUMNS = [
    "first_half_direction",          # North | South | Unverified
    "verification_source",           # YouTube URL with &t=<s>s of the frame used (or local path)
    "verification_note",             # method detail or the reason the row is Unverified
    "first_half_screen_direction",   # left | right : screen side LAFC attacked at kickoff
    "verification_confidence",       # 0-1 from frame agreement and kit-side purity
]

# Opponent names as they appear in matches.csv -> aliases accepted in a video title.
# Ambiguous short forms ("LA", "United", "City", "FC") are deliberately left out.
OPPONENT_ALIASES = {
    "Atlanta United": ["atlanta"],
    "Austin FC": ["austin"],
    "Charlotte FC": ["charlotte"],
    "Chicago Fire": ["chicago"],
    "Colorado Rapids": ["colorado", "rapids"],
    "Columbus Crew": ["columbus", "crew"],
    "D.C. United": ["d.c. united", "dc united", "d.c united"],
    "FC Cincinnati": ["cincinnati", "fcc"],
    "FC Dallas": ["dallas"],
    "Fresno FC": ["fresno"],
    "Houston Dynamo": ["houston", "dynamo"],
    "Inter Miami": ["miami"],
    "LA Galaxy": ["galaxy"],
    "Minnesota United": ["minnesota", "loons"],
    "Montreal Impact": ["montreal", "montréal", "impact"],
    "Nashville SC": ["nashville"],
    "New England Revolution": ["new england", "revolution", "revs"],
    "New York City FC": ["nycfc", "new york city"],
    "New York Red Bulls": ["red bulls", "rbny", "ny red bulls"],
    "Orlando City": ["orlando"],
    "Philadelphia Union": ["philadelphia", "union"],
    "Portland Timbers": ["portland", "timbers"],
    "Real Salt Lake": ["real salt lake", "salt lake", "rsl"],
    "Sacramento Republic": ["sacramento"],
    "San Diego FC": ["san diego"],
    "San Jose Earthquakes": ["san jose", "earthquakes", "quakes"],
    "Seattle Sounders": ["seattle", "sounders"],
    "Sporting Kansas City": ["sporting kc", "sporting kansas city", "kansas city", "skc"],
    "St. Louis City": ["st. louis", "st louis", "stl city"],
    "Toronto FC": ["toronto", "tfc"],
    "Vancouver Whitecaps": ["vancouver", "whitecaps"],
}
LAFC_ALIASES = ["lafc", "los angeles fc", "los angeles football club"]
OFFICIAL_CHANNEL_KEYS = ["major league soccer", "lafc", "los angeles football club", "los angeles fc"]

# --------------------------------------------------------------------------------------
# Dependency bootstrap
# --------------------------------------------------------------------------------------
REQUIRED = [("yt_dlp", "yt-dlp"), ("cv2", "opencv-python-headless"), ("pandas", "pandas"), ("numpy", "numpy")]


def ensure_dependencies(allow_install: bool) -> None:
    """Import every required module, pip-installing the ones that are missing."""
    for module, package in REQUIRED:
        try:
            importlib.import_module(module)
        except ImportError:
            if not allow_install:
                sys.exit(f"[deps] missing module '{module}'. Install with: pip install {package}")
            print(f"[deps] {module} missing -> pip install {package}", flush=True)
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet",
                                   "--disable-pip-version-check", package])
            importlib.invalidate_caches()
            importlib.import_module(module)


def ensure_ffmpeg(allow_install: bool) -> str | None:
    """Return a directory containing an `ffmpeg` executable, or None if none can be found.

    yt-dlp needs ffmpeg to cut the 0-90 s section. A system ffmpeg is used when present;
    otherwise the static binary shipped in the imageio-ffmpeg wheel is exposed through a
    symlink directory (yt-dlp's ffmpeg_location accepts a directory)."""
    exe = shutil.which("ffmpeg")
    if exe:
        return str(pathlib.Path(exe).parent)
    try:
        import imageio_ffmpeg  # type: ignore
    except ImportError:
        if not allow_install:
            return None
        print("[deps] ffmpeg missing -> pip install imageio-ffmpeg", flush=True)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet",
                               "--disable-pip-version-check", "imageio-ffmpeg"])
        importlib.invalidate_caches()
        import imageio_ffmpeg  # type: ignore
    binary = pathlib.Path(imageio_ffmpeg.get_ffmpeg_exe())
    bindir = CACHE_DIR / "ffmpeg-bin"
    bindir.mkdir(parents=True, exist_ok=True)
    link = bindir / "ffmpeg"
    if not link.exists():
        link.symlink_to(binary)
    return str(bindir)


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------
def setup_logging(verbose: bool) -> logging.Logger:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(SCRIPT_TAG)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.DEBUG if verbose else logging.INFO)
    sh.setFormatter(fmt)
    fh = logging.FileHandler(LOG_TXT, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(sh)
    logger.addHandler(fh)
    return logger


def parse_date(s: str) -> dt.date:
    return dt.date.fromisoformat(s.strip())


def human_date(d: dt.date) -> str:
    return f"{d:%B} {d.day}, {d.year}"


def norm(s: str | None) -> str:
    return (s or "").lower().replace("’", "'").strip()


def title_mentions(title: str, opponent: str) -> tuple[bool, bool]:
    t = norm(title)
    lafc = any(a in t for a in LAFC_ALIASES)
    opp = any(a in t for a in OPPONENT_ALIASES.get(opponent, [norm(opponent)]))
    return lafc, opp


def channel_kind(name: str | None, opponent: str) -> str:
    n = norm(name)
    if any(k in n for k in OFFICIAL_CHANNEL_KEYS):
        return "official"
    if any(a in n for a in OPPONENT_ALIASES.get(opponent, [])):
        return "club"
    return "unofficial"


def read_optional_csv(path: pathlib.Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {r["date"].strip(): r for r in csv.DictReader(f) if r.get("date")}


def screen_to_compass(screen_dir: str | None, camera_side: str) -> str | None:
    """Map the screen side LAFC attack toward to the physical end.

    camera on WEST sideline, looking east: screen-left = North (3252), screen-right = South.
    camera on EAST sideline, looking west: screen-left = South, screen-right = North."""
    if screen_dir not in ("left", "right") or camera_side not in ("west", "east"):
        return None
    if camera_side == "west":
        return NORTH if screen_dir == "left" else SOUTH
    return SOUTH if screen_dir == "left" else NORTH


# --------------------------------------------------------------------------------------
# YouTube search + download (yt-dlp)
# --------------------------------------------------------------------------------------
class NetworkBlocked(Exception):
    pass


def classify_error(message: str) -> str:
    m = message.lower()
    if any(k in m for k in ("tunnel connection failed", "unable to connect to proxy", "failed to resolve",
                            "name resolution", "network is unreachable", "connection refused",
                            "unable to download api page", "unable to download webpage", "timed out",
                            "getaddrinfo", "proxyerror", "403 forbidden")):
        return "network_blocked"
    if any(k in m for k in ("429", "too many requests", "rate-limit", "rate limit", "confirm you're not a bot",
                            "confirm you’re not a bot", "sign in to confirm")):
        return "rate_limited"
    if any(k in m for k in ("private video", "video unavailable", "has been removed", "not available in your",
                            "geo", "age", "members-only", "join this channel", "copyright", "terminated",
                            "requires payment", "premieres", "is not available")):
        return "restricted"
    return "search_error"


class _QuietYdlLogger:
    """Route yt-dlp's chatter into our logger at debug level."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.last_error = ""

    def debug(self, msg):
        self.logger.debug("yt-dlp: %s", msg)

    def info(self, msg):
        self.logger.debug("yt-dlp: %s", msg)

    def warning(self, msg):
        self.logger.debug("yt-dlp warning: %s", msg)

    def error(self, msg):
        self.last_error = str(msg)
        self.logger.debug("yt-dlp error: %s", msg)


class VideoFinder:
    def __init__(self, args, ffmpeg_dir: str | None, logger: logging.Logger):
        import yt_dlp  # noqa: F401  (imported lazily so --summary-only works without it)
        self.yt_dlp = yt_dlp
        self.args = args
        self.ffmpeg_dir = ffmpeg_dir
        self.logger = logger
        self.ylog = _QuietYdlLogger(logger)
        self.consecutive_network_failures = 0

    # ---- low level ------------------------------------------------------------------
    def _opts(self, **extra) -> dict:
        opts = {
            "quiet": True, "no_warnings": True, "noprogress": True, "skip_download": True,
            "socket_timeout": 25, "retries": 1, "extractor_retries": 1, "logger": self.ylog,
            "ignoreerrors": False, "nocheckcertificate": False,
        }
        if self.args.cookies:
            opts["cookiefile"] = self.args.cookies
        opts.update(extra)
        return opts

    def _pause(self, factor: float = 1.0) -> None:
        """Polite delay between YouTube requests (jittered so bursts do not align)."""
        d = self.args.delay * factor
        if d > 0:
            time.sleep(d * random.uniform(0.8, 1.4))

    def _call(self, fn, what: str):
        """Run a yt-dlp call with rate-limit backoff and error classification."""
        backoff = [10, 30, 90]
        attempt = 0
        while True:
            try:
                result = fn()
                self.consecutive_network_failures = 0
                return result, None
            except self.yt_dlp.utils.DownloadError as exc:
                msg = str(exc) or self.ylog.last_error
                reason = classify_error(msg)
                self.logger.debug("%s failed: %s -> %s", what, msg[:300], reason)
                if reason == "rate_limited" and attempt < len(backoff):
                    wait = backoff[attempt]
                    attempt += 1
                    self.logger.warning("rate limited by YouTube; waiting %ds before retry %d/%d",
                                        wait, attempt, len(backoff))
                    time.sleep(wait)
                    continue
                if reason == "network_blocked":
                    self.consecutive_network_failures += 1
                return None, reason
            except Exception as exc:  # noqa: BLE001 - anything else is logged, never fatal
                msg = f"{type(exc).__name__}: {exc}"
                reason = classify_error(msg)
                self.logger.debug("%s raised %s -> %s", what, msg[:300], reason)
                if reason == "network_blocked":
                    self.consecutive_network_failures += 1
                return None, reason

    def search(self, query: str) -> tuple[list[dict] | None, str | None]:
        def run():
            with self.yt_dlp.YoutubeDL(self._opts(extract_flat="in_playlist")) as ydl:
                info = ydl.extract_info(f"ytsearch{self.args.search_results}:{query}", download=False)
            return [e for e in (info or {}).get("entries", []) if e]
        self._pause()
        return self._call(run, f"search '{query}'")

    def details(self, url: str) -> tuple[dict | None, str | None]:
        def run():
            with self.yt_dlp.YoutubeDL(self._opts()) as ydl:
                return ydl.extract_info(url, download=False)
        self._pause(0.5)
        return self._call(run, f"details {url}")

    # ---- candidate validation ---------------------------------------------------------
    def _judge(self, entry: dict, match: dict) -> tuple[bool, str]:
        """Decide whether a fully-extracted video is the right match. Returns (ok, reason)."""
        title = entry.get("title") or ""
        lafc, opp = title_mentions(title, match["opponent"])
        if not (lafc and opp):
            return False, "title_mismatch"
        kind = channel_kind(entry.get("channel") or entry.get("uploader"), match["opponent"])
        if kind == "unofficial" and not self.args.allow_unofficial:
            return False, "unofficial_channel"
        if kind == "club" and not (self.args.allow_club_channels or self.args.allow_unofficial):
            return False, "club_channel_not_allowed"
        avail = entry.get("availability")
        if avail not in (None, "public", "unlisted"):
            return False, f"restricted:{avail}"
        if entry.get("is_live") or entry.get("live_status") in ("is_live", "is_upcoming"):
            return False, "restricted:live"
        up = entry.get("upload_date")
        if not up:
            return False, "upload_date_missing"
        try:
            up_d = dt.date(int(up[:4]), int(up[4:6]), int(up[6:8]))
        except ValueError:
            return False, "upload_date_unparseable"
        lag = (up_d - match["date_obj"]).days
        if lag < -1 or lag > self.args.max_upload_lag_days:
            return False, f"upload_date_off_by_{lag}d"
        dur = entry.get("duration") or 0
        if dur and dur > self.args.max_duration and not self.args.accept_long_videos:
            return False, f"not_highlight_length:{int(dur)}s"
        if dur and dur < 30:
            return False, f"too_short:{int(dur)}s"
        return True, "ok"

    def find(self, match: dict, log_rec: dict) -> tuple[dict | None, str]:
        """Search a few query variants; return (video, reason). video has url/id/title/channel."""
        d = match["date_obj"]
        queries = [
            f"LAFC vs {match['opponent']} {human_date(d)} highlights",
            f"{match['opponent']} vs LAFC {human_date(d)} highlights",
            f"LAFC {match['opponent']} highlights {d.isoformat()}",
        ]
        log_rec["queries"] = queries
        log_rec["candidates"] = []
        seen: set[str] = set()
        last_reason = "no_video_found"
        for q in queries:
            entries, err = self.search(q)
            if err:
                last_reason = err
                if err == "network_blocked":
                    raise NetworkBlocked(err)
                continue
            checked = 0
            for e in entries or []:
                vid = e.get("id") or ""
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                url = e.get("url") or f"https://www.youtube.com/watch?v={vid}"
                if not url.startswith("http"):
                    url = f"https://www.youtube.com/watch?v={vid}"
                # cheap pre-filter on the flat title before spending a details request
                lafc, opp = title_mentions(e.get("title") or "", match["opponent"])
                if not (lafc and opp):
                    log_rec["candidates"].append({"id": vid, "title": e.get("title"),
                                                  "channel": e.get("channel") or e.get("uploader"),
                                                  "verdict": "title_mismatch"})
                    continue
                if checked >= self.args.max_details_per_query:
                    break
                checked += 1
                info, err = self.details(url)
                if err:
                    if err == "network_blocked":
                        raise NetworkBlocked(err)
                    log_rec["candidates"].append({"id": vid, "title": e.get("title"), "verdict": err})
                    last_reason = err if err == "restricted" else last_reason
                    continue
                ok, why = self._judge(info, match)
                cand = {"id": vid, "title": info.get("title"), "channel": info.get("channel") or info.get("uploader"),
                        "upload_date": info.get("upload_date"), "duration": info.get("duration"), "verdict": why}
                log_rec["candidates"].append(cand)
                if ok:
                    return {"id": vid, "url": f"https://www.youtube.com/watch?v={vid}", "title": info.get("title"),
                            "channel": cand["channel"], "upload_date": info.get("upload_date"),
                            "duration": info.get("duration")}, "ok"
                if why.startswith("restricted"):
                    last_reason = "restricted"
        if last_reason == "no_video_found" and any(c.get("verdict") in ("unofficial_channel", "club_channel_not_allowed")
                                                   for c in log_rec["candidates"]):
            last_reason = "no_official_video"
        return None, last_reason

    # ---- download -------------------------------------------------------------------
    def download_clip(self, video: dict, match: dict) -> tuple[pathlib.Path | None, str]:
        """Download seconds 0..clip_seconds of the video into the cache; return (path, reason)."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        stem = f"{match['date']}_{video['id']}"
        for p in CACHE_DIR.glob(stem + ".*"):
            if p.suffix in (".mp4", ".mkv", ".webm") and p.stat().st_size > 0:
                return p, "cached"
        if self.ffmpeg_dir is None:
            return None, "ffmpeg_missing"
        ranges = self.yt_dlp.utils.download_range_func(None, [(0, float(self.args.clip_seconds))])
        opts = self._opts(
            skip_download=False,
            format=(f"bv*[height<={self.args.max_height}][ext=mp4]/bv*[height<={self.args.max_height}]"
                    f"/b[height<={self.args.max_height}][ext=mp4]/b[height<={self.args.max_height}]/worst"),
            outtmpl=str(CACHE_DIR / (stem + ".%(ext)s")),
            download_ranges=ranges, force_keyframes_at_cuts=True,
            ffmpeg_location=self.ffmpeg_dir, merge_output_format="mp4", overwrites=True,
        )

        def run():
            with self.yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([video["url"]])
            return True

        self._pause()
        ok, err = self._call(run, f"download {video['url']}")
        if not ok:
            return None, err or "download_error"
        for p in sorted(CACHE_DIR.glob(stem + ".*"), key=lambda p: p.stat().st_size, reverse=True):
            if p.suffix in (".mp4", ".mkv", ".webm") and p.stat().st_size > 0:
                return p, "downloaded"
        return None, "download_error"


# --------------------------------------------------------------------------------------
# Frame analysis (OpenCV)
# --------------------------------------------------------------------------------------
class FrameConfig:
    def __init__(self, args):
        self.sample_fps = args.sample_fps
        self.clip_seconds = args.clip_seconds
        self.min_grass = args.min_grass
        self.purity = args.purity
        self.min_team_blobs = args.min_team_blobs
        self.min_agree = args.min_agree
        self.min_confidence = args.min_confidence
        self.blob_min_frac = 0.00004
        self.blob_max_frac = 0.006
        self.allow_no_midline = args.allow_no_midline


def classify_kit(h: float, s: float, v: float) -> str:
    """Bucket a blob's median HSV into a kit class."""
    if v < 85:
        return "dark"
    if s < 70 and v > 165:
        return "light"
    if s < 60:
        return "grey"
    return f"hue{int(h // 15) * 15}"


def analyse_frame(bgr, cfg: FrameConfig) -> dict:
    """Return the features of one frame; kickoff_like=True when both kits sit in their own half."""
    import cv2
    import numpy as np

    H0, W0 = bgr.shape[:2]
    scale = 640.0 / W0 if W0 > 640 else 1.0
    img = cv2.resize(bgr, (int(W0 * scale), int(H0 * scale)), interpolation=cv2.INTER_AREA) if scale != 1 else bgr
    H, W = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, (30, 40, 40), (95, 255, 255))
    grass = float((green > 0).mean())
    out = {"grass_ratio": round(grass, 3), "kind": "not_wide", "scale": scale}
    if grass < cfg.min_grass:
        return out

    # Pitch region: close the grass mask over players/lines, keep the largest component.
    pitch = cv2.morphologyEx(green, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(pitch)
    if n <= 1:
        return out
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    pitch = ((lab == big).astype(np.uint8)) * 255
    pitch = cv2.erode(pitch, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    if float((pitch > 0).mean()) < cfg.min_grass:
        return out

    # Player candidates: non-grass inside the pitch, thin lines removed by opening.
    nong = cv2.bitwise_and(cv2.bitwise_not(green), pitch)
    nong = cv2.morphologyEx(nong, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    nong = cv2.morphologyEx(nong, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 7)))
    n, lab, stats, cents = cv2.connectedComponentsWithStats(nong)
    A = float(H * W)
    blobs = []
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        if area < cfg.blob_min_frac * A or area > cfg.blob_max_frac * A or w == 0:
            continue
        aspect = h / float(w)
        if aspect < 0.7 or aspect > 6.0:
            continue
        mask = lab == i
        hh, ss, vv = (float(np.median(hsv[..., c][mask])) for c in range(3))
        blobs.append({"x": float(cents[i][0]), "y": float(cents[i][1]), "area": area,
                      "cls": classify_kit(hh, ss, vv), "box": [x, y, w, h]})

    # Halfway line: a near-vertical white line in the central band of the frame.
    white = cv2.bitwise_and(cv2.inRange(hsv, (0, 0, 170), (180, 70, 255)), pitch)
    lines = cv2.HoughLinesP(white, 1, np.pi / 180, threshold=40, minLineLength=int(0.12 * H), maxLineGap=12)
    mid_x = None
    if lines is not None:
        xs = []
        for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):  # OpenCV 4 gives (N,1,4), OpenCV 5 gives (N,4)
            ang = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if 55 <= ang <= 125 and 0.22 * W <= (x1 + x2) / 2 <= 0.78 * W:
                xs.append((x1 + x2) / 2.0)
        if xs and float(np.std(xs)) < 0.06 * W:
            mid_x = float(np.median(xs))

    counts = Counter(b["cls"] for b in blobs)
    teams = [c for c, k in counts.most_common() if k >= cfg.min_team_blobs][:2]
    out.update(kind="wide", n_blobs=len(blobs), mid_x=None if mid_x is None else round(mid_x / W, 3),
               classes=dict(counts), width=W, height=H, blobs=blobs, kickoff_like=False)
    if len(teams) < 2:
        out["kind"] = "wide_no_teams"
        return out
    ref_x = mid_x if mid_x is not None else W / 2.0
    tinfo = {}
    for c in teams:
        xs = [b["x"] for b in blobs if b["cls"] == c]
        tinfo[c] = {"n": len(xs), "frac_left": round(sum(1 for x in xs if x < ref_x) / len(xs), 3),
                    "mean_x": round(sum(xs) / len(xs) / W, 3)}
    a, b = teams
    fa, fb = tinfo[a]["frac_left"], tinfo[b]["frac_left"]
    split = (fa >= cfg.purity and fb <= 1 - cfg.purity) or (fb >= cfg.purity and fa <= 1 - cfg.purity)
    out["teams"] = tinfo
    if split:
        out["left_team"], out["right_team"] = (a, b) if fa > fb else (b, a)
        out["purity"] = round((max(fa, 1 - fa) + max(fb, 1 - fb)) / 2, 3)
        out["kickoff_like"] = bool(mid_x is not None or cfg.allow_no_midline)
        if mid_x is None:
            out["kind"] = "wide_split_no_midline"
    return out


def lafc_side(frame: dict, lafc_kit: str) -> str | None:
    if not frame.get("kickoff_like"):
        return None
    if frame.get("left_team") == lafc_kit:
        return "left"
    if frame.get("right_team") == lafc_kit:
        return "right"
    return None


def save_contact_sheet(thumbs: list, frames: list[dict], path: pathlib.Path, lafc_kit: str) -> None:
    """Tile the sampled frames with their verdicts so a person can review the evidence."""
    import cv2
    import numpy as np

    if not thumbs:
        return
    tw, th = 240, 135
    cols = 6
    rows = (len(thumbs) + cols - 1) // cols
    sheet = np.zeros((rows * th, cols * tw, 3), np.uint8)
    for i, (thumb, fr) in enumerate(zip(thumbs, frames)):
        t = cv2.resize(thumb, (tw, th))
        s = fr.get("scale", 1.0)
        f = tw / (fr.get("width", thumb.shape[1] * s) / s) if fr.get("width") else tw / thumb.shape[1]
        if fr.get("kind", "").startswith("wide"):
            for b in fr.get("blobs", []):
                x, y, w, h = b["box"]
                color = {"dark": (0, 0, 255), "light": (255, 255, 255), "grey": (160, 160, 160)}.get(b["cls"], (0, 200, 255))
                cv2.rectangle(t, (int(x / s * f), int(y / s * f)), (int((x + w) / s * f), int((y + h) / s * f)), color, 1)
            if fr.get("mid_x") is not None:
                mx = int(fr["mid_x"] * tw)
                cv2.line(t, (mx, 0), (mx, th), (255, 0, 255), 1)
        side = lafc_side(fr, lafc_kit)
        tag = f"{fr['t']:.1f}s {fr.get('kind')}"
        if side:
            tag += f" LAFC:{side}"
        cv2.putText(t, tag, (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 3)
        cv2.putText(t, tag, (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1)
        r, c = divmod(i, cols)
        sheet[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = t
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 80])


def analyse_clip(path: pathlib.Path, cfg: FrameConfig, lafc_kit: str, frames_dir: pathlib.Path,
                 logger: logging.Logger) -> dict:
    """Sample the clip, classify the frames and aggregate a screen direction for LAFC."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return {"reason": "clip_unreadable", "screen_dir": None}
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, int(round(fps / cfg.sample_fps)))
    frames, thumbs = [], []
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            t = idx / fps
            if t > cfg.clip_seconds:
                break
            r = analyse_frame(frame, cfg)
            r["t"] = round(t, 2)
            frames.append(r)
            if len(thumbs) < 60:
                thumbs.append(cv2.resize(frame, (320, int(320 * frame.shape[0] / frame.shape[1]))))
        idx += 1
    cap.release()

    result = {"n_sampled": len(frames), "n_wide": sum(1 for f in frames if f.get("kind", "").startswith("wide")),
              "screen_dir": None, "confidence": 0.0, "t_first": None, "reason": None}
    q = [f for f in frames if f.get("kickoff_like")]
    votes: Counter = Counter()
    purities = []
    first_t = {}
    for f in q:
        side = lafc_side(f, lafc_kit)
        if side:
            votes[side] += 1
            purities.append(f.get("purity", 0))
            first_t.setdefault(side, f["t"])
    result["n_kickoff_like"] = len(q)
    result["votes"] = dict(votes)
    result["kit_classes_seen"] = dict(Counter(c for f in q for c in (f.get("left_team"), f.get("right_team")) if c))
    first_wide = next((f["t"] for f in frames if f.get("kind", "").startswith("wide")), None)
    result["t_first_wide"] = first_wide

    if not frames:
        result["reason"] = "clip_empty"
    elif result["n_wide"] == 0:
        result["reason"] = "no_wide_shot"
    elif not q:
        result["reason"] = "no_kickoff_frame"
    elif not votes:
        result["reason"] = "kit_not_found"
    else:
        (side, n_top), = votes.most_common(1)
        n_other = sum(votes.values()) - n_top
        if n_top < cfg.min_agree:
            result["reason"] = "ambiguous_frames:too_few_agreeing"
        elif n_other > 0.1 * n_top:
            result["reason"] = "ambiguous_frames:conflicting_sides"
        else:
            conf = (sum(purities) / len(purities)) * min(1.0, n_top / 5.0)
            result["confidence"] = round(conf, 3)
            if conf < cfg.min_confidence:
                result["reason"] = f"ambiguous_frames:low_confidence_{conf:.2f}"
            else:
                # LAFC defend `side`, so they attack the other side of the screen.
                result["screen_dir"] = "right" if side == "left" else "left"
                result["t_first"] = first_t[side]
                result["reason"] = "ok"

    try:
        save_contact_sheet(thumbs, frames, frames_dir / "contact_sheet.jpg", lafc_kit)
        slim = [{k: v for k, v in f.items() if k != "blobs"} for f in frames]
        (frames_dir / "frames.json").write_text(json.dumps({"clip": str(path), "result": result, "frames": slim}, indent=1))
    except Exception as exc:  # noqa: BLE001
        logger.debug("could not write review artefacts for %s: %s", frames_dir, exc)
    return result


# --------------------------------------------------------------------------------------
# Dataset I/O
# --------------------------------------------------------------------------------------
def load_matches(path: pathlib.Path):
    import pandas as pd

    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    for c in NEW_COLUMNS:
        if c not in df.columns:
            df[c] = ""
    df.loc[df["first_half_direction"] == "", "first_half_direction"] = UNVERIFIED
    return df


def _line_terminator(path: pathlib.Path) -> str:
    """Keep whatever line ending the CSV already uses (build_dataset.py writes CRLF via csv.writer)."""
    try:
        with open(path, "rb") as f:
            first = f.readline()
        return "\r\n" if first.endswith(b"\r\n") else "\n"
    except OSError:
        return "\n"


def save_matches(df, path: pathlib.Path) -> None:
    df.to_csv(path, index=False, lineterminator=_line_terminator(path))


def update_labels(row: dict, direction: str | None, source: str, timestamp: str, note: str, force: bool) -> None:
    """Mirror the result into data/direction_labels.csv without touching human 'verified' rows."""
    if not LABELS_CSV.exists():
        return
    with open(LABELS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        rows = list(reader)
    changed = False
    for r in rows:
        if r.get("date") != row["date"]:
            continue
        if r.get("status") == "verified" and r.get("coder") and r["coder"] != SCRIPT_TAG and not force:
            break  # a human label wins over the automated one
        r["attacking_end_1h"] = direction.lower() if direction else ""
        r["status"] = "verified" if direction else "unverified"
        r["evidence_type"] = "youtube_kickoff_frames" if direction else ""
        r["video_url"] = source
        r["video_timestamp"] = timestamp
        r["landmark"] = ("team halves at kickoff -> screen side -> camera-side calibration" if direction else "")
        r["coder"] = SCRIPT_TAG
        r["notes"] = note
        changed = True
        break
    if changed:
        with open(LABELS_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)


def write_row(df, idx, direction: str | None, source: str, note: str, screen_dir: str | None, conf: float) -> None:
    df.at[idx, "first_half_direction"] = direction or UNVERIFIED
    df.at[idx, "verification_source"] = source
    df.at[idx, "verification_note"] = note
    df.at[idx, "first_half_screen_direction"] = screen_dir or ""
    df.at[idx, "verification_confidence"] = f"{conf:.3f}" if conf else ""
    if "attacking_end_1h" in df.columns:
        df.at[idx, "attacking_end_1h"] = direction.lower() if direction else "unknown"
    if "direction_status" in df.columns:
        df.at[idx, "direction_status"] = "verified" if direction else "unverified"


# --------------------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------------------
def summarise(df, print_it: bool = True) -> str:
    lines = []
    P = lines.append
    reg = df[df["competition"] == "MLS"]
    P("# LAFC first-half attacking direction at BMO Stadium: empirical count\n")
    P(f"Generated {dt.datetime.now():%Y-%m-%d %H:%M} by {SCRIPT_TAG}. "
      f"Sequence A = 1H attacking North (the 3252) / 2H South; Sequence B = 1H South (scoreboard) / 2H North.\n")
    P("## MLS regular season, by season\n")
    P("| Season | Matches | Seq A (1H North) | Seq B (1H South) | Unverified | Verified % |")
    P("|---|---|---|---|---|---|")
    tot = Counter()
    for season, d in reg.groupby("season", sort=True):
        a = int((d["first_half_direction"] == NORTH).sum())
        b = int((d["first_half_direction"] == SOUTH).sum())
        u = len(d) - a - b
        tot.update({"n": len(d), "a": a, "b": b, "u": u})
        P(f"| {season} | {len(d)} | {a} | {b} | {u} | {(a + b) / len(d):.0%} |")
    n = tot["n"] or 1
    P(f"| **Total** | {tot['n']} | {tot['a']} | {tot['b']} | {tot['u']} | {(tot['a'] + tot['b']) / n:.0%} |")
    other = df[df["competition"] != "MLS"]
    if len(other):
        a = int((other["first_half_direction"] == NORTH).sum())
        b = int((other["first_half_direction"] == SOUTH).sum())
        P(f"\nOther competitions at BMO (playoffs, cup ties; not in the regular-season count): "
          f"{len(other)} matches, Seq A {a}, Seq B {b}, Unverified {len(other) - a - b}.\n")
    unv = df[df["first_half_direction"] == UNVERIFIED]
    if len(unv):
        P("## Why rows are Unverified\n")
        P("| Reason | Rows |\n|---|---|")
        reasons = Counter((re.split(r"[;:]", r)[0] or "not_run") for r in unv["verification_note"])
        for reason, k in reasons.most_common():
            P(f"| {reason} | {k} |")
        P("")
    text = "\n".join(lines)
    if print_it:
        print("\n" + text)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_MD.write_text(text + "\n", encoding="utf-8")
    return text


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", type=pathlib.Path, default=DEFAULT_CSV, help="matches.csv to verify and update in place")
    ap.add_argument("--camera-side", choices=["west", "east", "unknown"], default="unknown",
                    help="sideline the main broadcast camera is on; 'unknown' keeps rows Unverified (default)")
    ap.add_argument("--lafc-kit", choices=["dark", "light", "grey"], default="dark",
                    help="kit class LAFC wore (per-match overrides in data/kit_overrides.csv)")
    ap.add_argument("--limit", type=int, default=0, help="process at most N matches (0 = all)")
    ap.add_argument("--date", help="only this match date (YYYY-MM-DD)")
    ap.add_argument("--season", help="only this season (YYYY)")
    ap.add_argument("--competition", help="only this competition value, e.g. MLS")
    ap.add_argument("--force", action="store_true", help="re-verify rows that already hold North/South")
    ap.add_argument("--remap-only", action="store_true",
                    help="only re-map stored screen directions with --camera-side; no network, no video")
    ap.add_argument("--summary-only", action="store_true", help="print the season summary from the CSV and exit")
    ap.add_argument("--dry-run", action="store_true", help="search and validate videos but do not download")
    ap.add_argument("--clip-seconds", type=int, default=90, help="seconds of video to download and inspect")
    ap.add_argument("--sample-fps", type=float, default=2.0, help="frames analysed per second of clip")
    ap.add_argument("--max-height", type=int, default=480, help="max video height to download")
    ap.add_argument("--search-results", type=int, default=6, help="YouTube results per query")
    ap.add_argument("--max-details-per-query", type=int, default=3, help="full metadata fetches per query")
    ap.add_argument("--max-upload-lag-days", type=int, default=14, help="video must be uploaded within N days of match")
    ap.add_argument("--max-duration", type=int, default=25 * 60, help="videos longer than this are not highlights")
    ap.add_argument("--accept-long-videos", action="store_true", help="also accept full-match replays")
    ap.add_argument("--allow-club-channels", action="store_true", help="accept opponent club channels too")
    ap.add_argument("--allow-unofficial", action="store_true", help="accept any channel (not recommended)")
    ap.add_argument("--delay", type=float, default=2.0, help="base delay in seconds between YouTube requests")
    ap.add_argument("--cookies", help="cookies.txt for yt-dlp (age-gated or bot-check videos)")
    ap.add_argument("--min-grass", type=float, default=0.35, help="grass fraction that defines a wide shot")
    ap.add_argument("--purity", type=float, default=0.8, help="fraction of a kit's blobs that must sit in one half")
    ap.add_argument("--min-team-blobs", type=int, default=4, help="blobs needed to count a kit class as a team")
    ap.add_argument("--min-agree", type=int, default=3, help="kickoff-like frames that must agree")
    ap.add_argument("--min-confidence", type=float, default=0.7, help="confidence below this is Unverified")
    ap.add_argument("--allow-no-midline", action="store_true", help="accept split frames without a detected halfway line")
    ap.add_argument("--no-install", action="store_true", help="never pip install missing dependencies")
    ap.add_argument("--no-short-circuit", action="store_true", help="keep trying YouTube after repeated network failures")
    ap.add_argument("-v", "--verbose", action="store_true")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    logger = setup_logging(args.verbose)
    ensure_dependencies(allow_install=not args.no_install)
    import pandas as pd  # noqa: F401

    if not args.csv.exists():
        logger.error("dataset not found: %s", args.csv)
        return 2
    df = load_matches(args.csv)
    logger.info("loaded %d matches from %s", len(df), args.csv)

    if args.summary_only:
        summarise(df)
        return 0

    if args.remap_only:
        if args.camera_side == "unknown":
            logger.error("--remap-only needs --camera-side west|east")
            return 2
        n = 0
        for idx, row in df.iterrows():
            sd = row["first_half_screen_direction"]
            if sd in ("left", "right") and (args.force or row["first_half_direction"] == UNVERIFIED):
                direction = screen_to_compass(sd, args.camera_side)
                note = re.sub(r"camera_side_uncalibrated[^;]*", f"camera_side={args.camera_side}", row["verification_note"]) \
                    if "camera_side_uncalibrated" in row["verification_note"] else \
                    f"{row['verification_note']};camera_side={args.camera_side}"
                conf = float(row["verification_confidence"] or 0)
                write_row(df, idx, direction, row["verification_source"], note, sd, conf)
                ts = row["verification_source"].split("&t=")[-1] if "&t=" in row["verification_source"] else ""
                update_labels(row, direction, row["verification_source"], ts, note, args.force)
                n += 1
        save_matches(df, args.csv)
        logger.info("re-mapped %d rows with camera side = %s", n, args.camera_side)
        summarise(df)
        return 0

    # ---- normal run -------------------------------------------------------------------
    ffmpeg_dir = ensure_ffmpeg(allow_install=not args.no_install)
    if ffmpeg_dir is None:
        logger.warning("no ffmpeg available: downloads will be marked ffmpeg_missing")
    cfg = FrameConfig(args)
    overrides = read_optional_csv(OVERRIDES_CSV)
    kits = read_optional_csv(KIT_CSV)
    if args.camera_side == "unknown":
        logger.warning("camera side not calibrated: screen sides will be recorded but rows stay Unverified. "
                       "Run once with --remap-only --camera-side west|east after checking a contact sheet.")

    sel = df
    if args.date:
        sel = sel[sel["date"] == args.date]
    if args.season:
        sel = sel[sel["season"] == args.season]
    if args.competition:
        sel = sel[sel["competition"] == args.competition]
    if not args.force:
        sel = sel[~sel["first_half_direction"].isin([NORTH, SOUTH])]
    if args.limit:
        sel = sel.head(args.limit)
    todo = list(sel.index)
    logger.info("%d matches to process (%d already verified and kept)", len(todo),
                int(df["first_half_direction"].isin([NORTH, SOUTH]).sum()))

    finder = None
    network_down = False
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.time()
    counts: Counter = Counter()
    with open(LOG_JSONL, "a", encoding="utf-8") as jlog:
        for k, idx in enumerate(todo, 1):
            row = df.loc[idx]
            match = {"date": row["date"], "opponent": row["opponent"], "competition": row["competition"],
                     "date_obj": parse_date(row["date"])}
            lafc_kit = (kits.get(row["date"], {}).get("lafc_kit") or args.lafc_kit).strip().lower()
            rec = {"ts": dt.datetime.now().isoformat(timespec="seconds"), "date": row["date"],
                   "opponent": row["opponent"], "competition": row["competition"], "lafc_kit": lafc_kit,
                   "camera_side": args.camera_side}
            head = f"[{k}/{len(todo)}] {row['date']} vs {row['opponent']} ({row['competition']})"
            direction, screen_dir, conf, source, note = None, None, 0.0, "", ""
            video, clip = None, None
            try:
                ov = overrides.get(row["date"])
                if ov and ov.get("video"):
                    v = ov["video"].strip()
                    if v.startswith("http"):
                        vid = re.search(r"(?:v=|youtu\.be/)([\w-]{6,})", v)
                        video = {"id": vid.group(1) if vid else re.sub(r"\W", "_", v)[-16:], "url": v,
                                 "title": ov.get("note", "override"), "channel": "override"}
                        rec["override"] = v
                    else:
                        clip = pathlib.Path(v)
                        if not clip.is_absolute():
                            clip = ROOT / clip
                        rec["override"] = str(clip)
                        if not clip.exists():
                            note = "override_clip_missing"
                            clip = None
                if clip is None and video is None and not note:
                    if network_down:
                        note = "network_blocked:short_circuit"
                    else:
                        if finder is None:
                            finder = VideoFinder(args, ffmpeg_dir, logger)
                        logger.info("%s searching YouTube ...", head)
                        video, why = finder.find(match, rec)
                        if video is None:
                            note = why
                            logger.info("%s no usable video (%s)", head, why)
                if video is not None and clip is None and not note:
                    rec["video"] = video
                    logger.info("%s video: %s [%s] %s", head, video["title"], video.get("channel"), video["url"])
                    if args.dry_run:
                        note = "dry_run"
                    else:
                        if finder is None:
                            finder = VideoFinder(args, ffmpeg_dir, logger)
                        logger.info("%s downloading first %ds ...", head, args.clip_seconds)
                        clip, why = finder.download_clip(video, match)
                        if clip is None:
                            note = why
                            logger.info("%s download failed (%s)", head, why)
                    source = video["url"]
                if clip is not None and not note:
                    frames_dir = FRAMES_DIR / row["date"]
                    logger.info("%s analysing frames (%s) ...", head, clip.name)
                    res = analyse_clip(clip, cfg, lafc_kit, frames_dir, logger)
                    rec["analysis"] = res
                    base = video["url"] if video else str(clip)
                    if res.get("screen_dir"):
                        screen_dir = res["screen_dir"]
                        conf = res["confidence"]
                        t = int(res["t_first"])
                        source = f"{base}&t={t}s" if base.startswith("http") else f"{base}#t={t}"
                        direction = screen_to_compass(screen_dir, args.camera_side)
                        method = (f"kickoff_frames:n_agree={max(res['votes'].values())};kit={lafc_kit};"
                                  f"screen={screen_dir};contact_sheet={frames_dir.relative_to(ROOT)}/contact_sheet.jpg")
                        note = method + (f";camera_side={args.camera_side}" if direction else
                                         ";camera_side_uncalibrated (run --remap-only --camera-side west|east)")
                    else:
                        t = res.get("t_first_wide")
                        if t is not None:
                            source = f"{base}&t={int(t)}s" if base.startswith("http") else f"{base}#t={int(t)}"
                        note = f"{res.get('reason')};contact_sheet={frames_dir.relative_to(ROOT)}/contact_sheet.jpg"
            except NetworkBlocked:
                note = "network_blocked"
                if finder and finder.consecutive_network_failures >= 3 and not args.no_short_circuit:
                    if not network_down:
                        logger.error("YouTube unreachable three times in a row (proxy/network policy blocks "
                                     "youtube.com / googlevideo.com). Remaining matches are marked Unverified "
                                     "without further requests; re-run once the hosts are allowed.")
                    network_down = True
            except Exception as exc:  # noqa: BLE001 - one bad match must not stop the run
                note = f"error:{type(exc).__name__}:{str(exc)[:120]}"
                logger.exception("%s unexpected error", head)

            write_row(df, idx, direction, source, note, screen_dir, conf)
            ts = ""
            m = re.search(r"[&#]t=(\d+)", source)
            if m:
                ts = m.group(1) + "s"
            update_labels(match, direction, source, ts, note, args.force)
            rec.update({"result": direction or UNVERIFIED, "screen_dir": screen_dir, "confidence": conf,
                        "source": source, "note": note})
            jlog.write(json.dumps(rec, default=str) + "\n")
            jlog.flush()
            counts[direction or f"{UNVERIFIED}:{note.split(':')[0].split(';')[0]}"] += 1
            logger.info("%s -> %s%s", head, direction or UNVERIFIED,
                        f" (screen {screen_dir}, conf {conf:.2f})" if screen_dir else f" ({note.split(';')[0]})")
            save_matches(df, args.csv)  # checkpoint after every match

    logger.info("done in %.0fs: %s", time.time() - started, dict(counts))
    save_matches(df, args.csv)
    summarise(df)
    return 0


if __name__ == "__main__":
    sys.exit(main())
