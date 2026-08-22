# Owner Packet.pdf

Source: AppFolio (Overland Properties / Overland Properties-Metro Space Realty), bundled inside every monthly zip in `/Users/adikeller/Documents/assets/overland_reports/` as `Owner Packet.pdf`. Confirmed against real samples spanning Apr 2022, Aug 2023, Mar 2024, Jan 2025, May 2026.

## Detection signature

Anchor on **"Property Cash Summary"** (present on every sample, every year) — do not key on the letterhead name, which changed:

- 2022–2025 (through at least Jan 2025): `Overland Properties` / owner `Adi Keller`
- 2026 onward: `Overland Properties-Metro Space Realty` / owner `Keller Assets Ohio LLC` (an entity change, not a typo — Adi's LLC name)

## Page structure (varies by month — parse by content, not fixed page number)

1. **Page 1 — Consolidated Summary** across both properties. Header block: manager name/address/phone, owner name, "Owner Statement", statement period (`<Mon> <DD>, <YYYY> - <Mon> <DD>, <YYYY>`), "Consolidated Summary".
2. **One "Property Cash Summary" page per property** (Brunswick, then Colburn — order is consistent) — always immediately follows page 1. This section is present in **every single sample**, unchanged in field layout since 2022.
3. **"Income Statement - 12 Month" pages, one block per property** (1–2 pages each, more if a property has many active expense categories) — **absent in the 2022 sample** (2022 packet was only cash summaries + work orders, 5 pages total). First appears in the Aug 2023 sample. Once present, spans a variable number of pages depending on category count — always ends in a `NOI - Net Operating` / `Net Income` summary block. Don't hardcode a page count; detect by the `Income Statement - 12 Month` header repeating, and the `Net Income` line as the end-of-section marker.
4. **Work Order detail pages** (e.g. "Work Order # 3203-1"), one per work order that occurred that month, appended after the per-property sections — only present in months with a repair (2022 Apr had 1 work order = 2 pages; 2024 Mar had 2 work orders). These are a *fuller* record than the `work_order_*.jpeg` photo attachments in the zip (which are just supporting photos) — the in-PDF page has structured fields: `Work Order # <id>-<seq>`, `Status`, `Created On <date>`, `Estimate Requested On`, `Estimate Amount`, `Invoice #`.

## Property Cash Summary — fields (per property, per month)

Fixed label block at the top of each property's page:

```
<Property nickname/address> - <address again>
Property Cash Summary
Beginning Balance <amt>
Cash In <amt>
Cash Out -<amt>
[Owner Disbursements -<amt>]        <- conditional, see below
Ending Cash Balance <amt>
[Unpaid Bills -<amt>]               <- conditional, see below
Property Reserve -300.00            <- fixed at -300.00 in every sample checked, both properties, all years
Net Owner Funds <amt>
[Please Remit Balance Due <amt>]    <- only appears when Net Owner Funds is negative
Transactions
<date> <payee> <type> <ref> <description> <cash in> <cash out> <running balance>
...
Ending Cash Balance <amt>
Total <cash in total> <cash out total>
[Bills Due
<due date> <payee> <description> <unpaid amt>
...
Total <amt>]                        <- only present when there are unpaid bills that month
```

**Conditional fields — this is the important drift, not a fixed schema:**
- `Unpaid Bills` — appears when there's an outstanding bill(s) against the property as of statement date. When present, its magnitude matches the `Bills Due` table's total at the bottom of the page.
- `Owner Disbursements` — seen once (Colburn, Aug 2023): an **intra-portfolio transfer**, i.e. this property's surplus cash was swept to cover the other property's shortfall that month (visible in the transaction log as `Transfer to <other property address>` / `Transfer from <this property address>`). This is AppFolio netting the two properties against each other internally — not money leaving the portfolio. When this line is present, `Unpaid Bills` is typically absent (the surplus was already zeroed out via the transfer instead of being left as an unpaid-bill placeholder).
- `Please Remit Balance Due` — appears only when `Net Owner Funds` goes negative (Brunswick, Aug 2023: unpaid utility bills exceeded the cash balance that month) — this is money AppFolio says Adi owes *in*, not a payout.

**The arithmetic — confirmed across the full archive (dev-plan.md §8.4 cross-check,
implemented as `test_cash_summary_arithmetic_holds` / `test_full_archive_parses_without_crashing`
in `tests/test_parsers/test_owner_packet.py`), and initially got wrong in an earlier
draft of this note — Owner Disbursements and Unpaid Bills are NOT interchangeable:**
```
Net Owner Funds = Ending Cash Balance + Unpaid Bills (if present, already negative) + Property Reserve
```
`Owner Disbursements`, when present instead of `Unpaid Bills`, is **already netted
into `Ending Cash Balance`** (it's a real cash-out line in that month's transaction
log - the intra-portfolio transfer itself) — subtracting it again double-counts and
gives the wrong `Net Owner Funds`. Only `Unpaid Bills` gets subtracted a second time,
because unlike a disbursement, the unpaid amount hasn't actually left the cash
balance yet. When neither field is present (e.g. the 2025+ samples where the surplus
is simply left to accumulate), `Net Owner Funds = Ending Cash Balance + Property Reserve`.

## ⚠️ Critical: `Net Owner Funds` is a running balance, not a monthly delta

`Beginning Balance` of month N **equals** `Ending Cash Balance` of month N−1 for the same property — confirmed across every consecutive-month pair checked. This means each month's `Net Owner Funds` already reflects everything accumulated and not yet paid out, going all the way back — it is **not** an amount generated that month alone.

This matters directly for the app's "Accumulated Balance" headline card (docs/dev-plan.md §5.1, §13): **do not sum `net_owner_funds` across months** — that would multiply-count the same carried-forward cash. The correct read:

- Through 2024, AppFolio was creating an actual "Owner payment for MM/YYYY" bill each month for the surplus, which zeroed `Net Owner Funds` back to ~0 every month (see Beginning Balance resetting to ~$150–300 each month in the 2022–2024 samples).
- Starting Jan 2025, that monthly "owner payment" bill stopped being generated for most months — so the balance is simply **left to accumulate** (Beginning Balance jumps to $6,700+ by May 2026). This lines up exactly with what Adi described: no Wise transfer in ~8 months, so funds are piling up with Overland.
- **Correct formula:** `Accumulated Balance = Σ over properties of (Net Owner Funds from each property's most recent ingested monthly_statement) − Σ (transfer.amount_sent + transfer.fee for transfers dated after that statement's month)`. Once a transfer is reflected in a later month's statement as an actual cash-out line, stop subtracting it separately (it's already baked into that later `Net Owner Funds`).

This supersedes the original assumption in dev-plan.md §13 (which described summing net_owner_funds across all months) — flagging this as a real, confirmed correction, not a guess.

## Income Statement (P&L) page — fields

```
Income Statement - 12 Month
Overland Properties[-Metro Space Realty]
Properties:<address> - <address>
Owned By:<owner entity>
Fund Type:All
Period Range:<Mon YYYY> to <Mon YYYY>
Level of Detail:Detail View
Include Zero Balance GL Accounts:No
Account Name <Mon YYYY> <Mon YYYY> ... Total
Operating Income & Expense
Income
  RENTS
    Rent Income <amt> ... <total>
  Total RENTS ...
Total Operating Income ...
Expense
  <CATEGORY, e.g. CLEANING AND MAINTENANCE>
    <line item, e.g. General Maintenance Labor> <amt> ...
  Total <CATEGORY> ...
  ... (repeats per category: LEGAL AND OTHER PROFESSIONAL FEES, MANAGEMENT FEES, TAXES, etc.)
Total Operating Expense ...
[continuation page:]
NOI - Net Operating <amt per month> ... <total>
Income
Total Income ...
Total Expense ...
Net Income <amt per month> ... <total>
Created on <date> Page <n>
```

Category names observed so far: `RENTS` (income), `CLEANING AND MAINTENANCE`, `LEGAL AND OTHER PROFESSIONAL FEES`, `MANAGEMENT FEES`, `TAXES`. Expect more to appear over time (e.g. insurance) — map to the `expense_type` lookup taxonomy by category, not a hardcoded enum, per dev-plan.md §4.

Table columns are one per month in the period range (variable width, 1–12 months) plus a trailing `Total` column — extract via `pdfplumber`'s table extraction, not line-splitting on whitespace, since amounts and month columns aren't fixed-width across samples.

## Confirmed NOT supported yet: pre-Apr-2022 layout

Two files in the archive (`Jan 01, 2021 to Dec 31, 2021.pdf`, `Jan 01, 2022 to Jan 31,
2022.pdf`) use an older, structurally different layout: no "Property Cash Summary"
field block in the expected position, `Income`/`Expense` transaction-table columns
instead of `Cash In`/`Cash Out`, and the property name is presented as "-- <address>-"
under an "Owner Statement" / "Adi Keller Properties" header rather than the
"<address> - <address>" line used from Apr 2022 onward. `parse_owner_packet` detects
it can't find the expected fields and correctly returns nothing for these 2 files
rather than guessing — confirmed via the full-archive test. Every month from Apr 2022
onward uses the modern layout documented above. Picking up these 2 oldest files is a
future maintenance task, not blocking Phase 1.

## Extraction implementation note

Use `pdfplumber`'s `page.extract_tables()`, not `extract_text()` line-parsing, for
both the field block and the transaction log — confirmed to cleanly separate columns
even when a cell wraps across multiple lines (e.g. a payee name or a long maintenance
description). `extract_tables()` returns 2–3 tables per property page: the field
block, the transaction log, and (when present) the Bills Due table. One thing
`extract_tables()` does NOT capture: the `Please Remit Balance Due` line sits outside
the bordered table structure — don't try to extract it separately, it's mathematically
redundant with `|Net Owner Funds|` when negative anyway.

## Sample files used
- `Apr 01, 2022 to Apr 30, 2022.zip` (2022, pre-Income-Statement era, has 1 work order)
- `Aug 01, 2023 to Aug 31, 2023.zip` (2023, first sample with Income Statement pages + the Owner Disbursements / Please Remit Balance Due edge cases)
- `Mar 01, 2024 to Mar 31, 2024.zip` (2024, 2 work orders same month)
- `Jan 01, 2025 to Jan 31, 2025.zip` (2025, first sample with no monthly "owner payment" bill — balance starts accumulating)
- `May 01, 2026 to May 31, 2026.zip` (2026, new letterhead/owner entity, large accumulated balance)
