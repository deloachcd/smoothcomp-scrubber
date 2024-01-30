# smoothcomp-scrubber
Have you ever needed to manually scrub through Smoothcomp streams, to find
the timestamps where you or your teammates actually show up to fight? If so,
this script is for you. It allows you to take a video file containing the 
archive of a Smoothcomp tournament stream and automatically write the
timestamps where the people you list show up to a CSV file.

## Pre-Requisites
This depends on Google's `tesseract-ocr` engine, so you need that installed.
MacOS has it through homebrew, your favorite Linux distro probably has it in
its package manager, and Windows users should be using WSL and following 
instructions for Linux distros with stuff like this script anyway.

## Basic setup (assuming tesseract is installed)
``` sh
git clone https://github.com/deloachcd/smoothcomp-scrubber.git
cd smoothcomp-scrubber
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -r requirements.txt
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
#### Obtaining the video file with yt-dlp
First, we need a video file to scrub through for timestamps. These are usually
linked in the Smoothcomp page for the relevant tournament, and linked under the
"Livestreams" tab there. From here, we can obtain YouTube links to the videos
to be used with `yt-dlp`.

Many package managers provide an outdated version of `yt-dlp` that will not
actually work to retrieve videos - we can ensure we're using an up-to-date
version by installing it in our project's virtual environment instead and
calling it from there:
``` sh
source venv/bin/activate
pip install yt-dlp
yt-dlp() {
  ./venv/bin/yt-dlp \
    --merge-output-format mkv \
    $@
}
./venv/bin/yt-dlp 'https://www.youtube.com/watch?v=${VIDEO_ID}' -o stream.mkv
```

#### Scanning through the video file with the script
Now, let's say we want to look for some names within `stream.mkv`.
We'll first write them to a file `competitors.txt`:
```
osama bin laden
sadam hussein
jesus christ
bill burr
lena dunham
kid rock
```
Once we've done that, we can run the script to find where our
named competitors show up:
``` sh
./get-smoothcomp-timestamps.py \
  -v stream.mkv \
  -f competitors.txt \
  -o result.csv
```
The script will then scan through the video, writing its current progress
as console output and reporting when it detects listed names in the video
stream.

## TODOs for me to do later
- Exceptions. This script has none of them right now, and they would help
  out for sure.
- Export to markdown tables / convert to PDFs directly
- Orchestration for multiple mats/streams