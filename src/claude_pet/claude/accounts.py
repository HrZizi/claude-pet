"""Finds every Claude account on this machine, without touching any credentials.

Sources (all plain metadata):
  * CLI login        ~/.claude.json -> oauthAccount (uuid, email)
  * Desktop accounts <Claude app data>/claude-code-sessions/<accountUuid>/<orgUuid>/*.json
                     (one record per Desktop Code session, naming the account and its transcript id)
  * extra logins    config folders the user added (CLAUDE_CONFIG_DIR=<folder>), matched to the above by uuid

The Desktop app's own login is encrypted and carries no readable name, so Desktop-only accounts get a
generic name ("Desktop account (5bb3)") the user can rename. Their real limits need a CLI login linked to them.
"""
import json
import os
import sys
from pathlib import Path


def desktop_root():
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Claude/claude-code-sessions"
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", "")) / "Claude/claude-code-sessions"
    return Path.home() / ".config/Claude/claude-code-sessions"


def _read_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _birth(st):
    return getattr(st, "st_birthtime", None) or st.st_ctime


def identity(config_dir=None):
    """(uuid, email) of the CLI login stored in that config folder, or ('', '')."""
    base = Path(config_dir) if config_dir else Path.home()
    j = _read_json(base / ".claude.json") or {}
    if config_dir and not j:                      # some setups keep it next to the credentials
        j = _read_json(Path(config_dir) / ".claude.json") or {}
    oa = j.get("oauthAccount") or {}
    return oa.get("accountUuid", ""), oa.get("emailAddress", "")


def scan_desktop():
    """-> (owner {cliSessionId: accountUuid}, last_activity {accountUuid: epoch seconds})

    After the user signs in with a second account, Desktop copies the old session records into that
    account's folder too; the copy is newer, so the oldest record is taken as the real owner."""
    root = desktop_root()
    cand, activity = {}, {}
    try:
        accounts = [d for d in root.iterdir() if d.is_dir()]
    except OSError:
        return {}, {}
    for acct in accounts:
        for org in (d for d in acct.iterdir() if d.is_dir()):
            for f in org.glob("*.json"):
                j = _read_json(f)
                sid = (j or {}).get("cliSessionId")
                if not sid:
                    continue
                try:
                    birth = _birth(f.stat())
                except OSError:
                    continue
                cand.setdefault(sid, []).append((birth, acct.name))
                activity[(sid, acct.name)] = (j.get("lastActivityAt") or 0) / 1000
    owner = {sid: min(v)[1] for sid, v in cand.items()}
    last = {}
    for sid, o in owner.items():
        last[o] = max(last.get(o, 0), activity.get((sid, o), 0))
    return owner, last


def detect(extra, names, last=None):
    """-> list of account dicts: id, name, source (cli|desktop|manual), dir (login folder or None), email."""
    cli_uuid, cli_email = identity(None)
    cli_id = cli_uuid or "cli"
    accts = [dict(id=cli_id, name=names.get(cli_id, "CLI login"), source="cli", dir=None, email=cli_email)]
    if last is None:
        _, last = scan_desktop()
    for uuid in sorted(last, key=lambda u: -last[u]):
        if uuid != cli_id:
            accts.append(dict(id=uuid, name=names.get(uuid, "Desktop account (%s)" % uuid[:4]),
                              source="desktop", dir=None, email=""))
    for m in extra:
        d = m.get("dir")
        if not d:
            continue
        uuid, email = identity(d)
        match = next((a for a in accts if uuid and a["id"] == uuid), None)
        if match and match["dir"] is None and match["source"] != "cli":
            match["dir"], match["email"] = d, email or match["email"]      # link a login to a Desktop account
        elif not match:
            mid = "dir:" + str(d)
            accts.append(dict(id=mid, name=names.get(mid, m.get("name") or Path(d).name), source="manual",
                              dir=d, email=email))
    return accts
