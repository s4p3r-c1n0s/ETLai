"""Tests for ETLai forms."""

import pytest


class TestPassthrough:
    """Tests for passthrough form."""

    def test_with_existing_config(self):
        """Test that existing config is returned unchanged."""
        from etlai.forms.passthrough import configure

        existing = {"group_column": "religion", "target_path": "/tmp/out.csv"}
        result = configure([], existing)

        assert result == existing

    def test_with_empty_dict_config(self):
        """Test that empty dict is valid existing config."""
        from etlai.forms.passthrough import configure

        existing = {}
        result = configure([], existing)

        assert result == {}

    def test_without_config_raises(self):
        """Test that missing config raises RuntimeError."""
        from etlai.forms.passthrough import configure

        with pytest.raises(RuntimeError, match="No config.json found"):
            configure([], None)

    def test_with_file_paths(self):
        """Test that file_paths parameter is accepted but ignored."""
        from etlai.forms.passthrough import configure

        existing = {"key": "value"}
        result = configure(["/path/to/file.csv"], existing)

        assert result == existing
