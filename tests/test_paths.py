import sys
from pathlib import Path

from claude_pet import paths


def test_env_override_wins(isolated_data_dir):
    assert paths.data_dir() == isolated_data_dir
    assert paths.state_file().parent == isolated_data_dir


def test_portable_build_keeps_data_next_to_the_exe(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_PET_HOME", raising=False)
    exe_dir = tmp_path / "ClaudePet"
    exe_dir.mkdir()
    (exe_dir / "portable.flag").write_text("x")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "ClaudePet.exe"))
    assert paths.data_dir() == (exe_dir / "data").resolve() or paths.data_dir() == exe_dir / "data"
    assert (exe_dir / "data").is_dir()


def test_installed_build_uses_the_user_data_folder(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_PET_HOME", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Programs" / "ClaudePet" / "ClaudePet.exe"))
    d = paths.data_dir()
    assert tmp_path in d.parents and "data" not in d.relative_to(tmp_path).parts[:1]
    assert not (Path(sys.executable).parent / "data").exists()       # never writes into the install folder
