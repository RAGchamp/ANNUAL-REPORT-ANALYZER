"""Checks from the filing's own rules (INFO/XBRL-ROUTE.md §5):

  subtotal  every line the calculation linkbase defines as a sum: the sum of its items,
            with their weights (+1 / -1), for each period - "ok" or "fail", never
            "unverified": the filing says exactly which lines add up
  balance   Assets = LiabilitiesAndStockholdersEquity (ifrs: EquityAndLiabilities), each date
  carries   the same concept in two statements with the same figures (net income in the
            income statement, comprehensive income, cash flow and equity statements)

Sums use the facts' true amounts; the tolerance is the rounding the facts' `decimals`
allow (half a unit of the last digit per item).
"""

from ingest.xbrl.roles import local_name
from ingest.xbrl.statements import _short as statements_date

BALANCE_LEFT = {"Assets"}
BALANCE_RIGHT = {"LiabilitiesAndStockholdersEquity", "EquityAndLiabilities"}


def _decimals(fact):
    try:
        return int(fact.decimals)
    except (TypeError, ValueError):
        return 0


def _tolerance(facts):
    places = min((_decimals(f) for f in facts), default=0)
    return 0.5 * 10 ** (-places) * max(1, len(facts) - 1) + 1e-9


def _fmt(value, facts):
    return f"{value / 10 ** facts.scale:,.0f}" if facts.scale else f"{value:,.2f}"


def subtotals(lines, line_facts, lb, facts):
    checks = []
    doc = facts.doc
    for line in lines:
        info = line_facts.get(line["id"])
        if not info or info["dims"]:
            continue
        items = lb.calc.get(info["role"], {}).get(info["concept"])
        if not items:
            continue
        ok_cols, failed = [], []
        for col, total in info["facts"].items():
            if total.value is None:
                continue
            ctx = doc.contexts[total.context]
            found = []
            for concept, weight in items:
                fact = facts.find(concept, ctx.dims, instant=ctx.end) if ctx.instant else \
                    facts.find(concept, ctx.dims, start=ctx.start, end=ctx.end)
                if fact is not None and fact.value is not None:
                    found.append((fact, weight))
            if not found:
                continue
            total_sum = sum(f.value * w for f, w in found)
            tol = _tolerance([total] + [f for f, _ in found])
            if abs(total_sum - total.value) <= tol:
                ok_cols.append(col)
            else:
                failed.append((col, total, total_sum))
        if not ok_cols and not failed:
            continue
        names = ", ".join(("− " if w < 0 else "") + lb.label(c) for c, w in items[:6]) + (" …" if len(items) > 6 else "")
        if failed:
            col, total, total_sum = failed[0]
            checks.append({"kind": "subtotal", "subject": line["id"], "status": "fail",
                           "expected": total_sum, "actual": total.value,
                           "message": f"'{line['label']}' {_fmt(total.value, facts)} ≠ the sum of its items "
                                      f"{_fmt(total_sum, facts)} ({names}) per the calculation linkbase"})
        else:
            checks.append({"kind": "subtotal", "subject": line["id"], "status": "ok", "expected": None,
                           "actual": None,
                           "message": f"'{line['label']}' = the sum of its {len(items)} items "
                                      f"({names}) per the calculation linkbase"})
    return checks


def balance(lines, line_facts, values):
    checks = []
    by_line = {}
    for v in values:
        by_line.setdefault(v["line_id"], {})[v["col"]] = v
    for unit in sorted({l["unit_id"] for l in lines}):
        unit_lines = [l for l in lines if l["unit_id"] == unit and not line_facts[l["id"]]["dims"]]
        left = next((l for l in unit_lines if local_name(l["concept"]) in BALANCE_LEFT), None)
        right = next((l for l in unit_lines if local_name(l["concept"]) in BALANCE_RIGHT), None)
        if not left or not right:
            continue
        for col, fa in line_facts[left["id"]]["facts"].items():
            fb = line_facts[right["id"]]["facts"].get(col)
            if fb is None or fa.value is None or fb.value is None:
                continue
            ok = abs(fa.value - fb.value) <= _tolerance([fa, fb])
            va, vb = by_line[left["id"]][col], by_line[right["id"]][col]
            checks.append({"kind": "balance", "subject": left["id"], "status": "ok" if ok else "fail",
                           "expected": vb["value"], "actual": va["value"],
                           "message": f"Total assets {va['raw']} vs '{right['label']}' {vb['raw']} "
                                      f"({va['period_label']})"})
    return checks


def carries(lines, line_facts, values, facts):
    """The same concept, without dimensions, in two statements: compared fact by fact
    (same context), so an opening balance in the equity statement meets the balance
    sheet's figure for the year before."""
    checks, edges = [], []
    raw = {}
    for v in values:
        raw[(v["line_id"], v["col"])] = v["raw"]
    doc = facts.doc

    def when(fact):
        ctx = doc.contexts[fact.context]
        return statements_date(ctx.end) if ctx.instant else facts.fy(ctx.end)

    first = {}
    for line in lines:
        info = line_facts[line["id"]]
        if info["dims"] or line["kind"] == "text":
            continue
        first.setdefault((line["unit_id"], line["concept"]), line)
    by_concept = {}
    for (unit, concept), line in first.items():
        by_concept.setdefault(concept, []).append(line)
    for concept, group in by_concept.items():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                fa, fb = line_facts[a["id"]]["facts"], line_facts[b["id"]]["facts"]
                pairs = [(ca, x, cb, y) for ca, x in fa.items() for cb, y in fb.items()
                         if x.context == y.context and x.value is not None and y.value is not None]
                if not pairs:
                    continue
                ok = all(abs(x.value - y.value) <= _tolerance([x, y]) for _, x, _, y in pairs)
                shown = ", ".join(f"{when(x)} {raw[(a['id'], ca)]} / {raw[(b['id'], cb)]}" for ca, x, cb, y in pairs)
                checks.append({"kind": "carries", "subject": a["id"], "status": "ok" if ok else "warn",
                               "expected": pairs[0][3].shown, "actual": pairs[0][1].shown,
                               "message": f"'{a['label']}' in {a['unit_id']} and {b['unit_id']}: {shown}"})
                if ok:
                    edges.append({"src": a["id"], "dst": b["id"], "kind": "carries", "method": "same concept",
                                  "confidence": "high", "evidence": f"{concept}: {shown}"})
    return checks, edges
