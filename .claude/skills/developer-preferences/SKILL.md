---
name: developer-preferences
description: Use at the start of any work session on this repo, or whenever unsure how Adi wants something done. Holds Adi's working preferences and the technical decisions already made, so they don't get re-asked or re-decided differently.
---

# Developer preferences & decisions log

This is the working agreement for this repo - keep it updated as new preferences or
decisions come up (append, don't silently rewrite history - if a decision changes, note
what it changed from and why).

## Adi's working preferences

- **Always show localhost for anything visible.** Whenever a branch touches a route,
  page, or chart, run the Flask dev server and actually view/curl it before calling the
  branch done - don't just rely on green tests. Stated directly, 2026-08-22.
- **Ask, don't guess, on open decisions.** Anything under `docs/dev-plan.md` §11
  (access/secrets) or §12 (open product decisions) gets asked directly - see the
  "Resolved decisions" list below for what's already answered so it isn't re-asked.
- **One branch per step, approval before push/merge** (full detail in the
  `phase-workflow` skill) - Adi has approved each branch quickly so far when shown a
  short summary + confirmation tests pass; don't skip the summary-and-wait step even
  though approvals have been fast.
- **Keep `docs/PROJECT_STATUS.md` current** - update it at the end of every
  branch/phase, not in a separate catch-up pass later.
- **Use this repo's skills and actually follow them** - don't create a skill and then
  work around it; if a skill's guidance turns out wrong, fix the skill rather than
  quietly diverging from it.

## Resolved decisions (don't re-ask these)

| Decision | Answer | Where it's detailed |
|---|---|---|
| Postgres instance | A dedicated Neon serverless project, separate from both `maayan_recipes` and `photography` - live as of 2026-08-22. (Two earlier, superseded answers same day: `photography`/Neon, then `maayan_recipes`'s GCP Cloud SQL - dropped after an IP-allowlist dead end) | `docs/dev-plan.md` §13.1, `postgres-instance` memory |
| Property nicknames | Brunswick, Colburn (no "Ave") | §13.2 |
| App access | Private to Adi only, single password gate | §13.3 |
| ORM | SQLAlchemy + Alembic (versioned migrations, not push-based sync) | §13.6 |
| Money flow | No personal US bank account - Overland/AppFolio holds funds directly. Adi moves money to Israel irregularly via Wise (~$30 fee/transfer); none sent in ~8 months as of Aug 2026 (Wise account closed under new non-US-citizen regulations) | §13.5 |
| `owner_payment` expense type | Dropped - doesn't apply given the money-flow finding above | §13.5 |
| `transfer` table | Added - portfolio-level (not per-property), logs Wise transfers manually | §13.5 |
| "Net to Adi" reserve question | Proceeding with NOI − unpaid bills − mortgage (reserve not subtracted) as the default | §13.4 |
| Accumulated Balance formula | **Corrected 2026-08-22** after real data inspection - `net_owner_funds` is a running balance, not a monthly delta. See §14 for the corrected formula - don't reintroduce the original "sum across all months" version | §14 |
| Python version | Homebrew Python 3.12 (not system 3.9.6) - required `DYLD_LIBRARY_PATH="/opt/homebrew/opt/expat/lib"` workaround for a libexpat ABI mismatch on this Mac's macOS build; Adi found and applied this fix himself, added to `~/.zshrc` | `local-dev-stack` skill |
| Currency | All storage/math stays USD-only (VirtueTax's ~2000 NIS/year fee, and the mortgage payment - currently 5081 NIS, changes periodically - both get entered as their USD equivalent, no `currency` column anywhere). A future site-wide USD/NIS **display** toggle uses the current day's live exchange rate, default USD - display-layer only, its own future branch, not blocking Phase 1 | `docs/dev-plan.md` §15 |
| Mortgage editing | Needs to be editable from the site itself (a real UI page, not a DB edit) - Adi will update the USD-equivalent `monthly_payment` there whenever the NIS amount changes. This is the Phase 3 Mortgage settings page (dev-plan.md §5.6) | `docs/dev-plan.md` §15 |

## Still open (ask when work reaches these, don't guess)

- Mortgage details per property (lender, monthly payment, start date) - needed before
  the Phase 3 mortgage settings branch.
- The real Neon `DATABASE_URL` - needed before pointing anything at production data.
- GCP project ID / Cloud Run confirmation - needed before Phase 4 deployment.
- Telegram bot token + chat ID - optional, only if the notification feature is wanted.
