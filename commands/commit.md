Commit all changes from this working session with a descriptive summary.

Follow these steps:

1. Run `git status` to see all modified, added, and deleted files.
2. Run `git diff` and `git diff --cached` to review all staged and unstaged changes.
3. Run `git log --oneline -5` to see recent commit message style.
4. Stage all relevant changes with `git add` (stage specific files by name — avoid `git add -A` or `git add .` to prevent accidentally including sensitive files like .env or credentials). If there are files that look like they contain secrets or shouldn't be committed, warn the user and skip them.
5. Write a concise, descriptive commit message that summarizes the meaningful changes made during this session. Focus on the "why" and "what" rather than listing every file. Use the existing commit message style from the repo.
6. Create the commit using a heredoc format:
   ```
   git commit -m "$(cat <<'EOF'
   Your commit message here.

   Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
   EOF
   )"
   ```
7. Run `git status` after the commit to verify success.
8. Show the user the commit hash and message summary.
