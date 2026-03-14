Stage, commit, and push all changes from this working session in one flow.

Follow these steps:

## Phase 1: Stage

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

## Phase 2: Commit

7. Run `git diff --cached` to review all staged changes.
8. Run `git log --oneline -5` to see recent commit message style.
9. Write a concise, descriptive commit message that summarizes the meaningful changes made during this session. Focus on the "why" and "what" rather than listing every file. Use the existing commit message style from the repo.
10. Create the commit using a heredoc format:
    ```
    git commit -m "$(cat <<'EOF'
    Your commit message here.

    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
    EOF
    )"
    ```
11. Run `git status` after the commit to verify success.
12. Show the user the commit hash and message summary.

## Phase 3: Push

13. Run `git rev-list --count @{upstream}..HEAD 2>/dev/null || echo "No upstream set"` to check how many commits are ahead of the remote.
14. Confirm the current branch name with `git branch --show-current`.
15. If the branch has no upstream tracking branch, push with `git push -u origin <branch-name>`.
16. Otherwise, push with `git push`.
17. Show the user the result and confirm the push was successful.

IMPORTANT: Never use `--force` or `--force-with-lease` unless the user explicitly requests it. If the push is rejected, inform the user and suggest pulling first. If ANY phase fails, stop and report the error — do not continue to the next phase.
