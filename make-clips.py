#!/usr/bin/env python3
import argparse
import csv
import os
import subprocess
from datetime import timedelta


def parse_timedelta(s):
    # handles both H:MM:SS and H:MM:SS.ffffff from csv output
    s = s.strip()
    if "." in s:
        s = s.split(".")[0]
    parts = s.split(":")
    return timedelta(hours=int(parts[0]), minutes=int(parts[1]), seconds=int(parts[2]))


def timedelta_to_seconds(td):
    return max(0, td.total_seconds())


def format_timestamp_for_filename(td):
    total = int(td.total_seconds())
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}_{m:02d}_{s:02d}"


def build_clip_filename(name, start_td):
    safe_name = name.replace(" ", "_").replace("/", "_")
    ts_str = format_timestamp_for_filename(start_td)
    return f"{safe_name}_{ts_str}.mp4"


def build_ffmpeg_cmd(ffmpeg_bin, input_file, clip_start, duration, output_path):
    return [
        ffmpeg_bin,
        "-y",
        "-ss", str(clip_start),
        "-i", input_file,
        "-t", str(duration),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-movflags", "+faststart",
        output_path,
    ]


def compute_clip_window(start_td, end_td, padding_seconds):
    """Return (clip_start_seconds, duration_seconds) with padding applied."""
    clip_start = timedelta_to_seconds(start_td - timedelta(seconds=padding_seconds))
    clip_end = timedelta_to_seconds(end_td + timedelta(seconds=padding_seconds))
    return clip_start, clip_end - clip_start


def read_timestamps_csv(path, fallback_video_file=None):
    """Return list of (name, start_timedelta, end_timedelta, video_file) from a CSV file.

    If a row has no video_file column, fallback_video_file is used instead.
    """
    rows = []
    with open(path, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            name = row[0].strip()
            start_td = parse_timedelta(row[1])
            end_td = parse_timedelta(row[2])
            video_file = row[3].strip() if len(row) >= 4 else fallback_video_file
            rows.append((name, start_td, end_td, video_file))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input-file", type=str, default=None,
                    help="path to source video file (required if CSV has no video_file column)")
    ap.add_argument("-t", "--timestamps-file", type=str, default="output.csv",
                    help="path to CSV of match windows from get-smoothcomp-timestamps.py (default:output.csv)")
    ap.add_argument("-o", "--output-dir", type=str, default="clips",
                    help="directory to write clip files into (default:clips)")
    ap.add_argument("-p", "--clip-padding", type=float, default=10,
                    help="seconds of padding before and after each match window (default:10)")
    ap.add_argument("--ffmpeg", type=str, default="ffmpeg",
                    help="path to ffmpeg binary (default:ffmpeg)")
    args = vars(ap.parse_args())

    os.makedirs(args["output_dir"], exist_ok=True)

    rows = read_timestamps_csv(args["timestamps_file"], fallback_video_file=args["input_file"])

    if not rows:
        print("No match windows found in timestamps file.")
        exit(0)

    missing = [r for r in rows if not r[3]]
    if missing:
        print("ERROR: some rows have no video file. Pass -i/--input-file or re-scan with a newer version of the script.")
        for r in missing:
            print(f"  {r[0]} {r[1]}")
        exit(1)

    print(f"== MAKING CLIPS ==")
    print(f"Timestamps file: {args['timestamps_file']}")
    print(f"Output dir: {args['output_dir']}")
    print(f"Clip padding: {args['clip_padding']}s")
    print(f"Clips to generate: {len(rows)}\n")

    for name, start_td, end_td, video_file in rows:
        clip_start, duration = compute_clip_window(start_td, end_td, args["clip_padding"])
        output_path = os.path.join(args["output_dir"], build_clip_filename(name, start_td))

        print(f"Clipping {name} [{start_td} -> {end_td}] from {video_file}")
        print(f"  (with padding: {clip_start:.0f}s -> {clip_start + duration:.0f}s)")
        print(f"  -> {output_path}")

        cmd = build_ffmpeg_cmd(args["ffmpeg"], video_file, clip_start, duration, output_path)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ERROR: ffmpeg failed for {name}")
            print(result.stderr[-500:])
        else:
            print(f"  done.")

    print("\n== SUCCESS ==")
    print(f"Clips written to {args['output_dir']}/")
