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
                help="start at a specific time: (format:HH:MM:SS)")
ap.add_argument("-p", "--psm", type=str, default=11,
                help="have tesseract-ocr use a specific PSM (default:11)")
ap.add_argument("-d", "--debug", action="store_true",
                help="print OCR capture strings as the program runs")
ARGS = vars(ap.parse_args())

# competitor_names list will be used to check for relevant names
# in OCR-captured strings
competitor_names = []
with open(ARGS["competitors_file"], "r") as infile:
    for row in infile.readlines():
        competitor_names.append(row.replace("\n","").strip())

video = cv2.VideoCapture(ARGS["video"])
VIDEO_FPS = video.get(cv2.CAP_PROP_FPS)
VIDEO_FRAMES_TOTAL = int(video.get(cv2.CAP_PROP_FRAME_COUNT))

print("== INITIALIZING ==")
print(f"Video filename: {ARGS['video']}")
print(f"Video FPS: {VIDEO_FPS}")
print(f"Comptitor list: {ARGS['competitors_file']}")
print(f"Output filename: {ARGS['output_file']}")
print(f"Seconds between OCR capture frames: {ARGS['seconds']}")
FRAMES_TO_ITERATE = int(ARGS["seconds"] * VIDEO_FPS)

# read shape from first frame so we don't need to get dimensions on
# each loop iteration
START_TIME = time.time()
rval, first_frame = video.read()
F_HEIGHT, F_WIDTH, F_CHANNELS = first_frame.shape
video_time = timedelta(seconds=0)
if ARGS["jump_to_timestamp"]:
    TIMESKIP_STR = datetime.strptime(ARGS["jump_to_timestamp"],"%H:%M:%S")
    INITIAL_TIMESKIP = timedelta(
        hours=TIMESKIP_STR.hour,
        minutes=TIMESKIP_STR.minute,
        seconds=TIMESKIP_STR.second
    )
    video_time += INITIAL_TIMESKIP
    first_frame = int(INITIAL_TIMESKIP.seconds * VIDEO_FPS)
else:
    first_frame = 0
output_file = open(ARGS["output_file"],"w")

# start scanning through the video, looking for instances of listed
# competitor names
print("\n== SCANNING ==")
for current_frame in range(first_frame, VIDEO_FRAMES_TOTAL, FRAMES_TO_ITERATE):
    video.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
    rval, frame = video.read()
    if not rval:
        break
    
    # we make the frame from our video that OCR has to process smaller,
    # by converting it to grayscale and cropping it only to the area
    # where the relevant competitor names will actually show up on
    # the stream
    ocr_frame = crop_frame_to_competitor_names(
        cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), F_HEIGHT, F_WIDTH
    )
    # From the Tesseract docs:
    # PSM=11: Sparse text. Find as much text as possible in no particular order.
    # This seems to be faster and more accurate than the default method about
    # getting the names we're looking for.
    frame_as_str = pytesseract.image_to_string(ocr_frame,
                                               config=f"--psm {ARGS['psm']}")
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
    video_time += timedelta(seconds=ARGS["seconds"])
    if ARGS["debug"]:
        print("== DEBUG START ==")
        print(frame_as_str)
        print("== DEBUG END ==")
    print(f"{video_time} -- {(current_frame/VIDEO_FRAMES_TOTAL)*100:.2f}%"
          + " video scanned... " + ", ".join(detected_competitor_names))
output_file.close()

print("== SUCCESS ==")
print(f"Scanned through {VIDEO_FRAMES_TOTAL} frames in {time.time() - START_TIME}s")