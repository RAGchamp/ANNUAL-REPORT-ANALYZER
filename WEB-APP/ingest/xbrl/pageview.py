"""One document page of an inline XBRL filing as HTML (INFO/XBRL-ROUTE.md §8): what the
Ingest screen shows where a PDF report shows a page image.

The page is the filing's own HTML between two page breaks, cut from the source text
(the browser closes any element a cut leaves open). Scripts, frames and event
handlers are removed, and the route serves it with a Content-Security-Policy that
blocks scripts and outside requests.
"""

import re

from ingest.xbrl import filing as filing_mod

BREAK_AFTER_RE = re.compile(r"<hr\b[^>]*page-break-after\s*:\s*always[^>]*>", re.I)
BREAK_BEFORE_RE = re.compile(r"<(?:div|p|hr|table)\b[^>]*page-break-before\s*:\s*always[^>]*>", re.I)
BODY_RE = re.compile(r"<body\b[^>]*>(.*)</body>", re.I | re.S)
UNSAFE_RE = re.compile(r"<(script|iframe|object|embed)\b.*?(?:</\1\s*>|/>)", re.I | re.S)
HANDLER_RE = re.compile(r"\son[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*')", re.I)
HIDDEN_HEADER_RE = re.compile(r"<ix:header\b.*?</ix:header>", re.I | re.S)


def _cuts(body):
    cuts = [m.end() for m in BREAK_AFTER_RE.finditer(body)]
    cuts += [m.start() for m in BREAK_BEFORE_RE.finditer(body) if "page-break-after" not in m.group(0).lower()]
    return sorted(set(c for c in cuts if 0 < c < len(body)))


def page_count(path):
    body = _body(path)
    return len(_cuts(body)) + 1


def _body(path):
    fil = filing_mod.open_filing(path)
    text = fil.main.read_text(encoding="utf-8", errors="replace")
    match = BODY_RE.search(text)
    return HIDDEN_HEADER_RE.sub("", match.group(1) if match else text)


def page_html(path, page):
    """(html, page count) of document page `page` (1-based); ValueError when out of range."""
    body = _body(path)
    cuts = [0] + _cuts(body) + [len(body)]
    count = len(cuts) - 1
    if not 1 <= page <= count:
        raise ValueError(f"Page {page} is out of range (1–{count})")
    piece = body[cuts[page - 1]:cuts[page]]
    piece = HANDLER_RE.sub("", UNSAFE_RE.sub("", piece))
    piece = BREAK_AFTER_RE.sub("", piece)
    html = ("<!doctype html><html><head><meta charset=\"utf-8\"><title>Page {p}</title>"
            "<style>body{{max-width:8.5in;margin:1rem auto;padding:0 1rem;background:#fff;color:#000}}</style>"
            "</head><body>{body}</body></html>").format(p=page, body=piece)
    return html, count
