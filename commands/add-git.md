Stage files for commit with a confirmation prompt before executing.

Follow these steps:

1. Run `git status` to show the current state of the working tree.
2. Identify all untracked and modified files that could be staged.
3. Show the user a clear summary of what would be staged, organized by category:
   - New files (untracked)
   - Modified files
   - Deleted files
4. Flag any files that look like they contain secrets (`.env`, credentials, tokens, API keys) and recommend skipping them.
5. Ask the user to confirm which files to stage. Present options:
   - Stage all listed files
   - Stage specific files only
   - Abort
6. Only after the user confirms, run `git add` with the approved files (stage specific files by name — never use `git add -A` or `git add .`).
7. Run `git status` after staging to show the result.
