# Gap report — JP-MORGAN-2025.pdf

- Written 2026-11-07 23:58 by the model matcher (registry version 12, 8 model documents, 8 with extraction rules)
- SHA-256 e16cdad03ca84732dbe21b2595c112e975d5a3f27bce9f394828160275bfe79c

## Verdict

No model document matches this report: none of the nearest models' rules passed their acceptance checks (or two formats were equally close). The document data extraction logic needs an update for this format.

## Fingerprint compared with the nearest models

| Feature | This report | TYPE-3 USA 10-K 2025 Chubb | TYPE-8 AUSTRALIA 20-F 2025 BHP | TYPE-2 INDIA Ann rpt 1977 Reliance |
|---|---|---|---|---|
| physical.text_share | 1.0 | 1.0 | 1.0 | 1.0 |
| physical.page_shape | letter | letter | letter | letter |
| physical.pages | 410 **≠** | 460 | 363 | 33 |
| physical.pages_band | 300+ **≠** | 300+ | 300+ | <60 |
| physical.producer | other **≠** | edgar-agent | browser | distiller |
| typography.mono | 0.0 | 0.0 | 0.0 | 0.0 |
| typography.serif | 0.01 **≠** | 0.36 | 0.96 | 0.0 |
| typography.sans | 0.99 **≠** | 0.64 | 0.04 | 1.0 |
| typography.bold | 0.1 **≠** | 0.06 | 0.09 | 0.15 |
| typography.big_title_pages | 0.0 **≠** | 0.0 | 0.0 | 0.04 |
| typography.body_size | 10 **≠** | 7 | 7 | 9 |
| document.form | 10-K **≠** | 10-K | — | — |
| document.frameworks | us-gaap **≠** | ifrs, schedule-vi, us-gaap | ifrs, us-gaap | companies-act-1956 |
| document.currencies | usd **≠** | cad, eur, usd | aud, eur, usd | inr |
| document.units | millions, thousands **≠** | millions, thousands | millions | crores, lakhs |
| era.decade | 2020 **≠** | 2020 | 2020 | 1970 |
| structure.notes_header_pages | 0.0 **≠** | 22.2 | 0.3 | 0.0 |
| structure.note_headings | number-dot 5.9, note-word 24.1, section-numbered 0.2 **≠** | number-dot 11.5, note-word 5.0, section-numbered 5.0 | number-dot 5.5, number-caps 0.6, note-word 2.5, section-numbered 28.7 | number-dot 63.6 |
| structure.statement_title_pages | 13 **≠** | 9 | 7 | 2 |
| structure.numbered_statement_titles | 0 **≠** | 0 | 6 | 0 |
| structure.schedules | 3 **≠** | 25 | 1 | 18 |
| structure.item_8 | True **≠** | True | False | False |
| structure.item_18 | False **≠** | False | True | False |

## What the nearest models' rules found

- **TYPE-3 USA 10-K 2025 Chubb** — similarity 0.71; profile `us-10k-edgar`: failed
  - **failed**: notes — 0 notes found (need 5)
  - **failed**: statements — 0 of 4 statements found (need 3)
  - ok: wording — mentions Form 10-K
  - **failed**: wording — doesn't mention Item 8
- **TYPE-8 AUSTRALIA 20-F 2025 BHP** — similarity 0.48; not tried (too different)
- **TYPE-2 INDIA Ann rpt 1977 Reliance** — similarity 0.44; not tried (too different)

## Evidence pages

- **PDF p.22** (statement title): • actions by banking regulators, as well as changes in / applicable law or how applicable law is implemented / by banking regulators / • changes in the composition of JPMorganChase’s / balance sheet or developments that could increase / RWA, such as increased market risk, customer  
  fonts: Sons-Bold 12.0 bold, Sons-Bold 9.9 bold, Sons-Regular 8.0, Sons-Regular 9.9
- **PDF p.36** (financial statements / Item 8 or 18): Item 8. Financial Statements and / Supplementary Data. / The Consolidated Financial Statements, together with / the Notes thereto and the report thereon dated / February 13, 2026, of PricewaterhouseCoopers LLP, / the Firm’s independent registered public accounting  
  fonts: Sons-Bold 12.0 bold, Sons-Regular 10.0, Sons-Regular 12.0, Sons-Regular 8.0
- **PDF p.41** (financial statements / Item 8 or 18): Item 15. Exhibits, Financial Statement / Schedules. / 1 / Financial statements / The Consolidated Financial Statements, / the Notes thereto and the report of the  
  fonts: Sons-Regular 10.0, Sons-Regular 12.0, Sons-Regular 8.0
- **PDF p.57** (statement title): CONSOLIDATED BALANCE SHEETS AND CASH FLOWS ANALYSIS / Consolidated balance sheets analysis / The following is a discussion of the significant changes between Decem / 157 for a discussion of the Critical Accounting Estimates Used by the  / Sheets. / Selected Consolidated balance sheets data  
  fonts: Sons-Bold 10.0 bold, Sons-Bold 12.0 bold, Sons-Bold 8.0 bold, Sons-Regular 10.0
- **PDF p.61** (financial statements / Item 8 or 18): EXPLANATION AND RECONCILIATION OF THE FIRM’S USE OF NON-GAAP FINANCIAL / Non-GAAP financial measures / The Firm prepares its Consolidated Financial / Statements in accordance with U.S. GAAP; these / financial statements appear on pages 165–169. That / presentation, which is referred to as “reported” basis,  
  fonts: Sons-Bold 10.0 bold, Sons-Bold 8.0 bold, Sons-Regular 10.0, Sons-Regular 11.4
- **PDF p.107** (statement title): The following table summarizes short-term and long-term funding, exclu / and 2024, and average balances for the years ended December 31, 2025 a / Balance Sheets Analysis on pages 55–57 and Note 11 for additional info / Sources of funds (excluding deposits) / As of or for the year ended December 31, / Average  
  fonts: Sons-Bold 10.0 bold, Sons-Bold 8.0 bold, Sons-Regular 10.0, Sons-Regular 8.0
- **PDF p.131** (statement title): ALLOWANCE FOR CREDIT LOSSES / The Firm’s allowance for credit losses represents / management's estimate of expected credit losses over / the remaining expected life of the Firm's financial / assets measured at amortized cost and certain off- / balance sheet lending-related commitments. The  
  fonts: Sons-Bold 8.0 bold, Sons-Regular 10.0, Sons-Regular 12.0, Sons-Regular 8.0
- **PDF p.134** (statement title): INVESTMENT PORTFOLIO RISK MANAGEMENT / Investment portfolio risk is the risk associated with the / loss of principal or a reduction in expected returns on / investments arising from the investment securities / portfolio or from principal investments. The / investment securities portfolio is predominantly held  
  fonts: Sons-Bold 10.0 bold, Sons-Bold 12.0 bold, Sons-Bold 8.0 bold, Sons-Regular 10.0
- **PDF p.160** (financial statements / Item 8 or 18): ACCOUNTING AND REPORTING DEVELOPMENTS / Financial Accounting Standards Board (“FASB”) Standards Adopted since  / Standard / Summary of guidance / Effects on financial statements / Income Taxes:  
  fonts: Sons-Bold 10.0 bold, Sons-Bold 12.0 bold, Sons-Regular 10.0, Sons-Regular 12.0
- **PDF p.161** (statement title, financial statements / Item 8 or 18): FASB Standards Issued but not yet Adopted as of December 31, 2025 / Standard / Summary of guidance / Effects on financial statements / Income Statement - / Reporting Comprehensive  
  fonts: Sons-Bold 10.0 bold, Sons-Regular 8.0, Sons-Regular 9.8, Sons-RegularItalic 9.8
- **PDF p.163** (financial statements / Item 8 or 18): Management of JPMorgan Chase & Co. / (“JPMorganChase” or the “Firm”) is responsible for / establishing and maintaining adequate internal control / over financial reporting. Internal control over financial / reporting is a process designed by, or under the / supervision of, the Firm’s principal executive and  
  fonts: Sons-Bold 12.0 bold, Sons-Regular 10.0, Sons-Regular 8.0, Sons-Regular 9.8
- **PDF p.164** (statement title, financial statements / Item 8 or 18): To the Board of Directors and Shareholders of / JPMorgan Chase & Co.: / Opinions on the Financial Statements and Internal / Control over Financial Reporting / We have audited the accompanying consolidated / balance sheets of JPMorgan Chase & Co. and its  
  fonts: Sons-Bold 10.0 bold, Sons-Bold 12.0 bold, Sons-Bold 9.8 bold, Sons-BoldItalic 9.8 bold
- **PDF p.165** (financial statements / Item 8 or 18): Critical Audit Matters / The critical audit matters communicated below are / matters arising from the current period audit of the / consolidated financial statements that were / communicated or required to be communicated to the / audit committee and that (i) relate to accounts or  
  fonts: Sons-Bold 12.0 bold, Sons-BoldItalic 9.8 bold, Sons-Regular 10.0, Sons-Regular 8.0
- **PDF p.166** (financial statements / Item 8 or 18): 3 financial instruments; (ii) a high degree of auditor / judgment, subjectivity, and effort in performing / procedures and evaluating audit evidence related to / the aforementioned unobservable inputs; and (iii) the / audit effort involved the use of professionals with / specialized skill and knowledge.  
  fonts: Sons-Bold 12.0 bold, Sons-Regular 10.0, Sons-Regular 8.0
- **PDF p.176** (statement title): Note 2 – Fair value measurement / JPMorganChase carries a portion of its assets and / liabilities at fair value. These assets and liabilities are / predominantly carried at fair value on a recurring basis / (i.e., assets and liabilities that are measured and / reported at fair value on the Firm’s Consolidated  
  fonts: Sons-Bold 10.0 bold, Sons-Bold 12.0 bold, Sons-Regular 10.0, Sons-Regular 8.0
- **PDF p.196** (statement title): Additional disclosures about the fair value of / financial instruments that are not carried on the / Consolidated balance sheets at fair value / U.S. GAAP requires disclosure of the estimated fair / value of certain financial instruments, which are / included in the following table. However, this table  
  fonts: Sons-Bold 10.0 bold, Sons-Bold 12.0 bold, Sons-Bold 8.0 bold, Sons-Regular 10.0
- **PDF p.197** (statement title): The majority of the Firm’s lending-related commitments are not carried / Consolidated balance sheets. The carrying value and the estimated fair / commitments were as follows for the periods indicated. / December 31, 2025 / December 31, 2024 / Estimated fair value hierarchy  
  fonts: Sons-Bold 8.0 bold, Sons-Regular 10.0, Sons-Regular 8.0, Sons-Regular 9.5
- **PDF p.198** (statement title): Note 3 – Fair value option / The fair value option provides an option to elect fair / value for selected financial assets, financial liabilities, / unrecognized firm commitments, and written loan / commitments. / The Firm has elected to measure certain instruments  
  fonts: Sons-Bold 12.0 bold, Sons-Regular 10.0, Sons-Regular 8.0
- **PDF p.213** (statement title): Impact of derivatives on the Consolidated statements of income / The following tables provide information related to gains and losses r / accounting designation or purpose. / Fair value hedge gains and losses / The following tables present derivative instruments, by contract type, / relationships, as well as pre-tax gains/(losses) recorded on such deri  
  fonts: Sons-Bold 10.0 bold, Sons-Bold 8.0 bold, Sons-Regular 10.0, Sons-Regular 8.0
- **PDF p.230** (statement title): Note 10 – Investment securities / Investment securities consist of debt securities that / are classified as AFS or HTM. Debt securities classified / as trading assets are discussed in Note 2. / Predominantly all of the Firm’s AFS and HTM / securities are held by Treasury and CIO in connection  
  fonts: Sons-Bold 12.0 bold, Sons-Regular 10.0, Sons-Regular 8.0
- **PDF p.235** (statement title): Note 11 – Securities financing activities / JPMorganChase enters into resale, repurchase, / securities borrowed and securities loaned agreements / (collectively, “securities financing agreements”) / primarily to finance the Firm’s inventory positions, / acquire securities to cover short sales, accommodate  
  fonts: Sons-Bold 10.0 bold, Sons-Bold 12.0 bold, Sons-Regular 10.0, Sons-Regular 8.0
- **PDF p.260** (statement title): Note 13 – Allowance for credit losses / The Firm’s allowance for credit losses represents / management's estimate of expected credit losses over / the remaining expected life of the Firm's financial / assets measured at amortized cost and certain off- / balance sheet lending-related commitments. The  
  fonts: Sons-Bold 12.0 bold, Sons-Bold 9.9 bold, Sons-Regular 8.0, Sons-Regular 9.9
- **PDF p.290** (financial statements / Item 8 or 18): Note 25 – Income taxes / JPMorganChase and its eligible subsidiaries file a / consolidated U.S. federal income tax return. / JPMorganChase uses the asset and liability method to / provide for income taxes on all transactions recorded / in the Consolidated Financial Statements. This method  
  fonts: Sons-Bold 10.0 bold, Sons-Bold 12.0 bold, Sons-Bold 7.5 bold, Sons-Bold 8.0 bold
- **PDF p.291** (statement title): The following table reflects the components of income / tax expense/(benefit) included in the Consolidated / statements of income. / Income tax expense/(benefit) / Year ended December 31, / (in millions)  
  fonts: Sons-Bold 10.0 bold, Sons-Bold 8.0 bold, Sons-Regular 10.0, Sons-Regular 8.0
- **PDF p.302** (financial statements / Item 8 or 18): The Firm reflects its exposure to nonperformance risk / of the client through the recognition of margin / receivables from clients and margin payables to CCPs; / the clients’ underlying securities or derivative / contracts are not reflected in the Firm’s Consolidated / Financial Statements.  
  fonts: Sons-Bold 12.0 bold, Sons-Regular 10.0, Sons-Regular 8.0, Sons-RegularItalic 10.0

## Pages outside the notes and statements: section clues

Turn on the sources that fit in the new profile's `narrative_sections` switch (and `narrative_designed_pages` for designed pages).

- **bookmarks**: 202 in the PDF outline; 72 usable as sections, e.g. Form 10-K Cover, Form 10-K Index, Item 1. Business., Item 1A. Risk Factors.
- **contents**: no contents page found in the first 15 pages
- **form_items**: 0 bold `Item N.` headings
- **running_headers**: 4 runs of a title at the top of the pages, e.g. Selected metrics (p.69–70), Product/instrument (p.179–180), Fair value measurements using significant unobservable inputs (p.188–190)
- **headings** (last resort): 130 large bold headings, e.g. FORM 10-K, Part I, Part I

## Adding this format (MODEL-DOCS/README.md)

1. **Model document:** copy the PDF into `MODEL-DOCS\` as `TYPE-<next>-<COUNTRY>-<FORM>-<YEAR>-<Company>.pdf`
   ("Propose as a model document" puts it in `MODEL-DOCS\_candidates\` with this report).
2. **Profile:** in `WEB-APP\ingest\profiles\`, reuse a profile with different settings, `derive()` one,
   or add a new rule behind a new switch - never an `if` in another format's code path.
3. **Golden test:** notes (count, a known note's pages), statements (pages), a figure with its period;
   two or three hand-checked narrative pages in `tests\fixtures\narrative_gold\gold.json`.
4. **Register:** `python -m ingest.models register "MODEL-DOCS\TYPE-<n>-….pdf" --profile <id> --description "…"`
5. **Verify:** `python -m ingest.models verify` and `python -m pytest` (every model's baseline unchanged).
6. **Ship:** rebuild the exe.
