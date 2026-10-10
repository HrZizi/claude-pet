import json
import subprocess
import sys

from claude_pet import cli
from claude_pet.claude import integration


def test_install_preserves_foreign_settings_and_hooks(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({
        "theme": "dark",
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "notify-send done"}]}]}}))
    integration.install(p)
    s = json.loads(p.read_text())
    assert s["theme"] == "dark"
    stop_cmds = [h["command"] for g in s["hooks"]["Stop"] for h in g["hooks"]]
    assert "notify-send done" in stop_cmds and any("claude_pet" in c for c in stop_cmds)
    assert integration.is_installed(p)
    assert "statusLine" not in s                         # the statusLine is opt-in


def test_install_is_idempotent_and_uninstall_restores(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "mine"}]}]}}))
    integration.install(p)
    integration.install(p)
    s = json.loads(p.read_text())
    assert sum("claude_pet" in h["command"] for g in s["hooks"]["Stop"] for h in g["hooks"]) == 1
    integration.uninstall(p)
    s = json.loads(p.read_text())
    assert s["hooks"]["Stop"][0]["hooks"][0]["command"] == "mine"
    assert not integration.is_installed(p)


def test_backup_is_written_before_changes(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{}")
    integration.install(p)
    assert list(tmp_path.glob("settings.json.bak-*"))


def test_install_replaces_legacy_script_hooks(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": "python /opt/claude-pet/hook.py done"}]}]}}))
    integration.install(p)
    cmds = [h["command"] for g in json.loads(p.read_text())["hooks"]["Stop"] for h in g["hooks"]]
    assert len(cmds) == 1 and "-m claude_pet hook done" in cmds[0].replace("\\", "/")


def test_hook_command_is_runnable_and_records_state(isolated_data_dir, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(__import__("pathlib").Path(__file__).parents[1] / "src"))
    r = subprocess.run([sys.executable, "-m", "claude_pet", "hook", "working"], input='{"session_id": "abc"}',
                       capture_output=True, text=True, env=None)
    assert r.returncode == 0 and r.stdout == ""
    state = json.loads((isolated_data_dir / "state.json").read_text())
    assert state["sessions"]["abc"]["state"] == "working"
    subprocess.run([sys.executable, "-m", "claude_pet", "hook", "end"], input='{"session_id": "abc"}', text=True)
    assert "abc" not in json.loads((isolated_data_dir / "state.json").read_text())["sessions"]


def test_hook_tolerates_garbage_input(isolated_data_dir):
    assert cli.main(["--version"]) == 0
    r = subprocess.run([sys.executable, "-m", "claude_pet", "hook", "done"], input="not json", capture_output=True, text=True)
    assert r.returncode == 0
