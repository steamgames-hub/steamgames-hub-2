<div style="text-align: center;">
  <strong>SteamGamesHub</strong>
  <br/>
  CSV dataset repository for Steam games, integrated with Fakenodo.
</div>

# SteamGamesHub

CSV dataset repository for Steam games. Upload, preview, and publish CSV datasets with Fakenodo integration.

> Note: This project is a CSV-only refactor; prior UVL/UVLHub references have been removed.

## .env file and app secrets

Due to general security concerns, the pre-existing .env examples are lacking some important values. However, if you are 
a part of the University of Seville organization, you can access the complete .env files, ready to use, in 
the following [link](https://uses0-my.sharepoint.com/:f:/r/personal/albramvar1_alum_us_es/Documents/steamgames-hub-env?csf=1&web=1&e=SuQXbM).


## File storage (local vs AWS S3)

The app now uses a unified storage layer that keeps uploads under `uploads/` when
running locally, but transparently switches to AWS S3 whenever bucket
credentials are present. Configure the following environment variables in
production (e.g., on Render) to persist datasets and community images when the
dyno goes to sleep:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET`
- `S3_REGION`
- *(optional)* `S3_PREFIX` to store files under a custom folder inside the bucket

Files are still staged locally during uploads (so previews work instantly) and
re-downloaded on demand if the file is only present in S3. When the variables
above are not set, everything keeps behaving as before using the local
filesystem defined by `UPLOADS_DIR`/`WORKING_DIR`.

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

## Quick fix for common Vagrant errors

- In case you have an error corresponding to AMD-V and you cannot access the bios settings for that, please use this command `sudo rmmod kvm_amd`

- In case you have an error about Virtual Box instances, please go to your Virtual Box Manager and delete the current vagrant image or use `vagrant destroy` instead
