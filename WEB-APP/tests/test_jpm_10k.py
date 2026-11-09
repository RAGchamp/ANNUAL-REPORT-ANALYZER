"""TYPE-9: a US Form 10-K typeset like an annual report (JPMorgan Chase 2025), read
with the us-10k-two-column profile: two text columns, "Note 12 – Loans" headings,
the notes' running header on left-hand pages only, and a bank balance sheet whose
captions wrap with amounts in them and that ends with a table of its VIEs."""

import pytest

import config
from ingest import model_testing, pipeline, profiles

JPM = config.MODEL_DOCS_DIR / "TYPE-9-USA-10-K-2025-JPMorgan.pdf"


@pytest.fixture(scope="module")
def jpm():
    if not JPM.exists():
        pytest.skip(f"Model document not found: {JPM}")
    return pipeline.open_report(JPM)


def test_matched_to_its_own_model(jpm):
    meta = jpm.meta
    assert meta["model"] == "TYPE-9-USA-10-K-2025-JPMorgan" and meta["profile"] == "us-10k-two-column"
    assert meta["format"] == "us-10k"
    assert jpm.index["company"] == "JPMorgan Chase & Co."      # from the auditor's addressee line


def test_notes(jpm):
    section = jpm.index["sections"]["consolidated"]
    notes = section["notes"]
    assert [n["no"] for n in notes] == list(range(1, 35))
    # the contents page (p.45) lists the notes heading but is not a notes page
    assert (section["first_page"], section["last_page"], section["page_count"]) == (172, 316, 145)
    taxes = notes[24]
    assert (taxes["title"], taxes["start_page"], taxes["end_page"], taxes["printed_pages"]) == \
        ("Income taxes", 290, 293, "288-291")
    # headings wrap onto a second line in the same column
    assert notes[7]["title"] == "Pension and other postretirement employee benefit plans"
    assert notes[25]["title"] == "Restricted cash, other restricted assets and intercompany funds transfers"
    # two notes share p.279, one per column
    assert [(n["no"], n["title"], n["start_page"], n["end_page"]) for n in notes[15:17]] == \
        [(16, "Premises and equipment", 279, 279), (17, "Deposits", 279, 279)]


def test_statements(jpm):
    statements = jpm.index["sections"]["consolidated"]["statements"]
    pages = {s["type"]: [p["pdf_page"] for p in s["pages"]] for s in statements}
    assert pages == {"profit_loss": [167, 168], "balance_sheet": [169], "cash_flow": [171], "equity": [170]}
    printed = {s["type"]: [p["printed"] for p in s["pages"]] for s in statements}
    assert printed["balance_sheet"] == ["167"]          # from "JPMorgan Chase & Co./2025 Form 10-K  167"


def test_balance_sheet_captions_and_balance(jpm):
    lines = jpm.lines("C-BS")
    loans = next(ln for ln in lines if ln["label"].startswith("Loans (included"))
    assert loans["label"] == "Loans (included $70,684 and $41,350 at fair value)"
    assert [(v["raw"], v["period_label"]) for v in jpm.values(loans["id"])] == \
        [("1,493,429", "FY2025"), ("1,347,988", "FY2024")]
    afs = next(ln for ln in lines if ln["label"].startswith("Available-for-sale"))
    assert afs["label"].endswith("$7,735 and $10,162)")       # the caption's second line stays in it
    balance = [c for c in jpm.checks() if c["kind"] == "balance"]
    assert len(balance) == 2 and all(c["status"] == "ok" for c in balance)   # not the VIE table's total


def test_income_tax_line_links_to_note_25(jpm):
    line = next(ln for ln in jpm.lines("C-PL") if ln["label"] == "Income tax expense")
    assert [(v["raw"], v["period_label"]) for v in jpm.values(line["id"])][:2] == \
        [("15,547", "FY2025"), ("16,610", "FY2024")]
    assert "C25" in {e["dst"] for e in jpm.edges(src=line["id"])}


def test_two_columns_read_in_order(jpm):
    text = jpm.unit_text("consolidated", "C25")["text"]
    # the left column's paragraph is whole, and the right column follows it
    assert "Due to the inherent complexities arising from the\nnature of the Firm’s businesses" in text
    assert text.index("based on the tax rates that the Firm expects") < text.index("Effective tax rate and expense")
    # tables set side by side, one per column, stay apart
    assert "U.S. federal | $ 3,109 $ 7,091 $ 8,973\n" in text


def test_last_body_lines_are_kept(jpm):
    # the old footer rule cut every row in the bottom 10% of the page (p.176 ends at y=726)
    assert "based on factors that a relevant market participant" in jpm.unit_text("consolidated", "C2")["text"]


def test_other_10k_rules_do_not_read_it():
    if not JPM.exists():
        pytest.skip(f"Model document not found: {JPM}")
    from ingest import notes_index
    profile = profiles.get("us-10k-edgar")
    with profiles.using(profile):
        index = notes_index.build_index(JPM, profile=profile)
    assert not any(s["notes"] for s in index["sections"].values())


def test_model_testing_page(jpm):
    result = model_testing.extract_page(JPM, 290)
    assert result["extracted"]["source"] == "package" and result["notices"] == []
    assert [u["id"] for u in result["extracted"]["units_on_page"] if u["starts_here"]] == ["C25"]
