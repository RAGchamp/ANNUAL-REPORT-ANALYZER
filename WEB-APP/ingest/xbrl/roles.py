"""Which role is which (INFO/XBRL-ROUTE.md §5): the statements, the notes, and each
note's Tables / Details / Policies roles.

Statements are classified by the concepts in their presentation tree (the
standard taxonomy's names are the same for every filer); the role title is
only a hint. Notes are the *Disclosure* roles that hold a `…TextBlock` and are
not a note's Tables / Details / Policies role.
"""

import re
from dataclasses import dataclass, field

# a note's sub-role: "(Tables)", "(Table)" (Travelers), "(Details)", "(Policies)" ..., also with text after it:
# "Schedule II (Details) - Guarantees" (Travelers). Everything from the marker on is not part of the note's title.
SUB_ROLE_RE = re.compile(r"\s*\((?:Tables?|Details|Policies|Narrative|Parenthetical)\b[^)]*\).*$", re.I)
STRUCTURE_SUFFIXES = ("Table", "Axis", "Domain", "Member", "LineItems")

# local names, us-gaap and ifrs-full
BS_CONCEPTS = {"Assets", "LiabilitiesAndStockholdersEquity", "EquityAndLiabilities", "Liabilities"}
CF_CONCEPTS = {"NetCashProvidedByUsedInOperatingActivities", "CashFlowsFromUsedInOperatingActivities",
               "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
               "CashAndCashEquivalentsPeriodIncreaseDecrease", "IncreaseDecreaseInCashAndCashEquivalents"}
PL_CONCEPTS = {"EarningsPerShareBasic", "EarningsPerShareDiluted", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
               "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
               "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenue", "ProfitLoss",
               "BasicEarningsLossPerShare", "ProfitLossBeforeTax", "IncomeTaxExpenseBenefit", "IncomeTaxExpenseContinuingOperations"}
OCI_CONCEPTS = {"ComprehensiveIncomeNetOfTax", "ComprehensiveIncome", "OtherComprehensiveIncomeLossNetOfTax",
                "OtherComprehensiveIncome"}
EQUITY_AXIS = {"StatementEquityComponentsAxis", "ComponentsOfEquityAxis"}

STATEMENT_ORDER = ("profit_loss", "comprehensive", "balance_sheet", "equity", "cash_flow")


def local_name(concept):
    return concept.split(":")[-1]


def is_structure(concept):
    return local_name(concept).endswith(STRUCTURE_SUFFIXES)


def statement_type(role):
    """profit_loss | comprehensive | balance_sheet | cash_flow | equity | None."""
    names = {local_name(c) for c in role.concepts()}
    title = role.title.lower()
    if names & EQUITY_AXIS and ("equity" in title or "stockholders" in title or "shareholders" in title):
        return "equity"
    if "equity" in title and not names & BS_CONCEPTS and not names & CF_CONCEPTS:
        return "equity"
    if names & CF_CONCEPTS or "cash flow" in title:
        return "cash_flow"
    if names & BS_CONCEPTS or re.search(r"balance sheet|financial position|financial condition", title):
        return "balance_sheet"
    if names & PL_CONCEPTS:
        return "profit_loss"
    if names & OCI_CONCEPTS or "comprehensive" in title:
        return "comprehensive"
    if re.search(r"\b(income|operations|earnings|profit or loss)\b", title):
        return "profit_loss"
    return None


def base_title(title):
    """"Income Taxes - Deferred Taxes (Details)" -> "Income Taxes - Deferred Taxes"; "Schedule II (Details) -
    Guarantees" -> "Schedule II"."""
    return SUB_ROLE_RE.sub("", title).strip()


@dataclass
class Classified:
    statements: dict = field(default_factory=dict)     # type -> Role (the first of each type)
    notes: list = field(default_factory=list)          # [(Role, text-block concept)] in filing order
    details: dict = field(default_factory=dict)        # note role uri -> [Role] (Tables / Details / Policies)
    parenthetical: dict = field(default_factory=dict)  # statement type -> Role


def _text_block(role):
    return next((c for c in role.concepts() if local_name(c).endswith("TextBlock")), None)


def classify(lb):
    out = Classified()
    subs = []
    for role in lb.roles.values():
        category = role.category.lower()
        if category == "statement":
            kind = statement_type(role)
            if kind is None:
                continue
            if "parenthetical" in role.title.lower():
                out.parenthetical.setdefault(kind, role)
            else:
                out.statements.setdefault(kind, role)
        elif category in ("disclosure", "schedule"):
            if SUB_ROLE_RE.search(role.title):
                subs.append(role)
                continue
            block = _text_block(role)
            if block:
                out.notes.append((role, block))
    # each Tables / Details / Policies role belongs to the note whose title starts its own
    titles = sorted(((base_title(r.title).lower(), r) for r, _ in out.notes), key=lambda t: -len(t[0]))
    for sub in subs:
        name = base_title(sub.title).lower()
        owner = next((r for t, r in titles if name == t), None) or next(
            (r for t, r in titles if name.startswith(t + " ") or name.startswith(t + " -")), None)
        if owner is not None:
            out.details.setdefault(owner.uri, []).append(sub)
    if "profit_loss" not in out.statements and "comprehensive" in out.statements:
        out.statements["profit_loss"] = out.statements.pop("comprehensive")
    return out
