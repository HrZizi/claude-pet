"""Canned data for `claude-pet --demo` (README screenshots, trying the UI without Claude). No personal data."""
import time

TOKENS = {"5h": 1_240_000, "7d": 9_800_000}


def accounts():
    return [
        dict(id="demo-personal", name="Personal", source="cli", dir=None, email="you@example.com", plan="Max 5x"),
        dict(id="demo-work", name="Work", source="desktop", dir=None, email="", plan="Pro"),
    ]


def limits():
    now = time.time()
    return {"5h": (42.0, now + 2 * 3600 + 14 * 60), "7d": (68.0, now + 3 * 86400 + 5 * 3600)}
