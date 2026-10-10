import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Never touch the real per-user data folder."""
    monkeypatch.setenv("CLAUDE_PET_HOME", str(tmp_path / "data"))
    (tmp_path / "data").mkdir()
    return tmp_path / "data"
