# smoothcomp-scrubber
Have you ever needed to manually scrub through Smoothcomp streams, to find
the timestamps where you or your teammates actually show up to fight? If so,
this script is for you. It allows you to take a video file containing the
archive of a Smoothcomp tournament stream and automatically find the
timestamps where the people you list show up, and optionally cut those
matches into individual video clips.

## Pre-Requisites
Your computer needs to be able to run Docker. That's it - this used to be
a python virtualenv-based project, but after YouTube decided to roll out
AV1 for most of the videos hosted on the platform, setting up an environment
where OpenCV can decode said videos was complicated enough that bundling
everything in an image became a necessity. `yt-dlp` is included too, so
that you can obtain the videos themselves easily.

## Installation
``` sh
git clone https://github.com/deloachcd/smoothcomp-scrubber.git
cd smoothcomp-scrubber
make build
```

## Basic usage (the easy way)
Spin up a docker image and use [the UI Nate made](https://github.com/Felttrip/smoothcomp-scrubber-ui).

## Basic usage (old workflow)
The basic workflow with this program is:
- obtain the archive of the smoothcomp stream you want to scrub
  through, in a format like .MOV or .MP4 etc. (`yt-dlp` is a pretty
  good tool for this)
- write a list of competitor names to find in the stream to a text file
  (names should be written as they're going to appear in the smoothcomp 
  stream, case-insensitive)
- call the script, passing in the video archive and competitor list files
  as arguments, and either also specifying an output file or just reading 
  from the default `output.csv` once you want to see where the competitors
  you listed show up. the script has a `-h` option that will tell you all
  the flags you need to get going
``` sh
URL=https://www.youtube.com/watch?v=... make download
```

This saves the video to `targets/video.mp4`. You can also provide your own
video file and skip this step.

### Step 2: Create a competitors file
Write the names you want to find to `targets/competitors.txt`, one per line,
as they appear in the stream (case-insensitive):

```
Osama bin Laden
Sadam Hussein
Jesus Christ
Kevin Spacey
Lena Dunham
God
```

### Step 3: Scan the video
``` sh
make scan
```

The script scans through the video at regular intervals, using OCR to detect
competitor names on screen. When a name appears it opens a match window; when
the name stops appearing (after a configurable gap tolerance, to handle
occasional OCR misses mid-match) it closes the window and writes the start
and end timestamps to the output CSV.

Results are written to `outputs/results.csv` in the format:
```
name, start_time, end_time, video_file
```

Progress is printed as the scan runs:
```
0:00:05 -- 0.12% video scanned...
  >> opened window for God at 0:05:30
0:05:35 -- 14.23% video scanned... found God
  >> closed window for God: 0:05:30 -> 0:08:45
```

#### Scanning multiple videos at once

Tournaments often stream across multiple mats or days. You can pass multiple
video files in one run and all results will be written to a single CSV:

``` sh
make scan VIDEOS="targets/mat1.mp4 targets/mat2.mp4 targets/mat3.mp4"
```

Each row in the CSV will include the source video file, so `make-clips.py`
knows where to pull each clip from without any extra arguments.

### Step 4: Make clips (optional)
``` sh
make clips
```

This reads `outputs/results.csv` and uses ffmpeg to cut each match window
into a clip, saved to `outputs/clips/`. Clips are re-encoded as MP4 and
named after the competitor and match start time:

```
outputs/clips/God_00_05_30.mp4
```

10 seconds of padding is added before and after each detected window by
default, so you don't miss the walkout or the final submission.

## Makefile targets

| Target | Description |
|--------|-------------|
| `make build` | Build the Docker image |
| `make download URL=<url>` | Download a YouTube video to `targets/video.mp4` |
| `make scan` | Scan the video and write match timestamps to `outputs/results.csv` |
| `make clips` | Cut match clips from `outputs/results.csv` into `outputs/clips/` |
| `make test` | Run the test suite inside Docker |

All targets accept variable overrides:

``` sh
# single video
make scan VIDEOS=targets/other.mp4 COMPETITORS=targets/mynames.txt RESULTS=outputs/out.csv

# multiple videos — the Makefile automatically switches to -I
make scan VIDEOS="targets/mat1.mp4 targets/mat2.mp4 targets/mat3.mp4"

make clips RESULTS=outputs/out.csv CLIPS_DIR=outputs/myclips
```

## Script reference

### get-smoothcomp-timestamps.py

Scans one or more video files for competitor names using OCR and writes match windows to a CSV.

| Flag | Default | Description |
|------|---------|-------------|
| `-i, --input-file` | — | Path to a single video file (mutually exclusive with `-I`) |
| `-I, --input-files` | — | Paths to multiple video files, scanned sequentially |
| `-f, --competitors-file` | `competitors.txt` | Path to competitor names file |
| `-o, --output-file` | `output.csv` | Path to output CSV |
| `-s, --interval-seconds` | `5` | Seconds between OCR frames |
| `-g, --gap-tolerance` | `3` | Missed intervals before closing a match window |
| `--jump-to-timestamp` | — | Skip to a timestamp before scanning, single-file only (HH:MM:SS) |
| `--psm` | `11` | Tesseract page segmentation mode |
| `--print-captured-strings` | — | Print raw OCR output for debugging |

### make-clips.py

Reads a timestamps CSV and cuts each match into a clip using ffmpeg.

| Flag | Default | Description |
|------|---------|-------------|
| `-i, --input-file` | — | Fallback video file if CSV has no `video_file` column |
| `-t, --timestamps-file` | `output.csv` | Path to timestamps CSV |
| `-o, --output-dir` | `clips` | Directory to write clips into |
| `-p, --clip-padding` | `10` | Seconds of padding before and after each clip |
| `--ffmpeg` | `ffmpeg` | Path to ffmpeg binary |

## Running tests
``` sh
make test
```
