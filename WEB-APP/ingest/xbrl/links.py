"""Statement line -> note (INFO/XBRL-ROUTE.md §5).

A note's Tables and Details roles tag the figures of its tables and text with the
same concepts as the statements. A statement line whose concept is tagged in a
note's roles is linked to that note ("ties_to", method "xbrl concept"): exact, no
figure or title guessing. A concept used by one or two notes gives a high-confidence
link, three notes medium; a concept used by more (net income, total assets) is too
general to say which note explains the line.

Lines with no such link fall back to the PDF route's rules (ingest/links.py): a
note cited in the label ("Commitments and contingencies - see Note 12"), the same
figure printed in a note, a title match.
"""

from ingest import links as pdf_links
from rptpkg.model import note_unit_id

MAX_NOTES = 3


def _note_concepts(lb, classified, notes_index, section_key):
    """{concept: [(unit id, role title)]} over each note's own and sub roles."""
    by_role = {n["role"]: note_unit_id(section_key, n) for n in notes_index}
    out = {}
    for role, _ in classified.notes:
        uid = by_role.get(role.uri)
        if uid is None:
            continue
        for sub in [role] + classified.details.get(role.uri, []):
            for concept in sub.concepts():
                hits = out.setdefault(concept, [])
                if all(u != uid for u, _ in hits):
                    hits.append((uid, sub.title))
    return out


def build(index, content, lb, classified, section_key, line_facts):
    lines, values = content["lines"], content["values"]
    notes_index = index["sections"][section_key]["notes"]
    concepts = _note_concepts(lb, classified, notes_index, section_key)
    edges = []
    linked = set()
    for line in lines:
        info = line_facts.get(line["id"])
        hits = concepts.get(line["concept"], []) if info else []
        if not hits or len(hits) > MAX_NOTES:
            continue
        confidence = "high" if len(hits) <= 2 else "medium"
        for uid, title in hits:
            edges.append({"src": line["id"], "dst": uid, "kind": "ties_to", "method": "xbrl concept",
                          "confidence": confidence,
                          "evidence": f"{line['concept']} is tagged in the note's role '{title}'"})
        linked.add(line["id"])
    # the PDF route's rules for the rest; a note cited in a label always counts
    fallback = pdf_links.build_links(index, content["unit_texts"], lines, values)
    have = {(e["src"], e["dst"]) for e in edges}
    for e in fallback:
        if (e["src"], e["dst"]) in have:
            continue
        if e["kind"] == "references" or e["src"] not in linked:
            edges.append(e)
            have.add((e["src"], e["dst"]))
    return edges
