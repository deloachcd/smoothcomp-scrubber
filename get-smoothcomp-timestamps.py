#!/usr/bin/env python3
import sys
sys.stdout.reconfigure(line_buffering=True)

from datetime import timedelta


def log(msg):
    from datetime import datetime
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def crop_frame_to_competitor_names(frame, height, width):
    # crop to the section of the stream that's actually relevant
    # to our OCR engine - the small section where names actually
    # show up
    #
    # note that we assume a 16:9 aspect ratio here -
    # anything else will be likely to break our text recognition
    return frame[3*(height//16):height//2,
                 3*(width//32):29*(width//32)]


def load_competitor_names(path):
    """Load competitor names from a file, skipping blank lines."""
    names = []
    with open(path, "r") as f:
        for row in f.readlines():
            name = row.replace("\n", "").strip()
            if name:
                names.append(name)
    return names


def detect_competitor_names(frame_as_str, competitor_names):
    """Return list of names from competitor_names found in frame_as_str."""
    detected = []
    lowered = frame_as_str.lower()
    for name in competitor_names:
        parts = name.split()
        if parts and all(part.lower() in lowered for part in parts):
            detected.append(name)
    return detected


def update_match_windows(active_matches, competitor_names, detected_names, video_time, gap_tolerance):
    """Update open match windows given the current set of detected names.

    Returns list of (name, start_time, end_time) for any windows that closed.
    end_time is the last frame the name was actually detected, not the frame
    where the gap tolerance was exceeded.
    Mutates active_matches in place.
    """
    closed = []
    for name in competitor_names:
        if name in detected_names:
            if name not in active_matches:
                active_matches[name] = {
                    "start_time": video_time,
                    "last_seen_time": video_time,
                    "miss_count": 0,
                }
            else:
                active_matches[name]["miss_count"] = 0
                active_matches[name]["last_seen_time"] = video_time
        elif name in active_matches:
            active_matches[name]["miss_count"] += 1
            if active_matches[name]["miss_count"] > gap_tolerance:
                match = active_matches.pop(name)
                end_time = match.get("last_seen_time", video_time)
                closed.append((name, match["start_time"], end_time))
    return closed


def format_eta(seconds_remaining):
    seconds_remaining = int(seconds_remaining)
    h = seconds_remaining // 3600
    m = (seconds_remaining % 3600) // 60
    s = seconds_remaining % 60
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def scan_video(input_file, competitor_names, output_file, interval_seconds,
               gap_tolerance, psm, jump_to_timestamp=None, print_captured_strings=False):
    """Scan a single video file for competitor match windows.

    Writes rows of (name, start_time, end_time, video_file) to output_file.
    """
    # cv2/pytesseract imported here so the pure functions above can be imported
    # in tests without requiring those packages to be installed on the host.
    import cv2
    import pytesseract
    from datetime import datetime
    import time

    video = cv2.VideoCapture(input_file, cv2.CAP_FFMPEG, [
        cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_NONE
    ])

    if not video.isOpened():
        log(f"Error opening video stream: {input_file}")
        return

    video_fps = video.get(cv2.CAP_PROP_FPS)
    video_frames_total = int(video.get(cv2.CAP_PROP_FRAME_COUNT))

    log(f"Video FPS: {video_fps}")
    frames_to_iterate = int(interval_seconds * video_fps)

    start_time = time.time()
    rval, first_frame_data = video.read()
    if rval:
        f_height, f_width, _ = first_frame_data.shape
    else:
        log("Could not get first frame of video file! (bad return value)")
        return

    if jump_to_timestamp:
        timeskip_str = datetime.strptime(jump_to_timestamp, "%H:%M:%S")
        initial_timeskip = timedelta(
            hours=timeskip_str.hour,
            minutes=timeskip_str.minute,
            seconds=timeskip_str.second
        )
        start_frame = int(initial_timeskip.total_seconds() * video_fps)
    else:
        start_frame = 0

    active_matches = {}
    last_frame = start_frame
    frames_remaining = video_frames_total - start_frame

    for current_frame in range(start_frame, video_frames_total, frames_to_iterate):
        # derive video_time from actual frame position to avoid floating-point
        # drift when interval_seconds doesn't divide evenly into whole frames
        video_time = timedelta(seconds=current_frame / video_fps)
        last_frame = current_frame

        video.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
        rval, frame = video.read()
        if not rval:
            break

        ocr_frame = crop_frame_to_competitor_names(
            cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), f_height, f_width
        )
        frame_as_str = pytesseract.image_to_string(
            ocr_frame,
            config=f"--psm {psm} -c load_system_dawg=false -c load_freq_dawg=false"
        )

        detected_names = detect_competitor_names(frame_as_str, competitor_names)

        names_before = set(active_matches.keys())
        closed = update_match_windows(active_matches, competitor_names, detected_names, video_time, gap_tolerance)
        newly_opened = set(active_matches.keys()) - names_before

        for name, start, end in closed:
            output_file.write(f"{name},{start},{end},{input_file}\n")
            output_file.flush()
            log(f">> closed window for {name}: {start} -> {end}")

        for name in newly_opened:
            log(f">> opened window for {name} at {video_time}")

        if print_captured_strings:
            log("== CAPTURED STR START ==")
            print(frame_as_str)
            log("== CAPTURE STR END ==")

        elapsed = time.time() - start_time
        pct = (current_frame / video_frames_total) * 100
        frames_done = current_frame - start_frame + frames_to_iterate
        if frames_done > 0 and elapsed > 0:
            eta_str = f"ETA {format_eta(elapsed / frames_done * (frames_remaining - frames_done))}"
        else:
            eta_str = "ETA --"

        found_str = ", ".join([f"found {n}" for n in detected_names])
        log(f"{video_time} -- {pct:.1f}% -- {eta_str}" + (f" -- {found_str}" if found_str else ""))

    # close any windows still open at end of video
    final_time = timedelta(seconds=last_frame / video_fps) if video_frames_total > 0 else timedelta(0)
    for name in list(active_matches.keys()):
        match = active_matches.pop(name)
        end_time = match.get("last_seen_time", final_time)
        output_file.write(f"{name},{match['start_time']},{end_time},{input_file}\n")
        output_file.flush()
        log(f">> closed window for {name}: {match['start_time']} -> {end_time}")

    log(f"Scanned {video_frames_total} frames in {time.time() - start_time:.1f}s")


if __name__ == "__main__":
    import argparse
    import os
    import cv2

    ap = argparse.ArgumentParser()
    input_group = ap.add_mutually_exclusive_group(required=True)
    input_group.add_argument("-i", "--input-file", type=str,
                             help="path to a single input video file")
    input_group.add_argument("-I", "--input-files", type=str, nargs="+",
                             help="paths to multiple input video files")
    ap.add_argument("-f", "--competitors-file", type=str, default="competitors.txt",
                    help="path to input file listing competitors (default:competitors.txt)")
    ap.add_argument("-o", "--output-file", type=str, default="output.csv",
                    help="path to output CSV file (default:output.csv)")
    ap.add_argument("-s", "--interval-seconds", type=float, default=5,
                    help="seconds between OCR captures to check for competitor names (default:5)")
    ap.add_argument("-g", "--gap-tolerance", type=int, default=3,
                    help="consecutive missed intervals before closing a match window (default:3)")
    ap.add_argument("--jump-to-timestamp", type=str,
                    help="start at a specific time: (format:HH:MM:SS) — only applies to single-file mode")
    ap.add_argument("--psm", type=int, default=11,
                    help="have tesseract-ocr use a specific PSM (default:11)")
    ap.add_argument("--print-captured-strings", action="store_true",
                    help="print OCR capture strings as the program runs")
    ap.add_argument("--print-build-info", action="store_true",
                    help="print OpenCV build info")
    ap.add_argument("--opencv-log-level", type=str, default="WARNING",
                    help="OpenCV log level (default:WARNING)")
    args = vars(ap.parse_args())

    if args["opencv_log_level"]:
        os.environ["OPENCV_LOG_LEVEL"] = args["opencv_log_level"]
    if args["print_build_info"]:
        print(cv2.getBuildInformation())

    input_files = args["input_files"] if args["input_files"] else [args["input_file"]]
    competitor_names = load_competitor_names(args["competitors_file"])

    log("== INITIALIZING ==")
    log(f"Video file(s): {', '.join(input_files)}")
    log(f"Competitor list: {args['competitors_file']}")
    log(f"Output filename: {args['output_file']}")
    log(f"Seconds between OCR capture frames: {args['interval_seconds']}")
    log(f"Gap tolerance (missed intervals before closing window): {args['gap_tolerance']}")

    with open(args["output_file"], "w") as output_file:
        for i, input_file in enumerate(input_files):
            log(f"\n== SCANNING {input_file} ({i+1}/{len(input_files)}) ==")
            scan_video(
                input_file=input_file,
                competitor_names=competitor_names,
                output_file=output_file,
                interval_seconds=args["interval_seconds"],
                gap_tolerance=args["gap_tolerance"],
                psm=args["psm"],
                jump_to_timestamp=args["jump_to_timestamp"] if len(input_files) == 1 else None,
                print_captured_strings=args["print_captured_strings"],
            )

    log("== SUCCESS ==")
