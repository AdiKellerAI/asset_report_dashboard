---
name: report-ingestion
description: Use when writing or extending a document parser, working on the zip/bulk upload endpoint, or doing anything that reads an Overland/AppFolio report or utility bill and turns it into database rows. Covers detection signatures, the deterministic-parsing approach, and the review-queue rule.
---

# Report ingestion (parse → detect → extract → write)

Source of truth: `docs/dev-plan.md` §2 (why deterministic, no runtime LLM), §3 (document
types + zip structure), §6 (ingestion flow), §8 (the agentic workflow for building a new
parser). Per-document-type field maps: `docs/formats/owner-packet.md`,
`docs/formats/water-bill.md`, `docs/formats/sewer-bill.md`.

## Current implementation status (keep this updated)

As of `docs/PROJECT_STATUS.md`'s last update: format notes are done (real text extraction
confirmed against 5 years of samples), but the actual parser functions and the zip
ingestion endpoint are **not yet built** - that's the next branches in the Phase 1
roadmap. This skill describes the target design those branches implement; check
`docs/PROJECT_STATUS.md` for what's actually landed before assuming a parser exists.

## The pipeline (dev-plan.md §6)

```
upload (single file / multiple files / .zip)
  ↓
if .zip: unzip server-side, hash every extracted file's content
  ↓
drop exact-duplicate hashes (bill_*/work_order_* overlap - confirmed byte-identical
in every sample checked)
  ↓
group remaining files into one upload_batch row
  ↓
for each file: extract text (pdfplumber/pypdf; pytesseract OCR fallback for
image-only files like the UUID-named bill_*.jpeg photos)
  ↓
signature sniffer: match extracted text against known header strings
(see "Detection signatures" below) → route to the matching parser
  ↓
no match, OR parser flags low confidence (e.g. cash-summary arithmetic doesn't
add up) → document.status = 'needs_review', goes to the review queue - never
guess a number silently
  ↓
matched: parser extracts fields → write transaction/monthly_statement/tax_report
rows, linked via source_document_id back to the document row
```

**Determinism matters here**: re-running the same file must always produce the same
result. No model call in this path - if a parser can't confidently extract a field, that's
a `needs_review` document, not an LLM guess.

## Detection signatures (confirmed, see docs/formats/*.md for full field maps)

| Document type | Anchor string(s) | Don't key on |
|---|---|---|
| Owner Packet | `Property Cash Summary` | The letterhead/owner name - changed from "Overland Properties" / "Adi Keller" to "Overland Properties-Metro Space Realty" / "Keller Assets Ohio LLC" starting 2026 |
| Water bill | `City of Cleveland Division of Water` | - |
| Sewer bill | `neorsd.org` or `Northeast Ohio Regional Sewer District` | - |

## Cross-reference checks (dev-plan.md §8.4) - build these once individual parsers work

- A water bill's `Fixed Charge` billing period should roughly match the sewer bill's for
  the same property/month (confirmed identical in the May 2026 sample).
- `Ending Cash Balance − |Unpaid Bills or Owner Disbursements| − Property Reserve =
  Net Owner Funds` (confirmed exact across every sample, both properties, all years) -
  a parser producing a mismatch here is a bug, not a data anomaly; route to review.
- Cross-checking Owner Packet's per-property `Cash In` against its own Income Statement's
  `Rent Income` for the same month (both live in the same PDF from 2023 onward) is a
  cheap internal consistency check once the Income Statement pages are parsed too.

## Building a new parser (or fixing a broken one) - dev-plan.md §8's loop

1. Confirm/update the format note in `docs/formats/<type>.md` first if the layout looks
   different from what's documented - don't write extraction code against a layout you
   haven't actually looked at in the real file.
2. Write the extraction function, test against **every** sample of that type in
   `/Users/adikeller/Documents/assets/overland_reports/`, not just one - the layout has
   already drifted across years (see the format notes for confirmed examples: the 2026
   letterhead change, Income Statement pages absent before 2023, conditional
   `Unpaid Bills` vs `Owner Disbursements` fields).
3. Keep the samples used as a permanent regression fixture set (dev-plan.md §8 step 6) -
   a future parser change gets checked against everything that used to work.
