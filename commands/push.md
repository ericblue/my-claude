Push the current branch to the remote repository.

Follow these steps:

1. Run `git status` and `git log --oneline -3` to show the user what will be pushed.
2. Run `git rev-list --count @{upstream}..HEAD 2>/dev/null || echo "No upstream set"` to check how many commits are ahead of the remote.
3. Confirm the current branch name with `git branch --show-current`.
4. If the branch has no upstream tracking branch, push with `git push -u origin <branch-name>`.
5. Otherwise, push with `git push`.
6. Show the user the result and confirm the push was successful.

IMPORTANT: Never use `--force` or `--force-with-lease` unless the user explicitly requests it. If the push is rejected, inform the user and suggest pulling first.
