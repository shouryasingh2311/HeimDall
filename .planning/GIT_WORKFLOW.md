# Git workflow for the three-person team

## Current documentation delivery versus future implementation

This revision is documentation only, delivered on planning/eight-hour-team-execution. User authorized committing and pushing these documents. Implementation branches below are a future build workflow; do not start building merely by reading this plan.

Review/merge the planning branch into main before teammates branch for implementation. Never overwrite main or force-push shared history. GitHub collaborator/write access may be needed for teammates; do not share passwords/tokens. A fork plus PR works if direct push is unavailable.

## Branches

- main: reviewed integration branch; must start and pass relevant checks.
- feat/core-platform: M1, all core/security/AI work.
- feat/operations-dashboard: M2, UI/client only.
- feat/fixtures-validation: M3, adapters/demo input/local HTML/test harness.
- fix/<owner>-<issue>: optional short repair branch from latest main.

Use separate clones or worktrees when multiple agents run on one computer. Never let two agents switch branches in the same checkout.

## First setup (PowerShell-compatible commands, one per line)

    git clone https://github.com/shouryasingh2311/monitor.git
    cd monitor
    git fetch origin
    git switch main
    git pull --ff-only origin main

After the planning merge, choose exactly ONE branch for your role:

    git switch -c feat/core-platform
    git switch -c feat/operations-dashboard
    git switch -c feat/fixtures-validation

The three lines above are alternatives, not a sequence. Each member runs only their line in their own checkout.

## Small delivery cycle

    git status --short
    git diff
    git add <explicit-owned-paths>
    git diff --cached --check
    git diff --cached
    git commit -m "feat(ui): show fleet freshness and reasons"
    git push -u origin <your-branch>

Angle-bracket arguments are placeholders to replace. Do not paste them literally. Stage explicit paths; never git add . when credentials/databases/raw logs might exist. Keep commits focused. Prefix examples: docs(plan), feat(core), feat(ui), test(scenarios), fix(core).

Before commit, owner runs relevant checks in VALIDATION.md. Tests/build failures block merge; no success fallback such as '|| echo'. PR includes problem/behavior, requirement IDs, owned files, test evidence, known gaps and dependency on another unmerged PR if any. Open PR against main through GitHub UI or gh if installed/authenticated. Avoid bundling unrelated changes.

## Sync and integration

Save work as a commit first; then on your own feature branch:

    git fetch origin
    git merge origin/main

Resolve only understood conflicts. If conflict touches another owner's contract/core files, coordinate with M1; do not accept all ours/theirs. Run affected checks and push normally. Prefer merges for shared feature branches; no history rewriting after another member has based work on it.

M1 reviews at G1-G5, merges tested PRs into main, and announces the integration SHA via status files/team channel. Preserve commit ancestry with normal merge commits during the event so long-lived feature branches can continue. If using squash merges, create a NEW branch from updated main for the next slice; do not repeatedly reuse the old squashed branch.

Core interface PR merges before dependent live UI/harness PRs. Fixtures/UI scaffold may merge earlier if clearly marked mock-only. Merge order is by working slice, not by all eight phase numbers.

## Status and release

Each member edits only their .planning/status/MEMBER_N.md. M1 updates STATE.md with accepted gates and links to evidence; nobody marks a phase complete solely because files exist.

M1 creates a release tag only after V00-V13 outcomes are reviewed, clean startup rehearsed and limitations recorded. A failed external prerequisite is disclosed; never label organizer compatibility passed without its stream. Do not push a tag named validated when checks are blocked.

Never commit .env, CA private keys, bearer tokens, databases, real raw logs, or screenshots with secrets. During implementation M1 adds repository .gitignore/.env.example before any runtime artifacts are created.
