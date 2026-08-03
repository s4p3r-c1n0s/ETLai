"""Tests for InputResolver — file path injection into atom config."""

import pytest

from etlai.helpers.input_resolver import InputResolver


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
