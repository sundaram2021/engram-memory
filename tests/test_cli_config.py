import json

from click.testing import CliRunner

from engram.cli import main
from engram.workspace import WorkspaceConfig, write_workspace


def test_config_show_prints_editable_settings(monkeypatch, tmp_path):
    monkeypatch.setattr("engram.workspace.WORKSPACE_PATH", tmp_path / "workspace.json")

    write_workspace(
        WorkspaceConfig(
            engram_id="ENG-TEST-1234",
            db_url="postgres://localhost/test",
            anonymous_mode=True,
            anon_agents=False,
            display_name="Tunde",
        )
    )

    runner = CliRunner()
    result = runner.invoke(main, ["config", "show"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == {
        "anonymous_mode": True,
        "anon_agents": False,
        "display_name": "Tunde",
    }


def test_config_show_fails_when_workspace_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("engram.workspace.WORKSPACE_PATH", tmp_path / "workspace.json")

    runner = CliRunner()
    result = runner.invoke(main, ["config", "show"])

    assert result.exit_code != 0
    assert "No workspace config found" in result.output


def test_config_set_updates_anonymous_mode(monkeypatch, tmp_path):
    monkeypatch.setattr("engram.workspace.WORKSPACE_PATH", tmp_path / "workspace.json")

    write_workspace(
        WorkspaceConfig(
            engram_id="ENG-TEST-1234",
            db_url="postgres://localhost/test",
        )
    )

    runner = CliRunner()
    result = runner.invoke(main, ["config", "set", "anonymous_mode", "true"])

    assert result.exit_code == 0
    assert "Updated anonymous_mode=true" in result.output

    data = json.loads((tmp_path / "workspace.json").read_text())
    assert data["anonymous_mode"] is True


def test_config_set_updates_anon_agents(monkeypatch, tmp_path):
    monkeypatch.setattr("engram.workspace.WORKSPACE_PATH", tmp_path / "workspace.json")

    write_workspace(
        WorkspaceConfig(
            engram_id="ENG-TEST-1234",
            db_url="postgres://localhost/test",
        )
    )

    runner = CliRunner()
    result = runner.invoke(main, ["config", "set", "anon_agents", "false"])

    assert result.exit_code == 0
    assert "Updated anon_agents=false" in result.output

    data = json.loads((tmp_path / "workspace.json").read_text())
    assert data["anon_agents"] is False


def test_config_set_updates_display_name(monkeypatch, tmp_path):
    monkeypatch.setattr("engram.workspace.WORKSPACE_PATH", tmp_path / "workspace.json")

    write_workspace(
        WorkspaceConfig(
            engram_id="ENG-TEST-1234",
            db_url="postgres://localhost/test",
        )
    )

    runner = CliRunner()
    result = runner.invoke(main, ["config", "set", "display_name", "Tunde"])

    assert result.exit_code == 0
    assert 'Updated display_name="Tunde"' in result.output

    data = json.loads((tmp_path / "workspace.json").read_text())
    assert data["display_name"] == "Tunde"


def test_config_set_rejects_unknown_key(monkeypatch, tmp_path):
    monkeypatch.setattr("engram.workspace.WORKSPACE_PATH", tmp_path / "workspace.json")

    write_workspace(
        WorkspaceConfig(
            engram_id="ENG-TEST-1234",
            db_url="postgres://localhost/test",
        )
    )

    runner = CliRunner()
    result = runner.invoke(main, ["config", "set", "bad_key", "true"])

    assert result.exit_code != 0
    assert "Unknown config key" in result.output


def test_config_set_rejects_invalid_boolean(monkeypatch, tmp_path):
    monkeypatch.setattr("engram.workspace.WORKSPACE_PATH", tmp_path / "workspace.json")

    write_workspace(
        WorkspaceConfig(
            engram_id="ENG-TEST-1234",
            db_url="postgres://localhost/test",
        )
    )

    runner = CliRunner()
    result = runner.invoke(main, ["config", "set", "anonymous_mode", "maybe"])

    assert result.exit_code != 0
    assert "Invalid boolean value" in result.output


def test_config_set_rejects_empty_display_name(monkeypatch, tmp_path):
    monkeypatch.setattr("engram.workspace.WORKSPACE_PATH", tmp_path / "workspace.json")

    write_workspace(
        WorkspaceConfig(
            engram_id="ENG-TEST-1234",
            db_url="postgres://localhost/test",
        )
    )

    runner = CliRunner()
    result = runner.invoke(main, ["config", "set", "display_name", "   "])

    assert result.exit_code != 0
    assert "display_name cannot be empty" in result.output
