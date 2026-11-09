"""The XBRL route (INFO/XBRL-ROUTE.md): an inline XBRL filing -> report package.

A 10-K / 20-F / 40-F filed on EDGAR since 2019-2021 is an XHTML document in
which every statement figure is a tagged fact and every note one tagged text
block. Nothing here needs layout rules: the structure is in the filing.

    filing.py      find the main document and the linkbases (folder or .zip); the package key
    ixbrl.py       contexts, units, facts; the document as pages of blocks
    linkbase.py    presentation trees, calculation arcs, labels, role titles
    roles.py       which role is which statement / note / details table
    notes.py       one unit per note (its text block, continuations joined)
    statements.py  the statements from their presentation trees: views, lines, values
    checks.py      subtotals from the calculation linkbase, balance, carries
    links.py       statement line -> note through the note's Details roles
    narrative.py   Items 1-15, MD&A, risk factors ... as sections, blocks and passages
    build.py       all of it -> the index and content the package writer takes

The package it writes is the same as the PDF route's (plus meta "source": "xbrl"
and the lines' concepts), so the analyzer needs no change.
"""

XBRL_VERSION = 3        # 2: running-header Items (HIG). 3: "(Table)" sub-roles (TRV). Bump when what the XBRL route puts into a package changes
