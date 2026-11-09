"""Find an inline XBRL filing's files (INFO/XBRL-ROUTE.md §4).

A filing reaches the app as a folder under Annual-reports\\ (the files as
downloaded from EDGAR: "Download all files"), or as a .zip of them. It is
recognised by one main .htm with an `ix:header` plus a presentation linkbase
(`*_pre.xml`). A zip is unpacked once into the cache, keyed by its SHA-256.

The package key is the SHA-256 of the folder's filing files (rptpkg.store),
or of the zip itself.
"""

import zipfile
from dataclasses import dataclass
from pathlib import Path

import config
from rptpkg import store

IX_MARK = b"ix:header"
HEAD_BYTES = 200_000          # the ix:header sits at the top of the body


class FilingError(Exception):
    """The folder or zip is not an inline XBRL filing the app can read."""


@dataclass
class Filing:
    source: Path              # what the user picked: the folder or the .zip
    folder: Path              # where the files are (the unpacked zip for a .zip)
    main: Path                # the inline XBRL document
    schema: Path | None
    pre: Path | None
    cal: Path | None
    lab: Path | None
    defn: Path | None

    @property
    def name(self):
        return self.source.name


def _has_ix_header(path):
    try:
        with open(path, "rb") as handle:
            return IX_MARK in handle.read(HEAD_BYTES)
    except OSError:
        return False


def is_filing(path):
    """A folder or .zip that holds an inline XBRL filing (cheap: names and the first bytes only)."""
    return store.is_xbrl_filing(path)


def _unpacked(zip_path):
    """The zip's files, unpacked once into the cache (keyed by its hash)."""
    sha = store.pdf_sha256(zip_path)
    target = Path(config.CACHE_DIR) / "xbrl" / f"{zip_path.stem}-{sha[:16]}"
    if not (target / ".done").exists():
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                name = Path(info.filename).name          # flat: no paths from the archive are trusted
                if info.is_dir() or not name or name.startswith("."):
                    continue
                if not name.lower().endswith((".htm", ".html", ".xhtml", ".xsd", ".xml")):
                    continue
                (target / name).write_bytes(zf.read(info))
        (target / ".done").write_text(sha, encoding="utf-8")
    return target


def _one(folder, pattern):
    found = sorted(folder.glob(pattern))
    return found[0] if found else None


def open_filing(path):
    """The Filing at this folder or zip (FilingError if it is not one)."""
    source = Path(path)
    folder = _unpacked(source) if source.is_file() else source
    candidates = [p for p in folder.iterdir()
                  if p.suffix.lower() in (".htm", ".html", ".xhtml") and _has_ix_header(p)]
    if not candidates:
        raise FilingError(f"{source.name}: no inline XBRL document (an .htm with ix:header) found")
    main = max(candidates, key=lambda p: p.stat().st_size)       # exhibits can carry a few tags too
    pre = _one(folder, "*_pre.xml")
    if pre is None:
        raise FilingError(f"{source.name}: the presentation linkbase (*_pre.xml) is missing")
    return Filing(source=source, folder=folder, main=main, schema=_one(folder, "*.xsd"), pre=pre,
                  cal=_one(folder, "*_cal.xml"), lab=_one(folder, "*_lab.xml"), defn=_one(folder, "*_def.xml"))
