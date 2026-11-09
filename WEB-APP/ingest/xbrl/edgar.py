"""Download an inline XBRL filing from SEC EDGAR into XBRL-docs\\<TICKER>\\ (the XBRL page, /xbrl).

The user gives a ticker and any link into the filing: its index page
(".../0000874766-26-000012-index.htm"), the iXBRL viewer ("/ix?doc=/Archives/edgar/data/…/hig-20251231.htm")
or one of its documents. From the link's folder (/Archives/edgar/data/<CIK>/<accession>/) the filing
index page is read, and these files are saved:

  Document Format Files   the main document marked iXBRL (10-K, 10-K/A, 20-F, 40-F …)
  Data Files              EX-101.SCH (.xsd), EX-101.CAL / DEF / LAB / PRE (linkbases), and the
                          extracted XBRL instance (…_htm.xml)

plus filing.json (what was downloaded, from where, when). The folder is then an inline XBRL filing
the report list shows and the XBRL route ingests (ingest/xbrl, INFO/XBRL-ROUTE.md).

This changes decision Q1 of INFO/XBRL-ROUTE.md (the app did not download from EDGAR): the user asked
for it on 2026-11-08. Only www.sec.gov is contacted, only for the filing named, a few requests with a
pause between them (SEC allows 10 per second), with config.SEC_USER_AGENT as the User-Agent.
"""

import html
import json
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import config

SEC_HOSTS = {"www.sec.gov", "sec.gov"}
FOLDER_RE = re.compile(r"/Archives/edgar/data/(\d{1,10})/(\d{18})(?:/|$)")
ACCESSION_DASHED_RE = re.compile(r"/Archives/edgar/data/(\d{1,10})/(\d{10})-(\d{2})-(\d{6})")
TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,9}$")
TABLE_RE = re.compile(r'<table class="tableFile" summary="([^"]+)">(.*?)</table>', re.S | re.I)
ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
HREF_RE = re.compile(r'<a href="([^"]+)"', re.I)
TAG_RE = re.compile(r"<[^>]+>")
DATA_TYPES = {"EX-101.SCH": "schema", "EX-101.CAL": "calculation", "EX-101.DEF": "definition",
              "EX-101.LAB": "labels", "EX-101.PRE": "presentation"}
MAIN_FORMS = ("10-K", "10-K/A", "10-KT", "20-F", "20-F/A", "40-F", "40-F/A", "10-Q", "10-Q/A")
PAUSE = 0.2                    # seconds between requests
# www.sec.gov's CDN injects its bot check into the HTML it serves: a <script … defer> in <head> (not
# well-formed XML: the filing could not be parsed) and a script + <noscript> pixel at the end. A filing
# can't contain scripts (EDGAR rejects active content), so every script / noscript element is removed;
# the result is then exactly as filed (its size equals the size the index lists).
INJECTED_RE = re.compile(rb"<script\b[^>]*>.*?</script\s*>|<noscript\b[^>]*>.*?</noscript\s*>", re.S | re.I)


class EdgarError(ValueError):
    """Shown to the user as-is (a bad link, a filing without inline XBRL, SEC refusing)."""


def clean_ticker(ticker):
    ticker = (ticker or "").strip().upper()
    if not TICKER_RE.match(ticker):
        raise EdgarError("Enter the stock's ticker: letters and digits, e.g. HIG or BRK.B.")
    return ticker


def parse_link(link):
    """(CIK, accession without dashes) of any link into a filing on www.sec.gov."""
    link = (link or "").strip()
    try:
        parts = urllib.parse.urlsplit(link)
    except ValueError:
        parts = None
    if not parts or parts.scheme not in ("http", "https") or (parts.hostname or "").lower() not in SEC_HOSTS:
        raise EdgarError("Paste a link to the filing on www.sec.gov, e.g. its index page "
                         "https://www.sec.gov/Archives/edgar/data/874766/000087476626000012/0000874766-26-000012-index.htm")
    # the iXBRL viewer carries the document's path in ?doc=
    paths = [parts.path] + urllib.parse.parse_qs(parts.query).get("doc", [])
    for path in paths:
        match = FOLDER_RE.search(path)
        if match:
            return match.group(1), match.group(2)
        match = ACCESSION_DASHED_RE.search(path)
        if match:
            return match.group(1), match.group(2) + match.group(3) + match.group(4)
    raise EdgarError("This link doesn't point into a filing (…/Archives/edgar/data/<CIK>/<accession>/…). "
                     "Open the filing on EDGAR and copy the link of its index page.")


def folder_url(cik, accession):
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/"


def index_url(cik, accession):
    dashed = f"{accession[:10]}-{accession[10:12]}-{accession[12:]}"
    return folder_url(cik, accession) + f"{dashed}-index.htm"


def _text(cell):
    return " ".join(html.unescape(TAG_RE.sub(" ", cell)).split())


def parse_index(page):
    """The rows of the index page's tables: [{table, seq, description, href, document, type, size, ixbrl}]."""
    rows = []
    for summary, body in TABLE_RE.findall(page):
        for row in ROW_RE.findall(body):
            cells = CELL_RE.findall(row)
            if len(cells) < 4:
                continue                       # the heading row
            href = HREF_RE.search(cells[2])
            rows.append({"table": summary, "seq": _text(cells[0]), "description": _text(cells[1]),
                         "href": html.unescape(href.group(1)) if href else "", "document": _text(cells[2]).split(" ")[0],
                         "type": _text(cells[3]), "size": _text(cells[4]) if len(cells) > 4 else "",
                         "ixbrl": "iXBRL" in cells[2]})
    return rows


def _info(page):
    """Company, form and period from the index page header (for filing.json and the page)."""
    company = re.search(r'<span class="companyName">(.*?)</span>', page, re.S)
    form = re.search(r'<div id="formName">\s*<strong>(.*?)</strong>', page, re.S)
    period = re.search(r'Period of Report</div>\s*<div class="info">([^<]+)</div>', page)
    name = _text(company.group(1)) if company else None
    if name:
        name = re.sub(r"\s*\((?:Filer|Subject)\).*$", "", name).strip()
        name = re.sub(r"\s*CIK:.*$", "", name).strip()
    return {"company": name, "form": _text(form.group(1)) if form else None,
            "period": period.group(1).strip() if period else None}


def choose(rows, cik, accession):
    """The files to save: [(file name, url, kind)]. EdgarError when there is no inline XBRL document."""
    prefix = f"/Archives/edgar/data/{int(cik)}/{accession}/"

    def url_of(row):
        href = row["href"]
        if href.startswith("/ix?"):
            href = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query).get("doc", [""])[0]
        if not href.startswith(prefix):
            return None                        # only files of this filing
        name = Path(urllib.parse.urlsplit(href).path).name
        if not re.fullmatch(r"[\w.\-]+", name):
            return None
        return name, "https://www.sec.gov" + href

    main = next((r for r in rows if r["table"].startswith("Document Format") and r["ixbrl"]
                 and r["type"].upper() in MAIN_FORMS), None) or \
        next((r for r in rows if r["table"].startswith("Document Format") and r["ixbrl"]), None)
    if main is None:
        raise EdgarError("This filing has no inline XBRL document (EDGAR marks it 'iXBRL'). Filings before "
                         "2019-2021 were plain XBRL: the app reads inline XBRL only.")
    picked = [(main, f"main document ({main['type']}, iXBRL)")]
    for row in rows:
        if not row["table"].startswith("Data Files"):
            continue
        kind = DATA_TYPES.get(row["type"].upper())
        if kind:
            picked.append((row, kind))
        elif "INSTANCE" in row["description"].upper() and row["document"].lower().endswith(".xml"):
            picked.append((row, "extracted XBRL instance"))
    if not any(k == "presentation" for _, k in picked):
        raise EdgarError("The filing's index lists no presentation linkbase (EX-101.PRE): it can't be read.")
    out = []
    for row, kind in picked:
        found = url_of(row)
        if found:
            size = int(row["size"]) if row["size"].isdigit() else None
            out.append((found[0], found[1], kind, size))
    return out


def strip_injected(data):
    """The served HTML without what SEC's CDN added (see INJECTED_RE)."""
    return INJECTED_RE.sub(b"", data)


def _get(url):
    request = urllib.request.Request(url, headers={"User-Agent": config.SEC_USER_AGENT,
                                                   "Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            limit = config.SEC_MAX_FILE_MB * 1_048_576
            data = response.read(limit + 1)
            if len(data) > limit:
                raise EdgarError(f"{Path(url).name} is over {config.SEC_MAX_FILE_MB} MB: not downloaded.")
            return data
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429):
            raise EdgarError(f"SEC refused the request ({exc.code}). SEC asks automated tools to send a "
                             "User-Agent with a name and email: set the SEC_USER_AGENT environment variable "
                             "(e.g. \"Your Name your.email@example.com\") and restart the app.")
        if exc.code == 404:
            raise EdgarError(f"Not found on SEC: {url}")
        raise EdgarError(f"SEC answered {exc.code} for {url}")
    except urllib.error.URLError as exc:
        raise EdgarError(f"Could not reach www.sec.gov ({exc.reason}). Check the internet connection.")


def target_folder(ticker):
    return Path(config.XBRL_DOCS_DIR) / clean_ticker(ticker)


def download(ticker, link, overwrite=False, progress=None):
    """Save the filing's inline XBRL files in XBRL-docs\\<TICKER>\\; returns what was saved."""
    ticker = clean_ticker(ticker)
    cik, accession = parse_link(link)
    target = target_folder(ticker)
    if target.exists() and any(target.iterdir()) and not overwrite:
        raise EdgarError(f"XBRL-docs\\{ticker} already holds a filing. Tick 'Replace' to download over it.")
    say = progress or (lambda text: None)
    say("Reading the filing index on SEC…")
    index = index_url(cik, accession)
    page = _get(index).decode("utf-8", errors="replace")
    info = _info(page)
    files = choose(parse_index(page), cik, accession)
    partial = target.with_name(target.name + ".partial")
    shutil.rmtree(partial, ignore_errors=True)
    partial.mkdir(parents=True)
    saved = []
    try:
        for n, (name, url, kind, size) in enumerate(files, 1):
            say(f"Downloading {n} of {len(files)}: {name}")
            time.sleep(PAUSE)
            data = _get(url)
            if name.lower().endswith((".htm", ".html", ".xhtml")):
                data = strip_injected(data)
            (partial / name).write_bytes(data)
            saved.append({"name": name, "kind": kind, "bytes": len(data), "url": url,
                          "as_filed": size is None or size == len(data)})
        manifest = {"ticker": ticker, "link": link.strip(), "index": index, "cik": str(int(cik)),
                    "accession": accession, **info, "files": saved,
                    "downloaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        (partial / "filing.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        if target.exists():
            shutil.rmtree(target)
        partial.rename(target)
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise
    return manifest


def manifest(folder):
    """The filing.json of a downloaded folder ({} if it has none)."""
    try:
        return json.loads((Path(folder) / "filing.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
