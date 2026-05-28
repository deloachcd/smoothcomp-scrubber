import csv
import io
import os
import tempfile
from datetime import timedelta

import pytest

# Import only the pure functions — scripts are guarded by __name__ == "__main__"
from get_smoothcomp_timestamps import detect_competitor_names, update_match_windows
from make_clips import (
    parse_timedelta,
    format_timestamp_for_filename,
    build_clip_filename,
    build_ffmpeg_cmd,
    compute_clip_window,
    read_timestamps_csv,
)


# ---------------------------------------------------------------------------
# detect_competitor_names
# ---------------------------------------------------------------------------

class TestDetectCompetitorNames:
    def test_detects_full_name(self):
        assert detect_competitor_names("John Smith wins", ["John Smith"]) == ["John Smith"]

    def test_case_insensitive(self):
        assert detect_competitor_names("JOHN SMITH wins", ["John Smith"]) == ["John Smith"]

    def test_partial_name_not_matched(self):
        # both parts must appear
        assert detect_competitor_names("John wins", ["John Smith"]) == []

    def test_multiple_names_detected(self):
        result = detect_competitor_names("John Smith vs Jane Doe", ["John Smith", "Jane Doe", "Bob"])
        assert result == ["John Smith", "Jane Doe"]

    def test_name_not_in_frame(self):
        assert detect_competitor_names("Some other text", ["John Smith"]) == []

    def test_empty_frame(self):
        assert detect_competitor_names("", ["John Smith"]) == []

    def test_single_word_name(self):
        assert detect_competitor_names("God smites all", ["God"]) == ["God"]


# ---------------------------------------------------------------------------
# update_match_windows
# ---------------------------------------------------------------------------

T0 = timedelta(seconds=0)
T5 = timedelta(seconds=5)
T10 = timedelta(seconds=10)
T15 = timedelta(seconds=15)
T20 = timedelta(seconds=20)
T25 = timedelta(seconds=25)


class TestUpdateMatchWindows:
    def test_opens_window_on_first_detection(self):
        active = {}
        closed = update_match_windows(active, ["Alice"], ["Alice"], T0, gap_tolerance=3)
        assert "Alice" in active
        assert active["Alice"]["start_time"] == T0
        assert active["Alice"]["miss_count"] == 0
        assert closed == []

    def test_resets_miss_count_on_redetection(self):
        active = {"Alice": {"start_time": T0, "miss_count": 2}}
        update_match_windows(active, ["Alice"], ["Alice"], T5, gap_tolerance=3)
        assert active["Alice"]["miss_count"] == 0

    def test_increments_miss_count_on_miss(self):
        active = {"Alice": {"start_time": T0, "miss_count": 0}}
        closed = update_match_windows(active, ["Alice"], [], T5, gap_tolerance=3)
        assert active["Alice"]["miss_count"] == 1
        assert closed == []

    def test_closes_window_after_gap_tolerance_exceeded(self):
        active = {"Alice": {"start_time": T0, "miss_count": 3}}
        closed = update_match_windows(active, ["Alice"], [], T20, gap_tolerance=3)
        assert "Alice" not in active
        assert len(closed) == 1
        assert closed[0] == ("Alice", T0, T20)

    def test_does_not_close_window_at_exactly_gap_tolerance(self):
        # miss_count becomes gap_tolerance, not gap_tolerance+1
        active = {"Alice": {"start_time": T0, "miss_count": 2}}
        closed = update_match_windows(active, ["Alice"], [], T15, gap_tolerance=3)
        assert "Alice" in active
        assert active["Alice"]["miss_count"] == 3
        assert closed == []

    def test_multiple_competitors_independent(self):
        active = {
            "Alice": {"start_time": T0, "miss_count": 0},
            "Bob": {"start_time": T0, "miss_count": 3},
        }
        closed = update_match_windows(active, ["Alice", "Bob"], ["Alice"], T10, gap_tolerance=3)
        assert "Alice" in active
        assert "Bob" not in active
        assert closed == [("Bob", T0, T10)]

    def test_no_window_opened_for_undetected_untracked_name(self):
        active = {}
        closed = update_match_windows(active, ["Alice"], [], T0, gap_tolerance=3)
        assert active == {}
        assert closed == []


# ---------------------------------------------------------------------------
# parse_timedelta
# ---------------------------------------------------------------------------

class TestParseTimedelta:
    def test_basic(self):
        assert parse_timedelta("0:01:30") == timedelta(minutes=1, seconds=30)

    def test_hours(self):
        assert parse_timedelta("1:23:45") == timedelta(hours=1, minutes=23, seconds=45)

    def test_strips_microseconds(self):
        assert parse_timedelta("0:05:00.123456") == timedelta(minutes=5)

    def test_strips_whitespace(self):
        assert parse_timedelta("  0:00:10  ") == timedelta(seconds=10)

    def test_zero(self):
        assert parse_timedelta("0:00:00") == timedelta(0)


# ---------------------------------------------------------------------------
# format_timestamp_for_filename
# ---------------------------------------------------------------------------

class TestFormatTimestampForFilename:
    def test_simple(self):
        assert format_timestamp_for_filename(timedelta(hours=1, minutes=23, seconds=45)) == "01_23_45"

    def test_zero(self):
        assert format_timestamp_for_filename(timedelta(0)) == "00_00_00"

    def test_padding(self):
        assert format_timestamp_for_filename(timedelta(minutes=5, seconds=3)) == "00_05_03"


# ---------------------------------------------------------------------------
# build_clip_filename
# ---------------------------------------------------------------------------

class TestBuildClipFilename:
    def test_spaces_replaced(self):
        name = "John Smith"
        ts = timedelta(hours=1, minutes=2, seconds=3)
        assert build_clip_filename(name, ts) == "John_Smith_01_02_03.mp4"

    def test_slashes_replaced(self):
        name = "A/B"
        ts = timedelta(0)
        assert build_clip_filename(name, ts) == "A_B_00_00_00.mp4"

    def test_single_word(self):
        assert build_clip_filename("God", timedelta(seconds=30)) == "God_00_00_30.mp4"


# ---------------------------------------------------------------------------
# build_ffmpeg_cmd
# ---------------------------------------------------------------------------

class TestBuildFfmpegCmd:
    def test_structure(self):
        cmd = build_ffmpeg_cmd("ffmpeg", "/video.mp4", 10.0, 60.0, "/out/clip.mp4")
        assert cmd[0] == "ffmpeg"
        assert "-ss" in cmd
        assert str(10.0) in cmd
        assert "-t" in cmd
        assert str(60.0) in cmd
        assert "-i" in cmd
        assert "/video.mp4" in cmd
        assert cmd[-1] == "/out/clip.mp4"
        assert "libx264" in cmd
        assert "aac" in cmd

    def test_custom_ffmpeg_path(self):
        cmd = build_ffmpeg_cmd("/opt/ffmpeg/bin/ffmpeg", "v.mp4", 0, 10, "out.mp4")
        assert cmd[0] == "/opt/ffmpeg/bin/ffmpeg"


# ---------------------------------------------------------------------------
# compute_clip_window
# ---------------------------------------------------------------------------

class TestComputeClipWindow:
    def test_basic_padding(self):
        start = timedelta(minutes=1)       # 60s
        end = timedelta(minutes=2)         # 120s
        clip_start, duration = compute_clip_window(start, end, padding_seconds=10)
        assert clip_start == 50.0
        assert duration == 80.0            # (120+10) - (60-10)

    def test_padding_clamps_to_zero(self):
        start = timedelta(seconds=5)
        end = timedelta(seconds=30)
        clip_start, duration = compute_clip_window(start, end, padding_seconds=10)
        assert clip_start == 0.0           # max(0, 5-10)
        assert duration == 40.0            # (30+10) - 0

    def test_zero_padding(self):
        start = timedelta(minutes=1)
        end = timedelta(minutes=2)
        clip_start, duration = compute_clip_window(start, end, padding_seconds=0)
        assert clip_start == 60.0
        assert duration == 60.0


# ---------------------------------------------------------------------------
# read_timestamps_csv
# ---------------------------------------------------------------------------

class TestReadTimestampsCsv:
    def _write_csv(self, rows):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)
        f.close()
        return f.name

    def test_reads_rows(self):
        path = self._write_csv([
            ["John Smith", "0:01:00", "0:03:00"],
            ["Jane Doe", "0:05:00", "0:07:30"],
        ])
        try:
            rows = read_timestamps_csv(path)
            assert len(rows) == 2
            assert rows[0] == ("John Smith", timedelta(minutes=1), timedelta(minutes=3))
            assert rows[1] == ("Jane Doe", timedelta(minutes=5), timedelta(minutes=7, seconds=30))
        finally:
            os.unlink(path)

    def test_skips_short_rows(self):
        path = self._write_csv([["bad row"], ["John Smith", "0:01:00", "0:02:00"]])
        try:
            rows = read_timestamps_csv(path)
            assert len(rows) == 1
        finally:
            os.unlink(path)

    def test_empty_file(self):
        path = self._write_csv([])
        try:
            assert read_timestamps_csv(path) == []
        finally:
            os.unlink(path)

    def test_strips_whitespace(self):
        path = self._write_csv([[" John Smith ", " 0:01:00 ", " 0:02:00 "]])
        try:
            rows = read_timestamps_csv(path)
            assert rows[0][0] == "John Smith"
        finally:
            os.unlink(path)
