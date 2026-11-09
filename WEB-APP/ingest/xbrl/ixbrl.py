"""Read an inline XBRL document (INFO/XBRL-ROUTE.md §5): its contexts, units and
facts, and the document itself as pages of blocks.

Facts
  ix:nonFraction   a number: `format` (ixt:num-dot-decimal, ixt:fixed-zero …), `scale`
                   (6 = millions), `sign="-"`, `decimals`; `shown` keeps the number as
                   printed (before the scale) with its sign, `value` the true amount
  ix:nonNumeric    text: dei cover facts, and the notes / policies / note tables as
                   `…TextBlock` facts whose `continuedAt` chain of ix:continuation
                   elements continues them elsewhere in the document
  ix:hidden        facts not shown in the document (still facts)
  ix:exclude       printed inside a fact but not part of its value

Pages and blocks
  The XHTML has no pages, only page breaks (`page-break-after` / `-before`). A *document
  page* is the content between two breaks, numbered 1…n; its printed page number is the
  number in its footer. Each page is read into blocks in document order, the same kinds the
  PDF route's narrative reader gives (heading, paragraph, table), each with the text-block
  facts it belongs to ("owners"), so a note's text is the blocks its facts own.

Only the standard library's XML parser is used: the filing is well-formed XHTML.
"""

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field

XHTML = "http://www.w3.org/1999/xhtml"
IX = "http://www.xbrl.org/2013/inlineXBRL"
XBRLI = "http://www.xbrl.org/2003/instance"
XBRLDI = "http://xbrl.org/2006/xbrldi"
XSI = "http://www.w3.org/2001/XMLSchema-instance"

BLOCK_TAGS = {"div", "p", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "table", "center",
              "blockquote", "body", "section", "article", "dl", "dt", "dd", "pre"}
TEXTBLOCK_OWNERS = {"nonNumeric", "continuation"}
PRINTED_RE = re.compile(r"^(?:[A-Z]{1,2}\s?-\s?)?\d{1,3}$|^[ivxlc]{1,6}$")
WS_RE = re.compile(r"\s+")
BOLD_RE = re.compile(r"font-weight\s*:\s*(?:bold|[6-9]00)", re.I)
SIZE_RE = re.compile(r"font-size\s*:\s*([\d.]+)pt", re.I)
HIDDEN_RE = re.compile(r"display\s*:\s*none", re.I)
BREAK_AFTER_RE = re.compile(r"page-break-after\s*:\s*always|break-after\s*:\s*page", re.I)
BREAK_BEFORE_RE = re.compile(r"page-break-before\s*:\s*always|break-before\s*:\s*page", re.I)
SCRIPTS_RE = re.compile(rb"<script\b[^>]*>.*?</script\s*>|<noscript\b[^>]*>.*?</noscript\s*>", re.S | re.I)
NUMBER_WORDS = {"no": 0, "none": 0, "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
                "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
                "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
                "ninety": 90, "hundred": 100}
# a cell that only opens or closes a figure: "$" | "1,234" | ")" | "%" -> "$1,234" / "(1,234)" / "41%"
OPENERS = {"$", "(", "$(", "($", "€", "£", "¥", "US$", "C$", "A$"}
CLOSERS = {")", "%", ")%", "%)", "pts", "bps", "x"}


def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def ns(tag):
    return tag[1:].split("}", 1)[0] if isinstance(tag, str) and tag.startswith("{") else ""


def clean(text):
    return WS_RE.sub(" ", (text or "").replace("\xa0", " ").replace("​", "")).strip()


# ---------------------------------------------------------------- contexts, units, facts

@dataclass
class Context:
    id: str
    start: str | None = None          # ISO dates
    end: str | None = None            # duration end, or the instant
    instant: bool = False
    dims: dict = field(default_factory=dict)       # axis -> member (typed members: their text)


@dataclass
class Fact:
    id: str
    name: str                         # "us-gaap:Revenues"
    context: str
    unit: str | None = None
    numeric: bool = False
    shown: float | None = None        # as printed, signed: 130,497 (millions) -> 130497.0
    value: float | None = None        # the true amount: shown * 10**scale
    scale: int = 0
    decimals: str | None = None
    printed: str = ""                 # the tag's text as printed: "130,497"
    nil: bool = False                 # xsi:nil, or a dash (ixt:fixed-zero)
    hidden: bool = False
    text: str = ""                    # nonNumeric: the value as text
    escape: bool = False
    continued_at: str | None = None
    page: int | None = None           # the document page it is printed on


def _date(text):
    return (text or "").strip()[:10] or None


def _contexts(root):
    out = {}
    for el in root.iter(f"{{{XBRLI}}}context"):
        ctx = Context(id=el.get("id"))
        period = el.find(f"{{{XBRLI}}}period")
        if period is not None:
            instant = period.find(f"{{{XBRLI}}}instant")
            if instant is not None:
                ctx.instant, ctx.end = True, _date(instant.text)
            else:
                ctx.start = _date(period.findtext(f"{{{XBRLI}}}startDate"))
                ctx.end = _date(period.findtext(f"{{{XBRLI}}}endDate"))
        for member in el.iter(f"{{{XBRLDI}}}explicitMember"):
            ctx.dims[member.get("dimension")] = (member.text or "").strip()
        for member in el.iter(f"{{{XBRLDI}}}typedMember"):
            ctx.dims[member.get("dimension")] = clean("".join(member.itertext()))
        out[ctx.id] = ctx
    return out


def _units(root):
    out = {}
    for el in root.iter(f"{{{XBRLI}}}unit"):
        divide = el.find(f"{{{XBRLI}}}divide")
        if divide is not None:
            num = [m.text.split(":")[-1] for m in divide.find(f"{{{XBRLI}}}unitNumerator").iter(f"{{{XBRLI}}}measure")]
            den = [m.text.split(":")[-1] for m in divide.find(f"{{{XBRLI}}}unitDenominator").iter(f"{{{XBRLI}}}measure")]
            out[el.get("id")] = "*".join(num) + "/" + "*".join(den)
        else:
            out[el.get("id")] = "*".join(m.text.split(":")[-1] for m in el.iter(f"{{{XBRLI}}}measure"))
    return out


def parse_number(text, fmt):
    """The number an ix:nonFraction prints, before scale and sign; (value, nil)."""
    name = (fmt or "").split(":")[-1].lower()
    raw = clean(text)
    if name in ("fixed-zero", "fixedzero", "zerodash", "fixed-empty"):
        return 0.0, True
    if name in ("numwordsen", "num-word-en"):
        words = [w for w in re.split(r"[\s-]+", raw.lower()) if w and w != "and"]
        if words and all(w in NUMBER_WORDS for w in words):
            total = 0
            for w in words:
                total = total * 100 if w == "hundred" else total + NUMBER_WORDS[w]
            return float(total), False
        return None, False
    if raw in ("", "-", "—", "–"):
        return 0.0, True
    digits = raw
    if "comma-decimal" in name or "numcommadecimal" in name:
        digits = digits.replace(".", "").replace(" ", "").replace(",", ".")
    else:
        digits = digits.replace(",", "").replace(" ", "")
    digits = re.sub(r"[^\d.]", "", digits)
    try:
        return float(digits), False
    except ValueError:
        return None, False


def _fact_text(el, skip_exclude=True):
    """Text of an element, with <br> as a space and ix:exclude left out."""
    parts = []

    def walk(node):
        if skip_exclude and local(node.tag) == "exclude" and ns(node.tag) == IX:
            if node.tail:
                parts.append(node.tail)
            return
        if local(node.tag) == "br":
            parts.append(" ")
        if node.text:
            parts.append(node.text)
        for child in node:
            walk(child)
        if node is not el and node.tail:
            parts.append(node.tail)

    walk(el)
    return clean("".join(parts))


# ---------------------------------------------------------------- the document as blocks

@dataclass
class Block:
    kind: str                         # heading | paragraph | table
    page: int
    text: str = ""
    rows: list = field(default_factory=list)       # tables: [[cell, …], …] (figure cells merged)
    owners: frozenset = frozenset()                # ids of the text-block facts / continuations around it
    bold: bool = False
    size: float = 0.0

    def as_text(self):
        if self.kind == "table":
            return "\n".join(" | ".join(r) for r in self.rows)
        return self.text


def merge_cells(cells):
    """Table cells as the PDF route writes them: empty cells dropped, "$" joined to its
    figure, ")" and "%" to the figure before them."""
    out = []
    for cell in cells:
        cell = clean(cell)
        if not cell:
            continue
        if out and cell in CLOSERS:
            out[-1] += cell
            continue
        if out and out[-1] in OPENERS:
            out[-1] = (out[-1] + cell) if out[-1] != "$(" else "($" + cell
            continue
        out.append(cell)
    return out


class _Walker:
    """One pass over the body: pages, blocks with their owners, and each fact's page."""

    def __init__(self, root):
        self.page = 1
        self.blocks = []
        self.fact_pages = {}
        self.has_block = {}
        body = root.find(f"{{{XHTML}}}body")
        self.body = body if body is not None else root
        self._mark(self.body)

    def _is_block(self, el):
        return ns(el.tag) == XHTML and local(el.tag) in BLOCK_TAGS

    def _mark(self, el):
        """has_block[el]: a block element is inside it (post-order, once)."""
        found = False
        for child in el:
            if self._mark(child) or self._is_block(child):
                found = True
        self.has_block[el] = found
        return found

    @staticmethod
    def _hidden(el):
        return HIDDEN_RE.search(el.get("style") or "") is not None

    def _break(self, el):
        tag = local(el.tag)
        style = el.get("style") or ""
        return tag, BREAK_BEFORE_RE.search(style) is not None, BREAK_AFTER_RE.search(style) is not None

    def _owner(self, el):
        if ns(el.tag) == IX and local(el.tag) in TEXTBLOCK_OWNERS and el.get("id"):
            return el.get("id")
        return None

    def _note_facts(self, el):
        """Record the page of every fact inside el."""
        for node in el.iter():
            if ns(node.tag) == IX and local(node.tag) in ("nonFraction", "nonNumeric") and node.get("id"):
                self.fact_pages.setdefault(node.get("id"), self.page)

    def _inner_owners(self, el):
        return {n.get("id") for n in el.iter() if n is not el and self._owner(n)}

    def _styled_text(self, el):
        """(text, bold share, largest font size) of an inline run."""
        parts, sizes = [], []

        def walk(node, bold, size):
            style = node.get("style") or ""
            if self._hidden(node):
                return
            if BOLD_RE.search(style) or local(node.tag) in ("b", "strong"):
                bold = True
            m = SIZE_RE.search(style)
            if m:
                size = float(m.group(1))
            if local(node.tag) == "br":
                parts.append(" ")
            for piece in (node.text,):
                if piece:
                    parts.append(piece)
                    n = len(piece.strip())
                    nonlocal_counts[0] += n if bold else 0
                    nonlocal_counts[1] += n
                    if n:
                        sizes.append(size)
            for child in node:
                walk(child, bold, size)
                if child.tail:
                    parts.append(child.tail)
                    n = len(child.tail.strip())
                    nonlocal_counts[0] += n if bold else 0
                    nonlocal_counts[1] += n
                    if n:
                        sizes.append(size)

        nonlocal_counts = [0, 0]
        walk(el, False, 0.0)
        bold_chars, total_chars = nonlocal_counts
        return clean("".join(parts)), (bold_chars / total_chars if total_chars else 0.0), max(sizes, default=0.0)

    def _emit_text(self, el, owners, extra=()):
        text, bold, size = self._styled_text(el)
        self._note_facts(el)
        if not text:
            return
        owners = frozenset(owners) | self._inner_owners(el) | frozenset(extra)
        heading = bold >= 0.9 and len(text) <= 200
        self.blocks.append(Block("heading" if heading else "paragraph", self.page, text=text,
                                 owners=owners, bold=bold >= 0.9, size=size))

    def _emit_table(self, el, owners):
        rows = []
        for tr in el.iter(f"{{{XHTML}}}tr"):
            cells = [self._styled_text(td)[0] for td in tr if local(td.tag) in ("td", "th")]
            merged = merge_cells(cells)
            if merged:
                rows.append(merged)
        self._note_facts(el)
        if rows:
            self.blocks.append(Block("table", self.page, rows=rows,
                                     owners=frozenset(owners) | self._inner_owners(el)))

    def walk(self, el=None, owners=()):
        el = self.body if el is None else el
        for child in el:
            self._visit(child, owners)

    def _visit(self, el, owners):
        if not isinstance(el.tag, str):
            return
        tag, before, after = self._break(el)
        if ns(el.tag) == IX and tag in ("header", "hidden", "references", "resources"):
            return
        if self._hidden(el):
            return
        if before and self.blocks and self.blocks[-1].page == self.page:
            self.page += 1
        if tag == "hr" and (after or before):
            if after:
                self.page += 1
            return
        own = self._owner(el)
        if own:
            owners = tuple(owners) + (own,)
        if ns(el.tag) == XHTML and tag == "table":
            self._emit_table(el, owners)
        elif self._is_block(el) and not self.has_block[el]:
            self._emit_text(el, owners)
        elif not self.has_block[el]:
            # inline content directly in a container (rare): one paragraph of its own
            if ns(el.tag) == IX or tag in ("span", "a", "font", "b", "i", "u", "strong", "em", "sup", "sub"):
                self._emit_text(el, owners)
        else:
            # a container: text directly in it becomes paragraphs between its block children
            if clean(el.text):
                self.blocks.append(Block("paragraph", self.page, text=clean(el.text), owners=frozenset(owners)))
            for child in el:
                self._visit(child, owners)
                if clean(child.tail):
                    self.blocks.append(Block("paragraph", self.page, text=clean(child.tail),
                                             owners=frozenset(owners)))
        if after and tag != "hr":
            self.page += 1


@dataclass
class Page:
    no: int
    printed: str | None
    blocks: list
    header: list
    footer: list


def _pages(blocks):
    """Blocks per document page; the footer's page number becomes the printed page and the
    "Table of Contents" back-link at the top of each page is dropped."""
    by_page = defaultdict(list)
    for b in blocks:
        by_page[b.page].append(b)
    out = []
    count = max(by_page, default=0)
    for no in range(1, count + 1):
        items = list(by_page.get(no, []))
        header, footer, printed = [], [], None
        while items and items[0].kind != "table" and items[0].text.lower() in ("table of contents", "index"):
            header.append(items.pop(0).text)
        for i in range(len(items) - 1, max(len(items) - 3, -1), -1):
            b = items[i]
            if b.kind != "table" and PRINTED_RE.match(b.text):
                printed = b.text.replace(" ", "")
                footer.append(b.text)
                items.pop(i)
                break
        out.append(Page(no=no, printed=printed, blocks=items, header=header, footer=footer))
    return out


# ---------------------------------------------------------------- the document

@dataclass
class Document:
    contexts: dict
    units: dict
    facts: list                       # every fact in document order
    by_id: dict
    continuations: dict               # id -> continuedAt (or None)
    pages: list                       # [Page]
    blocks: list                      # all blocks in document order (after header / footer cuts)

    def facts_named(self, name):
        return [f for f in self.facts if f.name == name]

    def dei(self, local_name):
        """A cover fact's text: dei("EntityRegistrantName")."""
        fact = next((f for f in self.facts if f.name == f"dei:{local_name}"), None)
        return fact.text if fact else None

    def chain(self, fact_id):
        """The ids of a text-block fact and its continuations, in order."""
        ids, seen = [fact_id], {fact_id}
        fact = self.by_id.get(fact_id)
        nxt = fact.continued_at if fact else None
        while nxt and nxt not in seen:
            ids.append(nxt)
            seen.add(nxt)
            nxt = self.continuations.get(nxt)
        return ids

    def owned_blocks(self, fact_id):
        """The blocks a text-block fact covers (with its continuations), in document order."""
        ids = set(self.chain(fact_id))
        return [b for b in self.blocks if b.owners & ids]


def parse(path):
    """The Document of an inline XBRL file."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        # a copy saved from www.sec.gov carries the CDN's injected scripts (a bare "defer" attribute is
        # not XML); a filing has no scripts of its own (ingest/xbrl/edgar.py), so they are dropped
        with open(path, "rb") as handle:
            data = SCRIPTS_RE.sub(b"", handle.read())
        root = ET.fromstring(data)
    contexts, units = _contexts(root), _units(root)
    hidden_ids = set()
    for hidden in root.iter(f"{{{IX}}}hidden"):
        hidden_ids |= {el.get("id") for el in hidden.iter() if el.get("id")}

    walker = _Walker(root)
    walker.walk()
    facts, by_id, continuations = [], {}, {}
    for el in root.iter():
        if ns(el.tag) != IX:
            continue
        tag = local(el.tag)
        if tag == "continuation":
            continuations[el.get("id")] = el.get("continuedAt")
            continue
        if tag not in ("nonFraction", "nonNumeric"):
            continue
        fid = el.get("id") or f"_anon{len(facts)}"
        fact = Fact(id=fid, name=el.get("name"), context=el.get("contextRef"), hidden=fid in hidden_ids,
                    page=walker.fact_pages.get(fid))
        if tag == "nonFraction":
            fact.numeric = True
            fact.unit = units.get(el.get("unitRef"), el.get("unitRef"))
            fact.decimals = el.get("decimals")
            fact.scale = int(el.get("scale") or 0)
            fact.printed = _fact_text(el)
            if el.get(f"{{{XSI}}}nil") == "true":
                fact.nil, fact.shown, fact.value = True, None, None
            else:
                number, nil = parse_number(fact.printed, el.get("format"))
                fact.nil = nil
                if number is not None:
                    sign = -1.0 if el.get("sign") == "-" else 1.0
                    fact.shown = sign * number
                    fact.value = fact.shown * (10 ** fact.scale)
        else:
            fact.escape = el.get("escape") == "true"
            fact.continued_at = el.get("continuedAt")
            fact.text = _fact_text(el)
        facts.append(fact)
        by_id[fid] = fact

    pages = _pages(walker.blocks)
    blocks = [b for p in pages for b in p.blocks]
    return Document(contexts=contexts, units=units, facts=facts, by_id=by_id, continuations=continuations,
                    pages=pages, blocks=blocks)
