"""Tests for new generic atoms: computed_column, group_aggregate, filter_rows, flag_rows, rename_columns, sort_rows."""

import json

import pandas as pd
import pytest


class TestComputedColumn:
    def test_basic_expression(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("col_a,col_b\n10,5\n20,3\n")
        output_csv = tmp_path / "output.csv"

        from etlai.atoms.computed_column import execute

        params = {
            "input_file": str(input_csv),
            "expression": "col_a * col_b",
            "output_column": "result",
            "target_path": str(output_csv),
        }
        result = json.loads(execute(json.dumps(params)))

        assert result["success"] is True
        df = pd.read_csv(output_csv)
        assert "result" in df.columns
        assert df["result"].tolist() == [50, 60]

    def test_division_expression(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("col_a,col_b\n100,4\n200,5\n")
        output_csv = tmp_path / "output.csv"

        from etlai.atoms.computed_column import execute

        params = {
            "input_file": str(input_csv),
            "expression": "col_a / col_b",
            "output_column": "ratio",
            "target_path": str(output_csv),
        }
        result = json.loads(execute(json.dumps(params)))

        assert result["success"] is True
        df = pd.read_csv(output_csv)
        assert df["ratio"].tolist() == [25.0, 40.0]

    def test_missing_column_in_expression(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("col_a,col_b\n10,5\n")
        output_csv = tmp_path / "output.csv"

        from etlai.atoms.computed_column import execute

        params = {
            "input_file": str(input_csv),
            "expression": "col_a * col_z",
            "output_column": "result",
            "target_path": str(output_csv),
        }
        result = json.loads(execute(json.dumps(params)))

        assert result["success"] is False


class TestGroupAggregate:
    def test_sum_aggregation(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("group_col,value_col\nA,10\nB,20\nA,30\nB,5\n")
        output_csv = tmp_path / "output.csv"

        from etlai.atoms.group_aggregate import execute

        params = {
            "input_file": str(input_csv),
            "group_column": "group_col",
            "aggregations": [
                {"column": "value_col", "function": "sum", "output_column": "total"},
            ],
            "target_path": str(output_csv),
        }
        result = json.loads(execute(json.dumps(params)))

        assert result["success"] is True
        df = pd.read_csv(output_csv)
        assert len(df) == 2
        assert set(df["group_col"]) == {"A", "B"}
        a_row = df[df["group_col"] == "A"]
        assert a_row["total"].iloc[0] == 40

    def test_missing_group_column(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("col_a,col_b\n1,2\n")
        output_csv = tmp_path / "output.csv"

        from etlai.atoms.group_aggregate import execute

        params = {
            "input_file": str(input_csv),
            "group_column": "nonexistent",
            "aggregations": [{"column": "col_b", "function": "sum"}],
            "target_path": str(output_csv),
        }
        result = json.loads(execute(json.dumps(params)))

        assert result["success"] is False
        assert "nonexistent" in result["message"]

    def test_multiple_aggregations(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("grp,val_a,val_b\nX,10,1\nX,20,2\nY,30,3\n")
        output_csv = tmp_path / "output.csv"

        from etlai.atoms.group_aggregate import execute

        params = {
            "input_file": str(input_csv),
            "group_column": "grp",
            "aggregations": [
                {"column": "val_a", "function": "sum", "output_column": "sum_a"},
                {"column": "val_b", "function": "mean", "output_column": "avg_b"},
            ],
            "target_path": str(output_csv),
        }
        result = json.loads(execute(json.dumps(params)))

        assert result["success"] is True
        df = pd.read_csv(output_csv)
        x_row = df[df["grp"] == "X"]
        assert x_row["sum_a"].iloc[0] == 30
        assert x_row["avg_b"].iloc[0] == 1.5


class TestFilterRows:
    def test_basic_filter(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("col_a,col_b\n10,yes\n5,no\n20,yes\n3,no\n")
        output_csv = tmp_path / "output.csv"

        from etlai.atoms.filter_rows import execute

        params = {
            "input_file": str(input_csv),
            "condition": "col_a > 7",
            "target_path": str(output_csv),
        }
        result = json.loads(execute(json.dumps(params)))

        assert result["success"] is True
        assert result["row_count"] == 2
        assert result["rows_removed"] == 2
        df = pd.read_csv(output_csv)
        assert df["col_a"].tolist() == [10, 20]

    def test_filter_removes_nothing(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("col_a\n10\n20\n30\n")
        output_csv = tmp_path / "output.csv"

        from etlai.atoms.filter_rows import execute

        params = {
            "input_file": str(input_csv),
            "condition": "col_a > 0",
            "target_path": str(output_csv),
        }
        result = json.loads(execute(json.dumps(params)))

        assert result["success"] is True
        assert result["rows_removed"] == 0

    def test_invalid_condition(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("col_a\n1\n2\n")
        output_csv = tmp_path / "output.csv"

        from etlai.atoms.filter_rows import execute

        params = {
            "input_file": str(input_csv),
            "condition": "nonexistent_col > 0",
            "target_path": str(output_csv),
        }
        result = json.loads(execute(json.dumps(params)))

        assert result["success"] is False


class TestFlagRows:
    def test_basic_flag(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("col_a\n5\n15\n25\n10\n")
        output_csv = tmp_path / "output.csv"

        from etlai.atoms.flag_rows import execute

        params = {
            "input_file": str(input_csv),
            "condition": "col_a < 12",
            "output_column": "below_threshold",
            "target_path": str(output_csv),
        }
        result = json.loads(execute(json.dumps(params)))

        assert result["success"] is True
        assert result["row_count"] == 4
        assert result["flagged_count"] == 2
        df = pd.read_csv(output_csv)
        assert "below_threshold" in df.columns
        assert df["below_threshold"].tolist() == [True, False, False, True]

    def test_flag_keeps_all_rows(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("col_a\n1\n2\n3\n")
        output_csv = tmp_path / "output.csv"

        from etlai.atoms.flag_rows import execute

        params = {
            "input_file": str(input_csv),
            "condition": "col_a > 100",
            "output_column": "flag",
            "target_path": str(output_csv),
        }
        result = json.loads(execute(json.dumps(params)))

        assert result["success"] is True
        assert result["row_count"] == 3
        assert result["flagged_count"] == 0

    def test_invalid_expression(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("col_a\n1\n")
        output_csv = tmp_path / "output.csv"

        from etlai.atoms.flag_rows import execute

        params = {
            "input_file": str(input_csv),
            "condition": "nonexistent > 0",
            "output_column": "flag",
            "target_path": str(output_csv),
        }
        result = json.loads(execute(json.dumps(params)))

        assert result["success"] is False


class TestRenameColumns:
    def test_basic_rename(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("col_a,col_b,col_c\n1,2,3\n4,5,6\n")
        output_csv = tmp_path / "output.csv"

        from etlai.atoms.rename_columns import execute

        params = {
            "input_file": str(input_csv),
            "mapping": {"col_a": "id", "col_b": "value", "col_c": "category"},
            "target_path": str(output_csv),
        }
        result = json.loads(execute(json.dumps(params)))

        assert result["success"] is True
        assert result["columns_renamed"] == 3
        df = pd.read_csv(output_csv)
        assert list(df.columns) == ["id", "value", "category"]

    def test_partial_rename(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("col_a,col_b,col_c\n1,2,3\n")
        output_csv = tmp_path / "output.csv"

        from etlai.atoms.rename_columns import execute

        params = {
            "input_file": str(input_csv),
            "mapping": {"col_a": "renamed_a"},
            "target_path": str(output_csv),
        }
        result = json.loads(execute(json.dumps(params)))

        assert result["success"] is True
        assert result["columns_renamed"] == 1
        df = pd.read_csv(output_csv)
        assert list(df.columns) == ["renamed_a", "col_b", "col_c"]

    def test_mapping_with_nonexistent_column(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("col_a,col_b\n1,2\n")
        output_csv = tmp_path / "output.csv"

        from etlai.atoms.rename_columns import execute

        params = {
            "input_file": str(input_csv),
            "mapping": {"col_a": "new_a", "nonexistent": "new_x"},
            "target_path": str(output_csv),
        }
        result = json.loads(execute(json.dumps(params)))

        assert result["success"] is True
        assert result["columns_renamed"] == 1


class TestSortRows:
    def test_basic_sort_ascending(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("col_a,col_b\n30,x\n10,y\n20,z\n")
        output_csv = tmp_path / "output.csv"

        from etlai.atoms.sort_rows import execute

        params = {
            "input_file": str(input_csv),
            "sort_columns": ["col_a"],
            "ascending": True,
            "target_path": str(output_csv),
        }
        result = json.loads(execute(json.dumps(params)))

        assert result["success"] is True
        df = pd.read_csv(output_csv)
        assert df["col_a"].tolist() == [10, 20, 30]

    def test_sort_descending(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("col_a\n1\n3\n2\n")
        output_csv = tmp_path / "output.csv"

        from etlai.atoms.sort_rows import execute

        params = {
            "input_file": str(input_csv),
            "sort_columns": ["col_a"],
            "ascending": False,
            "target_path": str(output_csv),
        }
        result = json.loads(execute(json.dumps(params)))

        assert result["success"] is True
        df = pd.read_csv(output_csv)
        assert df["col_a"].tolist() == [3, 2, 1]

    def test_missing_sort_column(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("col_a\n1\n2\n")
        output_csv = tmp_path / "output.csv"

        from etlai.atoms.sort_rows import execute

        params = {
            "input_file": str(input_csv),
            "sort_columns": ["nonexistent"],
            "target_path": str(output_csv),
        }
        result = json.loads(execute(json.dumps(params)))

        assert result["success"] is False
        assert "nonexistent" in result["message"]
