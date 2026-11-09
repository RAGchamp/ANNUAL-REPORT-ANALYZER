"""The primary statements from their presentation trees (INFO/XBRL-ROUTE.md §5).

Each statement role's tree gives the lines in order, their labels (the preferred
label: `totalLabel`, `negatedLabel`, `periodStartLabel` …) and their depth; the
facts give the figures. Columns are the statement's periods: the fiscal years
(durations of about a year) for the income, comprehensive income and cash flow
statements, the year-end dates (instants) for the balance sheet.

The equity statement is dimensional: its components (common stock, paid-in
capital, retained earnings …) are members of the equity components axis. It is
written one component after another, each with its balances and movements per
fiscal year, then the total (the facts without a member) - the layout the PDF
route gives Chubb's equity statement, so lines keep one column per period.

Figures are kept as printed in the filing (in millions, with the filing's
sign for the line's label: a `negatedLabel` line prints its value negated).
"""

from collections import Counter, defaultdict
from datetime import date, timedelta

from ingest.xbrl import linkbase
from ingest.xbrl.roles import is_structure, local_name

LABELS = {"profit_loss": "Income Statement", "comprehensive": "Statement of Comprehensive Income",
          "balance_sheet": "Balance Sheet", "cash_flow": "Cash Flow Statement",
          "equity": "Statement of Changes in Equity"}
INDEX_TYPE = {"comprehensive": "profit_loss"}       # a second income statement: unit C-PL-2
ORDER = ("profit_loss", "comprehensive", "balance_sheet", "cash_flow", "equity")
SCALE_WORDS = {3: "thousands", 6: "millions", 9: "billions"}
CURRENCY_NAMES = {"USD": "U.S. dollars", "EUR": "euros", "GBP": "pounds sterling", "CAD": "Canadian dollars",
                  "AUD": "Australian dollars", "INR": "Indian rupees", "JPY": "Japanese yen", "CHF": "Swiss francs"}


def _d(iso):
    return date.fromisoformat(iso)


def _short(iso):
    return _d(iso).strftime("%b %d, %Y").replace(" 0", " ")


class Facts:
    """The filing's numeric facts by concept, and the fiscal-year labels."""

    def __init__(self, doc):
        self.doc = doc
        self.by_concept = defaultdict(list)
        for f in doc.facts:
            if f.numeric and (f.shown is not None or f.nil):
                self.by_concept[f.name].append(f)
        focus = doc.dei("DocumentFiscalYearFocus")
        end = self._period_end()
        self.fy_offset = int(focus) - int(end[:4]) if focus and focus.isdigit() and end else 0
        scales = Counter(f.scale for fs in self.by_concept.values() for f in fs
                         if f.unit and "/" not in f.unit and f.unit.isupper() and not f.hidden)
        self.scale = scales.most_common(1)[0][0] if scales else 0
        currencies = Counter(f.unit for fs in self.by_concept.values() for f in fs
                             if f.unit and "/" not in f.unit and f.unit.isupper())
        self.currency = currencies.most_common(1)[0][0] if currencies else None

    def _period_end(self):
        text = self.doc.dei("DocumentPeriodEndDate") or ""
        from ingest.figures import find_date
        found = find_date(text)
        if found:
            return f"{found[0]:04d}-{found[1]:02d}-{found[2]:02d}"
        ctx = next((self.doc.contexts[f.context] for f in self.doc.facts
                    if f.name == "dei:DocumentPeriodEndDate"), None)
        return ctx.end if ctx else None

    def fy(self, iso):
        return f"FY{int(iso[:4]) + self.fy_offset}"

    def units_text(self):
        if not self.currency:
            return None
        currency = CURRENCY_NAMES.get(self.currency, self.currency)
        words = SCALE_WORDS.get(self.scale)
        return f"(in {words} of {currency}, except per share data)" if words else f"(in {currency})"

    def find(self, concept, dims, start=None, end=None, instant=None):
        """The fact for a concept in a period with exactly these dimensions."""
        found = []
        for f in self.by_concept.get(concept, []):
            ctx = self.doc.contexts.get(f.context)
            if ctx is None or ctx.dims != dims:
                continue
            if instant is not None:
                if ctx.instant and ctx.end == instant:
                    found.append(f)
            elif not ctx.instant and ctx.start == start and ctx.end == end:
                found.append(f)
        if not found:
            return None
        # the same fact can be printed more than once (statement and note): keep the one in the
        # statements' scale, shown in the document
        return min(found, key=lambda f: (f.hidden, f.scale != self.scale and f.unit == self.currency, f.page or 0))


def _concepts(role):
    return [c for c in role.concepts() if not is_structure(c)]


def annual_columns(facts, concepts, any_dims=False):
    """The fiscal years a statement covers: [("d", start, end)], latest first (at most 3)."""
    counts = Counter()
    for concept in concepts:
        for f in facts.by_concept.get(concept, []):
            ctx = facts.doc.contexts.get(f.context)
            if ctx and not ctx.instant and ctx.start and (any_dims or not ctx.dims):
                if 300 <= (_d(ctx.end) - _d(ctx.start)).days <= 400:
                    counts[(ctx.start, ctx.end)] += 1
    if not counts:
        return []
    top = max(counts.values())
    keep = sorted((k for k, n in counts.items() if n >= 0.3 * top), key=lambda k: k[1], reverse=True)[:3]
    return [("d", s, e) for s, e in keep]


def instant_columns(facts, concepts):
    counts = Counter()
    for concept in concepts:
        for f in facts.by_concept.get(concept, []):
            ctx = facts.doc.contexts.get(f.context)
            if ctx and ctx.instant and not ctx.dims:
                counts[ctx.end] += 1
    if not counts:
        return []
    top = max(counts.values())
    keep = sorted((k for k, n in counts.items() if n >= 0.3 * top), reverse=True)[:2]
    return [("i", None, k) for k in keep]


def _heading(col):
    kind, start, end = col
    return _short(end) if kind == "i" else f"Year Ended {_short(end)}"


def _lookup(facts, node, col, dims):
    kind, start, end = col
    if kind == "i":
        return facts.find(node.concept, dims, instant=end)
    found = facts.find(node.concept, dims, start=start, end=end)
    if found is not None:
        return found
    role = (node.label_role or "").rsplit("/", 1)[-1]
    if "PeriodStart" in role or "periodStart" in role:
        for day in ((_d(start) - timedelta(days=1)).isoformat(), start):
            found = facts.find(node.concept, dims, instant=day)
            if found is not None:
                return found
        return None
    return facts.find(node.concept, dims, instant=end)


def _decimals(printed):
    text = printed.replace(",", "")
    return len(text.split(".")[1]) if "." in text else 0


def raw_of(fact, negate=False):
    """The figure as the statement prints it: "130,497", "(1,234)", "—", "4.90"."""
    if fact.shown is None or fact.nil:
        return "—", 0.0, True
    shown = -fact.shown if negate else fact.shown
    text = f"{abs(shown):,.{_decimals(fact.printed)}f}"
    if shown < 0:
        text = f"({text})"
    return text, shown + 0.0, False


class Statement:
    """One statement built from its role: rows for the view, lines and values, facts per line."""

    def __init__(self, kind, role):
        self.kind, self.role = kind, role
        self.rows = []               # view rows
        self.lines = []              # (label, kind, node, depth, [(col, fact)])
        self.columns = []
        self.pages = []


def _walk(facts, lb, role, columns, dims, calc_parents, emit_line, emit_text):
    def visit(node, depth, root=False):
        name = local_name(node.concept)
        if name.endswith("Axis"):
            return
        if is_structure(node.concept):
            for child in node.children:
                visit(child, depth)
            return
        found = [(col, _lookup(facts, node, col, dims)) for col in columns]
        if any(f is not None for _, f in found):
            role_name = (node.label_role or "").rsplit("/", 1)[-1]
            total = "total" in role_name.lower() or node.concept in calc_parents
            emit_line(lb.label(node.concept, node.label_role), "total" if total else "data", node, depth, found)
        elif node.children and not root and not name.endswith("RollForward"):
            # a roll-forward ("Increase (Decrease) in Shareholders' Equity") only groups the movements
            label = lb.label(node.concept, node.label_role)
            if not label.endswith(("[Abstract]", "[Roll Forward]", "[Line Items]")):
                emit_text(label, depth)
        for child in node.children:
            visit(child, depth + 1)

    for root in role.roots:
        visit(root, 0, root=True)


def _equity_groups(lb, role):
    """[(label, dims)] of the equity components in presentation order, then the total."""
    groups = []

    def find_axis(node):
        if local_name(node.concept).endswith("Axis") and "Equity" in local_name(node.concept):
            members = []

            def collect(n):
                for child in n.children:
                    if local_name(child.concept).endswith("Member"):
                        members.append(child)
                    collect(child)
            collect(node)
            for m in members:
                groups.append((lb.label(m.concept, m.label_role), {node.concept: m.concept}))
            return True
        return any(find_axis(c) for c in node.children)

    for root in role.roots:
        if find_axis(root):
            break
    groups.append(("Total", {}))
    return groups


def build(facts, lb, kind, role):
    st = Statement(kind, role)
    concepts = _concepts(role)
    calc_parents = set(lb.calc.get(role.uri, {}))
    if kind == "balance_sheet":
        st.columns = instant_columns(facts, concepts)
    else:
        st.columns = annual_columns(facts, concepts, any_dims=(kind == "equity"))
    if not st.columns:
        return None
    headings = [_heading(c) for c in st.columns]
    st.rows.append({"kind": "header", "label": facts.units_text() or "", "cells": headings})

    def emit_line(label, line_kind, node, depth, found):
        negate = linkbase.is_negated(node.label_role)
        cells, figures = [], []
        for col, fact in found:
            if fact is None:
                cells.append("")
                figures.append((col, None, None))
                continue
            raw, shown, nil = raw_of(fact, negate)
            cells.append(raw)
            figures.append((col, fact, (raw, shown, nil)))
        st.rows.append({"kind": line_kind, "label": label, "cells": cells, "depth": depth})
        st.lines.append({"label": label, "kind": line_kind, "concept": node.concept, "row_no": len(st.rows) - 1,
                         "negate": negate, "figures": figures, "dims": current_dims[0]})

    def emit_text(label, depth):
        st.rows.append({"kind": "text", "label": label, "depth": depth})

    current_dims = [{}]
    if kind == "equity":
        for label, dims in _equity_groups(lb, role):
            mark = len(st.rows)
            st.rows.append({"kind": "group", "label": label, "cells": [""] * len(st.columns)})
            current_dims[0] = dims
            before = len(st.lines)
            _walk(facts, lb, role, st.columns, dims, calc_parents, emit_line, emit_text)
            if len(st.lines) == before:
                del st.rows[mark:]          # a component with no figures
    else:
        _walk(facts, lb, role, st.columns, {}, calc_parents, emit_line, emit_text)
    # text rows with no line under them (before the next text row or the end) say nothing
    keep = []
    for i, row in enumerate(st.rows):
        if row["kind"] == "text":
            nxt = next((r for r in st.rows[i + 1:] if r["kind"] != "text"), None)
            if nxt is None or nxt["kind"] in ("group", "header"):
                continue
        keep.append(row)
    if len(keep) != len(st.rows):
        index_map, j = {}, 0
        for i, row in enumerate(st.rows):
            if row in keep:
                index_map[i] = keep.index(row)
        for line in st.lines:
            line["row_no"] = index_map[line["row_no"]]
        st.rows = keep
    # the document pages it is printed on: where most of its shown facts are
    pages = Counter(f.page for line in st.lines for _, f, _ in line["figures"] if f is not None and f.page
                    and not f.hidden)
    if pages:
        top_page, top = pages.most_common(1)[0]
        run = [top_page]
        while pages.get(run[0] - 1, 0) >= max(3, top // 4):
            run.insert(0, run[0] - 1)
        while pages.get(run[-1] + 1, 0) >= max(3, top // 4):
            run.append(run[-1] + 1)
        st.pages = run
    return st


def statement_text(st, title, section_label, printed):
    page = st.pages[0] if st.pages else None
    lines = [f"=== {title} ({section_label}) ==="]
    if page:
        lines.append(f"--- PDF page {page}" + (f" (printed page {printed.get(page)})" if printed.get(page) else "")
                     + " ---")
    lines.append(title)
    for row in st.rows:
        if row["kind"] in ("text", "group"):
            lines.append(row["label"])
        else:
            cells = [c for c in row["cells"]]
            lines.append(" | ".join([row["label"]] + cells) if any(cells) else row["label"])
    return "\n".join(lines)


def build_all(doc, lb, classified, section_key, section_label, code):
    """The statements of a filing for the index, the views, lines and values.

    Returns (index statements, {unit id: view}, lines, values, {line id: line facts})."""
    facts = Facts(doc)
    printed = {p.no: p.printed for p in doc.pages}
    index_statements, views, lines, values, line_facts = [], {}, [], [], {}
    seen = Counter()
    for kind in ORDER:
        role = classified.statements.get(kind)
        if role is None:
            continue
        st = build(facts, lb, kind, role)
        if st is None or not st.lines:
            continue
        index_type = INDEX_TYPE.get(kind, kind)
        code_type = {"profit_loss": "PL", "balance_sheet": "BS", "cash_flow": "CF", "equity": "EQ"}[index_type]
        seen[code_type] += 1
        uid = f"{code}-{code_type}" + (f"-{seen[code_type]}" if seen[code_type] > 1 else "")
        title = role.title
        pages = st.pages or [1]
        index_statements.append({
            "type": index_type, "label": LABELS[kind], "title": title,
            "pages": [{"pdf_page": p, "printed": printed.get(p), "rotation": 0, "top": 0.0, "bottom": 0.0,
                       "rows": []} for p in pages],
            "text": statement_text(st, title, section_label, printed),
            "role": role.uri, "xbrl_kind": kind,
        })
        views[(section_key, uid)] = {
            "id": index_type, "title": title, "label": LABELS[kind],
            "pages": [{"pdf_page": pages[0], "printed": printed.get(pages[0]), "note": "",
                       "tables": [{"rows": [{k: v for k, v in r.items() if k != "depth"} for r in st.rows],
                                   "width": len(st.columns), "notes_col": None}]}],
        }
        for n, line in enumerate(st.lines, 1):
            line_id = f"{uid}-L{n:03d}"
            lines.append({"id": line_id, "section_id": section_key, "unit_id": uid, "seq": n,
                          "pdf_page": pages[0], "table_no": 0, "label": line["label"], "kind": line["kind"],
                          "note_ref": None, "row_no": line["row_no"], "concept": line["concept"]})
            line_facts[line_id] = {"concept": line["concept"], "dims": line["dims"], "role": role.uri,
                                   "negate": line["negate"], "facts": {}}
            for col_no, (col, fact, shown) in enumerate(line["figures"]):
                if fact is None:
                    continue
                raw, value, nil = shown
                end = col[2]
                values.append({"line_id": line_id, "col": col_no, "heading": _heading(col),
                               "period_end": end, "period_label": facts.fy(end), "raw": raw, "value": value,
                               "nil": int(nil)})
                line_facts[line_id]["facts"][col_no] = fact
    return index_statements, views, lines, values, line_facts, facts
