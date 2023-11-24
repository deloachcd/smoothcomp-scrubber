#!/usr/bin/env python3
import argparse
import csv
import collections
import datetime
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


def detect_name_in_ocr_str(name, ocr_str):
    # detect name in condensed, lowercase OCR output by ensuring
    # that every character in the name shows up at least the same
    # number of times in the OCR string
    counter_name = collections.Counter(name)
    counter_ocr = collections.Counter(ocr_str)
    counter_name.subtract(counter_ocr)
    return all(counter_name[v] <= 0 for v in counter_name)


ap = argparse.ArgumentParser()
ap.add_argument("-v", "--video", type=str, help="path to input video file [required]")
ap.add_argument("-f", "--competitors-file", type=str, default="competitors.txt",
	            help="path to input file listing competitors (default:competitors.txt)")
ap.add_argument("-o", "--output-file", type=str, default="output.csv",
	            help="path to input file listing competitors (default:output.csv)")
ap.add_argument("-s", "--seconds", type=float, default=5,
                help="seconds between OCR captures to check for competitor names (default:5)")
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
video_time = datetime.timedelta(seconds=0)
output_file = open(args["output_file"],"a")

# start scanning through the video, looking for instances of listed
# competitor names
print("\n== SCANNING ==")
for current_frame in range(0, video_frames_total, FRAMES_TO_ITERATE):
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
    # getting the specific characters we're looking for (i.e. the ones in the
    # relevant names) - the 'drawback' is that we have to be more clever about 
    # how we match names (see: detect_name_in_ocr_string)
    frame_as_str = pytesseract.image_to_string(ocr_frame,config="--psm 11")
    condensed_ocr_str = "".join(list(filter(lambda c: c.isalnum(), frame_as_str)))
    detected_competitor_names = []
    for name in competitor_names:
        condensed_name = name.replace(" ", "")
        if detect_name_in_ocr_str(condensed_name.lower(), condensed_ocr_str.lower()):
            output_file.write(f"{name},{video_time}\n")
            output_file.flush()
            detected_competitor_names.append(f"found {name}")
    video_time += datetime.timedelta(seconds=args["seconds"])
    if args["debug"]:
        print(condensed_ocr_str)
    print(f"{video_time} -- {(current_frame/video_frames_total)*100:.2f}%"
          + " video scanned... " + ", ".join(detected_competitor_names))
output_file.close()

print("== SUCCESS ==")
print(f"Scanned through {video_frames_total} frames in {time.time() - start_time}s")