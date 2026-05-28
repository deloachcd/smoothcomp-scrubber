# smoothcomp-scrubber
Have you ever needed to manually scrub through Smoothcomp streams, to find
the timestamps where you or your teammates actually show up to fight? If so,
this script is for you. It allows you to take a video file containing the 
archive of a Smoothcomp tournament stream and automatically write the
timestamps where the people you list show up to a CSV file.

## Pre-Requisites
Your computer needs to be able to run Docker. That's it - this used to be
a python virtualenv-based project, but after YouTube decided to roll out
AV1 for most of the videos hosted on the platform, setting up an environment
where OpenCV can decode said videos was complicated enough that a bundling
everything in an image became a necessity. I put `yt-dlp` in there too, so
that you can obtain the videos themselves easily.

## Installation
``` sh
git clone https://github.com/deloachcd/smoothcomp-scrubber.git
cd smoothcomp-scrubber
docker build -t local/scrubber .
```

## Basic usage
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

### Usage example
#### Obtaining the video file as MP4 with yt-dlp
First, we need a video file to scrub through for timestamps. These are usually
linked in the Smoothcomp page for the relevant tournament, and linked under the
"Livestreams" tab there. From here, we can obtain YouTube links to the videos
to be used with `yt-dlp`.
``` sh
# pull a video
mkdir targets
docker run --rm -v ./targets:/targets local/scrubber yt-dlp -S res,ect:mp4:m4a --recode mp4 "${YOUTUBE_VIDEO_URL}" -o /targets/video.mp4
```

#### Scanning through the video file with the script
Now, let's say we want to look for some names within `stream.mkv`.
We'll first write them to a file `targets/competitors.txt`:
```
Osama bin Laden
Sadam Hussein
Jesus Christ
Kevin Spacey
Lena Dunham
God
```
Once we've done that, we can use the script to find where our
named competitors show up:
``` sh
mkdir outputs
docker run --rm -v ./targets:/targets -v ./outputs:/outputs local/scrubber pipenv run get-smoothcomp-timestamps.py -i /targets/video.mp4 -f /targets/competitors.txt -o /outputs/results.csv
```

The script will then scan through the video, writing its current progress
as console output and reporting when it detects listed names in the video
stream.