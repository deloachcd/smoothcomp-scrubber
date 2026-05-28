#!/usr/bin/env python3
from datetime import timedelta


def crop_frame_to_competitor_names(frame, height, width):
    # crop to the section of the stream that's actually relevant
    # to our OCR engine - the small section where names actually
    # show up
    #
    # note that we assume a 16:9 aspect ratio here -
    # anything else will be likely to break our text recognition
    return frame[3*(height//16):height//2,
                 3*(width//32):29*(width//32)]


def detect_competitor_names(frame_as_str, competitor_names):
    """Return list of names from competitor_names found in frame_as_str."""
    detected = []
    lowered = frame_as_str.lower()
    for name in competitor_names:
        if all(part.lower() in lowered for part in name.split()):
            detected.append(name)
    return detected


def update_match_windows(active_matches, competitor_names, detected_names, video_time, gap_tolerance):
    """Update open match windows given the current set of detected names.

    Returns list of (name, start_time, end_time) for any windows that closed.
    Mutates active_matches in place.
    """
    closed = []
    for name in competitor_names:
        if name in detected_names:
            if name not in active_matches:
                active_matches[name] = {"start_time": video_time, "miss_count": 0}
            else:
                active_matches[name]["miss_count"] = 0
        elif name in active_matches:
            active_matches[name]["miss_count"] += 1
            if active_matches[name]["miss_count"] > gap_tolerance:
                match = active_matches.pop(name)
                closed.append((name, match["start_time"], video_time))
    return closed


if __name__ == "__main__":
    import argparse
    from datetime import datetime
    import time
    import os
    import cv2
    import pytesseract

    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input-file", type=str, help="path to input video file [required]")
    ap.add_argument("-f", "--competitors-file", type=str, default="competitors.txt",
                    help="path to input file listing competitors (default:competitors.txt)")
    ap.add_argument("-o", "--output-file", type=str, default="output.csv",
                    help="path to input file listing competitors (default:output.csv)")
    ap.add_argument("-s", "--interval-seconds", type=float, default=5,
                    help="seconds between OCR captures to check for competitor names (default:5)")
    ap.add_argument("-g", "--gap-tolerance", type=int, default=3,
                    help="consecutive missed intervals before closing a match window (default:3)")
    ap.add_argument("--jump-to-timestamp", type=str,
                    help="start at a specific time: (format:HH:MM:SS)")
    ap.add_argument("--psm", type=str, default=11,
                    help="have tesseract-ocr use a specific PSM (default:11)")
    ap.add_argument("--print-captured-strings", action="store_true",
                    help="print OCR capture strings as the program runs")
    ap.add_argument("--print-build-info", action="store_true",
                    help="print OpenCV build info")
    ap.add_argument("--opencv-log-level", type=str, default="WARNING",
                    help="seconds between OCR captures to check for competitor names (default:5)")
    args = vars(ap.parse_args())

    if args["opencv_log_level"]:
        os.environ["OPENCV_LOG_LEVEL"] = args["opencv_log_level"]
    if args["print_build_info"]:
        print(cv2.getBuildInformation())

    competitor_names = []
    with open(args["competitors_file"], "r") as infile:
        for row in infile.readlines():
            competitor_names.append(row.replace("\n","").strip())

    # use ffmpeg backend and don't even try to use hardware acceleration for the
    # sake of portability
    video = cv2.VideoCapture(args["input_file"], cv2.CAP_FFMPEG, [
        cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_NONE
    ])
    video_fps = video.get(cv2.CAP_PROP_FPS)
    video_frames_total = int(video.get(cv2.CAP_PROP_FRAME_COUNT))

    if not video.isOpened():
        print("Error opening video stream")
        exit()

    print("== INITIALIZING ==")
    print(f"Video filename: {args['input_file']}")
    print(f"Video FPS: {video_fps}")
    print(f"Comptitor list: {args['competitors_file']}")
    print(f"Output filename: {args['output_file']}")
    print(f"Seconds between OCR capture frames: {args['interval_seconds']}")
    print(f"Gap tolerance (missed intervals before closing window): {args['gap_tolerance']}")
    frames_to_iterate = int(args["interval_seconds"] * video_fps)

    start_time = time.time()
    rval, first_frame = video.read()
    if rval:
        f_height, f_width, f_channels = first_frame.shape
    else:
        print("Could not get first frame of video file! (bad return value)")
    video_time = timedelta(seconds=0)
    if args["jump_to_timestamp"]:
        timeskip_str = datetime.strptime(args["jump_to_timestamp"],"%H:%M:%S")
        initial_timeskip = timedelta(
            hours=timeskip_str.hour,
            minutes=timeskip_str.minute,
            seconds=timeskip_str.second
        )
        video_time += initial_timeskip
        first_frame = int(initial_timeskip.seconds * video_fps)
    else:
        first_frame = 0
    output_file = open(args["output_file"],"w")

    active_matches = {}

    print("\n== SCANNING ==")
    for current_frame in range(first_frame, video_frames_total, frames_to_iterate):
        video.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
        rval, frame = video.read()
        if not rval:
            break

        ocr_frame = crop_frame_to_competitor_names(
            cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), f_height, f_width
        )
        frame_as_str = pytesseract.image_to_string(ocr_frame, config=f"--psm {args['psm']} -c load_system_dawg=false -c load_freq_dawg=false")

        detected_names = detect_competitor_names(frame_as_str, competitor_names)
        closed = update_match_windows(active_matches, competitor_names, detected_names, video_time, args["gap_tolerance"])

        for name, start, end in closed:
            output_file.write(f"{name},{start},{end}\n")
            output_file.flush()
            print(f"  >> closed window for {name}: {start} -> {end}")

        for name in detected_names:
            if name in active_matches and active_matches[name]["miss_count"] == 0 and active_matches[name]["start_time"] == video_time:
                print(f"  >> opened window for {name} at {video_time}")

        video_time += timedelta(seconds=args["interval_seconds"])
        if args["print_captured_strings"]:
            print("== CAPTURED STR START ==")
            print(frame_as_str)
            print("== CAPTURE STR END ==")
        print(f"{video_time} -- {(current_frame/video_frames_total)*100:.2f}%"
              + " video scanned... " + ", ".join([f"found {n}" for n in detected_names]))

    # close any windows still open at end of video
    for name in list(active_matches.keys()):
        match = active_matches.pop(name)
        output_file.write(f"{name},{match['start_time']},{video_time}\n")
        output_file.flush()
        print(f"  >> closed window for {name}: {match['start_time']} -> {video_time}")

    output_file.close()

    print("== SUCCESS ==")
    print(f"Scanned through {video_frames_total} frames in {time.time() - start_time}s")
