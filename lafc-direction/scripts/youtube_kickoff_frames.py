"""Pull highlight/full-match video for each LAFC home match and dump frames for
attacking-direction coding. Runs only where youtube.com and *.googlevideo.com are
reachable (this cloud environment's network policy currently blocks them).

Usage:
  pip install yt-dlp imageio-ffmpeg
  python scripts/youtube_kickoff_frames.py --limit 10          # first 10 unlabelled matches
  python scripts/youtube_kickoff_frames.py --date 2024-04-27   # one match

For each match it (1) searches YouTube for the MLS/LAFC highlights, (2) downloads the
lowest-quality stream, (3) extracts frames every 2 s over the first 90 s and around
every goal minute, into out/frames/<date>/. A coder (human or vision model) then reads
the frames: the North goal is the one with the 3252 safe-standing terrace behind it and
the open north-east 'keyhole' corner with the downtown skyline beside it; the scorebug
minute fixes the half. Record the result in data/direction_labels.csv with the video
URL, timestamp and landmark used. Never infer direction from the score.
"""
import argparse, csv, pathlib, subprocess, sys, json, shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]

def ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe: return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

def find_video(date, opponent):
    q = f"ytsearch5:LAFC vs {opponent} highlights {date}"
    r = subprocess.run(["yt-dlp", "--flat-playlist", "-J", q], capture_output=True, text=True, check=True)
    entries = json.loads(r.stdout).get("entries", [])
    pref = [e for e in entries if any(k in (e.get("uploader") or e.get("channel") or "").lower() for k in ("mls", "lafc"))]
    return (pref or entries)[0]["url"] if (pref or entries) else None

def dump_frames(url, date, goals):
    dest = ROOT / "out/frames" / date; dest.mkdir(parents=True, exist_ok=True)
    vid = dest / "video.mp4"
    if not vid.exists():
        subprocess.run(["yt-dlp", "-f", "worst[ext=mp4]/worst", "-o", str(vid), url], check=True)
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", str(vid), "-t", "90", "-vf", "fps=0.5", str(dest / "open_%03d.jpg")], check=True)
    (dest / "source.txt").write_text(url + "\n")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int, default=5); ap.add_argument("--date")
    a = ap.parse_args()
    labels = list(csv.DictReader(open(ROOT / "data/direction_labels.csv")))
    todo = [l for l in labels if (a.date and l["date"] == a.date) or (not a.date and l["status"] != "verified")][: a.limit]
    for l in todo:
        url = find_video(l["date"], l["opponent"])
        print(l["date"], l["opponent"], "->", url)
        if url: dump_frames(url, l["date"], None)

if __name__ == "__main__":
    main()
