<div style="text-align: center;">
  <strong>SteamGamesHub</strong>
  <br/>
  CSV dataset repository for Steam games, integrated with Fakenodo.
</div>

# SteamGamesHub

CSV dataset repository for Steam games. Upload, preview, and publish CSV datasets with Fakenodo integration.

> Note: This project is a CSV-only refactor; prior UVL/UVLHub references have been removed.

## Git hooks and Conventional Commits

This repository ships a versioned `commit-msg` hook to enforce [Conventional Commits 1.0.0].

Install locally (once per clone):

```
bash scripts/setup-git-hooks.sh
```

From then on, Git will use `.githooks/` as the hooks directory. The `commit-msg` hook enforces titles like:

- `feat(scope): description`
- `fix: description`
- `refactor(core)!: important change`

Rules included:
- Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert.
- Optional scope, optional `!` for breaking changes.
- Blank line between title and body when a body is present.
- If you use `!`, add a footer `BREAKING CHANGE: ...` in the body.

Example:

```
feat(payments): add SEPA support

Add context of the change here.

Closes: #321
Refs: #220
```
