import json
import os
import time

from claude_pet.claude import accounts

MAIN, SECOND = "11111111-aaaa-4aaa-8aaa-000000000001", "22222222-bbbb-4bbb-8bbb-000000000002"


def write_session(root, account, org, sid, last_ms, birth_offset=0):
    d = root / account / org
    d.mkdir(parents=True, exist_ok=True)
    f = d / ("local_%s.json" % sid[:6])
    f.write_text(json.dumps({"sessionId": "local_" + sid[:6], "cliSessionId": sid, "lastActivityAt": last_ms}))
    if birth_offset:                                    # make the copy look newer than the original
        t = time.time() + birth_offset
        os.utime(f, (t, t))
    return f


def test_desktop_accounts_and_ownership(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    monkeypatch.setattr(accounts, "desktop_root", lambda: root)
    write_session(root, MAIN, "orgA", "s-old", 1_000_000)
    write_session(root, SECOND, "orgB", "s-old", 2_000_000)      # Desktop copies old sessions to a new account
    write_session(root, SECOND, "orgB", "s-new", 3_000_000)
    owner, last = accounts.scan_desktop()
    assert owner["s-new"] == SECOND
    assert owner["s-old"] in (MAIN, SECOND)                      # resolved by oldest record, never both
    assert last[SECOND] == 3000


def test_detect_cli_and_desktop_accounts(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude.json").write_text(json.dumps(
        {"oauthAccount": {"accountUuid": MAIN, "emailAddress": "me@example.com"}}))
    monkeypatch.setattr(accounts.Path, "home", lambda: home)
    root = tmp_path / "sessions"
    monkeypatch.setattr(accounts, "desktop_root", lambda: root)
    write_session(root, MAIN, "orgA", "s1", 1000)
    write_session(root, SECOND, "orgB", "s2", 2000)
    found = {a["id"]: a for a in accounts.detect([], {})}
    assert found[MAIN]["source"] == "cli" and found[MAIN]["email"] == "me@example.com"
    assert found[SECOND]["source"] == "desktop" and found[SECOND]["name"].startswith("Desktop account")


def test_custom_names_and_login_folder_linking(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude.json").write_text(json.dumps({"oauthAccount": {"accountUuid": MAIN}}))
    monkeypatch.setattr(accounts.Path, "home", lambda: home)
    root = tmp_path / "sessions"
    monkeypatch.setattr(accounts, "desktop_root", lambda: root)
    write_session(root, SECOND, "orgB", "s2", 2000)
    cfg_dir = tmp_path / "second-login"
    cfg_dir.mkdir()
    (cfg_dir / ".claude.json").write_text(json.dumps(
        {"oauthAccount": {"accountUuid": SECOND, "emailAddress": "second@example.com"}}))
    found = {a["id"]: a for a in accounts.detect([{"name": "x", "dir": str(cfg_dir)}], {SECOND: "Work"})}
    assert found[SECOND]["name"] == "Work"                       # user rename wins
    assert found[SECOND]["dir"] == str(cfg_dir)                  # login linked to the Desktop account by uuid
    assert found[SECOND]["email"] == "second@example.com"
    assert len(found) == 2                                       # ...and not listed twice


def test_unlinked_login_folder_becomes_its_own_account(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts, "desktop_root", lambda: tmp_path / "none")
    d = tmp_path / "other"
    d.mkdir()
    found = accounts.detect([{"name": "Side", "dir": str(d)}], {})
    assert [a["name"] for a in found][-1] == "Side" and found[-1]["source"] == "manual"
