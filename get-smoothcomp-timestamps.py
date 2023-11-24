#!/usr/bin/env python3
import argparse
import csv
import datetime
import time

import cv2
import pytesseract


def crop_frame_to_competitor_names(frame, height, width):
    # crop to the section of the stream that's actually relevant
    # to our OCR engine - the small section where names actually
    # show up
    return frame[3*(height//16):height//2, 
                 3*(width//32):29*(width//32)]


ap = argparse.ArgumentParser()
ap.add_argument("-v", "--video", type=str, help="path to input video file [required]")
ap.add_argument("-f", "--competitors-file", type=str, default="competitors.csv",
	            help="path to input file listing competitors (default:competitors.csv)")
ap.add_argument("-o", "--output-file", type=str, default="output.csv",
	            help="path to input file listing competitors (default:output.csv)")
ap.add_argument("-s", "--seconds", type=float, default=5,
                help="seconds between OCR captures to check for competitor names (default:5)")
args = vars(ap.parse_args())

# competitor_names list will be used to check for relevant names
# in OCR-captured strings
competitor_names = []
with open(args["competitors_file"], "r") as csvfile:
    reader = csv.reader(csvfile, delimiter=",")
    for row in reader:
        firstname, lastname = row[0].strip(), row[1].strip()
        competitor_names.append([firstname, lastname])

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
    frame_as_str = pytesseract.image_to_string(ocr_frame).lower()
    detected_competitor_names = []
    for firstname, lastname in competitor_names:
        if firstname in frame_as_str and lastname in frame_as_str:
            output_file.write(f"{firstname} {lastname},{video_time}\n")
            output_file.flush()
            detected_competitor_names.append(f"found {firstname}")
    video_time += datetime.timedelta(seconds=args["seconds"])
    print(f"{video_time} -- {(current_frame/video_frames_total)*100:.2f}%"
          + " video scanned... " + ", ".join(detected_competitor_names))
output_file.close()

print("== SUCCESS ==")
print(f"Scanned through {video_frames_total} frames in {time.time() - start_time}s")