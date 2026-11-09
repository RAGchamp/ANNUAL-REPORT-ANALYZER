# XBRL Route — Plan (ingest SEC / ESEF filings from their inline XBRL instead of the PDF)

Status: **phases 0–4 built, 2026-11-08** (US GAAP). Phases 5 (cross-check against JPMorgan / Chubb XBRL),
6 (IFRS / 20-F / 40-F) and 7 (ESEF) are open: no filings of those companies are on this PC yet. See §15.

---

## 0. Goal and thesis

Today every report is a PDF, and a PDF has no structure: just characters at x/y positions. The ingester
needs layout rules per format to find the notes and statements. Each format is a model document
(`MODEL-DOCS\`, 9 so far), and every new layout is a new onboarding job
(`INFO\STEPS-NEEDED-FOR-ONBOARDING-NEW-ANNUAL-REPORT.html`). JPMorgan's 10-K needed 8 new switches although
a 10-K model (Chubb) already existed.

Filings to the SEC (10-K, 20-F, 40-F, since 2019–2021) and EU annual reports under ESEF are published as
**inline XBRL**. That is the same report as an XHTML file in which every statement figure is a tagged fact (concept,
period, unit, scale) and every note is one tagged text block. The structure is already in the file, so no layout
rules are needed.

**Thesis:** add a second ingestion route, **XBRL → report package**, next to **PDF → report package**. The
package stays the one standard document; the analyzer does not change. One XBRL reader replaces a layout profile
for every filer that publishes XBRL, so **new US/EU filers need no onboarding at all**. PDF profiles stay for
reports without XBRL: Indian annual reports, old and scanned reports.

```
PDF  ──► ingest\  (model match + profile rules) ──┐
                                                  ├──► report package (.rptpkg.db) ──► analyzer ──► Claude
XBRL ──► ingest\xbrl\ (no layout rules)       ────┘
```

---

## 1. What exists today (verified 2026-11-08)

- `XBRL\Nvidia\` (not in git): Nvidia's FY2026 10-K as filed on EDGAR. `nvda-20260125.htm` (inline XBRL,
  2.0 MB), its schema `.xsd`, and the linkbases `_pre.xml` (presentation), `_cal.xml` (calculation),
  `_lab.xml` (labels), `_def.xml` (definitions); exhibits as separate `.htm`.
- Probe of that filing:

| What | Count | Meaning |
|---|---|---|
| `ix:nonFraction` facts | 1,127 (317 concepts) | every figure in the statements and note tables |
| `ix:nonNumeric` facts | 178, of which 76 `…TextBlock` | notes, policies, note tables, cover data |
| contexts | 281 | period × dimensions |
| `ix:continuation` | 93 | a text block continued across the document (`continuedAt`) |
| roles (`.xsd` definitions) | 7 *Statement*, 83 *Disclosure*, 2 *Document* | statements, notes and their tables/details |
| notes = *Disclosure* roles without "(Tables)/(Details)/(Policies)" | 18 | "Income Taxes", "Debt", "Leases", "Segment Information", … |
| cover facts (`dei:`) | registrant name, document type, fiscal year/period end, CIK | company, form, periods: no guessing |

- Each note is one fact, e.g. `us-gaap:IncomeTaxDisclosureTextBlock` (`escape="true"`, `continuedAt="f-919-1"`):
  the note's full HTML, tables included.
- `lxml` is installed; **Arelle is not**. The `.htm` is XHTML, so Python's standard `xml.etree` can parse it.
- Nothing in the app reads XBRL today. `Annual-reports\` lists `*.pdf` only.

---

## 2. Why this beats one generic PDF script

| | Generic PDF script | XBRL route |
|---|---|---|
| Where notes start/end | layout guesses (headers, fonts, columns) | one tagged text block per note |
| Statement lines and figures | rebuilt from x positions; wrapped captions, `$` cells, columns | facts with concept, period, unit, scale, sign |
| Periods and units | parsed from headings ("Year ended…", "in millions") | in the context and unit of each fact |
| Subtotal checks | "is it a simple sum of the lines above?" (often *unverified*) | the calculation linkbase says exactly which lines add up |
| Statement line → note links | figure match / title match (54% for JPMorgan) | the same concept tagged in the statement and in the note's *Details* role (exact) |
| New filer | onboarding if the layout is new | nothing to do |

What XBRL does **not** give: the PDF's page numbers (the XHTML has page breaks, see §8), and anything not filed
in XBRL (Indian annual reports, filings before 2009, scanned reports).

---

## 3. Scope

**In:** 10-K, 20-F and 40-F inline XBRL filings from EDGAR (US GAAP `us-gaap:` and IFRS `ifrs-full:` taxonomies,
company extensions such as `nvda:`), and ESEF annual reports (inline XBRL, IFRS) as a later phase.

**Out (stay on the PDF route):** Indian annual reports (TYPE-1; MCA/exchange XBRL uses a different, non-inline
format: possible later, §14), old and scanned reports (TYPE-2/4/5), filings before inline XBRL, and any report
the user only has as a PDF.

---

## 4. Input: how a filing reaches the app

- A **filing folder** under `Annual-reports\` (e.g. `Annual-reports\Nvidia-10-K-2026\`) holding the
  `.htm` + `.xsd` + linkbases as downloaded from EDGAR, or a `.zip` of it. The report dropdown lists PDFs **and**
  filing folders. A folder is recognized by one main `.htm` with `ix:header` plus a `_pre.xml`.
- The app **does not download** from EDGAR by itself (decision Q1, §13). The SEC asks automated clients for a
  contact User-Agent, and the app stays local-only. The user downloads the filing (EDGAR → filing index →
  "Download all files"), or a later phase adds an explicit download button.
- A report with both a PDF and its XBRL (e.g. JPMorgan) is ingested from the **XBRL** (Q3).

---

## 5. The reader (`ingest\xbrl\`)

| Module | Does |
|---|---|
| `filing.py` | Find the main document and linkbases in a folder or zip; SHA-256 over all files (the package key) |
| `ixbrl.py` | Parse the XHTML: contexts (period, entity, dimensions), units, `ix:nonFraction` (apply `scale`, `sign`, `format` e.g. `ixt:num-dot-decimal`, `ixt:fixed-zero`, `decimals`), `ix:nonNumeric` with `continuedAt` chains joined in order, `ix:hidden` facts, `ix:exclude` |
| `linkbase.py` | Presentation tree per role (order, parent/child, preferred label roles incl. `negatedLabel`, `totalLabel`), calculation arcs with weights, labels by role, role definitions from the `.xsd` |
| `roles.py` | Classify roles: *Statement* → which of the 4 statements (by role title / root concepts: `Assets`, `NetIncomeLoss`, cash-flow and equity roots); *Disclosure* → note, policy, tables, details; parenthetical roles attached to their statement |
| `notes.py` | One unit per note role: number = its order in the filing, title = role title, text = its level-1 TextBlock as HTML → text, tables as `label \| FY2026 \| FY2025` rows (same format as today) |
| `statements.py` | Each statement from its presentation tree: line label (preferred label), indent level, facts per period column (non-dimensional contexts; the equity statement's component axis → columns); the same `view` and `lines`/`values` rows the PDF route stores |
| `checks.py` | Subtotals from the calculation linkbase (*ok* / *fail*, no *unverified*), balance (`Assets` = `LiabilitiesAndStockholdersEquity`), carries (same concept in two statements) |
| `links.py` | Statement line → note: the line's concept appears in a note's Details/Tables role (`ties_to`, high confidence). Existing title matching as a fallback |
| `narrative.py` | Everything outside the statements and notes (Items 1–15, MD&A, risk factors): sections from the "Item N." headings in the HTML; blocks from HTML elements (`<p>`, `<table>`, headings); then the existing passage cutter (`ingest\narrative\passages.py`) |

Parsing: start with stdlib `xml.etree.ElementTree` (no new dependency; the exe stays small). Use `lxml` only
if the standard parser is too slow or chokes on a real filing. **Arelle** (the reference XBRL processor) is a
development tool for checking our output (§11), not a runtime dependency.

---

## 6. The package it writes (no analyzer change)

The XBRL route writes the same `rptpkg` tables, so note picking, prompts, LINKED FIGURES, statements page,
threads and history all work unchanged:

- `meta`: `source = "xbrl"`, `format = "us-10k"` / `"20-f"` / `"esef"` (from `dei:DocumentType`), company from
  `dei:EntityRegistrantName`, periods from `dei:DocumentPeriodEndDate` / contexts, units from the facts' unit
  and scale ("USD in millions").
- `units`: notes `C1…Cn`, statements `C-PL`, `C-BS`, `C-CF`, `C-EQ` (consolidated only; 10-Ks have no standalone
  section; a 20-F parent-only schedule can become `standalone` later).
- `lines`, `values`, `edges`, `checks`: from §5.
- `pages`: one row per "page" of the XHTML (§8).
- `doc_sections`, `doc_passages`: from `narrative.py`.
- Schema: one new `meta` key (`source`) and an optional `concept` column on `lines` (shown in the quality report,
  useful for links). Schema 1.2 → 1.3.

---

## 7. Model documents and matching (changes decision MD-Q1)

Today every report must match a model document or it is blocked. The XBRL route needs no layout model. Proposal
(Q2): an XBRL filing **skips layout matching** and passes **acceptance checks** instead: ≥ 5 notes, ≥ 3 of
the 4 statements, figures readable, balance holds, a known taxonomy (`us-gaap` / `ifrs-full`). Failing them shows
an "XBRL filing could not be read" box with the reason, like the gap report. One registry entry,
`XBRL-US-GAAP` / `XBRL-IFRS`, with Nvidia as its reference document, keeps `verify` and the Model testing screen
meaningful.

The existing PDF models stay: they read the PDFs users already have. TYPE-3/6/7/8/9 simply stop being the only
way to read those companies.

---

## 8. Page numbers (changes decision "always PDF page numbers")

The XHTML has no PDF pages. It has page breaks (`page-break-before/after` styles, about 84 in Nvidia's) and printed
page numbers in its footers. Proposal (Q4): a "page" = the content between two page breaks, numbered 1…n
(**document page**), with the printed number alongside, exactly where the PDF route shows "PDF page 405 (printed
402)". Prompts say "page 63 (printed 61)". Manual page selection works on these pages. Page images: the Ingest
screen renders the HTML page instead of a PDF page image.

---

## 9. Code changes outside `ingest\xbrl\`

| File | Change |
|---|---|
| `webcommon.py` (report list) | List filing folders / zips next to PDFs, marked "XBRL" |
| `ingest\pipeline.py` | `ensure_package` picks the route by input type; `INGESTER_VERSION` covers both |
| `ingest\quality.py` | Quality report for XBRL: facts, roles, notes, statements, calc checks |
| `analyzer\context.py` | A REPORT PROFILE line "Source: the filing's inline XBRL" (only for XBRL packages, so PDF prompts stay byte-identical) |
| `ingest\routes.py`, `templates\ingest.html` | Ingest screen: XBRL filings, the HTML page view |
| `ingest\model_testing.py` | The reference XBRL filing on the Model testing screen |
| `requirements.txt` | Nothing at first (stdlib); `lxml` only if needed |

The analyzer boundary is unchanged: it never imports `ingest` and never reads the filing.

---

## 10. Phases

| Phase | Work | Done when |
|---|---|---|
| 0. Spike (½ day) | `ixbrl.py` + `linkbase.py` on Nvidia; print the 4 statements and the 18 notes as text | Statements match the filed HTML tables; Income Taxes note text complete (continuations joined) |
| 1. Statements and notes | `roles.py`, `notes.py`, `statements.py` → package; quality report | Nvidia: 18 notes, 4 statements, every figure read, balance ok |
| 2. Checks and links | `checks.py` (calc linkbase), `links.py` (Details roles) | Every subtotal *ok* or a reported *fail*; most statement lines linked to a note |
| 3. Input and app | Report list, pipeline route, Ingest screen, REPORT PROFILE line; one real Claude run (Nvidia tax question) | Analyze works end to end on Nvidia; PDF prompts byte-identical (baseline) |
| 4. Narrative | `narrative.py`: Item sections, HTML blocks, passages | "Analyze non notes" works on Nvidia (e.g. a risk-factors question) |
| 5. Cross-check against the PDF route | JPMorgan and Chubb iXBRL vs their PDF packages (same documents) | Same notes (count, titles), same statement figures; differences explained |
| 6. IFRS / 20-F / 40-F | `ifrs-full` statement roots; Infosys, BHP, Magna filings | All three ingest from XBRL |
| 7. ESEF (optional) | ESEF zip layout (`reports\*.xhtml`, taxonomy package) | One EU annual report ingests |

Rough effort: phases 0–3 about 3–4 focused sessions; 4–6 about 3 more.

---

## 11. Tests

- Golden test `tests\test_xbrl_nvidia.py`: notes (count, Income Taxes title and text start), the 4 statements,
  a figure with its period and scale (e.g. revenue FY2026, "in millions"), a calc check, a line → note link.
- Unit tests for `ixbrl.py` on small hand-written snippets: `scale`, `sign="-"`, `ixt:fixed-zero`, a continuation
  chain, `ix:exclude`, a dimensional context.
- **Cross-check with Arelle** (dev only, not in the test suite): run Arelle once on Nvidia, compare fact counts
  and values.
- Phase 5 comparison test: JPMorgan XBRL package vs TYPE-9 PDF package on the 34 notes and the balance sheet.
- `tests\test_prompt_identity.py` unchanged: PDF reports' prompts stay byte-identical.
- `tests\test_boundary.py`: the analyzer still imports no `ingest`.

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| Company extension concepts (`nvda:…`) with no standard meaning | Labels come from the filing's own label linkbase; statements come from presentation roles, not concept names |
| Equity statement is dimensional (components as columns) | Columns from the `StatementEquityComponentsAxis` members; tested on Nvidia, JPMorgan |
| Text blocks hold HTML tables with odd structure (colspans, `$` cells) | Reuse the PDF route's row format; only `<td>`/`<th>` text, colspans expanded |
| Note numbering not tagged | Order of the note roles (their `.xsd` sort codes) = note number; check it against the "Note N" in the text |
| Role classification varies by filer | Classify by the presentation tree's root concepts, role titles only as a hint; acceptance checks catch failures |
| Sign conventions (`negatedLabel`, `sign="-"`) | Unit tests; balance and calc checks catch sign errors |
| Exe size / parsing speed on 5–10 MB filings | stdlib parser first; measure; `lxml` (already installed) if needed |
| Users only have PDFs | The PDF route is untouched; XBRL is an addition |

---

## 13. Decisions (confirmed with the user 2026-11-08)

| # | Question | Decision |
|---|---|---|
| Q1 | Should the app download filings from EDGAR itself? | ~~**No.**~~ **Yes, since 2026-11-08** (user's request): the XBRL page (`/xbrl`) downloads a filing from a ticker and a SEC link into `WEB-APP\XBRL-docs\<TICKER>\` (§16). |
| Q2 | XBRL filings skip model-document matching (changes MD-Q1)? | **Yes:** acceptance checks + one `XBRL-US-GAAP` / `XBRL-IFRS` registry entry each |
| Q3 | When both the PDF and its XBRL are present, which wins? | **XBRL**; the dropdown shows one entry |
| Q4 | Page numbers for XBRL reports (changes "always PDF page numbers")? | **Document pages** between page breaks, printed number alongside |
| Q5 | Keep TYPE-3/6/7/8/9 PDF models after the XBRL route works? | **Keep them**, for users who only have the PDF |
| Q6 | Start with US GAAP 10-Ks only, IFRS later? | **US GAAP first** (phases 0–5), IFRS in phase 6 |
| Q7 | Indian XBRL (MCA / exchange filings)? | **Not now**; a separate plan later |

---

## 14. Later

- Indian XBRL: listed companies file Ind AS financial statements in XBRL with the exchanges / MCA. It is not
  inline (no HTML text), so notes would still come from the PDF. A possible hybrid: statements from XBRL, notes
  from the PDF profile.
- An "update from EDGAR" button (needs a User-Agent with contact details; user's decision).
- Cross-year comparison becomes easy with XBRL (same concepts across years), though decision Q8 says it is
  not needed today.

---

## 16. Downloading from SEC: the XBRL page (2026-11-08)

`/xbrl` (`ingest\xbrl_routes.py`, `ingest\xbrl\edgar.py`, `templates\xbrl.html`, `static\xbrl.js`; linked from the
home page and the Ingest screen). The user gives a **ticker** and **any link into the filing** (its index page, the
iXBRL viewer link `/ix?doc=…`, or one of its documents). The app reads the filing index page and saves, in
`WEB-APP\XBRL-docs\<TICKER>\`: the main document marked **iXBRL** under *Document Format Files* (10-K, 10-K/A,
20-F, 40-F …) and the *Data Files* EX-101.SCH / CAL / DEF / LAB / PRE plus the extracted XBRL instance
(`…_htm.xml`), and `filing.json` (company, form, period, link, files, time). The folders are listed with the
reports (`webcommon.list_reports`, after `Annual-reports\`; a name already used there is skipped) and can be
ingested from the page or anywhere else.

- Only `www.sec.gov` is contacted, only for files inside that filing's folder, with a pause between requests;
  User-Agent `config.SEC_USER_AGENT` (env `SEC_USER_AGENT`; SEC asks for a name and email - the default names
  the app only and is accepted today). A 403/429 says to set it.
- **SEC's CDN injects a bot check into the HTML it serves** (a `<script … defer>` in `<head>`, a script and
  `<noscript>` pixel at the end): the bare `defer` is not XML, so the filing could not be parsed. Filings can't
  contain scripts, so the downloader removes every script / noscript; HIG's `.htm` is then exactly the size
  the index lists (`as_filed` in `filing.json`). The parser also drops scripts and retries when a file saved
  from a browser does not parse.
- The folder is replaced only when "Replace" is ticked; files go to `<TICKER>.partial\` first, so a failed
  download leaves nothing behind.
- Real run, The Hartford (HIG) 10-K FY2025: 7 files, 25.9 MB, 9 s; ingested in 3 s with no onboarding:
  25 notes (pages 135–220), all statements, 6,794 facts, 24/24 checks ok, 103 of 139 lines linked (75 by concept).
  HIG prints its Items as a running header on every page ("Part I - Item 1. Business"), not as bold headings:
  `narrative._running_headers` reads those (XBRL_VERSION 2).
- Tests: `tests\test_xbrl_download.py` (SEC mocked).

## 15. What was built (2026-11-08)

Modules: `ingest\xbrl\` (`filing`, `ixbrl`, `linkbase`, `roles`, `notes`, `statements`, `checks`, `links`,
`narrative`, `build`, `pageview`); tests `tests\test_xbrl.py` (15: hand-written snippets + Nvidia golden + app flow).

Nvidia FY2026 10-K (`Annual-reports\NVIDIA-10-K-2026\`, a copy of `XBRL\Nvidia\`): read in ~1 s, 85 document
pages, 18 notes (pages 56–81; Note 13 Income Taxes = pages 72–76), income statement, comprehensive income
(`C-PL-2`), balance sheet, cash flow, equity; 124 lines, 332/332 figures readable; 28/28 checks ok (18 subtotals
from the calculation linkbase, 2 balance, 8 carries); 55 of 124 lines linked (29 by XBRL concept; the rest are
lines no note tags, e.g. cash-flow working-capital lines, which fall back to the PDF route's rules); 23 Item
sections, 62 passages.

How it differs from the plan:

| Plan | Built | Why |
|---|---|---|
| §7 one registry entry `XBRL-US-GAAP` in `registry.json` | `build.MODELS` in code, meta `model = XBRL-US-GAAP`, `profile = xbrl-us-gaap` | the registry, `verify` and matching are PDF-only (fingerprints, SHA of a MODEL-DOCS PDF); a filing entry would break them |
| §8 prompts say "page 63 (printed 61)" | extracts keep the marker "--- PDF page 63 (printed page 61) ---"; the REPORT PROFILE says these are document pages | the analyzer, passage cutter and link rules parse that marker; changing it would touch PDF prompts |
| §5 statements as filed | equity written one component after another, then the total (columns = fiscal years) | keeps one column per period in `lines` / `values`, like Chubb's PDF equity statement |
| §9 Model testing screen | not done | the screen is built around PDF page images |

Other decisions in the code: a PDF and a filing with the same name → only the filing is listed (Q3); the package
key of a folder is the SHA-256 of its `.htm/.xsd/.xml` files; a `.zip` is unpacked once into
`cache\xbrl\<stem>-<sha16>\`; the page view (`/page-image` for a filing) serves the filing's own HTML with
scripts removed and a CSP that blocks scripts; `INDEX_VERSION` 36 (schema 1.3: `lines.concept`, meta `source`);
`XBRL_VERSION` in `ingest\xbrl\__init__.py` rebuilds XBRL packages only.
