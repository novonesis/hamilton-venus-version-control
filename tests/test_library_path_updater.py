"""Tests for library_path_updater: normalize_path, _extract_includes, is_path_relative,
__repr__ safety, dependency report safety, and to_dict()."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from library_path_updater import (
    DependencyAnalyzer,
    DependencyReport,
    HamiltonLibrarySync,
    LibraryDependency,
)

# ── normalize_path ──────────────────────────────────────────────────


class TestNormalizePath:
    """HamiltonLibrarySync.normalize_path() doubles backslashes for Venus HSL."""

    def setup_method(self):
        self.sync = HamiltonLibrarySync.__new__(HamiltonLibrarySync)
        self.sync.library_logger = MagicMock()

    def test_forward_slashes(self):
        assert self.sync.normalize_path("C:/Users/lab") == "C:\\\\Users\\\\lab"

    def test_single_backslashes(self):
        assert self.sync.normalize_path("C:\\Users\\lab") == "C:\\\\Users\\\\lab"

    def test_mixed_slashes(self):
        assert (
            self.sync.normalize_path("C:\\Users/lab/file.hsl") == "C:\\\\Users\\\\lab\\\\file.hsl"
        )

    def test_already_doubled_backslashes(self):
        # Input already has doubled backslashes -> each pair gets doubled again (4 total)
        assert self.sync.normalize_path("C:\\\\Users") == "C:\\\\\\\\Users"

    def test_empty_string(self):
        assert self.sync.normalize_path("") == ""


# ── _extract_includes ───────────────────────────────────────────────


class TestExtractIncludes:
    """DependencyAnalyzer._extract_includes() parses #include directives."""

    def setup_method(self):
        # Use a dummy .txt path so __init__ skips _load_file
        self.analyzer = DependencyAnalyzer("dummy.txt")

    @patch.object(LibraryDependency, "resolve_path", return_value=None)
    def test_standard_include(self, _mock_resolve):
        self.analyzer._extract_includes('#include "HSLTipCountingLib.hsl"')
        items = self.analyzer.report.report_items
        assert len(items) == 1
        assert items[0].dependency.raw_include_path == "HSLTipCountingLib.hsl"

    @patch.object(LibraryDependency, "resolve_path", return_value=None)
    def test_include_with_path(self, _mock_resolve):
        self.analyzer._extract_includes('#include "SubDir/Utilities.hsl"')
        items = self.analyzer.report.report_items
        assert len(items) == 1
        assert items[0].dependency.raw_include_path == "SubDir/Utilities.hsl"

    @patch.object(LibraryDependency, "resolve_path", return_value=None)
    def test_filename_placeholder(self, _mock_resolve):
        self.analyzer._extract_includes('#include __filename__ ".hsi"')
        items = self.analyzer.report.report_items
        assert len(items) == 1
        assert "__filename__" in items[0].dependency.raw_include_path

    def test_non_include_line(self):
        self.analyzer._extract_includes("variable x = 42;")
        assert len(self.analyzer.report.report_items) == 0

    def test_empty_line(self):
        self.analyzer._extract_includes("")
        assert len(self.analyzer.report.report_items) == 0


# ── is_path_relative ───────────────────────────────────────────────


class TestIsPathRelative:
    """LibraryDependency.is_path_relative() wraps Path.is_absolute()."""

    def _make_dep(self, raw_path):
        """Create a LibraryDependency with resolve_path patched out."""
        with patch.object(LibraryDependency, "resolve_path", return_value=None):
            return LibraryDependency(raw_path, Path("."), Path("source.hsl"))

    def test_relative_path(self):
        dep = self._make_dep("SubDir/file.hsl")
        assert dep.is_path_relative() is True

    def test_absolute_windows_path(self):
        dep = self._make_dep("C:\\Program Files\\HAMILTON\\file.hsl")
        assert dep.is_path_relative() is False

    def test_bare_filename(self):
        dep = self._make_dep("file.hsl")
        assert dep.is_path_relative() is True

    def test_absolute_unc_path(self):
        dep = self._make_dep("\\\\server\\share\\file.hsl")
        assert dep.is_path_relative() is False


# ── __repr__ safety ─────────────────────────────────────────────────


class TestReprSafety:
    """LibraryDependency.__repr__ must NOT trigger the lazy sub_dependencies property."""

    def test_repr_does_not_load_sub_dependencies(self):
        with patch.object(LibraryDependency, "resolve_path", return_value=None):
            dep = LibraryDependency("foo.hsl", Path("."), Path("source.hsl"))
        assert dep._sub_dependencies is None
        result = repr(dep)
        # _sub_dependencies must still be None — repr did not trigger the property
        assert dep._sub_dependencies is None
        assert "not loaded" in result

    def test_repr_shows_count_when_loaded(self):
        with patch.object(LibraryDependency, "resolve_path", return_value=None):
            dep = LibraryDependency("foo.hsl", Path("."), Path("source.hsl"))
        dep._sub_dependencies = ["a", "b"]  # Simulate loaded state
        result = repr(dep)
        assert "sub_dependencies=2" in result


# ── DependencyReport safety ─────────────────────────────────────────


def _make_dep(raw_path, resolved_path=None):
    """Helper: create a LibraryDependency with resolve_path + sub_dependencies stubbed."""
    with patch.object(LibraryDependency, "resolve_path", return_value=resolved_path):
        dep = LibraryDependency(raw_path, Path("."), Path("source.hsl"))
    dep._sub_dependencies = []  # No sub-dependencies by default
    return dep


class TestDependencyReportSafety:
    """Safety guards: dedup by resolved path, max depth, circular deps."""

    def test_circular_dependency_terminates(self):
        """A→B→A cycle should not cause infinite recursion."""
        report = DependencyReport(Path("test.hsl"))

        dep_a = _make_dep("a.hsl", "/path/a.hsl")
        dep_b = _make_dep("b.hsl", "/path/b.hsl")
        # Create a cycle: A's sub-deps include B, B's sub-deps include A
        dep_a._sub_dependencies = [dep_b]
        dep_b._sub_dependencies = [dep_a]

        # Should terminate without error
        report.add_library_dependency(dep_a)
        assert len(report.report_items) >= 2

    def test_max_depth_stops_recursion(self):
        """Recursion should stop at MAX_DEPTH."""
        report = DependencyReport(Path("test.hsl"))

        # Build a chain deeper than MAX_DEPTH
        chain_length = report.MAX_DEPTH + 5
        deps = []
        for i in range(chain_length):
            deps.append(_make_dep(f"dep_{i}.hsl", f"/path/dep_{i}.hsl"))
        # Wire each dep to point to the next as a sub-dependency
        for i in range(chain_length - 1):
            deps[i]._sub_dependencies = [deps[i + 1]]

        report.add_library_dependency(deps[0])
        # Should have fewer items than chain_length due to depth cap
        assert len(report.report_items) < chain_length
        assert report.max_level < chain_length

    def test_same_file_two_raw_paths_analyzed_once(self):
        """Two different raw paths resolving to the same file → analyzed once."""
        report = DependencyReport(Path("test.hsl"))

        shared_sub = _make_dep("shared.hsl", "/path/shared.hsl")

        dep_a = _make_dep("relative/lib.hsl", "/path/lib.hsl")
        dep_a._sub_dependencies = [shared_sub]

        dep_b = _make_dep("/absolute/lib.hsl", "/path/lib.hsl")
        dep_b._sub_dependencies = [shared_sub]

        report.add_library_dependency(dep_a)
        report.add_library_dependency(dep_b)

        # /path/lib.hsl should only appear in _processed_resolved_paths once
        assert "/path/lib.hsl" in report._processed_resolved_paths


# ── to_dict() ───────────────────────────────────────────────────────


class TestDependencyReportToDict:
    """DependencyReport.to_dict() returns correct JSON-serializable structure."""

    def test_empty_report(self):
        report = DependencyReport(Path("empty.hsl"))
        result = report.to_dict()
        assert result["dependencies"] == []
        assert result["primary_count"] == 0
        assert result["total_unique"] == 0
        assert result["max_level"] == 0
        assert result["source_file_name"] == "empty.hsl"

    def test_single_resolved_dependency(self):
        report = DependencyReport(Path("test.hsl"))
        dep = _make_dep("lib.hsl", "/path/lib.hsl")
        report.add_library_dependency(dep)

        result = report.to_dict()
        assert len(result["dependencies"]) == 1
        node = result["dependencies"][0]
        assert node["resolved"] is True
        assert node["children"] == []
        assert node["file_name"] == "lib.hsl"
        assert node["level"] == 1

    def test_single_unresolved_dependency(self):
        report = DependencyReport(Path("test.hsl"))
        dep = _make_dep("missing.hsl", None)
        report.add_library_dependency(dep)

        result = report.to_dict()
        assert len(result["dependencies"]) == 1
        assert result["dependencies"][0]["resolved"] is False

    def test_nested_dependencies(self):
        report = DependencyReport(Path("test.hsl"))
        child = _make_dep("child.hsl", "/path/child.hsl")
        parent = _make_dep("parent.hsl", "/path/parent.hsl")
        parent._sub_dependencies = [child]

        report.add_library_dependency(parent)
        result = report.to_dict()

        assert len(result["dependencies"]) == 1
        parent_node = result["dependencies"][0]
        assert len(parent_node["children"]) == 1
        child_node = parent_node["children"][0]
        assert child_node["file_name"] == "child.hsl"
        assert child_node["level"] == 2

    def test_stats_fields(self):
        report = DependencyReport(Path("test.hsl"))
        dep1 = _make_dep("a.hsl", "/path/a.hsl")
        dep2 = _make_dep("b.hsl", "/path/b.hsl")
        child = _make_dep("c.hsl", "/path/c.hsl")
        dep1._sub_dependencies = [child]

        report.add_library_dependency(dep1)
        report.add_library_dependency(dep2)
        result = report.to_dict()

        assert result["primary_count"] == 2
        assert result["total_unique"] == 3
        assert result["max_level"] == 2
