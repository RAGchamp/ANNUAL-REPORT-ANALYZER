"""The XBRL page (/xbrl): a ticker and a link to a filing on SEC EDGAR -> XBRL-docs\\<TICKER>\\
(ingest/xbrl/edgar.py). SEC is never contacted: edgar._get is replaced by canned pages."""

import json
import shutil
import time
from pathlib import Path

import pytest

import app as app_module
import config
import webcommon
from ingest.xbrl import edgar

ROOT = Path(__file__).resolve().parents[2]
NVIDIA = ROOT / "XBRL" / "Nvidia"
CIK, ACC = "874766", "000087476626000012"
FOLDER = f"/Archives/edgar/data/{CIK}/{ACC}/"
INDEX = f"https://www.sec.gov{FOLDER}0000874766-26-000012-index.htm"


def _row(seq, description, href, doc, typ, size, ixbrl=False):
    mark = ' &nbsp;&nbsp;<span style="color: green">iXBRL</span>' if ixbrl else ""
    return (f'<tr><td scope="row">{seq}</td><td scope="row">{description}</td>'
            f'<td scope="row"><a href="{href}">{doc}</a>{mark}</td><td scope="row">{typ}</td>'
            f'<td scope="row">{size}</td></tr>')


def index_page(files):
    """An EDGAR filing index page like HIG's (Document Format Files + Data Files)."""
    head = '<tr><th scope="col">Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>'
    fmt = [_row(1, "10-K", f"/ix?doc={FOLDER}t-20251231.htm", "t-20251231.htm", "10-K", files["t-20251231.htm"], True),
           _row(2, "EX-21", f"{FOLDER}ex21.htm", "ex21.htm", "EX-21", 100)]
    data = [_row(12, "XBRL TAXONOMY EXTENSION SCHEMA DOCUMENT", f"{FOLDER}t-20251231.xsd", "t-20251231.xsd", "EX-101.SCH", 1),
            _row(16, "XBRL TAXONOMY EXTENSION PRESENTATION LINKBASE DOCUMENT", f"{FOLDER}t-20251231_pre.xml",
                 "t-20251231_pre.xml", "EX-101.PRE", 1),
            _row(15, "XBRL TAXONOMY EXTENSION LABEL LINKBASE DOCUMENT", f"{FOLDER}t-20251231_lab.xml",
                 "t-20251231_lab.xml", "EX-101.LAB", 1),
            _row(235, "<b>EXTRACTED</b> XBRL INSTANCE DOCUMENT", f"{FOLDER}t-20251231_htm.xml", "t-20251231_htm.xml",
                 "XML", 1),
            _row(99, "AN OUTSIDER", "/Archives/edgar/data/1/000000000000000001/x_cal.xml", "x_cal.xml", "EX-101.CAL", 1)]
    return ('<div id="formName"><strong>Form 10-K</strong> - Annual report</div>'
            '<div class="infoHead">Period of Report</div>\n<div class="info">2025-12-31</div>'
            '<span class="companyName">TEST INSURANCE GROUP, INC. (Filer) CIK: 0000874766</span>'
            '<p>Document Format Files</p><table class="tableFile" summary="Document Format Files">' + head
            + "".join(fmt) + '</table><p>Data Files</p><table class="tableFile" summary="Data Files">' + head
            + "".join(data) + "</table>")


MAIN = (b'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>t</title>'
        b'<script >x="1"</script><script type="text/javascript" src="https://www.sec.gov/akam/13/abc"  defer>'
        b'</script></head><body><div style="display:none"><ix:header/></div><p>Filed text</p>'
        b'<script type="text/javascript" src="/K-L/x"></script><noscript><img src="https://www.sec.gov/akam/13/pixel"/>'
        b'</noscript></body></html>')
AS_FILED = edgar.strip_injected(MAIN)


@pytest.fixture
def sec(monkeypatch, tmp_path):
    """Canned SEC answers; records the URLs asked for."""
    monkeypatch.setattr(config, "XBRL_DOCS_DIR", tmp_path / "XBRL-docs")
    (tmp_path / "XBRL-docs").mkdir()
    monkeypatch.setattr(edgar, "PAUSE", 0)
    bodies = {INDEX: index_page({"t-20251231.htm": len(AS_FILED)}).encode(),
              f"https://www.sec.gov{FOLDER}t-20251231.htm": MAIN}
    for name in ("t-20251231.xsd", "t-20251231_pre.xml", "t-20251231_lab.xml", "t-20251231_htm.xml"):
        bodies[f"https://www.sec.gov{FOLDER}{name}"] = f"<x>{name}</x>".encode()
    asked = []

    def fake_get(url):
        asked.append(url)
        if url not in bodies:
            raise edgar.EdgarError(f"Not found on SEC: {url}")
        return bodies[url]

    monkeypatch.setattr(edgar, "_get", fake_get)
    return asked


def test_links_to_a_filing():
    assert edgar.parse_link(INDEX) == (CIK, ACC)
    assert edgar.parse_link(f"https://www.sec.gov/ix?doc={FOLDER}hig-20251231.htm") == (CIK, ACC)
    assert edgar.parse_link(f"https://www.sec.gov{FOLDER}hig-20251231_pre.xml") == (CIK, ACC)
    assert edgar.parse_link("https://www.sec.gov/Archives/edgar/data/874766/0000874766-26-000012.txt") == (CIK, ACC)
    assert edgar.index_url(CIK, ACC) == INDEX
    for bad in ("https://example.com" + FOLDER, "ftp://www.sec.gov" + FOLDER, "not a link",
                "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=874766"):
        with pytest.raises(edgar.EdgarError):
            edgar.parse_link(bad)


def test_tickers():
    assert edgar.clean_ticker(" hig ") == "HIG" and edgar.clean_ticker("brk.b") == "BRK.B"
    for bad in ("", "..", "A/B", "TOO-LONG-TICKER", "a b"):
        with pytest.raises(edgar.EdgarError):
            edgar.clean_ticker(bad)


def test_index_rows_and_the_files_chosen():
    rows = edgar.parse_index(index_page({"t-20251231.htm": 5}))
    assert len(rows) == 7 and rows[0]["ixbrl"] and not rows[1]["ixbrl"]
    chosen = edgar.choose(rows, CIK, ACC)
    assert [(name, kind) for name, _, kind, _ in chosen] == [
        ("t-20251231.htm", "main document (10-K, iXBRL)"), ("t-20251231.xsd", "schema"),
        ("t-20251231_pre.xml", "presentation"), ("t-20251231_lab.xml", "labels"),
        ("t-20251231_htm.xml", "extracted XBRL instance")]       # not the exhibit, not another filing's file
    assert chosen[0][1] == f"https://www.sec.gov{FOLDER}t-20251231.htm"
    without_ixbrl = [r for r in rows if not r["ixbrl"]]
    with pytest.raises(edgar.EdgarError, match="no inline XBRL"):
        edgar.choose(without_ixbrl, CIK, ACC)


def test_injected_scripts_are_removed():
    assert b"script" not in AS_FILED and b"akam" not in AS_FILED
    assert b"<p>Filed text</p>" in AS_FILED and AS_FILED.endswith(b"</body></html>")


def test_download(sec):
    result = edgar.download("hig", INDEX)
    folder = Path(config.XBRL_DOCS_DIR) / "HIG"
    assert sorted(p.name for p in folder.iterdir()) == [
        "filing.json", "t-20251231.htm", "t-20251231.xsd", "t-20251231_htm.xml", "t-20251231_lab.xml",
        "t-20251231_pre.xml"]
    assert (folder / "t-20251231.htm").read_bytes() == AS_FILED
    manifest = json.loads((folder / "filing.json").read_text(encoding="utf-8"))
    assert (manifest["company"], manifest["form"], manifest["period"]) == ("TEST INSURANCE GROUP, INC.", "Form 10-K",
                                                                        "2025-12-31")
    assert manifest["files"][0]["as_filed"] is True
    assert result["ticker"] == "HIG" and sec[0] == INDEX
    assert all(url.startswith("https://www.sec.gov" + FOLDER) for url in sec)
    # a second download needs "Replace"
    with pytest.raises(edgar.EdgarError, match="Replace"):
        edgar.download("HIG", INDEX)
    edgar.download("HIG", INDEX, overwrite=True)
    assert not (Path(config.XBRL_DOCS_DIR) / "HIG.partial").exists()


def test_failed_download_leaves_nothing(sec, monkeypatch):
    real = edgar._get

    def broken(url):
        if url.endswith("_lab.xml"):
            raise edgar.EdgarError("SEC answered 500")
        return real(url)

    monkeypatch.setattr(edgar, "_get", broken)
    with pytest.raises(edgar.EdgarError):
        edgar.download("HIG", INDEX)
    assert list(Path(config.XBRL_DOCS_DIR).iterdir()) == []


@pytest.mark.skipif(not (NVIDIA / "nvda-20260125.htm").exists(), reason="Nvidia's XBRL filing is not on this PC")
def test_page_lists_and_ingests_downloaded_filings(monkeypatch, tmp_path):
    docs = tmp_path / "XBRL-docs"
    shutil.copytree(NVIDIA, docs / "NVDA")
    (docs / "EMPTY").mkdir()
    monkeypatch.setattr(config, "XBRL_DOCS_DIR", docs)
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "A.pdf").write_bytes(b"%PDF-1.4")
    # a downloaded filing is a report like the others
    assert [p.name for p in webcommon.list_reports()] == ["A.pdf", "NVDA"]

    client = app_module.app.test_client()
    page = client.get("/xbrl").get_data(as_text=True)
    assert "STOCK INVESTMENT PLAYBOOK" in page and 'id="download-form"' in page and "SEC_USER_AGENT" in page
    assert client.get("/xbrl.html").status_code == 200
    assert 'href="/xbrl"' in client.get("/").get_data(as_text=True)
    folders = {f["ticker"]: f for f in client.get("/api/xbrl/folders").get_json()["folders"]}
    assert folders["NVDA"]["readable"] and folders["NVDA"]["status"] == "not ingested"
    assert not folders["EMPTY"]["readable"]

    bad = client.post("/api/xbrl/download", json={"ticker": "NVDA", "link": INDEX})
    assert bad.status_code == 400 and "Replace" in bad.get_json()["error"]
    assert client.post("/api/xbrl/download", json={"ticker": "X", "link": "https://example.com"}).status_code == 400

    job_id = client.post("/api/xbrl/ingest", json={"ticker": "NVDA"}).get_json()["job_id"]
    for _ in range(200):
        job = client.get(f"/api/jobs/{job_id}").get_json()
        if job["status"] != "running":
            break
        time.sleep(0.05)
    assert job["status"] == "done", job
    assert job["result"]["status"] == "up to date"
    assert any("18 notes" in line for line in job["result"]["quality"])
