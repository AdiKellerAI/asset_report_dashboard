---
name: db-schema
description: Use when adding, changing, or reviewing a database table/column, an Alembic migration, or the seed data (properties, expense taxonomy) in this repo.
---

# Database schema (SQLAlchemy + Alembic)

Source of truth for what fields belong on which table: `docs/dev-plan.md` §4 (original
spec) and §13-14 (decisions and corrections made after building against real data) -
check there before adding/inventing a column.

## Tables (all 9, in `app/models.py`)

| Table | Purpose | Columns |
|---|---|---|
| `property` | The two rental properties | `id`, `nickname` (Brunswick/Colburn), `address`, `unit_details`, `purchase_info`, `created_at` |
| `expense_type` | Growing lookup of income/expense categories - not a hardcoded enum | `id`, `code` (e.g. `management_fee`), `label`, `is_income`, `created_at` |
| `upload_batch` | Groups files uploaded together (e.g. one zip) | `id`, `uploaded_at`, `source` (`single_file`/`multi_file`/`zip`), `file_count`, `notes` |
| `document` | Every original file ever ingested - the audit trail everything else points back to | `id`, `property_id` (nullable), `type`, `upload_date`, `original_filename`, `source_batch_id`, `storage_path`, `raw_extracted_json`, `status` (`needs_review`/`parsed`/`confirmed`), `created_at` |
| `transaction` | Every individual income/expense line item | `id`, `property_id`, `expense_type_id`, `date`, `amount`, `description`, `source_document_id`, `created_at` |
| `monthly_statement` | One row per property per month - a snapshot of AppFolio's cash summary, frozen so past numbers don't shift if parsing logic changes later | `id`, `property_id`, `month`, `gross_income`, `total_operating_expense`, `noi`, `beginning_balance`, `ending_balance`, `unpaid_bills`, `reserve`, `net_owner_funds`, `source_document_id`, `created_at` - unique on `(property_id, month)` |
| `mortgage` | Manually entered, not parsed from any document | `id`, `property_id`, `lender`, `monthly_payment`, `principal_balance`, `start_date`, `created_at` |
| `tax_report` | VirtueTax's annual filings | `id`, `year`, `provider` (default "VirtueTax"), `amount_paid` (USD), `what_it_covers`, `filed_date`, `document_id`, `created_at` |
| `transfer` | Wise transfers to Israel - portfolio-level, not tied to a property, since Overland holds combined funds | `id`, `transfer_date`, `amount_sent`, `fee`, `note`, `source_document_id`, `created_at` |

Every `transaction`, `monthly_statement`, and `tax_report` row links back to the
`document` it came from via `source_document_id` - that's the "every number is
traceable" rule (dev-plan.md §4's closing line).

## Layout

- Models: `app/models.py` (all 9 tables in one module - kept flat since the schema is
  small; don't split into a package prematurely).
- Engine/session: `app/db.py` - `Base`, `make_engine()`, `SessionLocal`. Reads
  `DATABASE_URL` from `app/config.py`.
- Migrations: `alembic/versions/` - `alembic/env.py` is wired to `app.db.Base.metadata`
  and overrides `sqlalchemy.url` from the `DATABASE_URL` env var (not from `alembic.ini`,
  which just has a dummy placeholder).
- Seed data: `app/seed.py` (`seed(session)` - idempotent, checks existing rows before
  inserting) + the `flask seed-db` CLI command in `app/__init__.py`.

## Conventions

- Integer serial primary keys, not UUIDs - this project's own choice, kept as-is;
  note `maayan_recipes` (the Postgres instance actually being reused, see the
  `postgres-instance` memory) uses UUID PKs, but that's a difference between the
  two apps' schemas, not something this project needs to match.
- snake_case columns, `created_at` with `server_default=func.now()`.
- Money columns are `Numeric(12, 2)`, never `Float`.
- `expense_type` is a **growing lookup table**, not a hardcoded enum (dev-plan.md §4) -
  new expense categories get added as new rows, not new code. `owner_payment` was
  deliberately dropped from the original spec's taxonomy (doesn't apply - see
  `developer-preferences` skill).
- `transfer` is portfolio-level (no `property_id`) - Overland holds combined funds across
  both properties, confirmed by real data (see `docs/formats/owner-packet.md`'s "Owner
  Disbursements" note on intra-portfolio transfers).
- `monthly_statement` has a unique constraint on `(property_id, month)` - one statement
  per property per month, enforced at the DB level, not just app logic.
- Every number the dashboard shows should trace back to a `document` row
  (`source_document_id`) - don't add a data-bearing table without a way to audit where
  its numbers came from.

## Verification (do all of these before considering a schema change done)

1. `alembic revision --autogenerate -m "..."` against the local test Postgres (see
   `local-dev-stack` skill) - check the generated migration file actually matches intent,
   autogenerate misses some things (e.g. check constraints, some index changes).
2. `alembic upgrade head` applies clean.
3. `docker compose exec -T db psql -U postgres -d asset_report_dashboard_test -c '\dt'` /
   `\d <table>` to confirm the real shape.
4. `alembic downgrade base` then `upgrade head` round-trips without error - down
   migrations must be real, not stubs.
5. `pytest` covers the change - round-trip a row through the ORM, and if a constraint was
   added, a test that actually violates it and confirms the DB rejects it (see
   `tests/test_models.py`'s `monthly_statement` uniqueness test for the pattern).
