"""An inline XBRL filing -> the index and content the package writer takes
(INFO/XBRL-ROUTE.md §6).

The index has the same shape as the PDF route's (one "consolidated" section with
its notes and statements, a page layout per page), so note picking, prompts,
LINKED FIGURES, the statements page, threads and history work unchanged. Page
numbers are *document pages*: the content between two page breaks of the
XHTML, numbered 1…n, with the printed number from its footer (§8).

Instead of model-document matching (§7, Q2) a filing passes acceptance checks:
at least 5 notes, at least 3 of the 4 statements, readable figures, a balance
sheet that balances, and a known taxonomy.
"""

import time
from dataclasses import dataclass
from datetime import datetime

from ingest import links as pdf_links
from ingest import notes_index
from ingest.pdf_utils import PdfError
from ingest.xbrl import XBRL_VERSION, checks, filing as filing_mod, ixbrl, linkbase, links, narrative, notes, roles
from ingest.xbrl import statements as statements_mod

SECTION = "consolidated"
SECTION_LABEL = "Consolidated"
CODE = "C"

# The one model of the XBRL route (Q2): no layout rules, so no model document to match.
# IFRS filings (ifrs-full) are phase 6.
MODELS = {
    "us-gaap": {"id": "XBRL-US-GAAP", "short": "XBRL US GAAP", "profile": "xbrl-us-gaap",
                "reference": "Nvidia 10-K FY2026 (XBRL\\Nvidia)"},
}
FORM_LABELS = {"10-K": "US Form 10-K (US GAAP, inline XBRL)", "10-K/A": "US Form 10-K/A (US GAAP, inline XBRL)",
               "10-KT": "US Form 10-KT (US GAAP, inline XBRL)", "20-F": "Form 20-F (US GAAP, inline XBRL)",
               "40-F": "Form 40-F (US GAAP, inline XBRL)"}
MIN_NOTES = 5
MIN_STATEMENT_TYPES = 3
MIN_READABLE = 0.9
SHORT = {"profit_loss": "P&L", "balance_sheet": "BS", "cash_flow": "CF", "equity": "Equity"}


class XbrlError(PdfError):
    """The filing could not be read: shown to the user like a PDF that can't be read."""


@dataclass
class Result:
    index: dict
    content: dict
    meta: dict
    seconds: float


def _taxonomy(doc):
    prefixes = {f.name.split(":")[0] for f in doc.facts if f.numeric}
    if "us-gaap" in prefixes:
        return "us-gaap"
    if "ifrs-full" in prefixes:
        return "ifrs-full"
    return None


def _check(name, ok, detail):
    return {"name": name, "ok": bool(ok), "detail": detail}


def acceptance(taxonomy, notes_found, statements, values, balance_checks):
    types = sorted({s["type"] for s in statements})
    readable = [v for v in values if v["value"] is not None]
    failed_balance = [c for c in balance_checks if c["status"] != "ok"]
    result = [
        _check("taxonomy", taxonomy in MODELS,
               f"facts use the {taxonomy or 'no known'} taxonomy"
               + ("" if taxonomy in MODELS else " (this app reads US GAAP filings; IFRS comes later)")),
        _check("notes", len(notes_found) >= MIN_NOTES, f"{len(notes_found)} notes found (need {MIN_NOTES})"),
        _check("statements", len(types) >= MIN_STATEMENT_TYPES,
               f"{len(types)} of 4 statements found ({', '.join(SHORT.get(t, t) for t in types)})"
               f" (need {MIN_STATEMENT_TYPES})"),
        _check("figures readable", values and len(readable) / len(values) >= MIN_READABLE,
               f"{len(readable)} of {len(values)} statement figures read as numbers"),
        _check("balance sheet", balance_checks and not failed_balance,
               f"{len(balance_checks) - len(failed_balance)} of {len(balance_checks)} balance checks ok"
               if balance_checks else "no totals to compare"),
    ]
    passed = all(c["ok"] for c in result)
    return {"passed": passed, "checks": result,
            "summary": "checks passed" if passed else "; ".join(c["detail"] for c in result if not c["ok"])}


def read(path):
    """Read the filing at this folder / zip into a Result (XbrlError if it can't be used)."""
    started = time.monotonic()
    try:
        fil = filing_mod.open_filing(path)
        doc = ixbrl.parse(fil.main)
        lb = linkbase.load(fil)
    except filing_mod.FilingError as exc:
        raise XbrlError(str(exc))
    except Exception as exc:          # a damaged file: say which, not a stack trace
        raise XbrlError(f"{path.name}: the XBRL filing could not be read ({exc})")
    taxonomy = _taxonomy(doc)
    classified = roles.classify(lb)
    note_units = notes.build(doc, classified, SECTION_LABEL)
    st_list, views, lines, values, line_facts, facts = statements_mod.build_all(
        doc, lb, classified, SECTION, SECTION_LABEL, CODE)

    printed = {p.no: p.printed for p in doc.pages}
    note_pages = {p for n, _ in note_units for p in range(n["start_page"], n["end_page"] + 1)}
    statement_pages = {p["pdf_page"] for s in st_list for p in s["pages"]}
    pages_all = [n["start_page"] for n, _ in note_units] + [n["end_page"] for n, _ in note_units]
    company = doc.dei("EntityRegistrantName") or path.name
    doc_type = (doc.dei("DocumentType") or "").strip()
    period_end = facts._period_end()
    section = {"label": SECTION_LABEL, "first_page": min(pages_all) if pages_all else None,
               "last_page": max(pages_all) if pages_all else None,
               "page_count": (max(pages_all) - min(pages_all) + 1) if pages_all else 0,
               "notes": [n for n, _ in note_units], "statements": st_list}
    index = {
        "version": notes_index.INDEX_VERSION, "format": "us-10k", "format_source": "xbrl",
        "source": "xbrl", "document_type": doc_type, "taxonomy": taxonomy,
        "pdf": str(path), "pdf_name": path.name, "page_count": len(doc.pages), "company": company,
        "fiscal_year_end": period_end, "fiscal_year_focus": doc.dei("DocumentFiscalYearFocus"),
        "built_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "pages": {str(p.no): {"printed": p.printed, "top": 0.0, "bottom": 0.0, "body_top": 0.0,
                              **({"section": SECTION} if p.no in note_pages else {})} for p in doc.pages},
        "sections": {SECTION: section} if note_units or st_list else {},
    }
    unit_texts = {(SECTION, f"{CODE}{n['no']}"): text for n, text in note_units}
    pages = {}
    for p in doc.pages:
        pages[p.no] = {"printed": p.printed, "text": "\n".join(b.as_text() for b in p.blocks),
                       "text_source": "xbrl"}
    content = {"unit_texts": unit_texts, "pages": pages, "statement_views": views, "lines": lines,
               "values": values, "fiscal_month_day": [int(period_end[5:7]), int(period_end[8:10])]
               if period_end else None, "units": facts.units_text()}
    edges = links.build(index, content, lb, classified, SECTION, line_facts)
    found_checks = checks.subtotals(lines, line_facts, lb, facts)
    balance = checks.balance(lines, line_facts, values)
    carry_checks, carry_edges = checks.carries(lines, line_facts, values, facts)
    content["edges"] = edges + carry_edges
    content["checks"] = found_checks + balance + carry_checks
    content["link_summary"], content["check_summary"] = pdf_links.summaries(lines, content["edges"],
                                                                           content["checks"])
    content["narrative"] = narrative.build(doc, note_pages | statement_pages)
    verdict = acceptance(taxonomy, note_units, st_list, values, balance)
    model = MODELS.get(taxonomy, {"id": "XBRL-UNKNOWN", "short": "XBRL", "profile": "xbrl-unknown"})
    meta = {
        "source": "xbrl", "xbrl_version": XBRL_VERSION, "model": model["id"], "model_short": model["short"],
        "profile": model["profile"], "profile_version": XBRL_VERSION, "model_score": 1.0, "model_match": "xbrl",
        "model_checks": verdict, "format_label": FORM_LABELS.get(doc_type, f"{doc_type or 'Filing'} (inline XBRL)"),
        "xbrl_files": {"main": fil.main.name, "schema": fil.schema.name if fil.schema else None,
                       "pre": fil.pre.name, "cal": fil.cal.name if fil.cal else None,
                       "lab": fil.lab.name if fil.lab else None},
        "xbrl_facts": {"numeric": sum(1 for f in doc.facts if f.numeric),
                       "text": sum(1 for f in doc.facts if not f.numeric),
                       "concepts": len({f.name for f in doc.facts if f.numeric}),
                       "contexts": len(doc.contexts), "roles": len(lb.roles),
                       "statement_roles": sum(1 for r in lb.roles.values() if r.category == "Statement"),
                       "disclosure_roles": sum(1 for r in lb.roles.values() if r.category == "Disclosure")},
    }
    return Result(index=index, content=content, meta=meta, seconds=time.monotonic() - started)


def check_or_raise(result, path):
    verdict = result.meta["model_checks"]
    if not verdict["passed"]:
        raise XbrlError(f"XBRL filing could not be read: {path.name}: {verdict['summary']}")

