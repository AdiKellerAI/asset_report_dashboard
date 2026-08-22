# Water bill — City of Cleveland Division of Water

Source: `bill_*` files inside the monthly zips — sometimes a UUID-named JPEG (photographed bill, needs OCR), sometimes a normal text PDF (`bill_document_0_*.pdf`, `bill_past_*_document_0_*.pdf`). Confirmed against 4 real samples: Aug 2023 (Brunswick, past-due), Jan 2025 (Colburn), May 2026 ×2 (Colburn).

## Detection signature

`City of Cleveland Division of Water` (appears near the top of page 1, right after the barcode line). Also present: `1201 Lakeside Avenue`, `my.clevelandwater.com`.

## Page structure

- **Page 1**: account header, usage chart, meter reading table, itemized "Cleveland Water Current Charges" (labeled ❶), remittance stub begins.
- **Page 2**: remittance stub continues (barcode, mailing address) — **and, conditionally**, a "❷ Local & Other Current Charges" section when the bill has local/municipal charges that month. Confirmed absent in the Aug 2023 sample (bill had only 1 charge, no page-2 charges section) and present in both 2025/2026 samples (2 charges).

## Fields to extract

```
Customer Name: <name>              <- "KELLER ASSETS OHIO LLC" (2023) vs "KELLER ASSETS OHIO,LLC" (2025/2026, no space before comma) - normalize, don't exact-match
Account Number: <acct>
Service Address: <address>
Due Date: <Month DD, YYYY>
Account Summary as of <date>
  Previous Balance <amt>
  Payments Received <amt>            <- usually negative (a payment applied)
  Balance Forward <amt>
Your current Bill has <N> Charge(s):
  ❶Cleveland Water Charges (page 1) <amt>
  [❷Local Charges (page 2) <amt>]    <- conditional, only when N=2
Total Amount Due: <amt>

Meter Number <id> | Previous Read <date, val> | Current Read <date, val> | Usage <val> MCF

❶ Cleveland Water Current Charges
  Fixed Charge - <MM-DD-YYYY> to <MM-DD-YYYY> <amt>     <- billing period shifts every month, don't assume a fixed date range
  Water - <usage> MCF at $<rate> for first/additional <threshold> MCF <amt>   <- 0, 1, or 2 tiers depending on usage (0 usage → 0.00 water charge line, still present)
  Cleveland Water Total <amt>

[page 2, if present:]
❷ Local & Other Current Charges
  Billing Period <MM-DD-YYYY to MM-DD-YYYY>
  Waste Collection Fee - <N> month(s) at $<rate> per month <amt>
  Billing Period <MM-DD-YYYY to MM-DD-YYYY>              <- can differ slightly from the Waste Collection billing period
  Water Pollution Control Fixed Charge <amt>
  Water Pollution Control Charge - <usage> MCF at $<rate> per MCF <amt>
  Local & Other Current Charges Total <amt>
```

**Reliable anchors for the parser:** `Account Number:`, `Service Address:`, `Due Date:`, `Total Amount Due:` — all appear as clean `label: value` or `label value` pairs on their own line in every sample. The remittance-stub barcode/OCR-glyph lines (`(cid:NN)...`) are junk from pdfplumber and should be filtered out (they come from a barcode font it can't decode — ignore any line matching `(cid:\d+)`).

**Splitting Water vs. Sewer expense types:** this bill is `water_bill` only — despite including "Water Pollution Control" charges, those are still billed by Cleveland Water (not NEORSD) and should stay bundled into the single `water_bill` transaction amount = `Total Amount Due`. Don't try to split Cleveland Water Total vs. Local Charges Total into separate transactions.

## Confirmed edge case: one file with a corrupted font encoding

`bill_water_bill_2113_w_10406012026144542158_0001.pdf` (Jun 2026 zip) extracts
garbled text throughout - "Due" reads as "Oue", "of" as "ot"/"o{", etc. - a bad-PDF
font-encoding issue, not a parser bug. Confirmed isolated (no other file in the
archive exhibits this via the full-archive test in
`tests/test_parsers/test_utility_bills.py`). The parser correctly returns
`total_amount_due=None` for it (fails closed) rather than extracting a wrong
number - would need OCR or fuzzy matching to recover, out of scope for now; falls
through to the review queue in the real ingestion flow.

## Sample files used
- `Aug 01, 2023 to Aug 31, 2023.zip` → `bill_past_07_11_document_0_59.pdf` (past-due, single charge, no page-2 local charges section)
- `Jan 01, 2025 to Jan 31, 2025.zip` → `bill_document_0_10.pdf` (2 charges, Colburn)
- `May 01, 2026 to May 31, 2026.zip` → `bill_document_0_2026_05_31t142329_275.pdf` (2 charges, Colburn, higher usage tier)
