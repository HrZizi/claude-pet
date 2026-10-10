import json
import time
from datetime import datetime, timezone

from claude_pet.claude import usage


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def line(msg_id, ts, inp, out, cache=0):
    return json.dumps({"timestamp": iso(ts), "requestId": "r" + msg_id, "message": {
        "id": msg_id, "usage": {"input_tokens": inp, "output_tokens": out,
                                "cache_creation_input_tokens": cache, "cache_read_input_tokens": 999999}}}) + "\n"


def test_token_totals_dedupe_windows_and_cache_reads(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    now = time.time()
    (proj / "sessA.jsonl").write_text(
        line("m1", now - 60, 100, 10) +
        line("m1", now - 59, 100, 50) +                  # streaming duplicate: the larger one wins
        line("m2", now - 6 * 3600, 1000, 0) +            # outside 5h, inside 7d
        line("m3", now - 8 * 86400, 5000, 0))            # outside 7d
    loc = usage.LocalTokens(proj)
    loc.scan()
    assert loc.totals() == {"5h": 150, "7d": 1150}       # cache_read tokens never counted


def test_per_account_attribution(tmp_path):
    proj = tmp_path / "proj"
    (proj / "x").mkdir(parents=True)
    now = time.time()
    (proj / "x" / "mine.jsonl").write_text(line("a", now - 10, 10, 0))
    (proj / "x" / "theirs.jsonl").write_text(line("b", now - 10, 20, 0))
    loc = usage.LocalTokens(proj)
    loc.scan()
    owner = {"theirs": "acct-2"}
    assert loc.totals(owner, "acct-2", default="acct-1")["5h"] == 20
    assert loc.totals(owner, "acct-1", default="acct-1")["5h"] == 10     # unknown sessions -> default account


def test_incremental_scan_only_reads_new_lines(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    f = proj / "s.jsonl"
    now = time.time()
    f.write_text(line("a", now - 5, 1, 1))
    loc = usage.LocalTokens(proj)
    loc.scan()
    with open(f, "a") as fh:
        fh.write(line("b", now - 4, 2, 2))
    loc.scan()
    assert loc.totals()["5h"] == 6


def test_read_limits_resets_rolled_over_windows(isolated_data_dir):
    now = time.time()
    (isolated_data_dir / "usage.json").write_text(json.dumps({"rate_limits": {
        "five_hour": {"used_percentage": 80, "resets_at": now - 10},
        "seven_day": {"used_percentage": 30, "resets_at": iso(now + 3600)}}}))
    lim = usage.read_limits()
    assert lim["5h"][0] == 0.0 and lim["7d"][0] == 30.0


def test_formatting():
    assert usage.fmt_tokens(1_240_000) == "1.2M" and usage.fmt_tokens(54_321) == "54k"
    assert usage.fmt_delta(3 * 86400 + 5 * 3600) == "3d5h" and usage.fmt_delta(125 * 60) == "2h05m"
