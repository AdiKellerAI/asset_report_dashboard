# Sewer bill — Northeast Ohio Regional Sewer District (NEORSD)

Source: `bill_*.pdf` files inside monthly zips. Confirmed against 2 real samples: Jan 2025 and May 2026 (both Colburn).

## Detection signature

`neorsd.org` and/or `Northeast Ohio Regional Sewer District` (both appear on page 1).

## Page structure

Single page, always. No conditional sections observed (unlike the water bill's page-2 local charges).

## Fields to extract

```
ACCOUNT: <acct>
CUSTOMER NAME: <name>              <- "KELLER ASSETS OHIO,LLC" - same entity name as the water bill, same comma-spacing quirk
SERVICE ADDRESS: <address>
BILLING DATE: <MM/DD/YYYY>
DUE DATE: <MM/DD/YYYY>

<a row of 6 numbers with no extractable labels - see note below>

Fixed Charge - <MM-DD-YYYY> to <MM-DD-YYYY> $<amt>
Sewage Charge - <usage> MCF at $<rate> per MCF $<amt>
Stormwater Charge $<rate> per month for <N> month(s) $<amt>
<billing period for the stormwater charge, on its own line>

Meter Number <id> | Previous Read <date, val> | Current Read <date, val> | Usage <val> MCF

TOTAL AMOUNT DUE $<amt>
```

**The unlabeled 6-number row** (e.g. `$337.23 -$337.23 $0.00 $0.00 $201.30 $201.30`) is almost certainly `Previous Balance / Payments / Adjustments / Balance Forward / Current Charges / Total Due`, matching the pattern from the water bill's labeled "Account Summary" block — but `pdfplumber`'s `extract_text()` doesn't preserve the column headers for this compact table (they're likely rendered as small-print labels pdfplumber's text extraction drops or as a table needing `extract_tables()`/`extract_words()` with position data instead of plain text). **Don't parse this row by position** — it's fragile. Use the itemized breakdown instead:

**Reliable anchors:** `ACCOUNT:`, `DUE DATE:`, `Fixed Charge`, `Sewage Charge`, `Stormwater Charge`, `TOTAL AMOUNT DUE` — all clean `label ... $amount` lines. `sewer_bill` transaction amount = `TOTAL AMOUNT DUE`.

**Cross-check opportunity (dev-plan.md §8.4):** the sewer bill's `Fixed Charge` billing period should roughly match the water bill's `Fixed Charge` billing period for the same property/month (both samples confirm this: e.g. May 2026 water bill fixed charge `03-28-2026 to 04-28-2026`, sewer bill fixed charge for the same statement `03-28-2026 to 04-28-2026` — identical). A mismatch here is a good signal to route to the review queue.

## Sample files used
- `Jan 01, 2025 to Jan 31, 2025.zip` → `bill_document_0_86.pdf` (Colburn)
- `May 01, 2026 to May 31, 2026.zip` → `bill_document_0_2026_05_25t140618_321.pdf` (Colburn)

No Brunswick sewer bill sample was found in the 5 years sampled — worth confirming during the actual parser-writing branch whether Brunswick has ever had one archived, or whether its sewer service is billed differently/bundled elsewhere.
