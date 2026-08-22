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
| `utility-bill-parsers` | `app/parsers/water_bill.py`, `app/parsers/sewer_bill.py` - tested against every `bill_*.pdf` in the archive. Found the `bill_*` prefix also covers property tax, insurance, gas bills, invoices, and lease renewals (not yet parsed - see `report-ingestion` skill) and one file with a corrupted PDF font encoding (fails closed, doesn't crash) | Merged to `main` |
| `zip-ingestion-endpoint` | `app/ingestion.py` + `POST /upload` - unzip/hash-dedupe (within-batch and across history via `document.content_hash`)/signature-route/write. Tested as one bulk upload of the entire real archive. Also: the real Neon Postgres project is now live - schema migrated, properties + expense types seeded, verified via a direct read-only check | Merged to `main` |

## Key decisions locked in (see `docs/dev-plan.md` §13–14 for full detail)

- Postgres: a **dedicated Neon serverless project** (not shared with `maayan_recipes` or `photography` — both were considered and dropped, see the `postgres-instance` memory). **Live as of 2026-08-22** — Adi created the project, ran `alembic upgrade head` and `flask seed-db` against it directly; verified schema (all 10 tables) and seed data (Brunswick/Colburn + 12 expense types) are correctly in place. `DATABASE_URL` lives in `.env` (gitignored). **Neon free tier is 500MB — be deliberate about what goes in it**: original uploaded files are archived to local disk (`instance/documents/`), never to Postgres; only structured rows go to the DB, and `document.content_hash` prevents duplicate ingestion.
- Property nicknames: **Brunswick**, **Colburn**.
- Access: private to Adi only.
- ORM: SQLAlchemy + Alembic (versioned migrations).
- Money flow: Overland/AppFolio holds funds directly (no personal US bank account) — Adi periodically moves money to Israel via Wise (~$30 fee/transfer). A `transfer` table logs these. The `owner_payment` expense type from the original spec was dropped since it doesn't apply.
- **Accumulated Balance formula corrected** after real data inspection: `net_owner_funds` is a running balance (rolls forward month to month), not a monthly delta — summing it across months would be wrong. Corrected formula in `docs/dev-plan.md` §14.
- Local dev environment quirk: Homebrew's Python 3.12 needs `DYLD_LIBRARY_PATH="/opt/homebrew/opt/expat/lib"` set (already in `~/.zshrc`) to work around a libexpat ABI mismatch against this Mac's very new macOS build — see the `local-dev-stack` skill.
- Standing rule: whenever a branch touches anything visible, run the Flask dev server and actually view it on localhost before calling the branch done.

## Not yet done (rest of Phase 1 roadmap)

1. `transfer-log` — manual-entry endpoint for logging Wise transfers.
2. `landing-page` — the 4 original headline cards + the Accumulated Balance card + property/period filters.
3. The actual bulk-import of the real archive into the live Neon database hasn't happened yet — the pipeline is proven against it in tests (a throwaway DB), but no real historical data has been loaded into the production database yet.

Then Phase 2 (reports/charts), Phase 3 (mortgage + tax tracker), Phase 4 (polish/mobile/automation) per `docs/dev-plan.md` §10 — plus one new feature not in the original phase list: a **site-wide USD/NIS currency toggle** using the current day's live exchange rate for display (storage stays USD-only, no schema change — see `docs/dev-plan.md` §15). Scope this as its own branch once reports/UI exist (Phase 2), not bolted onto the first page that shows a dollar figure.

## Still waiting on Adi

- GCP project ID, if/when we get to Cloud Run deployment (Phase 4).
- Telegram bot token + chat ID, if the notification feature is wanted (optional, Phase 4).
- Mortgage details per property (Phase 3).
