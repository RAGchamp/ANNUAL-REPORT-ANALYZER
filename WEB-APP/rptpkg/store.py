"""Where report packages live, and which package belongs to which PDF.

Packages are kept in the app cache (INFO/SPLIT-FUNCTIONALITY-PLAN.md, Q3):
<CACHE_DIR>/packages/<pdf stem>-<first 16 hex of the PDF's SHA-256>.rptpkg.db.
The hash in the name means a renamed or copied PDF still finds its package,
and a PDF whose content changed gets a new one.
"""

import hashlib
import re
import threading
import zipfile
from pathlib import Path

import config

SUFFIX = ".rptpkg.db"
_hashes = {}
_hash_lock = threading.Lock()


def packages_dir():
    folder = Path(config.CACHE_DIR) / "packages"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


FILING_SUFFIXES = (".htm", ".html", ".xhtml", ".xsd", ".xml")
IX_MARK = b"ix:header"


def is_xbrl_filing(path):
    """A folder (or .zip) holding an inline XBRL filing: a presentation linkbase (*_pre.xml)
    and an .htm with an ix:header (INFO/XBRL-ROUTE.md §4). Cheap: names and first bytes only.
    It lives here because both the report list (webcommon) and the ingester need it."""
    path = Path(path)
    try:
        if path.is_dir():
            if not any(path.glob("*_pre.xml")):
                return False
            for item in path.iterdir():
                if item.suffix.lower() in (".htm", ".html", ".xhtml"):
                    with open(item, "rb") as handle:
                        if IX_MARK in handle.read(200_000):
                            return True
            return False
        if path.is_file() and path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as zf:
                names = [n.lower() for n in zf.namelist()]
            return any(n.endswith("_pre.xml") for n in names) and any(
                n.endswith((".htm", ".html", ".xhtml")) for n in names)
    except (OSError, ValueError, zipfile.BadZipFile):        # unreadable, or a damaged zip
        return False
    return False


def report_size(path):
    """Bytes of a report: the PDF / zip, or a filing folder's files."""
    path = Path(path)
    if path.is_dir():
        return sum(p.stat().st_size for p in path.iterdir() if p.is_file())
    return path.stat().st_size


def _folder_sha256(folder):
    """An XBRL filing folder (INFO/XBRL-ROUTE.md §4): the SHA-256 over its filing files'
    names and contents, in name order (images and other files don't count)."""
    digest = hashlib.sha256()
    for path in sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in FILING_SUFFIXES):
        digest.update(path.name.encode("utf-8") + b"\0")
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
    return digest.hexdigest()


def _folder_stamp(folder):
    return tuple((p.name, p.stat().st_size, p.stat().st_mtime) for p in sorted(folder.iterdir())
                 if p.is_file() and p.suffix.lower() in FILING_SUFFIXES)


def pdf_sha256(pdf_path):
    """SHA-256 of the PDF (or of an XBRL filing folder), remembered while its size and
    mtime are unchanged."""
    pdf_path = Path(pdf_path)
    if pdf_path.is_dir():
        key = (str(pdf_path.resolve()), _folder_stamp(pdf_path))
        with _hash_lock:
            if key not in _hashes:
                _hashes[key] = _folder_sha256(pdf_path)
            return _hashes[key]
    stat = pdf_path.stat()
    key = (str(pdf_path.resolve()), stat.st_size, stat.st_mtime)
    with _hash_lock:
        if key in _hashes:
            return _hashes[key]
    digest = hashlib.sha256()
    with open(pdf_path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    with _hash_lock:
        _hashes[key] = digest.hexdigest()
    return _hashes[key]


def package_path(pdf_path, sha=None):
    """Where this PDF's package is (or will be) written."""
    pdf_path = Path(pdf_path)
    sha = sha or pdf_sha256(pdf_path)
    return packages_dir() / f"{pdf_path.stem}-{sha[:16]}{SUFFIX}"


def find_package(pdf_path):
    """This PDF's package, also under another file name; None if not ingested."""
    sha = pdf_sha256(pdf_path)
    own = package_path(pdf_path, sha)
    if own.exists():
        return own
    return next(iter(sorted(packages_dir().glob(f"*-{sha[:16]}{SUFFIX}"))), None)


def other_versions(pdf_path, keep):
    """Older packages of a PDF with this name (its content has changed since)."""
    name_re = re.compile(re.escape(Path(pdf_path).stem) + r"-[0-9a-f]{16}" + re.escape(SUFFIX))
    return [p for p in packages_dir().glob(f"{Path(pdf_path).stem}-*{SUFFIX}")
            if p != keep and name_re.fullmatch(p.name)]
