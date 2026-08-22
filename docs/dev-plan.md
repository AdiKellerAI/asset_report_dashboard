# Asset Report Dashboard — Development Plan

**Owner:** Adi (Keller Assets Ohio, LLC)
**Assets:** 2 rental properties in Ohio (managed remotely from Israel)
**Property manager:** Overland Properties — Metro Space Realty (reports via AppFolio)
**Accountant:** VirtueTax (annual tax filings)
**Repo:** [github.com/AdiKellerAI/asset_report_dashboard](https://github.com/AdiKellerAI/asset_report_dashboard), cloned locally at `/Users/adikeller/git/asset_report_dashboard/` — this is where Claude Code should do all its work for this project

This document is the spec for Claude Code to build the app. It captures the requirements, the data sources, the report design, and a phased build plan.

---

## 0. Start here (instructions for Claude Code)

Read this entire file before writing any code. This plan lives alongside (or should be copied into, e.g. as `docs/dev-plan.md`) the project repo at `/Users/adikeller/git/asset_report_dashboard/` — do all work there, not in a new location. Then:

1. **Inspect the local resources first, before designing anything:**
   - `/Users/adikeller/Documents/assets/overland_reports/` — the full local archive of monthly report zips. Unzip a handful spanning different years (layouts have drifted over time — e.g. `Apr_01__2022_to_Apr_30__2022.zip` vs `May_01__2026_to_May_31__2026.zip` already show differences) and confirm your understanding of the structure in section 3.1 against what's actually there.
   - `/Users/adikeller/git/photography` — Adi's existing project. Read how it connects to and manages Postgres (connection setup, migrations if any, env var naming) and **match that pattern** in this new project rather than inventing a new one. Do not reuse this repo's UI, business logic, or structure — only its Postgres connection approach.
2. **Follow section 8 (Agentic development workflow)** for how to go from "sample files" to "working parsers" — do the inventory pass, write the per-type format notes, then build and test parsers against the real local archive, not just one or two examples.
3. **Follow section 9 (Git & testing workflow) for every step**, starting from the very first branch — a feature branch per step, tests added alongside the code that needs them, tests run before push (not on every save), and Adi's approval before anything gets pushed/merged.
4. **Build in the phase order in section 10.** Don't skip ahead to charts/UI before Phase 1's ingestion + schema is solid — everything downstream depends on the data being correctly and consistently extracted.
5. **Ask Adi directly** (don't guess) when you hit anything in section 11 (access/secrets) or section 12 (open decisions) that hasn't been answered yet.

---

## 1. Goal

A single-user web app, usable equally well from phone and laptop, that turns messy monthly PDFs/statements into a **simple, always-current picture** of:

- What each property earned and cost, this month / this year / all-time
- What's left for Adi personally after property expenses **and** mortgage
- A searchable history of every income/expense event, forever, with a per-expense-type drill-down
- Tax-prep tracking (what VirtueTax was paid, what each report covers)

The current AppFolio owner statements are hard to read at a glance — the app's #1 job is to make "how much did I actually make this month, combined" and "what exactly did I spend money on" answerable in one look.

---

## 2. Ingestion sources, and the AI-service boundary

**AppFolio (owner portal):** No automated login. AppFolio owner logins require SMS 2FA — a human has to receive and enter the one-time code. That can't be scripted reliably or safely, and there's no official AppFolio API for individual owners. **Manual export + upload is the ingestion method.**

**Gmail / email inbox access:** Not used for MVP — a full-inbox grant is more exposure than this needs. Manual upload (including forwarding an email as a PDF/screenshot) covers it. A narrower forwarding-address option is a possible later phase, not now.

**NanoClaw:** not used for this project, per your call — no autonomous background agent is planned, so there's nothing for it to secure.

**The important architecture decision from this round: no LLM/AI API calls at runtime.** Claude (via Claude Code, agentically) is used **only during development** to study your sample reports and write deterministic, rule-based parsers — regular Python code using PDF text/table extraction (e.g. `pdfplumber`/`pypdf`) plus pattern matching, not a live model call. Once the app is running, uploading a new statement runs it through that code, not through an API. This means:
- No ongoing API cost or latency per upload
- No risk of an LLM misreading a number differently between two runs of the same file
- Parsers are inspectable, testable, and debuggable like normal code

The trade-off: a brand-new document layout Overland/AppFolio has never sent before won't be understood automatically — it'll fall into a manual-entry flow, and (during development, or in an occasional maintenance session) Claude Code updates the parser to handle the new layout. This is a deliberate trade: robustness and zero runtime AI dependency over "the model just figures out anything."

---

## 3. Document types the app must recognize

Based on the samples reviewed:

| Type | Source | What it contains | Frequency |
|---|---|---|---|
| Owner Cash Summary + Transactions | AppFolio (Overland) | Beginning/ending balance, cash in (rent), cash out (mgmt fee), unpaid bills, reserve, net owner funds | Monthly per property |
| Owner Statement / Income & Expense (P&L) | AppFolio (Overland) | Rents, cleaning/maintenance, legal/professional fees, management fees, property tax, NOI | Monthly per property |
| Water/Sewer bill | Northeast Ohio Regional Sewer District | Usage, fixed charge, sewage charge, stormwater charge, total due | Monthly per property |
| Water bill | City of Cleveland Division of Water | Water charges + local charges (waste collection, water pollution control) | Monthly per property |
| Lease agreement | Overland/Metro Space Realty | Rent amount, term, renewal terms, tenant responsibilities | Once per lease, re-referenced |
| Annual tax report | VirtueTax | Filing details, fee paid to VirtueTax, what the filing covers | Yearly |
| Misc. emails from Overland staff | Manually forwarded/pasted PDF or screenshot | One-off notices: repairs, tenant changes, notices to owner | Irregular |
| Consolidated Owner Packet | AppFolio (Overland), inside each monthly zip | Multi-page PDF combining the consolidated (both-properties) cash summary *and* each property's own cash summary + transaction list — appears to be the canonical monthly document, superseding the need to separately source the two AppFolio types above | Monthly, one per zip |
| Work order / repair photos | AppFolio (Overland), inside each monthly zip | Photos tied to a maintenance/repair job — supporting evidence for a `maintenance_repair` transaction, not itself a source of new numbers (see 3.1 on de-duplication) | Irregular, bundled with the zip for the month the work happened |

### 3.1 Zip file structure (confirmed from the two sample zips provided)

Each monthly zip (e.g. `Apr_01__2022_to_Apr_30__2022.zip`, `May_01__2026_to_May_31__2026.zip`) contains:

- **The zip's own filename encodes the statement period** (`<Mon>_<DD>__<YYYY>_to_<Mon>_<DD>__<YYYY>.zip`) — parse this directly for the batch's date range; don't re-derive it from file contents.
- **`Owner Packet.pdf`** — always present, the master document (see table above). Confirmed structure: page 1 = consolidated 2-property summary, then one section per property with its own cash summary + transaction table.
- **`bill_*` files** — one per bill/utility document for that month, filename either a UUID (`bill_<uuid>.jpeg`, a photographed paper bill — OCR required) or a descriptive timestamp (`bill_document_0_2026_05_25t140618_321.pdf`, a normal text PDF).
- **`work_order_<id>_<uuid>.jpeg`** — confirmed to be **byte-identical** to a `bill_<uuid>.jpeg` sharing the same UUID in the same zip (AppFolio attaches the same photo to both a work-order record and its linked bill). **The ingestion parser must hash file contents on unzip and treat matching hashes as one underlying document, not two** — otherwise repair costs get double-counted and the same photo shows up twice in the UI.
- Not every zip will have `work_order_*` files (only present when a repair happened that month) — the April 2022 zip has 5 pairs, the May 2026 zip has none, just two `bill_document_*.pdf` utility bills.

Document **type detection is rule-based, not model-based**: each source has a fixed, recognizable signature in its extracted text (e.g. "Northeast Ohio Regional Sewer District" header, "City of Cleveland Division of Water" header, "Property Cash Summary" table title, "Overland Properties-Metro Space Realty" letterhead, "VirtueTax" branding). The parser layer sniffs for these signatures first, then routes to the matching field-extraction function. Anything that doesn't match a known signature goes to a manual-review queue instead of being guessed.

---

## 4. Data model (PostgreSQL)

You already run Postgres — reuse it (new schema/database within it, or a new database on the same instance; decide when you share the existing project's connection setup).

Core tables:

- **property** — id, nickname (e.g. "Brunswick Ave", "Colburn Ave"), address, unit details, purchase/loan info
- **transaction** — property_id, date, type, amount, description, source_document_id. Expense `type` is a growing taxonomy stored as a lookup table (`expense_type`), not a hardcoded enum — new categories get added as new expense kinds show up. Starting set based on what you've mentioned:
  - `rent_income` (income, not an expense, kept here for completeness)
  - `management_fee` — Overland's recurring monthly management fee
  - `tenant_placement_fee` — Overland's fee for finding a new tenant/leasing a vacancy
  - `maintenance_repair` — repairs, general maintenance labor
  - `property_tax` — county/city property tax
  - `annual_state_fee` — Ohio LLC/registration fees, rental registration, and similar yearly government fees
  - `legal_professional_fee` — legal/other professional fees
  - `water_bill`, `sewer_bill` — utility charges (split since they're billed separately)
  - `insurance` — landlord/liability insurance, if applicable
  - `tax_prep_fee` — VirtueTax's own fee (also mirrored in `tax_report` below)
  - `other_expense` — catch-all, reviewed periodically for whether it deserves its own category
  - `owner_payment` — the net payout that hits your bank
- **monthly_statement** — property_id, month, gross_income, total_operating_expense, NOI, beginning_balance, ending_balance, unpaid_bills, reserve, net_owner_funds (the AppFolio summary, stored as a snapshot so historical reports don't shift if categorization logic changes later)
- **mortgage** — property_id, lender, monthly_payment, principal_balance (optional), start_date — entered manually by Adi, not from a document
- **tax_report** — year, provider ("VirtueTax"), amount_paid, what_it_covers (free text/notes), filed_date, document_id
- **document** — id, property_id (nullable), type, upload_date, original_filename, source_batch_id (see zip ingestion below), storage_path, raw_extracted_json, status (`parsed`, `needs_review`, `confirmed`)
- **upload_batch** — id, uploaded_at, source (`single_file`, `multi_file`, `zip`), file_count, notes — groups files that came in together, so a bulk import stays traceable as one event

Every number the dashboard shows should be traceable back to the `document` row it came from — critical for trusting an automated extraction, especially one running with no human-in-the-loop model call to catch obvious errors.

---

## 5. Reports & dashboard (the "make it simple" part)

### 5.1 Landing page
Top-level filter bar: **Property** (All / Brunswick Ave / Colburn Ave) × **Period** (This Month / This Year / Custom month / Custom year / All-time).

Four headline cards, in this order, because this is the actual question Adi asks each month:

1. **Gross Rent Collected**
2. **Total Property Expenses** (mgmt fee + maintenance + taxes + utilities + legal)
3. **Net Operating Income (NOI)** = 1 − 2
4. **Net to Adi** = NOI − Mortgage Payment − any owner draws/reserves held back

A simple combined trend chart (last 12 months) showing Gross → NOI → Net to Adi as three lines, per property and combined.

### 5.2 Per-property deep dive page
- The same numbers as a literal **waterfall chart**: Gross Rent → (− Mgmt Fee) → (− Maintenance) → (− Property Tax) → (− Other) → NOI → (− Mortgage) → Net to Adi.
- Monthly table, one row per month, columns = the categories above.
- Reserve & unpaid bills status (from the AppFolio cash summary) so nothing owed is missed.

### 5.3 History / all transactions page
- Full searchable/filterable transaction log across both properties, all time.
- Filter by category, property, date range; export to CSV.

### 5.4 Expenses page (dedicated tab)

The page for "what exactly did I spend money on, and on what" — separate from the summary waterfall, which only shows category totals, not individual line items and timing.

- **Filter bar:** Property (All / one) × Expense type (all categories from the taxonomy above) × Year range.
- **Monthly expense grid:** rows = expense type, columns = months, cells = amount that month (blank if none) — scan a whole year per category at a glance, spot unusual months immediately.
- **Year-over-year comparison:** for a selected expense type, a bar chart of yearly totals side by side, plus % change vs. the previous year.
- **"Last occurred" list:** one row per expense type showing the date/amount of its most recent occurrence and how long ago (e.g. "Property tax — last paid Jan 2026, $1,675.01, 8 months ago").
- **Line-item log:** every individual expense, sortable/filterable, each linked back to its source document.

### 5.5 Tax tracker page
- One row per year: VirtueTax fee paid, filing date, what it covered, linked source document.
- Running total of VirtueTax fees paid across years.

### 5.6 Mortgage settings page
- Manually enter/update mortgage per property. Feeds "Net to Adi" everywhere else.

---

## 6. Ingestion flow (upload + zip + bulk)

1. Adi uploads **one file, several files at once, or a `.zip`** (e.g. the entire `overland_reports` folder zipped) via drag-and-drop.
2. If a `.zip` is uploaded, the backend unzips it server-side first (the zip's own filename gives the batch's statement period, per 3.1), computes a content hash for each extracted file, drops exact-duplicate hashes (the confirmed `bill_*`/`work_order_*` overlap), and treats the remaining files as one `upload_batch`.
3. Each file is text-extracted (PDF text layer / OCR fallback for image-only PDFs or photos like the two JPEGs you sent), then run through the **signature sniffer** (section 3) to detect its document type — no file needs to be manually labeled first, though Adi can override the detected type.
4. The matching deterministic parser extracts fields into the schema (`transaction`, `monthly_statement`, `tax_report`, etc.).
5. Anything that fails to match a known signature, or that a parser flags as low-confidence (e.g. a total that doesn't add up), goes to a **review queue** — a simple screen listing "N documents need your attention," each shown next to its extracted-so-far data for a quick manual fix.
6. On confirm, rows are written to Postgres and the original document is archived (linked, not deleted) for the audit trail.
7. Optional: a Telegram message summarizing the batch just processed ("Added: 14 documents from zip upload — 2 need review").

Because this whole path is deterministic parsing rather than a model call, **re-running the same batch of files always produces the same result** — useful when a parser gets improved later and you want to reprocess old files without them silently changing.

---

## 7. Tech stack

- **Backend:** Python (Flask, per the earlier decision for this project)
- **Database:** **PostgreSQL** (your existing instance) — Claude Code reads `/Users/adikeller/git/photography` directly to match its existing connection pattern rather than inventing a new one (see section 0 and section 11)
- **PDF/parsing:** `pdfplumber` or `pypdf` for text/table extraction, `pytesseract`/similar OCR only as a fallback for image-based uploads (like the two annotated JPEGs), `zipfile` (stdlib) for zip ingestion
- **Frontend:** Server-rendered responsive pages (mobile-first CSS, e.g. simple flexbox/grid breakpoints — no heavy JS framework needed for a single-user app) + Chart.js for the waterfall/trend/comparison charts. A lightweight [PWA manifest](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps) (so it can be "added to home screen" on your phone and opens full-screen like an app) is a cheap addition worth including.
- **Responsive design requirement:** every page — landing, per-property, expenses, history, tax, mortgage — needs a layout that reflows for a phone-width screen (stacked cards, swipeable/scrollable tables, tap-sized filter controls) as well as a laptop-width screen (side-by-side cards, full tables, hover states). Build mobile-first, verify laptop layout second.
- **Hosting:** Google Cloud Run (matches earlier decision) — HTTPS by default, scales to zero when idle (cheap for a single user), reachable from any browser on phone or laptop with no native app needed. Postgres stays wherever it already is (Cloud SQL, or wherever your existing project points it); Cloud Run connects to it over its existing connection method.
- **Notifications:** Telegram bot (keep — already decided)
- **Auth:** Password/basic-auth gate on the whole app (financial data — don't leave it open); if a phone "add to home screen" is used, a longer-lived session/remember-me avoids retyping a password on mobile constantly
- **No runtime AI dependency:** the Anthropic API is a **development-time tool only** (used through Claude Code to build/refine the parsers) — nothing in the running app calls an external LLM

---

## 8. Agentic development workflow (how Claude Code should build this)

This is the process for the build itself, not something that runs after launch:

1. **Inventory pass:** point Claude Code at `/Users/adikeller/Documents/assets/overland_reports/` (a folder of monthly zips, per section 3.1), have it unzip a representative spread across years, list every distinct document layout it finds (by source + report type), and confirm the list matches section 3 above — flag anything new. Specifically verify: does `Owner Packet.pdf`'s internal structure stay consistent across years, or has AppFolio's template changed (the two samples already span 2022 and 2026)? Does the `bill_*`/`work_order_*` byte-identical duplication pattern hold across all zips, or only some?
2. **Per-type "report format" notes:** for each document type, Claude Code writes a short reference doc (a project-local `docs/formats/<type>.md`, not a memory file) describing: the header/signature text used for detection, the exact fields to extract and where they sit on the page, and 1-2 sample files to test against. This is the artifact that makes the parsers maintainable later — six months from now, "why did this parser break" is answerable by reading these notes instead of re-deriving the layout from scratch.
3. **Write the parser, test against the real folder:** for each type, write the extraction function and run it against every sample of that type in your local folder, not just one — Overland's layout has already drifted slightly between months in your samples (e.g. the sewer bill's "Fixed Charge" date range shifts monthly), so the parser needs to handle the parts that vary vs. the parts that are fixed structure.
4. **Cross-referencing / consistency checks:** once individual parsers work, add checks that catch mismatches across documents rather than trusting each one in isolation — e.g. the AppFolio cash summary's "Cash In" for a month should equal the P&L statement's "Rent Income" for the same property/month; a water bill's billing period should roughly match the sewer bill's billing period for the same address; the AppFolio "Ending Cash Balance" minus "Unpaid Bills" minus "Property Reserve" should equal "Net Owner Funds" (this arithmetic is already visible in your sample images). Failed checks route to the review queue with a note on what didn't match, rather than silently taking one source's number.
5. **Batch/zip test:** once individual parsers pass, test the full ingestion flow against the whole `overland_reports` zip at once, confirming correct type detection and routing across a large, mixed batch — this is the actual day-one use case (bulk-importing your entire history), so it should be tested as a batch, not just file-by-file.
6. **Regression set:** keep the sample files (or copies) as a permanent test fixture set so future parser changes can be checked against everything that used to work, not just the new format that prompted the change.

---

## 9. Git & testing workflow

This applies for the whole build, across every phase:

- **One branch per feature/step.** Don't build directly on `main`. Each item in the phase lists below (section 10) — or any sub-step big enough to be its own unit of work, e.g. "sewer bill parser," "expenses page grid" — gets its own branch (`git checkout -b <descriptive-name>`).
- **Write/append unit tests as part of the same branch**, not as a separate cleanup pass later. Every new feature or parser adds its own tests in the same commit(s) as the feature — a parser isn't "done" until its test (using the regression fixture set from section 8, step 6) is committed alongside it.
- **Tests run before push, not on every save.** Wire this as a pre-push git hook (or a `make test` / `npm test`-equivalent step Claude Code runs manually right before pushing) — not a slow watch-mode loop running on every file change during active development. The point of "before push" is a gate: nothing broken reaches the shared branch/remote, but iterating locally stays fast.
- **Test → Adi approves → push**, in that order. Once a branch's tests pass locally, show Adi what changed (a short summary of the feature + confirmation the tests pass) and get a explicit go-ahead before pushing/merging — don't push automatically just because tests are green. This mirrors the "confirm before commit" rule already in section 6 for financial data — the same caution applies to shipping code changes.
- Merge into `main` only after that approval; keep `main` always in a working, deployable state.

---

## 10. Build phases

**Phase 1 — Core capture (MVP)**
- Postgres schema (property, transaction, monthly_statement, document, upload_batch)
- Parsers for the two AppFolio statement types + both utility bill formats (built via the agentic workflow above, tested against your local folder)
- Bulk/zip upload endpoint + review queue for anything unrecognized
- Landing page with the 4 headline cards + period/property filters

**Phase 2 — Reports**
- Waterfall chart + per-property deep dive page
- 12-month trend chart
- Transaction history page with filters + CSV export
- Expenses tab: monthly-by-category grid, year-over-year comparison chart, "last occurred" per expense type

**Phase 3 — Mortgage & tax**
- Mortgage settings page, wired into "Net to Adi"
- VirtueTax report tracking page + lease-agreement parser

**Phase 4 — Polish, mobile, automation**
- Responsive pass on every page (phone-width verification), PWA manifest for home-screen install
- Telegram summary on new upload / monthly digest
- Cross-reference anomaly flags surfaced in the UI (not just the review queue)
- Revisit narrower email-forwarding ingestion *only if* manual/zip upload proves too much friction after a few months

Each bullet above (and each parser under Phase 1) is a candidate branch under the workflow in section 9 — don't batch several of them into one branch/commit just because they're in the same phase.

---

## 11. What I'll need from you (access & secrets)

None of this should be pasted into a chat — hand these to Claude Code directly via `.env`/secret manager when you sit down to build:

1. **Postgres connection details** — host, port, database name, username, password (or a full connection string). Claude Code can read `/Users/adikeller/git/photography` directly (local filesystem access) to see how that project authenticates to Postgres and match the pattern — no need to re-share those files, just confirm whether the new app should point at the *same* database/instance or a separate one.
2. **GCP project ID** (and confirm you want Cloud Run — if you'd rather host elsewhere, say so and this section changes).
3. **Telegram bot token + chat ID**, if you want to keep the notification feature (optional — skip if you don't need it).
4. Nothing else is required to start — no AppFolio credentials (not used), no Anthropic API key needed at runtime (development-time only, and that's handled through your own Claude Code session, not a key you hand to the running app).

---

## 12. Open decisions for Adi before Claude Code starts building

1. Property nicknames to use in the app (e.g. "Brunswick" / "Colburn")?
2. Do you want the app private to you only, or ever shared read-only with someone (e.g. accountant)?
3. Mortgage details for each property (lender, monthly payment, start date)?
4. Should "Net to Adi" also subtract the property reserve AppFolio holds back, or only unpaid bills + mortgage?
5. Confirm hosting choice (Cloud Run, per section 7) and where Postgres will live relative to it (same project/region as your existing Postgres instance?).

---

## 13. Decisions made (2026-08-22 kickoff)

Resolved directly with Adi during Phase 1 kickoff — supersedes section 12 where noted:

1. **Postgres:** same Neon instance as the `photography` project, new database/schema within it (not a separate instance).
2. **Property nicknames:** **Brunswick** / **Colburn** (no "Ave").
3. **Access model:** private to Adi only — single password gate, no accountant sharing.
4. **Net to Adi:** proceeding with NOI − unpaid bills − mortgage (reserve not subtracted) as the default, pending confirmation once real numbers are in front of us.
5. **Money-flow correction (new, not in the original doc):** Adi has no personal US bank account — Overland/AppFolio holds his net owner funds directly, and he moves money to Israel irregularly via Wise (~$30 fee/transfer; none sent in ~8 months as of Aug 2026 due to a Wise account closure under new non-US-citizen regulations). Consequences:
   - The `owner_payment` expense type above ("net payout that hits your bank") doesn't apply and is dropped from the taxonomy.
   - A new **`transfer`** table is added (portfolio-level, not per-property): `transfer_date, amount_sent, fee, note, source_document_id (nullable)` — logged manually, like `mortgage`.
   - The landing page (section 5.1) gets a **5th headline card**: **Accumulated Balance** — funds still sitting with Overland, not yet transferred to Israel. First-pass formula: `SUM(monthly_statement.net_owner_funds) − SUM(transfer.amount_sent + transfer.fee)`, to be validated once real Owner Packet text extraction confirms what "net owner funds" represents month-to-month.
6. **ORM:** SQLAlchemy + Alembic (versioned migrations), not a push-based sync — chosen since financial-data schema changes should be auditable.
7. **Dev workflow addition:** whenever a branch touches anything visible (route, page, chart), run the Flask dev server on localhost and actually view it in a browser before considering that branch done — not just green tests.

---

## 14. Format-notes findings (2026-08-22, Branch 3) — corrects §13.5

Real text extraction (via `pdfplumber`) across Owner Packet samples spanning Apr 2022 → May 2026 (see `docs/formats/owner-packet.md` for full detail) turned up a correction to the Accumulated Balance formula agreed in §13.5:

**`monthly_statement.net_owner_funds` is a running balance, not a monthly delta.** Each month's `Beginning Balance` equals the prior month's `Ending Cash Balance` — confirmed across every consecutive pair checked. Through 2024, AppFolio zeroed this out monthly via an actual "Owner payment" bill; from Jan 2025 onward that stopped happening for most months, so the balance is simply left to accumulate (this is exactly why Adi has ~8 months of undisbursed funds sitting with Overland).

**Consequence:** Accumulated Balance must NOT sum `net_owner_funds` across months (that would multiply-count carried-forward cash). Corrected formula:

```
Accumulated Balance = Σ over properties of (net_owner_funds from each property's MOST RECENT monthly_statement)
                       − Σ (transfer.amount_sent + transfer.fee for transfers dated after that statement's month)
```

Once a transfer is reflected in a later ingested month's statement (as an actual cash-out line), stop subtracting it separately — it's already baked into that month's `net_owner_funds`.

See `docs/formats/owner-packet.md`, `docs/formats/water-bill.md`, `docs/formats/sewer-bill.md` for full per-document-type field maps, detection signatures, and confirmed layout drift (e.g. the 2026 letterhead/owner-entity change to "Overland Properties-Metro Space Realty" / "Keller Assets Ohio LLC", and the Income Statement (P&L) pages only existing from 2023 onward, absent in 2022).
