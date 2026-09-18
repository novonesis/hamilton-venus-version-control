"""Tests for csv_operations.read_csv_paths()."""

from csv_operations import read_csv_paths


def _write_csv(path, lines):
    path.write_text("\n".join(lines), encoding="utf-8")


def test_valid_paths(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    csv_file = tmp_path / "paths.csv"
    _write_csv(csv_file, ["source,destination", f"{src},{dst}"])

    result = read_csv_paths(str(csv_file))
    assert result == [(str(src), str(dst))]


def test_nonexistent_paths_skipped(tmp_path):
    csv_file = tmp_path / "paths.csv"
    _write_csv(csv_file, ["source,destination", "/no/such/src,/no/such/dst"])

    result = read_csv_paths(str(csv_file))
    assert result == []


def test_empty_csv(tmp_path):
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("", encoding="utf-8")

    result = read_csv_paths(str(csv_file))
    assert result == []


def test_header_only_csv(tmp_path):
    csv_file = tmp_path / "header.csv"
    _write_csv(csv_file, ["source,destination"])

    result = read_csv_paths(str(csv_file))
    assert result == []


def test_mixed_valid_invalid(tmp_path):
    good_src = tmp_path / "good_src"
    good_dst = tmp_path / "good_dst"
    good_src.mkdir()
    good_dst.mkdir()
    csv_file = tmp_path / "mix.csv"
    _write_csv(
        csv_file,
        [
            "source,destination",
            f"{good_src},{good_dst}",
            "/bad/src,/bad/dst",
        ],
    )

    result = read_csv_paths(str(csv_file))
    assert len(result) == 1
    assert result[0] == (str(good_src), str(good_dst))
