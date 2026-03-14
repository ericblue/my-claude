# my-claude

A curated collection of custom Claude Code slash commands and skills. More will be added over time.

## Commands

Slash commands that extend Claude Code's built-in capabilities for common Git workflows and image generation.

### `/add-git`

Interactive file staging for Git. Runs `git status`, presents a categorized summary of new, modified, and deleted files, flags anything that looks like it contains secrets, and asks for confirmation before staging. Stages files by name (never `git add -A`) for safety.

### `/commit`

Commits changes with an auto-generated descriptive message. Reviews staged and unstaged diffs, matches the repo's existing commit style, warns about sensitive files, and creates the commit with a `Co-Authored-By` trailer.

### `/commit-push`

All-in-one stage, commit, and push flow. Combines the interactive staging of `/add-git`, the smart commit message generation of `/commit`, and a safe push (auto-detects whether `-u origin` is needed, never force-pushes unless explicitly asked).

### `/push`

Pushes the current branch to the remote. Shows what will be pushed, checks how many commits are ahead, and sets upstream tracking if needed. Refuses to force-push without explicit permission.

### `/generate-images`

Generates images using OpenAI's `gpt-image-1.5` model. Supports a natural shorthand syntax (`/generate-images 3 cats wearing hats`) as well as full flags for count, size, quality, output directory, filename prefix, and format. Requires `OPENAI_API_KEY` and `jq`.

## Skills

More advanced capabilities with dedicated scripts and configuration, designed for use with Claude Code or OpenClaw. Some skills are used by both but should be interchangeable between the two.

### `searxng`

Privacy-friendly web search via a locally-running [SearXNG](https://github.com/searxng/searxng) instance (`http://127.0.0.1:8888`). Includes a Python helper script that accepts query, result count, categories, and language parameters. Returns results as a concise bullet list with titles, URLs, and snippets.

### `clawdbot-backup`

Backup and snapshot manager for OpenClaw configuration and workspace. Supports creating timestamped `.zip` backups, listing existing backups, and diffing against the previous snapshot. Each backup includes a manifest and a change summary (with Git status/diff when available). Excludes `.git/`, `node_modules/`, and other bulky directories by default.

### `gog-custom`

Secure, **read-only** Gmail and Google Calendar access via gogcli. All operations go through a Python security wrapper that enforces a strict allowlist -- no sending, replying, forwarding, drafting, or deleting. Supports searching threads, reading messages, listing calendars/events, checking freebusy/conflicts, and managing auth aliases. All email and calendar content is treated as untrusted input.

### `generate-images`

Skill version of the `/generate-images` command. Wraps a Bash helper script that handles argument parsing, sequential API calls, file naming (with collision avoidance), progress reporting, and cost estimation. Triggered when the user asks to generate, create, or make images.

## Related Projects

Additional skills and commands available in their own dedicated repos:

- **[Mac Agent Gateway](https://github.com/ericblue/mac-agent-gateway)** — HTTP gateway for controlling macOS apps (Messages, Reminders, etc.) from Claude Code or other agents.
- **[Claude VibeKanban](https://github.com/ericblue/claude-vibekanban)** — Kanban-style task management and parallel workflow orchestration for Claude Code.
- **[Habit Sprint](https://github.com/ericblue/habit-sprint)** — Habit tracking and sprint-based goal management.
- **[Claude OpenClaw Bridge](https://github.com/ericblue/claude-openclaw-bridge)** — Bridge skill for relaying tasks and queries between Claude Code and an OpenClaw agent.

## About

Created by [Eric Blue](https://about.ericblue.com)

## Structure

```
commands/          Slash command definitions (Markdown)
skills/
  searxng/         SearXNG web search
  clawdbot-backup/ Clawdbot backup & snapshot
  gog-custom/      Read-only Gmail + Calendar
  generate-images/ OpenAI image generation
```
