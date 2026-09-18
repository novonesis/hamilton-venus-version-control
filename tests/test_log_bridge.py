"""Tests for webgui.log_bridge — LogBuffer and sink factory."""

from __future__ import annotations

from webgui.log_bridge import LogBuffer, make_log_sink, make_tab_filter


class TestLogBuffer:
    def test_append_and_read_new(self):
        buf = LogBuffer(maxlen=100)
        buf.append("line 1")
        buf.append("line 2")
        lines, cursor = buf.read_new(0)
        assert lines == ["line 1", "line 2"]
        assert cursor == 2

    def test_read_new_incremental(self):
        buf = LogBuffer()
        buf.append("a")
        buf.append("b")
        _, cursor = buf.read_new(0)
        buf.append("c")
        lines, cursor2 = buf.read_new(cursor)
        assert lines == ["c"]
        assert cursor2 == 3

    def test_read_new_no_new_lines(self):
        buf = LogBuffer()
        buf.append("x")
        _, cursor = buf.read_new(0)
        lines, cursor2 = buf.read_new(cursor)
        assert lines == []
        assert cursor2 == cursor

    def test_clear(self):
        buf = LogBuffer()
        buf.append("a")
        buf.clear()
        lines, cursor = buf.read_new(0)
        assert lines == []
        assert cursor == 0

    def test_ring_buffer_evicts_old(self):
        buf = LogBuffer(maxlen=3)
        for i in range(5):
            buf.append(f"line {i}")
        # Only last 3 should remain
        lines, cursor = buf.read_new(0)
        assert lines == ["line 2", "line 3", "line 4"]
        assert cursor == 5


class TestMakeLogSink:
    def test_sink_appends_to_buffer(self):
        buf = LogBuffer()
        sink = make_log_sink(buf)
        sink("hello world\n")
        lines, _ = buf.read_new(0)
        assert lines == ["hello world"]

    def test_sink_strips_trailing_newline(self):
        buf = LogBuffer()
        sink = make_log_sink(buf)
        sink("test\n")
        lines, _ = buf.read_new(0)
        assert lines[0] == "test"


class TestMakeTabFilter:
    def test_matching_tab(self):
        filt = make_tab_filter("library")
        record = {"extra": {"tab": "library"}}
        assert filt(record) is True

    def test_non_matching_tab(self):
        filt = make_tab_filter("library")
        record = {"extra": {"tab": "conversion"}}
        assert filt(record) is False

    def test_missing_tab(self):
        filt = make_tab_filter("library")
        record = {"extra": {}}
        assert filt(record) is False
