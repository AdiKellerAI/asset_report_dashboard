---
name: phase-workflow
description: Use whenever starting a new branch/step in this repo, deciding how to scope a unit of work, or about to push/merge. Encodes this project's required git and testing workflow from dev-plan.md secs 9-10 - one branch per step, tests before push, Adi's approval before push/merge, build in phase order.
---

# Phase workflow (dev-plan.md §9-10)

Source of truth: `docs/dev-plan.md` §9 (git & testing workflow), §10 (build phases), `docs/PROJECT_STATUS.md` (current progress).

## The loop, every branch

```
git checkout -b <descriptive-name>   (off main, main is always clean/deployable)
  ↓
implement + write/append tests in the SAME branch, not a later cleanup pass
  ↓
run tests locally (see local-dev-stack skill for the Postgres/venv setup)
  ↓
if the branch touches anything visible (route/page/chart): run the Flask
dev server and actually view it on localhost - don't just trust green tests
  ↓
show Adi a short summary of what changed + confirm tests pass
  ↓
WAIT for explicit approval - don't push automatically because tests are green
  ↓
commit → push → merge --ff-only into main → push main
  ↓
update docs/PROJECT_STATUS.md (done-so-far table + "not yet done" list)
```

## Rules

- **One branch per step.** A parser for one document type, the ingestion endpoint, a single dashboard page - each is its own branch. Don't batch several Phase-1 bullets into one branch just because they're in the same phase (dev-plan.md §10's own closing line).
- **Build in phase order** (dev-plan.md §10): Phase 1 (schema + parsers + ingestion + landing page) before Phase 2 (charts/reports) before Phase 3 (mortgage/tax) before Phase 4 (polish/mobile/Telegram). Don't skip ahead to UI polish before Phase 1's ingestion is solid.
- **Don't invent open decisions.** Property details, mortgage numbers, hosting choices, anything under dev-plan.md §11-12 - surface it to Adi directly (AskUserQuestion or plain text), don't guess. See the `developer-preferences` skill for what's already been resolved so you don't re-ask.
- **Merge only after Adi's explicit approval of that branch's result** - a plan being approved earlier is not the same as this specific branch's diff being approved.
- After merging, `git branch` may still have the now-redundant feature branch sitting at the same commit as `main` - leave it (don't delete branches without being asked).

## When NOT to invoke this

Trivial fixes (a typo, a one-line config tweak) don't need their own branch - use judgment - but default to the full loop for anything touching schema, parsers, or more than a couple of files.
