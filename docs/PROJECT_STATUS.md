# Project Status

Living summary of what this project is and how far it's gotten. Update this at the end of every branch/phase — don't let it go stale. The full spec is `docs/dev-plan.md`; this doc is the "where are we right now" companion to it.

## What this is

A single-user Flask + PostgreSQL app that turns Adi's monthly AppFolio/Overland property-management statements and utility bills (2 Ohio rental properties: Brunswick, Colburn) into a clear dashboard of income, expenses, and what's actually accumulated with the property manager. Parsing is deterministic (rule-based Python, no runtime LLM calls) — see `docs/dev-plan.md` §2.

## Current phase

**Phase 1 — Core capture (MVP)**, per `docs/dev-plan.md` §10. Schema and format research are done; parsers and the ingestion endpoint are next.

## Done so far

| Branch | What it added | Status |
|---|---|---|
| `project-scaffolding` | Flask app skeleton, `/health` route, pytest wiring, `docs/dev-plan.md` copied in | Merged to `main` |
| `postgres-schema` | SQLAlchemy models + Alembic migration for all 9 tables, seed data (properties + expense taxonomy), local Docker Postgres for dev/test | Merged to `main` |
| `format-notes` | Real `pdfplumber` text extraction across 5 years of Owner Packet samples + both utility bill types → `docs/formats/*.md`. Found and corrected a bug in the planned "Accumulated Balance" formula (see below) | Merged to `main` |
| `project-status-and-skills` | This doc + `.claude/skills/` for this repo, plus the currency decision (dev-plan.md §15) | Merged to `main` |
| `owner-packet-parser` | `app/parsers/` - cash-summary field extraction + categorized transaction parsing from Owner Packet.pdf, tested against the full real archive (~52 files). Found and fixed a real arithmetic bug (Owner Disbursements vs Unpaid Bills) and identified 2 pre-Apr-2022 files with an unsupported older layout | Merged to `main` |

## Key decisions locked in (see `docs/dev-plan.md` §13–14 for full detail)

- Postgres: same Neon instance as the `photography` project, new database within it. **Real `DATABASE_URL` not yet handed over** — schema/migrations only verified against a local Docker Postgres so far.
- Property nicknames: **Brunswick**, **Colburn**.
- Access: private to Adi only.
- ORM: SQLAlchemy + Alembic (versioned migrations).
- Money flow: Overland/AppFolio holds funds directly (no personal US bank account) — Adi periodically moves money to Israel via Wise (~$30 fee/transfer). A `transfer` table logs these. The `owner_payment` expense type from the original spec was dropped since it doesn't apply.
- **Accumulated Balance formula corrected** after real data inspection: `net_owner_funds` is a running balance (rolls forward month to month), not a monthly delta — summing it across months would be wrong. Corrected formula in `docs/dev-plan.md` §14.
- Local dev environment quirk: Homebrew's Python 3.12 needs `DYLD_LIBRARY_PATH="/opt/homebrew/opt/expat/lib"` set (already in `~/.zshrc`) to work around a libexpat ABI mismatch against this Mac's very new macOS build — see the `local-dev-stack` skill.
- Standing rule: whenever a branch touches anything visible, run the Flask dev server and actually view it on localhost before calling the branch done.

## Not yet done (rest of Phase 1 roadmap)

1. `utility-bill-parsers` — water bill + sewer bill extraction functions (docs/formats/water-bill.md, docs/formats/sewer-bill.md), used for cross-checking against the Owner Packet's transaction log, not as a second source of `transaction` rows (see the `report-ingestion` skill).
2. `zip-ingestion-endpoint` — upload/unzip/hash-dedupe/batch + signature-sniffer routing + review queue.
3. `transfer-log` — manual-entry endpoint for logging Wise transfers.
4. `landing-page` — the 4 original headline cards + the Accumulated Balance card + property/period filters.

Then Phase 2 (reports/charts), Phase 3 (mortgage + tax tracker), Phase 4 (polish/mobile/automation) per `docs/dev-plan.md` §10 — plus one new feature not in the original phase list: a **site-wide USD/NIS currency toggle** using the current day's live exchange rate for display (storage stays USD-only, no schema change — see `docs/dev-plan.md` §15). Scope this as its own branch once reports/UI exist (Phase 2), not bolted onto the first page that shows a dollar figure.

## Still waiting on Adi

- The real Neon `DATABASE_URL` for this project (new database within the existing instance).
- GCP project ID, if/when we get to Cloud Run deployment (Phase 4).
- Telegram bot token + chat ID, if the notification feature is wanted (optional, Phase 4).
- Mortgage details per property (Phase 3).
