"""Everything outside the statements and notes (INFO/XBRL-ROUTE.md §5): Items 1-16
of a 10-K (business, risk factors, MD&A …) as report sections, the document pages
as blocks, and passages for questions.

Sections come from the "Part I" / "Item 1A." headings in the HTML (bold headings,
not the contents table), or, when a filing has none, from a running header at the top of each page
("Part I - Item 1. Business", The Hartford); pages before the first one are "Front matter". The
blocks are the ones ixbrl.py read (heading, paragraph, table), in the same form
the PDF route's narrative reader stores, so the passage cutter
(ingest/narrative/passages.py) and everything after it work unchanged.
"""

import re
import time
from collections import Counter

from ingest.narrative import kinds, passages, render

ITEM_RE = re.compile(r"^item\s+(\d{1,2}[A-C]?)\.?\s+(.+)$", re.I)
RUNNING_RE = re.compile(r"^part\s+([IVX]{1,4})\s*[-–—:,]\s*item\s+(\d{1,2}[A-C]?)\.?\s+(.+)$", re.I)
PART_RE = re.compile(r"^part\s+([IVX]{1,4})\b\.?\s*(.*)$", re.I)


def _slug(title):
    return "N-" + re.sub(r"[^A-Z0-9]+", "-", title.upper()).strip("-")[:40]


def block_dict(b):
    if b.kind == "table":
        return {"kind": "table", "head": [], "rows": b.rows, "bbox": [0, 0, 0, 0]}
    if b.kind == "heading":
        return {"kind": "heading", "text": b.text, "level": 1 if b.size >= 11 else 2, "bbox": [0, 0, 0, 0]}
    return {"kind": "paragraph", "text": b.text, "bbox": [0, 0, 0, 0]}


def _headings(doc, covered):
    """[(page, level, title)] of bold "Part I" / "Item 1A." headings, in order."""
    out = []
    for b in doc.blocks:
        if b.kind != "heading" or b.page in covered or b.owners:
            continue
        if ITEM_RE.match(b.text):
            out.append((b.page, 2, b.text))
        elif PART_RE.match(b.text) and len(b.text) <= 40:
            out.append((b.page, 1, b.text))
    return out


def _running_headers(doc, covered):
    """[(page, level, title)] from a running header "Part I - Item 1. Business" printed at the top of
    every page (The Hartford): a section starts on the first page that carries its header."""
    out, seen_parts, seen_items = [], set(), set()
    for page in doc.pages:
        if page.no in covered:
            continue
        first = next((b for b in page.blocks if b.kind != "table"), None)
        match = RUNNING_RE.match(first.text) if first and len(first.text) <= 160 else None
        if not match:
            continue
        part, item = f"Part {match.group(1).upper()}", f"Item {match.group(2)}. {match.group(3).strip()}"
        if part.lower() not in seen_parts:
            seen_parts.add(part.lower())
            out.append((page.no, 1, part))
        if item.lower() not in seen_items:
            seen_items.add(item.lower())
            out.append((page.no, 2, item))
    return out


def _entries(doc, covered):
    """The section starts: bold Item headings, else the running headers."""
    found = _headings(doc, covered)
    if found:
        return found, "item_heading"
    return _running_headers(doc, covered), "running_header"


def build(doc, covered):
    """{"sections", "pages", "passages", "warnings", "stats"} like ingest.narrative.build."""
    started = time.monotonic()
    page_count = len(doc.pages)
    printed = {p.no: p.printed for p in doc.pages}
    todo = [p.no for p in doc.pages if p.no not in covered]
    entries, source = _entries(doc, covered)
    sections, used = [], Counter()
    warnings = []

    def add(title, start, end, level, parent, source):
        sid = _slug(title)
        used[sid] += 1
        if used[sid] > 1:
            sid = f"{sid}-{used[sid]}"
        sections.append({"id": sid, "parent_id": parent, "seq": len(sections), "title": title,
                         "kind": kinds.kind_of(title), "level": level, "start_page": start,
                         "end_page": max(end, start), "printed": printed.get(start), "source": source,
                         "confirmed_by": []})
        return sid

    if not entries:
        warnings.append("no Part / Item headings found: the narrative pages are one section")
        add("Report", 1, page_count, 1, None, "fallback")
    else:
        if entries[0][0] > 1:
            add("Front matter", 1, entries[0][0] - 1, 1, None, "fallback")
        part_id = None
        for i, (page, level, title) in enumerate(entries):
            later = [e for e in entries[i + 1:] if e[1] <= level] if level == 1 else entries[i + 1:i + 2]
            end = (later[0][0] - 1) if later else page_count
            if level == 1:
                part_id = add(title, page, end, 1, None, source)
            else:
                add(title, page, end, 2 if part_id else 1, part_id, source)

    page_info = {}
    blocks_by_page = {}
    for page in doc.pages:
        if page.no in covered:
            continue
        blocks = [block_dict(b) for b in page.blocks]
        leaf = None
        for s in sections:
            if s["start_page"] <= page.no <= s["end_page"] and (leaf is None or s["level"] >= leaf["level"]):
                leaf = s
        tables = sum(len(b.as_text()) for b in page.blocks if b.kind == "table")
        chars = sum(len(b.as_text()) for b in page.blocks) or 1
        kind = "table" if tables / chars >= 0.5 else "prose"
        page_info[page.no] = {"section_id": leaf["id"] if leaf else None, "layout_kind": kind, "blocks": blocks,
                              "header": page.header, "footer": page.footer, "fallback": False}
        blocks_by_page[page.no] = blocks

    has_children = {s["parent_id"] for s in sections}
    for s in sections:
        s["text"] = None if s["id"] in has_children else render.section_text(s, blocks_by_page, printed, covered)
    passage_list = passages.build(sections, page_info, printed)
    block_kinds = Counter(b["kind"] for info in page_info.values() for b in info["blocks"])
    stats = {
        "pages": len(todo), "blocks": sum(len(i["blocks"]) for i in page_info.values()),
        "layout_kinds": dict(Counter(i["layout_kind"] for i in page_info.values())),
        "block_kinds": dict(block_kinds), "fallback_pages": [],
        "sources": {src: sum(1 for s in sections if s["source"] == src) for src in {s["source"] for s in sections}},
        "confirmed": 0, "contents_page": None,
        "passages": passages.stats(passage_list),
        "seconds": round(time.monotonic() - started, 1),
    }
    return {"sections": sections, "pages": page_info, "passages": passage_list, "warnings": warnings,
            "stats": stats}
