<div style="text-align: center;">
  <img src="https://www.uvlhub.io/static/img/logos/logo-light.svg" alt="Logo">
</div>

# uvlhub.io

Repository of feature models in UVL format integrated with Zenodo and flamapy following Open Science principles - Developed by DiversoLab

## Official documentation

You can consult the official documentation of the project at [docs.uvlhub.io](https://docs.uvlhub.io/)

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
