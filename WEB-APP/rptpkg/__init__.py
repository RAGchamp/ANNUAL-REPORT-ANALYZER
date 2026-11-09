"""Report packages: the file between the ingester and the analyzer
(INFO/SPLIT-FUNCTIONALITY-PLAN.md §5).

SCHEMA_VERSION is "major.minor". A different major version means the
analyzer can't read the package and the report must be re-ingested; a minor
bump only adds optional tables or columns.
"""

SCHEMA_VERSION = "1.3"      # 1.1: doc_sections, narrative_pages, page_blocks; 1.2: doc_passages;
                            # 1.3: lines.concept, meta "source" (INFO/XBRL-ROUTE.md)

from rptpkg.reader import Package, PackageError, open_package  # noqa: E402

__all__ = ["SCHEMA_VERSION", "Package", "PackageError", "open_package"]
