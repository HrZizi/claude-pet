# Security policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Use GitHub's *Report a vulnerability* (Security tab → Advisories)
on this repository. Include the affected version and steps to reproduce.

## What claude-pet touches

- Reads Claude Code transcripts and account metadata locally; never uploads them.
- With *Fetch real limits* enabled (off by default) it sends the Claude Code access token, from memory, to `api.anthropic.com` only.
- Edits `~/.claude/settings.json` only when you connect it (backup written first).

See the *Privacy & security* section of the README for the full list. Anything that goes beyond it is a bug worth reporting.
