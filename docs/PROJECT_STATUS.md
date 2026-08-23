# Project Status

Living summary of what this project is and how far it's gotten. Update this at the end of every branch/phase — don't let it go stale. The full spec is `docs/dev-plan.md`; this doc is the "where are we right now" companion to it.

## What this is

A single-user Flask + PostgreSQL app that turns Adi's monthly AppFolio/Overland property-management statements and utility bills (2 Ohio rental properties: Brunswick, Colburn) into a clear dashboard of income, expenses, and what's actually accumulated with the property manager. Parsing is deterministic (rule-based Python, no runtime LLM calls) — see `docs/dev-plan.md` §2.

## Current phase

**Phase 1 — Core capture (MVP)**, per `docs/dev-plan.md` §10, is functionally complete (see "Not yet done" below) - several Phase 2/3/4 items (Trends page, the `/manage` page's Mortgage/Tax/Transfer forms, the USD/NIS currency toggle which grew into full Hebrew/RTL i18n) have already been pulled forward at Adi's request.

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
| `fix-transfer-categorization` | Added `expense_type.is_operating` (migration `a6f966c5a581`) + 3 new categories (`internal_transfer`, `security_deposit_transfer`, `owner_distribution`), gated `monthly_statement`'s NOI fields on it, fixed a few real expenses (make-ready, lease/renewal fees) that were falling through to `other_expense` for lack of a keyword match. Added `flask recategorize-transactions` (no PDF re-parse needed) and ran it against production - corrected all 518 already-loaded transactions. See "Real data is now loaded" below for before/after numbers | Merged to `main` |
| `landing-page` | `app/reports.py` (period/property aggregation over `monthly_statement`) + `app/routes/dashboard.py` (`GET /`) + `app/templates/dashboard.html` - the 5 headline cards (Gross Rent Collected, Total Property Expenses, NOI, Net to Adi, Accumulated Balance) with Property × Period filters (This Month/This Year/Custom Month/Custom Year/All Time). Verified against real production-shaped numbers via curl + a manual dev-server check | Merged to `main` |
| `trends-page` | New requirement from Adi (not in the original dev-plan.md §5.1 spec, which only planned a fixed 3-line trend chart on the landing page): a dedicated `GET /trends` page graphing *any* monthly_statement figure or expense-category monthly total over time, Property-filtered, defaulting to Gross Rent/NOI/Net to Adi. `app/reports.py`'s `trend_series()` (one point per month - no cross-month aggregation, so the unpaid_bills snapshot caveat from `dashboard_summary` doesn't apply here) + Chart.js (CDN) line chart in `app/templates/trends.html`. Added `app/templates/base.html` (shared nav) and refactored `dashboard.html` to extend it | Merged to `main` |
| `dark-elegant-redesign` | Full visual redesign per Adi's request ("total change of the look and feel... dark, elegant, gentle visual effect... latest high-end UI"), refined over several follow-up rounds of his feedback: (1) dark theme rewrite - Manrope font, glass-panel cards, gradient wordmark, gold-accented Accumulated Balance card, Trends chart re-themed with the dataviz skill's validated dark categorical palette; (2) landing page now shows a Gross Rent Collected/NOI/Net to Adi 5-month income line chart, "This Month" defaults to the latest actual report month (`latest_reported_month()`) instead of `date.today()` (which had no data yet), and all money renders as "1,234.56 $" (comma thousands separator, dollar suffix) via a new `money` Jinja filter; (3) landing page redesigned again - dropped the Property filter entirely in favor of a single Brunswick/Colburn/Total comparison table (`dashboard_breakdown()`) plus a 3-line (per-property + Total) income chart, and the Trends page's series checkboxes were fixed (a too-broad `.filter-bar label` rule was stacking every checkbox above its own label - narrowed to `.filter-bar > label`) and reorganized into an aligned grid with "By Category" collapsed behind a native `<details>` disclosure to cut the visual clutter; (4) both charts now force `beginAtZero` on the y-axis (a non-zero baseline was making 5 months of near-flat real rent look like a steep climb); the Trends page got a Range picker (Last 6mo/1yr/2yr/3yr/5yr/All Time, `trend_series()`'s new `months_limit`) defaulting to 1 year instead of always showing full history; "By Category"'s box was restyled to match "Summary"'s exactly (same border/padding/label treatment, chevron aside); the landing page's Period filter-bar now shrinks to fit its own controls instead of stretching full-width; and a site-wide USD/NIS currency toggle button (`app/fx.py`, cached once/day, static fallback if the lookup fails) went into the header - every `money`-filtered value is a `<span data-usd=...>` and both charts read `window.formatMoney()` so the whole page (tables + both charts) flips together, no reload. 80 tests pass; verified via real-browser screenshots at desktop and the narrowest width headless Chrome can reliably render (500px); (5) **dashboard load-time fix** - Adi reported "page is not loading" against the real Neon DB; traced to `dashboard_breakdown()`/`recent_income_trend()` each calling `dashboard_summary()`/`trend_series()` 3x (once per property + once for the total), and each of those independently re-querying properties/mortgages/`_accumulated_balance` (itself a per-property N+1 query) - roughly 30 remote round trips for one page load against Neon (each ~150-300ms over the network, unlike the local Docker Postgres used for iterating), not a data-volume problem. Refactored both to fetch properties/statements/mortgages once and pass them into every `dashboard_summary`/`trend_series` call (both gained optional `properties`/`statements`/`accumulated_balance`/`monthly_mortgage_total` params, defaulting to their old self-querying behavior so every existing caller/test is unaffected), and rewrote `_accumulated_balance` from a per-property loop to one GROUP BY query. Dashboard load dropped from ~7s to ~2.1s against production; verified the real numbers still match exactly (spot-checked against a direct DB query) before and after. (6) verified the suspiciously-flat rent numbers directly against the source Owner Packet PDFs (not just Postgres) at Adi's request - confirmed genuine: Brunswick's tenant pays exactly $1,460.00/month in one payment every month, Colburn's tenant pays exactly $1,500.00/month too, sometimes split across 2 installments (e.g. July was $1,000 + $500) - both fixed leases, not a parsing bug; (7) the landing page's 5-month chart was changed from Gross Rent to Net Operating Income per Adi's request (`recent_income_trend` renamed `recent_noi_trend`); (8) the currency toggle got its own switch design (a sliding gold thumb between $/₪, distinct from the nav's segmented-pill look) plus a visible exchange-rate note ("1 $ = 3.70 ₪") shown only while NIS is active; and (9) the Period filter-bar and its controls were shrunk further (padding/min-height roughly halved) and the period-label date (e.g. "July 2026") was made much more prominent (0.85rem muted -> 1.4rem bold ink) per Adi's "too small/too big" feedback on both. 80 tests pass (function rename only, no behavior change to migrate). | Pending Adi's approval to push/merge |
| `dark-elegant-redesign` (cont.) | Three bigger asks in one round: (1) landing page's NOI chart now shows **6 months** (was 5); (2) a new **`/manage` page** (`app/routes/manage.py`) pulling several Phase 3 items forward at Adi's request - upload new report zips/files (reuses `process_upload`), a Mortgage form per property (upserts the existing `mortgage` table - the Phase 3 settings page from dev-plan.md §5.6, built early), a Yearly Tax Payment form (`tax_report` table, §5.5), and a Transfer-to-Israel form (the previously-deferred `transfer-log` item - `<input type=month>` since Adi only tracks these to month/year precision, mapped to day=1 of that month); all three tables already existed in the schema, so this was routes/templates/forms, no migration. Feedback is a redirect + `?msg=`/`level=` query param (no Flask session/secret-key needed). (3) **Full Hebrew + RTL site-wide i18n** - the header's currency toggle now flips language too (one `lang` cookie drives both, since Adi wants them as one unit); Adi chose full RTL over "translated text, same layout" when asked. Architecture: a `lang`/`he` cookie set by a real redirect (`app/routes/language.py`, `GET /set-language/<lang>`) - not a client-side flip, since an RTL layout mirror needs a fresh server render - read once per request into `g.lang`/`g.dir` (`before_request` in `app/__init__.py`), exposed to every template via a context processor and a new `t` Jinja filter (`app/i18n.py`'s `TRANSLATIONS` dict, keyed by the English source string itself - gettext-style - falling back to the original text for anything not yet translated, so partial coverage never breaks). The `money` filter now renders directly in NIS server-side when `g.lang == "he"` (dropped the earlier client-side `.money`/`data-usd`/`moneyCharts` JS entirely - no longer needed once the toggle became a real page reload). Setting `dir="rtl"` on `<html>` mirrors nearly everything for free (flexbox/grid/table column order all auto-reverse under RTL, native form controls too) - the only manual RTL CSS needed was the currency-toggle thumb's slide direction and the select dropdown arrow's side; charts deliberately stay `dir="ltr"` internally (numeric axes read LTR even in RTL apps, by convention) while their legends/tooltips are translated. Property nicknames and user-typed free text (notes, "what it covers") are deliberately never translated. Verified end-to-end via real HTTP requests with the `lang` cookie (not just the Jinja layer) after a stale-dev-server hot-reload artifact briefly made it look broken - a clean restart fixed it, not a code bug. 95 tests pass (15 new: `test_i18n.py`, `test_manage_route.py`, plus dashboard-route coverage for both language modes and the `/set-language` redirect). | Pending Adi's approval to push/merge |

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

**Two things this surfaced - both now resolved (2026-08-22):**
1. **`other_expense` was inflated** ($116,517/151 transactions, almost as big as
   total rent income) — fixed on the `fix-transfer-categorization` branch and
   corrected in production. It was a mix of causes, not just the one originally
   suspected:
   - Intra-portfolio transfers (Brunswick↔Colburn, e.g. "Transfer to 11301
     Brunswick Ave"): 34 txns, $28,977
   - Security-deposit sweeps/refunds ("Auto transfer of funds from Operating Cash
     to Security Deposit Cash", clearing-account move-out refunds): 6 txns, $3,549
   - **"Owner Distribution - Owner payment for MM/YYYY" / "Owner Contribution"**:
     64 txns, $71,091 — bigger than the other two combined, and not anticipated in
     the original brief. Adi confirmed (2026-08-22) these *are* the Wise-to-Israel
     transfer mechanism ("all income arrives to Overland Properties and passed to
     me with transaction by Wise") — not a separate personal-bank-account payout,
     so the "no personal US bank account, `owner_payment` doesn't apply" decision
     (dev-plan.md §13.5) needs a mental update: distributions do leave Overland,
     they just leave *as* the Wise transfer, recorded in AppFolio's ledger as
     "Owner Distribution."
   - ~47 remaining txns (~$12,900) were real expenses missing a keyword match
     (e.g. "Rent Ready - Make ready", "Commissions/Placement Fees - Lease Fee",
     "Lease renewal Fee") - now correctly land in `maintenance_repair` /
     `tenant_placement_fee`.
   `other_expense` is now $1,699.88 across 41 transactions - a true catch-all.
   Fix: new `expense_type.is_operating` flag (migration `a6f966c5a581`), three new
   categories (`internal_transfer`, `security_deposit_transfer`,
   `owner_distribution`) excluded from `monthly_statement`'s
   `gross_income`/`total_operating_expense`/`noi`, plus the missing keywords.
   `flask recategorize-transactions` corrected the already-loaded data in place
   (no PDF re-parse - the transaction descriptions were already in Postgres).
2. **Transfer timeline, resolved.** The earlier "~8 months vs ~4 months"
   discrepancy was based on the wrong signal — `net_owner_funds` resetting to $0
   turns out to be an unrelated arithmetic effect (Ending Cash Balance − Unpaid
   Bills − Property Reserve, dev-plan.md §14), not tied to when money actually
   left the portfolio. The real signal is the `owner_distribution` transactions
   from finding #1 above (since Adi confirmed those *are* the Wise transfers): the
   **last one for both properties is 2026-02-19** — none since. That lines up
   with Adi's original "~8 months ago" recollection much better than the "April
   2026" this doc previously flagged. Still worth a final confirmation from Adi
   against his own Wise records before treating Feb 19, 2026 as the authoritative
   cutoff for backfilling the `transfer` table.

## Not yet done (rest of Phase 1 roadmap)

**Phase 1 is now functionally complete** - `transfer-log` (originally deferred 2026-08-22)
landed as part of the `/manage` page (2026-08-23), so every original Phase 1 bullet is
done. `trends-page` and `/manage`'s Mortgage/Tax forms are Phase 2/3 items pulled forward
early at Adi's request - the rest of Phase 2 (waterfall + per-property deep dive,
transaction history page, expenses tab) and Phase 3 (VirtueTax filing tracker page beyond
the basic form already in `/manage`, lease-agreement parser) are still ahead, per
dev-plan.md sec 10. The site-wide USD/NIS currency toggle (dev-plan.md §15) also landed
early, and grew into full Hebrew/RTL i18n at Adi's request - see the `dark-elegant-redesign`
branch entry above.

Then Phase 4 (polish/mobile/automation) per `docs/dev-plan.md` §10.

## Still waiting on Adi

- GCP project ID, if/when we get to Cloud Run deployment (Phase 4).
- Telegram bot token + chat ID, if the notification feature is wanted (optional, Phase 4).
- Mortgage details per property (Phase 3).
