"""Tests for InputResolver — file path injection and pattern ordering."""

import pytest

from etlai.helpers.input_resolver import InputResolver, order_files_by_pattern


@pytest.fixture
def resolver():
    return InputResolver()


class TestFallbackMode:
    """Legacy heuristic behavior (no inputs_map)."""

    def test_first_step_two_files(self, resolver):
        config = {}
        resolver.resolve(
            is_first=True,
            file_paths=["/a.csv", "/b.csv"],
            prev_output=None,
            config=config,
        )
        assert config["left_file"] == "/a.csv"
        assert config["right_file"] == "/b.csv"

    def test_first_step_one_file_right_present(self, resolver):
        config = {"right_file": "/ref.csv"}
        resolver.resolve(
            is_first=True,
            file_paths=["/a.csv"],
            prev_output=None,
            config=config,
        )
        assert config["left_file"] == "/a.csv"
        assert config["right_file"] == "/ref.csv"

    def test_first_step_one_file(self, resolver):
        config = {}
        resolver.resolve(
            is_first=True,
            file_paths=["/a.csv"],
            prev_output=None,
            config=config,
        )
        assert config["input_file"] == "/a.csv"
        assert "left_file" not in config

    def test_continuation_right_present(self, resolver):
        config = {"right_file": "/ref.csv"}
        resolver.resolve(
            is_first=False,
            file_paths=["/a.csv"],
            prev_output="/prev.csv",
            config=config,
        )
        assert config["left_file"] == "/prev.csv"

    def test_continuation_no_right(self, resolver):
        config = {}
        resolver.resolve(
            is_first=False,
            file_paths=["/a.csv"],
            prev_output="/prev.csv",
            config=config,
        )
        assert config["input_file"] == "/prev.csv"
        assert "left_file" not in config

    def test_skips_if_already_set(self, resolver):
        config = {"input_file": "/already.csv"}
        resolver.resolve(
            is_first=True,
            file_paths=["/a.csv"],
            prev_output=None,
            config=config,
        )
        assert config["input_file"] == "/already.csv"

    def test_skips_if_left_already_set(self, resolver):
        config = {"left_file": "/already.csv"}
        resolver.resolve(
            is_first=False,
            file_paths=[],
            prev_output="/prev.csv",
            config=config,
        )
        assert config["left_file"] == "/already.csv"


class TestExplicitMode:
    """inputs_map declared in manifest step."""

    def test_two_files_explicit(self, resolver):
        config = {}
        inputs_map = [{"param": "left_file"}, {"param": "right_file"}]
        resolver.resolve(
            is_first=True,
            file_paths=["/a.csv", "/b.csv"],
            prev_output=None,
            config=config,
            inputs_map=inputs_map,
        )
        assert config["left_file"] == "/a.csv"
        assert config["right_file"] == "/b.csv"

    def test_three_files_explicit(self, resolver):
        config = {}
        inputs_map = [
            {"param": "source_a"},
            {"param": "source_b"},
            {"param": "source_c"},
        ]
        resolver.resolve(
            is_first=True,
            file_paths=["/x.csv", "/y.csv", "/z.csv"],
            prev_output=None,
            config=config,
            inputs_map=inputs_map,
        )
        assert config["source_a"] == "/x.csv"
        assert config["source_b"] == "/y.csv"
        assert config["source_c"] == "/z.csv"

    def test_five_files_explicit(self, resolver):
        config = {}
        inputs_map = [
            {"param": f"file_{i}"} for i in range(5)
        ]
        files = [f"/{i}.csv" for i in range(5)]
        resolver.resolve(
            is_first=True,
            file_paths=files,
            prev_output=None,
            config=config,
            inputs_map=inputs_map,
        )
        for i in range(5):
            assert config[f"file_{i}"] == f"/{i}.csv"

    def test_continuation_explicit_prev_output_first(self, resolver):
        config = {}
        inputs_map = [{"param": "input_file"}, {"param": "lookup"}]
        resolver.resolve(
            is_first=False,
            file_paths=["/a.csv", "/b.csv"],
            prev_output="/prev.csv",
            config=config,
            inputs_map=inputs_map,
        )
        assert config["input_file"] == "/prev.csv"
        assert config["lookup"] == "/b.csv"

    def test_skips_already_set_params(self, resolver):
        config = {"source_b": "/already.csv"}
        inputs_map = [{"param": "source_a"}, {"param": "source_b"}]
        resolver.resolve(
            is_first=True,
            file_paths=["/x.csv", "/y.csv"],
            prev_output=None,
            config=config,
            inputs_map=inputs_map,
        )
        assert config["source_a"] == "/x.csv"
        assert config["source_b"] == "/already.csv"

    def test_fewer_files_than_map(self, resolver):
        config = {}
        inputs_map = [{"param": "a"}, {"param": "b"}, {"param": "c"}]
        resolver.resolve(
            is_first=True,
            file_paths=["/only.csv"],
            prev_output=None,
            config=config,
            inputs_map=inputs_map,
        )
        assert config["a"] == "/only.csv"
        assert "b" not in config
        assert "c" not in config

    def test_custom_param_names(self, resolver):
        config = {}
        inputs_map = [
            {"param": "transactions_file"},
            {"param": "accounts_file"},
            {"param": "rates_file"},
        ]
        resolver.resolve(
            is_first=True,
            file_paths=["/tx.csv", "/acc.csv", "/rates.csv"],
            prev_output=None,
            config=config,
            inputs_map=inputs_map,
        )
        assert config["transactions_file"] == "/tx.csv"
        assert config["accounts_file"] == "/acc.csv"
        assert config["rates_file"] == "/rates.csv"


class TestOrderFilesByPattern:
    """Pattern-based file reordering for inbox files."""

    def test_matches_by_pattern(self):
        files = ["/inbox/marks_2024.csv", "/inbox/students_all.csv"]
        inputs = [
            {"name": "student_records", "role": "transient", "pattern": "student*.csv"},
            {"name": "marks_data", "role": "transient", "pattern": "marks*.csv"},
        ]
        result = order_files_by_pattern(files, inputs)
        assert result == ["/inbox/students_all.csv", "/inbox/marks_2024.csv"]

    def test_alphabetical_order_reversed_by_pattern(self):
        files = ["/inbox/a_marks.csv", "/inbox/z_students.csv"]
        inputs = [
            {"name": "students", "role": "transient", "pattern": "z_*.csv"},
            {"name": "marks", "role": "transient", "pattern": "a_*.csv"},
        ]
        result = order_files_by_pattern(files, inputs)
        assert result == ["/inbox/z_students.csv", "/inbox/a_marks.csv"]

    def test_no_pattern_uses_first_available(self):
        files = ["/inbox/a.csv", "/inbox/b.csv"]
        inputs = [
            {"name": "first", "role": "transient"},
            {"name": "second", "role": "transient", "pattern": "b*.csv"},
        ]
        result = order_files_by_pattern(files, inputs)
        assert result == ["/inbox/a.csv", "/inbox/b.csv"]

    def test_unmatched_files_appended(self):
        files = ["/inbox/extra.csv", "/inbox/marks.csv", "/inbox/students.csv"]
        inputs = [
            {"name": "students", "role": "transient", "pattern": "student*.csv"},
            {"name": "marks", "role": "transient", "pattern": "marks*.csv"},
        ]
        result = order_files_by_pattern(files, inputs)
        assert result == ["/inbox/students.csv", "/inbox/marks.csv", "/inbox/extra.csv"]

    def test_skips_reference_inputs(self):
        files = ["/inbox/marks.csv", "/inbox/students.csv"]
        inputs = [
            {"name": "lookup", "role": "reference", "pattern": "lookup*.csv"},
            {"name": "students", "role": "transient", "pattern": "student*.csv"},
            {"name": "marks", "role": "transient", "pattern": "marks*.csv"},
        ]
        result = order_files_by_pattern(files, inputs)
        assert result == ["/inbox/students.csv", "/inbox/marks.csv"]

    def test_empty_inputs_returns_unchanged(self):
        files = ["/inbox/b.csv", "/inbox/a.csv"]
        result = order_files_by_pattern(files, [])
        assert result == ["/inbox/b.csv", "/inbox/a.csv"]

    def test_no_transient_inputs_returns_unchanged(self):
        files = ["/inbox/b.csv", "/inbox/a.csv"]
        inputs = [{"name": "ref", "role": "reference", "pattern": "ref*.csv"}]
        result = order_files_by_pattern(files, inputs)
        assert result == ["/inbox/b.csv", "/inbox/a.csv"]

    def test_three_files_pattern_ordering(self):
        files = ["/inbox/accounts.csv", "/inbox/rates.csv", "/inbox/transactions.csv"]
        inputs = [
            {"name": "tx", "role": "transient", "pattern": "transaction*.csv"},
            {"name": "acc", "role": "transient", "pattern": "account*.csv"},
            {"name": "rates", "role": "transient", "pattern": "rate*.csv"},
        ]
        result = order_files_by_pattern(files, inputs)
        assert result == ["/inbox/transactions.csv", "/inbox/accounts.csv", "/inbox/rates.csv"]
