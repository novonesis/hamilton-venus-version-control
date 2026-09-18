"""Tests for webgui.api — VersionatorApi (pure Python, no webview needed)."""

from __future__ import annotations

from webgui.api import VersionatorApi


class TestPollLogs:
    def test_poll_logs_returns_empty_for_unknown_tab(self):
        api = VersionatorApi()
        result = api.poll_logs("nonexistent", 0)
        assert result == {"lines": [], "cursor": 0}
        api.cleanup()

    def test_poll_logs_returns_lines_for_known_tab(self):
        api = VersionatorApi()
        # Write directly to the buffer
        api._log_buffers["conversion"].append("test line")
        result = api.poll_logs("conversion", 0)
        assert result["lines"] == ["test line"]
        assert result["cursor"] == 1
        api.cleanup()


class TestClearLogs:
    def test_clear_logs_resets_buffer(self):
        api = VersionatorApi()
        api._log_buffers["library"].append("x")
        api.clear_logs("library")
        result = api.poll_logs("library", 0)
        assert result["lines"] == []
        assert result["cursor"] == 0
        api.cleanup()


class TestIsTaskRunning:
    def test_default_not_running(self):
        api = VersionatorApi()
        assert api.is_task_running("library") is False
        api.cleanup()

    def test_running_when_set(self):
        api = VersionatorApi()
        api._running["library"] = True
        assert api.is_task_running("library") is True
        api.cleanup()


class TestSearchFiles:
    def test_search_files_returns_results(self, tmp_path):
        # Create a test file with searchable content
        test_file = tmp_path / "test.hsl"
        test_file.write_text("line one\nfind me here\nline three\n")

        api = VersionatorApi()
        results = api.search_files(str(tmp_path), "find me", False)
        assert len(results) == 1
        assert results[0]["path"] == str(test_file)
        assert results[0]["line"] == 2
        assert "find me here" in results[0]["content"]
        api.cleanup()

    def test_search_files_empty_when_no_match(self, tmp_path):
        test_file = tmp_path / "test.hsl"
        test_file.write_text("nothing here\n")

        api = VersionatorApi()
        results = api.search_files(str(tmp_path), "nonexistent", False)
        assert results == []
        api.cleanup()


class TestCreateFolderStructure:
    def test_creates_folder(self, tmp_path):
        api = VersionatorApi()
        result = api.create_folder_structure(str(tmp_path), "TestMethod", "", False)
        assert result["status"] == "success"
        assert (tmp_path / "TestMethod" / "Libraries").is_dir()
        api.cleanup()

    def test_nonexistent_dest_returns_error(self, tmp_path):
        api = VersionatorApi()
        result = api.create_folder_structure(str(tmp_path / "nope"), "TestMethod", "", False)
        assert result["status"] == "error"
        api.cleanup()


class TestMonitoring:
    def test_get_monitoring_status_default(self):
        api = VersionatorApi()
        assert api.get_monitoring_status() == "Not Started"
        api.cleanup()

    def test_is_monitoring_active_default(self):
        api = VersionatorApi()
        assert api.is_monitoring_active() is False
        api.cleanup()

    def test_stop_monitoring_when_not_running(self):
        api = VersionatorApi()
        result = api.stop_monitoring()
        assert result["ok"] is False
        api.cleanup()
