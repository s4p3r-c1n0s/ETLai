"""Tests for etlai CLI — sync sensor-enable behavior."""

import types


def _fake_state(name, status, instigator_type="SENSOR", origin_id="origin-1", selector_id="selector-1"):
    """Build a minimal fake InstigatorState-like object for _enable_sensors."""
    return types.SimpleNamespace(
        instigator_type=types.SimpleNamespace(value=instigator_type),
        instigator_name=name,
        status=types.SimpleNamespace(value=status),
        instigator_origin_id=origin_id,
        selector_id=selector_id,
    )


def _make_project(tmp_path):
    """Create a minimal project with one pipeline whose sensor should be enabled."""
    (tmp_path / "atoms").mkdir()
    (tmp_path / "atoms" / "vlookup.py").write_text("")
    pipeline = tmp_path / "pipelines" / "test_pipeline"
    pipeline.mkdir(parents=True)
    (tmp_path / "etlai.yaml").write_text("pipelines_root: ./pipelines\n")
    (pipeline / "manifest.yaml").write_text(
        "name: test_pipeline\natom: vlookup\nmin_files: 2\n"
    )
    return tmp_path


class TestSyncEnablesSensors:
    """cmd_sync should turn detected STOPPED sensors back on (revert to RUNNING default)."""

    def test_stopped_sensor_is_enabled(self, tmp_path, monkeypatch):
        from etlai import cli
        from dagster import DagsterInstance

        _make_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        deleted = []
        fake_instance = types.SimpleNamespace(
            all_instigator_state=lambda: [
                _fake_state("test_pipeline_sensor", "STOPPED"),
            ],
            delete_instigator_state=lambda origin_id, selector_id: deleted.append(
                (origin_id, selector_id)
            ),
        )
        monkeypatch.setattr(DagsterInstance, "get", lambda *a, **k: fake_instance)

        cli.cmd_sync(None)

        assert deleted == [("origin-1", "selector-1")]

    def test_running_sensor_is_left_alone(self, tmp_path, monkeypatch):
        from etlai import cli
        from dagster import DagsterInstance

        _make_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        deleted = []
        fake_instance = types.SimpleNamespace(
            all_instigator_state=lambda: [
                _fake_state("test_pipeline_sensor", "RUNNING"),
            ],
            delete_instigator_state=lambda origin_id, selector_id: deleted.append(
                (origin_id, selector_id)
            ),
        )
        monkeypatch.setattr(DagsterInstance, "get", lambda *a, **k: fake_instance)

        cli.cmd_sync(None)

        assert deleted == []

    def test_non_sensor_state_is_ignored(self, tmp_path, monkeypatch):
        from etlai import cli
        from dagster import DagsterInstance

        _make_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        deleted = []
        fake_instance = types.SimpleNamespace(
            all_instigator_state=lambda: [
                _fake_state("test_pipeline_sensor", "STOPPED", instigator_type="SCHEDULE"),
            ],
            delete_instigator_state=lambda origin_id, selector_id: deleted.append(
                (origin_id, selector_id)
            ),
        )
        monkeypatch.setattr(DagsterInstance, "get", lambda *a, **k: fake_instance)

        cli.cmd_sync(None)

        assert deleted == []

    def test_unrelated_sensor_is_ignored(self, tmp_path, monkeypatch):
        from etlai import cli
        from dagster import DagsterInstance

        _make_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        deleted = []
        fake_instance = types.SimpleNamespace(
            all_instigator_state=lambda: [
                _fake_state("other_pipeline_sensor", "STOPPED"),
            ],
            delete_instigator_state=lambda origin_id, selector_id: deleted.append(
                (origin_id, selector_id)
            ),
        )
        monkeypatch.setattr(DagsterInstance, "get", lambda *a, **k: fake_instance)

        cli.cmd_sync(None)

        assert deleted == []
