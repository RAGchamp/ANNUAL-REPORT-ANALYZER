"""The XBRL page (/xbrl): download a company's inline XBRL filing from SEC EDGAR into
XBRL-docs\\<TICKER>\\ (ingest/xbrl/edgar.py), see the downloaded filings and ingest them.

  GET  /xbrl, /xbrl.html     the page
  GET  /api/xbrl/folders     the downloaded filings with their package status
  POST /api/xbrl/download    {ticker, link, overwrite} -> a job
  POST /api/xbrl/ingest      {ticker} -> a job: the XBRL route builds its package

A downloaded folder is also listed with the reports (webcommon.list_reports), so the Analyze
screen and the Ingest screen use it like any other report.
"""

import logging
import os
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request

import config
from ingest import pipeline
from ingest.pdf_utils import PdfError
from ingest.xbrl import edgar
from rptpkg import store
from webcommon import UserError, start_job, update_current_job

log = logging.getLogger("app")
bp = Blueprint("xbrl", __name__)


@bp.route("/xbrl")
@bp.route("/xbrl.html")
def xbrl_page():
    return render_template("xbrl.html", docs_dir=str(config.XBRL_DOCS_DIR),
                           custom_agent="SEC_USER_AGENT" in os.environ)


def _folder_row(folder):
    info = edgar.manifest(folder)
    row = {"ticker": folder.name, "company": info.get("company"), "form": info.get("form"),
           "period": info.get("period"), "downloaded_at": info.get("downloaded_at"), "index": info.get("index"),
           "files": [{"name": p.name, "kb": round(p.stat().st_size / 1024)} for p in sorted(folder.iterdir())
                     if p.is_file()],
           "size_mb": round(store.report_size(folder) / 1_048_576, 1), "readable": store.is_xbrl_filing(folder)}
    if row["readable"]:
        status = pipeline.package_status(folder)
        row.update(status=status.get("status"), model=status.get("model"),
                   quality=status.get("quality") or [], ingested_at=status.get("ingested_at"))
    return row


def _folders():
    docs = Path(config.XBRL_DOCS_DIR)
    if not docs.is_dir():
        return []
    return sorted((p for p in docs.iterdir() if p.is_dir() and not p.name.endswith(".partial")),
                  key=lambda p: p.name)


@bp.route("/api/xbrl/folders")
def api_folders():
    return jsonify({"folders": [_folder_row(p) for p in _folders()], "docs_dir": str(config.XBRL_DOCS_DIR)})


def download_job(ticker, link, overwrite):
    try:
        manifest = edgar.download(ticker, link, overwrite, progress=lambda text: update_current_job(progress=text))
    except edgar.EdgarError as exc:
        raise UserError(str(exc))
    log.info("Downloaded %s (%s %s) from %s", manifest["ticker"], manifest.get("form"), manifest.get("period"),
             manifest["index"])
    return _folder_row(Path(config.XBRL_DOCS_DIR) / manifest["ticker"])


@bp.route("/api/xbrl/download", methods=["POST"])
def api_download():
    data = request.get_json(silent=True) or {}
    try:     # check the input now, not in the job
        ticker = edgar.clean_ticker(data.get("ticker"))
        edgar.parse_link(data.get("link"))
    except edgar.EdgarError as exc:
        raise UserError(str(exc))
    overwrite = bool(data.get("overwrite"))
    target = edgar.target_folder(ticker)
    if target.exists() and any(target.iterdir()) and not overwrite:
        raise UserError(f"XBRL-docs\\{ticker} already holds a filing. Tick 'Replace' to download over it.")
    return jsonify({"job_id": start_job("xbrl-download", download_job, ticker, data.get("link"), overwrite)})


def ingest_job(ticker):
    folder = Path(config.XBRL_DOCS_DIR) / ticker
    try:
        pipeline.build_package(folder)
    except PdfError as exc:          # an XBRL filing that fails its acceptance checks
        raise UserError(str(exc))
    return _folder_row(folder)


@bp.route("/api/xbrl/ingest", methods=["POST"])
def api_ingest():
    data = request.get_json(silent=True) or {}
    try:
        ticker = edgar.clean_ticker(data.get("ticker"))
    except edgar.EdgarError as exc:
        raise UserError(str(exc))
    folder = Path(config.XBRL_DOCS_DIR) / ticker
    if not store.is_xbrl_filing(folder):
        raise UserError(f"XBRL-docs\\{ticker} holds no inline XBRL filing.")
    return jsonify({"job_id": start_job("ingest", ingest_job, ticker)})
