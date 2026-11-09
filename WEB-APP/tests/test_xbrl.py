"""The XBRL route (INFO/XBRL-ROUTE.md): an inline XBRL filing -> report package.

Unit tests on small hand-written documents (scale, sign, fixed-zero, continuation
chains, ix:exclude, dimensional contexts, page breaks), and golden tests on
Nvidia's FY2026 10-K as filed on EDGAR (Annual-reports\\NVIDIA-10-K-2026, or
XBRL\\Nvidia; skipped when neither is there). Claude is mocked.
"""

import json
import re
import shutil
import time
import zipfile
from pathlib import Path

import pytest

import app as app_module
import config
import rptpkg
import webcommon
from analyzer import jobs as analyzer_jobs
from analyzer import note_selector
from ingest import pipeline
from ingest.xbrl import build, filing, ixbrl, pageview
from rptpkg import store

ROOT = Path(__file__).resolve().parents[2]
NVIDIA = next((p for p in (ROOT / "Annual-reports" / "NVIDIA-10-K-2026", ROOT / "XBRL" / "Nvidia")
               if (p / "nvda-20260125.htm").exists()), None)
needs_nvidia = pytest.mark.skipif(NVIDIA is None, reason="Nvidia's XBRL filing is not on this PC")

# ---------------------------------------------------------------- a small hand-written filing

SNIPPET = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
      xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12"
      xmlns:ixt-sec="http://www.sec.gov/inlineXBRL/transformation/2015-08-31"
      xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
      xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:dei="http://xbrl.sec.gov/dei/2025"
      xmlns:us-gaap="http://fasb.org/us-gaap/2025" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<head><title>t</title></head><body>
<div style="display:none"><ix:header><ix:hidden>
  <ix:nonNumeric contextRef="d1" name="dei:DocumentType" id="h1">10-K</ix:nonNumeric>
  <ix:nonFraction contextRef="d1" name="us-gaap:HiddenThing" unitRef="usd" decimals="0" id="h2">7</ix:nonFraction>
</ix:hidden><ix:resources>
  <xbrli:context id="d1"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
  <xbrli:context id="i1"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier>
    <xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementEquityComponentsAxis">us-gaap:RetainedEarningsMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity>
    <xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period></xbrli:context>
  <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
</ix:resources></ix:header></div>
<div><span style="font-weight:700">Note 3 - <ix:nonNumeric contextRef="d1" name="us-gaap:IncomeTaxDisclosureTextBlock" id="tb" continuedAt="tb-1" escape="true">Income Taxes</ix:nonNumeric></span></div>
<ix:continuation id="tb-1" continuedAt="tb-2"><div>First part of the note.</div>
<table><tr><td>Revenue</td><td>$</td><td><ix:nonFraction contextRef="d1" name="us-gaap:Revenues" unitRef="usd" decimals="-6" scale="6" format="ixt:num-dot-decimal" id="r1">1,234.5</ix:nonFraction></td></tr>
<tr><td>Loss</td><td>(</td><td><ix:nonFraction contextRef="d1" name="us-gaap:Loss" unitRef="usd" decimals="-6" scale="6" sign="-" id="r2">12</ix:nonFraction></td><td>)</td></tr>
<tr><td>Nothing</td><td><ix:nonFraction contextRef="d1" name="us-gaap:Zero" unitRef="usd" decimals="INF" format="ixt:fixed-zero" id="r3">—</ix:nonFraction></td></tr>
<tr><td>Balance</td><td><ix:nonFraction contextRef="i1" name="us-gaap:StockholdersEquity" unitRef="usd" decimals="0" id="r4">5</ix:nonFraction></td></tr>
</table></ix:continuation>
<div style="text-align:center">7</div>
<hr style="page-break-after:always"/>
<div>Other text on the next page.</div>
<ix:continuation id="tb-2"><div>Second part <ix:exclude>(not in the fact)</ix:exclude>of the note.</div></ix:continuation>
<div><ix:nonNumeric contextRef="d1" name="dei:EntityRegistrantName" id="n1">Example <ix:exclude>[x]</ix:exclude>Corp</ix:nonNumeric></div>
<div>8</div>
</body></html>
"""


@pytest.fixture
def snippet(tmp_path):
    path = tmp_path / "t.htm"
    path.write_text(SNIPPET, encoding="utf-8")
    return ixbrl.parse(path)


def test_numbers_scale_sign_and_formats(snippet):
    by = snippet.by_id
    assert (by["r1"].shown, by["r1"].value, by["r1"].scale, by["r1"].printed) == (1234.5, 1234.5e6, 6, "1,234.5")
    assert by["r2"].shown == -12 and by["r2"].value == -12e6
    assert by["r3"].nil and by["r3"].shown == 0
    assert by["h2"].hidden and by["h2"].value == 7
    assert ixbrl.parse_number("twelve", "ixt-sec:numwordsen") == (12.0, False)
    assert ixbrl.parse_number("1.234,5", "ixt:num-comma-decimal") == (1234.5, False)
    assert ixbrl.parse_number("no", "ixt-sec:numwordsen") == (0.0, False)


def test_contexts_units_and_text_facts(snippet):
    assert snippet.contexts["i1"].dims == {"us-gaap:StatementEquityComponentsAxis": "us-gaap:RetainedEarningsMember"}
    assert snippet.contexts["i1"].instant and snippet.contexts["i1"].end == "2025-12-31"
    assert snippet.contexts["d1"].start == "2025-01-01"
    assert snippet.units["usd"] == "USD"
    assert snippet.dei("EntityRegistrantName") == "Example Corp"          # ix:exclude left out
    assert snippet.dei("DocumentType") == "10-K"


def test_pages_continuations_and_owned_blocks(snippet):
    assert [(p.no, p.printed) for p in snippet.pages] == [(1, "7"), (2, "8")]
    assert snippet.chain("tb") == ["tb", "tb-1", "tb-2"]
    blocks = snippet.owned_blocks("tb")
    assert [b.page for b in blocks] == [1, 1, 1, 2]
    assert blocks[0].kind == "heading" and blocks[0].text == "Note 3 - Income Taxes"
    assert blocks[2].rows == [["Revenue", "$1,234.5"], ["Loss", "(12)"], ["Nothing", "—"], ["Balance", "5"]]
    assert "Other text" not in " ".join(b.as_text() for b in blocks)
    assert snippet.by_id["r1"].page == 1


def test_merge_cells():
    assert ixbrl.merge_cells(["Margin", "", "41", "%", ""]) == ["Margin", "41%"]
    assert ixbrl.merge_cells(["Cash", "$", "1,000", "", "(", "5", ")"]) == ["Cash", "$1,000", "(5)"]


def test_acceptance_names_what_failed():
    verdict = build.acceptance("ifrs-full", [], [{"type": "balance_sheet"}], [{"value": None}], [])
    assert not verdict["passed"]
    assert "IFRS comes later" in verdict["summary"] and "0 notes found" in verdict["summary"]


def test_not_a_filing(tmp_path):
    (tmp_path / "x.htm").write_text("<html/>", encoding="utf-8")
    assert not filing.is_filing(tmp_path)
    with pytest.raises(filing.FilingError):
        filing.open_filing(tmp_path)


# ---------------------------------------------------------------- Nvidia's 10-K

@pytest.fixture(scope="module")
def nvidia():
    return build.read(NVIDIA)


@needs_nvidia
def test_nvidia_notes(nvidia):
    notes = nvidia.index["sections"]["consolidated"]["notes"]
    assert len(notes) == 18
    assert [n["no"] for n in notes] == list(range(1, 19))
    tax = notes[12]
    assert (tax["no"], tax["title"], tax["start_page"], tax["end_page"]) == (13, "Income Taxes", 72, 76)
    text = nvidia.content["unit_texts"][("consolidated", "C13")]["text"]
    assert text.startswith("=== Note 13 — Income Taxes (Consolidated) ===\n--- PDF page 72 (printed page 72) ---\n"
                           "Note 13 - Income Taxes\n")
    assert "Federal | $19,039 | $14,032 | $5,710" in text
    # the last continuation is there (the note runs over five pages)
    assert "--- PDF page 76" in text and "unrecognized tax benefits" in text
    assert notes[0]["title"] == "Organization and Summary of Significant Accounting Policies"
    assert notes[17]["title"].startswith("Schedule II")


@needs_nvidia
def test_nvidia_statements_and_figures(nvidia):
    statements = nvidia.index["sections"]["consolidated"]["statements"]
    assert [s["type"] for s in statements] == ["profit_loss", "profit_loss", "balance_sheet", "cash_flow", "equity"]
    assert statements[1]["title"] == "Consolidated Statements of Comprehensive Income"
    assert statements[2]["pages"][0]["pdf_page"] == 53
    lines = {l["id"]: l for l in nvidia.content["lines"]}
    values = {(v["line_id"], v["col"]): v for v in nvidia.content["values"]}
    revenue = lines["C-PL-L001"]
    assert (revenue["label"], revenue["concept"]) == ("Revenue", "us-gaap:Revenues")
    first = values[("C-PL-L001", 0)]
    assert (first["raw"], first["value"], first["period_end"], first["period_label"]) == (
        "215,938", 215938.0, "2026-01-25", "FY2026")
    # negated labels print as filed: interest expense (259)
    interest = next(l for l in lines.values() if l["label"] == "Interest expense")
    assert values[(interest["id"], 0)]["raw"] == "(259)"
    # the cash flow statement's opening cash is the year before's closing instant
    opening = next(l for l in lines.values() if l["label"] == "Cash and cash equivalents at beginning of period")
    assert values[(opening["id"], 0)]["raw"] == "8,589"
    assert "Total liabilities and shareholders' equity | 206,803 | 111,601" in statements[2]["text"]
    assert nvidia.content["units"] == "(in millions of U.S. dollars, except per share data)"
    # every figure read
    assert all(v["value"] is not None for v in nvidia.content["values"])
    # the equity statement: one group per component, then the total
    view = nvidia.content["statement_views"][("consolidated", "C-EQ")]
    groups = [r["label"] for r in view["pages"][0]["tables"][0]["rows"] if r["kind"] == "group"]
    assert groups == ["Common Stock Outstanding", "Additional Paid-in Capital",
                      "Accumulated Other Comprehensive Income (Loss)", "Retained Earnings", "Total"]


@needs_nvidia
def test_nvidia_checks_and_links(nvidia):
    checks = nvidia.content["checks"]
    assert checks and all(c["status"] == "ok" for c in checks)
    kinds = {c["kind"] for c in checks}
    assert kinds == {"subtotal", "balance", "carries"}
    gross = next(c for c in checks if c["kind"] == "subtotal" and "'Gross profit'" in c["message"])
    assert "calculation linkbase" in gross["message"]
    assert sum(1 for c in checks if c["kind"] == "balance") == 2
    edges = nvidia.content["edges"]
    tax_line = next(l for l in nvidia.content["lines"] if l["label"] == "Income tax expense")
    tax_edges = [e for e in edges if e["src"] == tax_line["id"]]
    assert [(e["dst"], e["method"], e["confidence"]) for e in tax_edges] == [("C13", "xbrl concept", "high")]
    # a note cited in a label still counts
    commitments = next(l for l in nvidia.content["lines"] if l["label"].startswith("Commitments and contingencies"))
    assert any(e["dst"] == "C12" and e["kind"] == "references" for e in edges if e["src"] == commitments["id"])
    assert any(e["kind"] == "carries" and e["method"] == "same concept" for e in edges)


@needs_nvidia
def test_nvidia_narrative(nvidia):
    narrative = nvidia.content["narrative"]
    titles = [s["title"] for s in narrative["sections"]]
    assert "Item 1A. Risk Factors" in titles and titles[0] == "Front matter"
    risk = next(s for s in narrative["sections"] if s["title"] == "Item 1A. Risk Factors")
    assert (risk["kind"], risk["parent_id"], risk["start_page"]) == ("risk", "N-PART-I", 12)
    assert len(narrative["passages"]) >= 40
    assert any("Risk Factors" in p["path"] for p in narrative["passages"])
    # notes and statements pages stay out of the narrative
    assert 72 not in narrative["pages"] and 53 not in narrative["pages"]


@needs_nvidia
def test_nvidia_page_view():
    html, count = pageview.page_html(NVIDIA, 72)
    assert count == 85 and "Income Taxes" in html and "<script" not in html.lower()
    with pytest.raises(ValueError):
        pageview.page_html(NVIDIA, 86)


# ---------------------------------------------------------------- the app

@pytest.fixture
def xbrl_reports(tmp_path, monkeypatch):
    """A private reports folder with the Nvidia filing (and a PDF of the same name) and cache."""
    folder = tmp_path / "reports"
    folder.mkdir()
    shutil.copytree(NVIDIA, folder / "NVIDIA-10-K-2026")
    (folder / "NVIDIA-10-K-2026.pdf").write_bytes(b"%PDF-1.4 the same report as a PDF")
    (folder / "Other.pdf").write_bytes(b"%PDF-1.4")
    for name, sub in (("REPORTS_DIR", "reports"), ("CACHE_DIR", "cache"), ("HISTORY_DIR", "hist"),
                      ("THREADS_DIR", "threads"), ("ANALYSIS_HISTORY_DIR", "html")):
        monkeypatch.setattr(config, name, tmp_path / sub)
        (tmp_path / sub).mkdir(exist_ok=True)
    monkeypatch.setattr(config, "INPUT_FILE", tmp_path / "in.txt")
    monkeypatch.setattr(config, "OUTPUT_FILE", tmp_path / "out.txt")
    return folder


@needs_nvidia
def test_report_list_prefers_the_filing(xbrl_reports):
    assert [p.name for p in webcommon.list_reports()] == ["NVIDIA-10-K-2026", "Other.pdf"]


@needs_nvidia
def test_zip_filing(xbrl_reports, tmp_path):
    archive = xbrl_reports / "Nvidia-zip.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for item in NVIDIA.iterdir():
            zf.write(item, f"filing/{item.name}")
    assert filing.is_filing(archive)
    fil = filing.open_filing(archive)
    assert fil.main.name == "nvda-20260125.htm" and fil.folder.parent.name == "xbrl"


@needs_nvidia
def test_package_built_once_and_reused(xbrl_reports, monkeypatch):
    path = xbrl_reports / "NVIDIA-10-K-2026"
    built = pipeline.ensure_package(path)
    package = rptpkg.open_package(built)
    assert package.meta["source"] == "xbrl" and package.meta["format"] == "us-10k"
    assert package.meta["schema_version"] == rptpkg.SCHEMA_VERSION
    assert package.meta["pdf_sha256"] == store.pdf_sha256(path)
    assert package.lines("C-PL")[0]["concept"] == "us-gaap:Revenues"
    assert package.page(72)["printed"] == "72"
    assert pipeline.package_status(path)["status"] == "up to date"
    assert any(line.startswith("XBRL: nvda-20260125.htm") for line in package.meta["quality"]["lines_text"])
    calls = []
    monkeypatch.setattr(pipeline, "build_xbrl_package", lambda p: calls.append(p))
    assert pipeline.ensure_package(path) == built and not calls


@needs_nvidia
def test_analyze_flow_on_a_filing(xbrl_reports, monkeypatch):
    sent = []

    def fake_claude(prompt, system, timeout, **kwargs):
        sent.append(prompt)
        if "Reply with ONLY this JSON" in prompt:
            return '{"notes": ["C13"], "reason": "Income taxes"}'
        return "## Summary\n- Tax expense rose."

    monkeypatch.setattr(analyzer_jobs, "run_claude", fake_claude)
    monkeypatch.setattr(note_selector, "run_claude", fake_claude)
    client = app_module.app.test_client()
    reports = client.get("/api/reports").get_json()["reports"]
    assert [(r["name"], r["xbrl"]) for r in reports] == [("NVIDIA-10-K-2026", True), ("Other.pdf", False)]
    idx = client.post("/api/index", json={"report": "NVIDIA-10-K-2026"}).get_json()
    assert idx["sections"]["consolidated"]["count"] == 18
    assert "inline XBRL" in idx["model"]

    q = "Analyze the company's income taxes."
    job = _wait(client, client.post("/api/identify", json={"report": "NVIDIA-10-K-2026", "question": q})
                .get_json()["job_id"])
    assert job["status"] == "done", job
    assert [n["id"] for n in job["result"]["notes"]] == ["C13"]
    job = _wait(client, client.post("/api/analyze", json={
        "report": "NVIDIA-10-K-2026", "question": q, "notes": ["C13"]}).get_json()["job_id"])
    assert job["status"] == "done", job
    prompt = sent[-1]
    assert "Source: the filing's inline XBRL" in prompt
    assert "=== Note 13 — Income Taxes (Consolidated) ===" in prompt
    assert "=== Consolidated Balance Sheets (Consolidated) ===" in prompt
    assert ("- Income tax expense (Consolidated Statements of Income, PDF p.51) | FY2026 21,383 | FY2025 11,146 | "
            "FY2024 4,058 -> Note 13 (same XBRL concept tagged in the note)") in prompt      # LINKED FIGURES
    assert job["result"]["pages"].startswith("72")

    # the Ingest screen's page view serves the filing's HTML, locked down
    page = client.get("/page-image?report=NVIDIA-10-K-2026&page=72")
    assert page.status_code == 200 and "script-src 'none'" in page.headers["Content-Security-Policy"]
    assert b"Income Taxes" in page.data


def _wait(client, job_id):
    for _ in range(400):
        job = client.get(f"/api/jobs/{job_id}").get_json()
        if job["status"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_note_sub_roles_are_not_notes():
    """Travelers names a note's tables "(Table)" and puts text after "(Details)": neither is a note."""
    from ingest.xbrl.roles import SUB_ROLE_RE, base_title
    for title, base in (("Earnings per Share (Table)", "Earnings per Share"),
                        ("Schedule II (Details) - Guarantees", "Schedule II"),
                        ("Income Taxes - Deferred Taxes (Details)", "Income Taxes - Deferred Taxes"),
                        ("Debt (Tables)", "Debt"), ("Organization (Policies)", "Organization")):
        assert SUB_ROLE_RE.search(title) and base_title(title) == base
    assert not SUB_ROLE_RE.search("Debt") and not SUB_ROLE_RE.search("Leases (Tablet)")
