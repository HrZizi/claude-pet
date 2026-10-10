# How account detection works

Claude Pet never reads credentials to *find* accounts. It uses three plain-metadata sources:

1. **CLI login**: `~/.claude.json` → `oauthAccount` (account id, e-mail).
2. **Desktop accounts**: the Claude Desktop app stores one JSON record per Code session under
   `<app data>/Claude/claude-code-sessions/<accountId>/<orgId>/*.json`. Each record contains the `cliSessionId`, the
   same id Claude Code passes to hooks and uses as the transcript file name.
3. **Extra login folders** you add: Claude Code config folders (`CLAUDE_CONFIG_DIR`), matched to a detected account by account id.

## Which account is "active"? (Auto mode)

The hook reports a `session_id`; the pet maps it to its owning account through the Desktop records. The most
recently active session wins. Sessions it cannot map are terminal CLI sessions and belong to the CLI login.

## Who owns a session?

When you sign in with a second Desktop account, the app copies existing session records into the new account's
folder. The copy is newer than the original, so the **oldest record** is treated as the owner.

## Per-account tokens

Transcripts live in one shared folder. Every transcript is attributed to the owner of its session id. Unknown ids belong to the CLI login.

## Limits and the Desktop login

The Desktop app's own login is protected by the operating system and Claude Pet does not attempt to read it, so
Desktop-only accounts have no limit percentages by default. Link a CLI login to the same account
(*Account → Add / link a login folder…*): the pet reads that folder's `.claude.json`, sees the same account id, and
attaches the login to the Desktop account.

Desktop accounts have no readable name or e-mail on disk, so they are called `Desktop account (xxxx)`; rename them from the menu.
