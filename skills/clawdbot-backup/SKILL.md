---
name: clawdbot-backup
description: Create and manage local backups/snapshots of Clawdbot configuration and workspace. Use when the user asks to back up or snapshot Clawdbot, create a .zip backup for download, list existing backups, or diff/summarize changes since the last backup.
---

# Clawdbot Backup

Use the bundled script to create, list, and diff backups.

## Commands

- Create a backup (default destination `/Users/ericblue/clawdbot-backup`):

```bash
python3 skills/private/clawdbot-backup/scripts/clawdbot_backup.py create
```

- List backups:

```bash
python3 skills/private/clawdbot-backup/scripts/clawdbot_backup.py list
```

- Show a change summary vs the previous backup (does not create a new backup):

```bash
python3 skills/private/clawdbot-backup/scripts/clawdbot_backup.py diff
```

## What gets backed up

- Gateway config: `~/.clawdbot/clawdbot.json`
- Workspace: `/Users/ericblue/clawd`

Excludes by default (to keep backups small): `.git/`, `node_modules/`, `dist/`, `.next/`, `.DS_Store`, `*.log`, `tmp/`, `backups/`.

## Output / “download link”

The `create` command produces:
- a staging folder with the snapshot contents
- a `.zip` archive

It prints a `file://` URL to the `.zip` (clickable in many clients) plus the full local path.

## Notes about diffs

Each backup includes:
- `manifest.json` (inventory + basic metadata)
- `notes.md` (high-level change summary vs the previous backup when available)

If the workspace is a git repo, `notes.md` also includes git HEAD + `git status` + `git diff --stat`.
