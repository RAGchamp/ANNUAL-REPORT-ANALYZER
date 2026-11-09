"""The notes (INFO/XBRL-ROUTE.md §5): one unit per note role, its text the blocks
its text-block fact covers (continuations joined), tables as `label | FY2026 | FY2025`
rows - the same text format as the PDF route's notes.

The note number is the "Note 13" printed in the note's heading when there is one,
else the next number after the notes before it (role order = filing order).
"""

import re

from ingest.xbrl.roles import base_title

NOTE_NO_RE = re.compile(r"^\s*note\s+(\d{1,3})\b", re.I)


def page_label(no, printed):
    """The page marker the analyzer and the passage cutter read ("--- PDF page N …"):
    for an XBRL filing N is the document page (INFO/XBRL-ROUTE.md §8)."""
    return f"PDF page {no}" + (f" (printed page {printed})" if printed else "")


def blocks_text(blocks, printed):
    """Blocks as text with a page marker at every page change."""
    parts, page = [], None
    for b in blocks:
        if b.page != page:
            parts.append(("\n" if parts else "") + f"--- {page_label(b.page, printed.get(b.page))} ---")
            page = b.page
        parts.append(b.as_text())
    return "\n".join(parts)


def _printed_range(pages, printed):
    first, last = printed.get(pages[0]), printed.get(pages[-1])
    if not first:
        return None
    return first if first == last or not last else f"{first}-{last}"


def build(doc, classified, section_label):
    """[(note dict for the index, {"text", "pages"})] in filing order."""
    printed = {p.no: p.printed for p in doc.pages}
    out, last_no = [], 0
    for role, concept in classified.notes:
        fact = next((f for f in doc.facts if f.name == concept and not f.numeric), None)
        if fact is None:
            continue
        blocks = doc.owned_blocks(fact.id)
        if not blocks:
            continue
        title = base_title(role.title)
        match = next((NOTE_NO_RE.match(b.text) for b in blocks[:2] if b.kind != "table" and NOTE_NO_RE.match(b.text)),
                     None)
        no = int(match.group(1)) if match and int(match.group(1)) > last_no else last_no + 1
        last_no = no
        pages = sorted({b.page for b in blocks})
        subheadings = [b.text for b in blocks[1:] if b.kind == "heading" and len(b.text) <= 120][:15]
        note = {"no": no, "title": title, "start_page": pages[0], "start_y": 0.0, "end_page": pages[-1],
                "end_y": None, "subheadings": subheadings, "printed_pages": _printed_range(pages, printed),
                "concept": concept, "role": role.uri}
        header = f"=== Note {no} — {title} ({section_label}) ==="
        text = header + "\n" + blocks_text(blocks, printed)
        out.append((note, {"text": text, "pages": [{"pdf_page": p, "printed": printed.get(p)} for p in pages]}))
    return out
