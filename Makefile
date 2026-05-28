IMAGE       := local/scrubber
VIDEO       := targets/video.mp4
COMPETITORS := targets/competitors.txt
RESULTS     := outputs/results.csv
CLIPS_DIR   := outputs/clips

.PHONY: build download scan clips test dirs

build:
	docker build -t $(IMAGE) .

dirs:
	mkdir -p targets outputs

## URL=<youtube-url> make download
download: dirs
	docker run --rm -v ./targets:/targets $(IMAGE) \
		yt-dlp -S res,ect:mp4:m4a --recode mp4 "$(URL)" -o /targets/video.mp4

## Optionally override: VIDEO= COMPETITORS= RESULTS=
scan: dirs
	docker run --rm -v ./targets:/targets -v ./outputs:/outputs $(IMAGE) \
		pipenv run get-smoothcomp-timestamps.py \
			-i /$(VIDEO) \
			-f /$(COMPETITORS) \
			-o /$(RESULTS)

## Optionally override: VIDEO= RESULTS= CLIPS_DIR=
clips: dirs
	docker run --rm -v ./targets:/targets -v ./outputs:/outputs $(IMAGE) \
		pipenv run make-clips.py \
			-i /$(VIDEO) \
			-t /$(RESULTS) \
			-o /$(CLIPS_DIR)

test:
	docker run --rm $(IMAGE) pipenv run pytest /usr/local/bin/test_scrubber.py -v
