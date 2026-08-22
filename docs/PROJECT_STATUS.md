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

## Real data is now loaded (2026-08-22)

Ran the full archive (54 top-level files) through `process_upload` into the live Neon
database. Results: 149 documents after dedup (57 duplicates skipped), 104
`monthly_statement` rows (52 months × 2 properties), 518 transactions. Breakdown:
- 52 Owner Packets parsed, 2 flagged (the known pre-Apr-2022 layout)
- 13 water bills + 14 sewer bills parsed, 1 water bill flagged (known garbled font)
- 67 "unknown", flagged for review — expected: other `bill_*` types not yet parsed
  (property tax, insurance, gas, invoices, lease renewals) plus photographed
  bill/work-order JPEGs (need OCR, not built)
- DB size: 8.3 MB (well within Neon's 500MB free tier — original files stay on local
  disk, only structured rows go to Postgres)

**Two things this surfaced, not yet fixed:**
1. **`other_expense` category is suspiciously large** ($116,517 across 151
   transactions, almost as big as total rent income). Likely cause: intra-portfolio
   transfers (money moved between Brunswick/Colburn internally, e.g. "Transfer to
   11301 Brunswick Ave") and security-deposit bookkeeping entries ("Auto transfer of
   funds from Operating Cash to Security Deposit Cash") are being categorized as
   `other_expense` when they're not real property expenses at all. Needs a parser
   fix (`app/parsers/owner_packet.py`'s `categorize_transaction`, or a filter in
   `app/ingestion.py`'s `_write_transactions`) to exclude/separate these.
2. **Transfer timeline needs reconciling with Adi.** Adi said transfers to Israel
   stopped ~8 months ago (~Jan 2026). The real loaded data shows both properties'
   `net_owner_funds` still getting disbursed back to $0 through **March 2026**, and
   only starts accumulating continuously from **April 2026** onward (~4 months ago,
   not 8) — query used: `SELECT month, beginning_balance, ending_balance,
   net_owner_funds FROM monthly_statement ms JOIN property p ON p.id=ms.property_id
   WHERE p.nickname=... ORDER BY month`. Asked Adi to confirm which is right before
   this becomes load-bearing for the `transfer` table / Accumulated Balance card.

## Not yet done (rest of Phase 1 roadmap)

1. `transfer-log` — manual-entry endpoint for logging Wise transfers.
2. `landing-page` — the 4 original headline cards + the Accumulated Balance card + property/period filters.

Then Phase 2 (reports/charts), Phase 3 (mortgage + tax tracker), Phase 4 (polish/mobile/automation) per `docs/dev-plan.md` §10 — plus one new feature not in the original phase list: a **site-wide USD/NIS currency toggle** using the current day's live exchange rate for display (storage stays USD-only, no schema change — see `docs/dev-plan.md` §15). Scope this as its own branch once reports/UI exist (Phase 2), not bolted onto the first page that shows a dollar figure.

## Still waiting on Adi

- GCP project ID, if/when we get to Cloud Run deployment (Phase 4).
- Telegram bot token + chat ID, if the notification feature is wanted (optional, Phase 4).
- Mortgage details per property (Phase 3).
