#!/usr/bin/env python3
import argparse
from datetime import datetime, timedelta
import time

import cv2
import pytesseract


def crop_frame_to_competitor_names(frame, height, width):
    # crop to the section of the stream that's actually relevant
    # to our OCR engine - the small section where names actually
    # show up
    # 
    # note that we assume a 16:9 aspect ratio here - 
    # anything else will be likely to break our text recognition
    return frame[3*(height//16):height//2, 
                 3*(width//32):29*(width//32)]


ap = argparse.ArgumentParser()
ap.add_argument("-v", "--video", type=str, help="path to input video file [required]")
ap.add_argument("-f", "--competitors-file", type=str, default="competitors.txt",
	            help="path to input file listing competitors (default:competitors.txt)")
ap.add_argument("-o", "--output-file", type=str, default="output.csv",
	            help="path to input file listing competitors (default:output.csv)")
ap.add_argument("-s", "--seconds", type=float, default=5,
                help="seconds between OCR captures to check for competitor names (default:5)")
ap.add_argument("-j", "--jump-to-timestamp", type=str,
                help="start at a specific time")
ap.add_argument("-d", "--debug", action="store_true",
                help="print OCR capture strings as the program runs")
args = vars(ap.parse_args())

# competitor_names list will be used to check for relevant names
# in OCR-captured strings
competitor_names = []
with open(args["competitors_file"], "r") as infile:
    for row in infile.readlines():
        competitor_names.append(row.replace("\n","").strip())

video = cv2.VideoCapture(args["video"])
video_fps = video.get(cv2.CAP_PROP_FPS)
video_frames_total = int(video.get(cv2.CAP_PROP_FRAME_COUNT))

print("== INITIALIZING ==")
print(f"Video filename: {args['video']}")
print(f"Video FPS: {video_fps}")
print(f"Comptitor list: {args['competitors_file']}")
print(f"Output filename: {args['output_file']}")
print(f"Seconds between OCR capture frames: {args['seconds']}")
FRAMES_TO_ITERATE = int(args["seconds"] * video_fps)

# read shape from first frame so we don't need to get dimensions on
# each loop iteration
start_time = time.time()
rval, first_frame = video.read()
f_height, f_width, f_channels = first_frame.shape
video_time = timedelta(seconds=0)
if args["jump_to_timestamp"]:
    timeskip_str = datetime.strptime(args["jump_to_timestamp"],"%H:%M:%S")
    initial_timeskip = timedelta(
        hours=timeskip_str.hour,
        minutes=timeskip_str.minute,
        seconds=timeskip_str.second
    )
    video_time += initial_timeskip
    first_frame = initial_timeskip.seconds * video_fps
else:
    first_frame = 0
output_file = open(args["output_file"],"w")

# start scanning through the video, looking for instances of listed
# competitor names
print("\n== SCANNING ==")
for current_frame in range(first_frame, video_frames_total, FRAMES_TO_ITERATE):
    video.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
    rval, frame = video.read()
    if not rval:
        break
    
    # we make the frame from our video that OCR has to process smaller,
    # by converting it to grayscale and cropping it only to the area
    # where the relevant competitor names will actually show up on
    # the stream
    ocr_frame = crop_frame_to_competitor_names(
        cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), f_height, f_width
    )
    # From the Tesseract docs:
    # PSM=11: Sparse text. Find as much text as possible in no particular order.
    # This seems to be faster and more accurate than the default method about
    # getting the names we're looking for.
    frame_as_str = pytesseract.image_to_string(ocr_frame,config="--psm 11")
    detected_competitor_names = []
    for name in competitor_names:
        lowered_frame_str = frame_as_str.lower()
        competitor_name_in_frame = all(
            map(lambda x: x.lower() in lowered_frame_str, name.split())
        )
        if competitor_name_in_frame:
            output_file.write(f"{name},{video_time}\n")
            output_file.flush()
            detected_competitor_names.append(f"found {name}")
    video_time += timedelta(seconds=args["seconds"])
    if args["debug"]:
        print("== DEBUG START ==")
        print(frame_as_str)
        print("== DEBUG END ==")
    print(f"{video_time} -- {(current_frame/video_frames_total)*100:.2f}%"
          + " video scanned... " + ", ".join(detected_competitor_names))
output_file.close()

print("== SUCCESS ==")
print(f"Scanned through {video_frames_total} frames in {time.time() - start_time}s")