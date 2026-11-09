"""The filing's linkbases (INFO/XBRL-ROUTE.md §5): presentation trees, calculation
arcs, labels and role titles.

Presentation trees are built over the locators, not the concepts: one concept can
sit twice in a role (shareholders' equity at the start and at the end of the
equity statement), each time with its own preferred label.
"""

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field

LINK = "http://www.xbrl.org/2003/linkbase"
XLINK = "http://www.w3.org/1999/xlink"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

LABEL = "http://www.xbrl.org/2003/role/label"
TERSE = "http://www.xbrl.org/2003/role/terseLabel"
VERBOSE = "http://www.xbrl.org/2003/role/verboseLabel"
TOTAL = "http://www.xbrl.org/2003/role/totalLabel"
PERIOD_START = "http://www.xbrl.org/2003/role/periodStartLabel"
PERIOD_END = "http://www.xbrl.org/2003/role/periodEndLabel"
NEGATED_SUFFIXES = ("negatedLabel", "negatedTerseLabel", "negatedTotalLabel", "negatedPeriodStartLabel",
                    "negatedPeriodEndLabel", "negatedNetLabel")
ROLE_DEF_RE = re.compile(r"^\s*(\d+)\s*-\s*(Statement|Disclosure|Document|Schedule)\s*-\s*(.+?)\s*$", re.I)


def _x(name):
    return f"{{{XLINK}}}{name}"


def concept_of(href):
    """"…us-gaap-2025.xsd#us-gaap_Revenues" -> "us-gaap:Revenues"."""
    fragment = href.rsplit("#", 1)[-1]
    prefix, _, name = fragment.partition("_")
    return f"{prefix}:{name}" if name else fragment


def is_negated(label_role):
    return bool(label_role) and label_role.rsplit("/", 1)[-1] in NEGATED_SUFFIXES


@dataclass
class Node:
    concept: str
    label_role: str | None = None     # the preferred label
    order: float = 0.0
    children: list = field(default_factory=list)


@dataclass
class Role:
    uri: str
    sort: str = ""                    # "9952170"
    category: str = ""                # Statement | Disclosure | Document
    title: str = ""                   # "Income Taxes", "Income Taxes - Deferred Taxes (Details)"
    roots: list = field(default_factory=list)      # [Node]

    def concepts(self):
        out, stack = [], list(self.roots)
        while stack:
            node = stack.pop()
            out.append(node.concept)
            stack.extend(node.children)
        return out


@dataclass
class Linkbases:
    roles: dict                       # uri -> Role (presentation), in sort order
    calc: dict                        # uri -> {parent concept: [(child concept, weight)]}
    labels: dict                      # concept -> {label role: text}

    def label(self, concept, role=None):
        found = self.labels.get(concept, {})
        for candidate in (role, TERSE, LABEL, VERBOSE):
            if candidate and found.get(candidate):
                return found[candidate]
        name = concept.split(":")[-1]
        return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)


def _role_titles(xsd_path):
    titles = {}
    if not xsd_path:
        return titles
    root = ET.parse(xsd_path).getroot()
    for rt in root.iter(f"{{{LINK}}}roleType"):
        definition = (rt.findtext(f"{{{LINK}}}definition") or "").strip()
        match = ROLE_DEF_RE.match(definition)
        if match:
            titles[rt.get("roleURI")] = (match.group(1), match.group(2).capitalize(), match.group(3))
        else:
            titles[rt.get("roleURI")] = ("", "", definition)
    return titles


def _arcs(link, arc_tag):
    locs = {loc.get(_x("label")): concept_of(loc.get(_x("href")))
            for loc in link.iter(f"{{{LINK}}}loc")}
    arcs = [arc for arc in link.iter(f"{{{LINK}}}{arc_tag}")]
    return locs, arcs


def _presentation(pre_path, titles):
    roles = {}
    root = ET.parse(pre_path).getroot()
    for link in root.iter(f"{{{LINK}}}presentationLink"):
        uri = link.get(_x("role"))
        locs, arcs = _arcs(link, "presentationArc")
        nodes = {label: Node(concept) for label, concept in locs.items()}
        is_child = set()
        for arc in arcs:
            parent, child = nodes.get(arc.get(_x("from"))), nodes.get(arc.get(_x("to")))
            if parent is None or child is None:
                continue
            child.order = float(arc.get("order") or 0)
            child.label_role = arc.get("preferredLabel")
            parent.children.append(child)
            is_child.add(arc.get(_x("to")))
        for node in nodes.values():
            node.children.sort(key=lambda n: n.order)
        sort, category, title = titles.get(uri, ("", "", uri.rsplit("/", 1)[-1]))
        role = roles.get(uri) or Role(uri=uri, sort=sort, category=category, title=title)
        # a role can be split over several presentationLink elements
        role.roots += [n for label, n in nodes.items() if label not in is_child and n.children]
        roles[uri] = role
    return dict(sorted(roles.items(), key=lambda kv: (kv[1].sort or "9999999", kv[1].title)))


def _calculation(cal_path):
    calc = defaultdict(lambda: defaultdict(list))
    if not cal_path:
        return {}
    root = ET.parse(cal_path).getroot()
    for link in root.iter(f"{{{LINK}}}calculationLink"):
        uri = link.get(_x("role"))
        locs, arcs = _arcs(link, "calculationArc")
        for arc in sorted(arcs, key=lambda a: float(a.get("order") or 0)):
            parent, child = locs.get(arc.get(_x("from"))), locs.get(arc.get(_x("to")))
            if parent and child:
                calc[uri][parent].append((child, float(arc.get("weight") or 1)))
    return {uri: dict(v) for uri, v in calc.items()}


def _labels(lab_path):
    labels = defaultdict(dict)
    if not lab_path:
        return {}
    root = ET.parse(lab_path).getroot()
    for link in root.iter(f"{{{LINK}}}labelLink"):
        locs = {loc.get(_x("label")): concept_of(loc.get(_x("href"))) for loc in link.iter(f"{{{LINK}}}loc")}
        resources = defaultdict(list)
        for res in link.iter(f"{{{LINK}}}label"):
            lang = res.get(XML_LANG) or "en"
            if not lang.lower().startswith("en"):
                continue
            resources[res.get(_x("label"))].append((res.get(_x("role")) or LABEL, " ".join((res.text or "").split())))
        for arc in link.iter(f"{{{LINK}}}labelArc"):
            concept = locs.get(arc.get(_x("from")))
            for role, text in resources.get(arc.get(_x("to")), []):
                if concept and text:
                    labels[concept].setdefault(role, text)
    return dict(labels)


def load(filing):
    titles = _role_titles(filing.schema)
    return Linkbases(roles=_presentation(filing.pre, titles), calc=_calculation(filing.cal),
                     labels=_labels(filing.lab))
