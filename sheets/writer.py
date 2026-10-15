"""
sheets/writer.py
----------------
Google Sheets integration.

Responsibilities:
- Create worksheets if they don't exist.
- Read existing job IDs + application statuses + notes from "All Jobs".
- Append only genuinely new jobs (no duplicates).
- Overwrite "Today's Jobs" with this run's newly discovered listings.
- Overwrite "High Match" with all jobs above the score threshold (full list).
- Leave "Application Tracker" untouched except for preserving existing data.
- NEVER print credentials in logs.

Authentication:
  The service account JSON is expected in the environment variable named by
  config["google_sheets"]["credentials_env"].  The sheet ID is in
  config["google_sheets"]["sheet_id_env"].
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Set, Tuple

from core.models import JobListing
from core.date_utils import today_iso

logger = logging.getLogger(__name__)

# Lazy imports so tests can run without gspread installed
try:
    import gspread
    from google.oauth2.service_account import Credentials
    _GSPREAD_AVAILABLE = True
except ImportError:
    _GSPREAD_AVAILABLE = False
    logger.warning("gspread / google-auth not installed — Sheets writer disabled.")

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# Column positions in "All Jobs" (1-indexed, matching JobListing.sheet_headers())
_COL_JOB_ID = 1
_COL_STATUS = 14   # Application Status
_COL_NOTES = 15
_COL_LAST_VERIFIED = 16


def _get_client(config: Dict[str, Any]) -> Optional[Any]:
    """Authenticate and return a gspread client.  Returns None on failure."""
    if not _GSPREAD_AVAILABLE:
        logger.error("gspread not available — cannot connect to Google Sheets.")
        return None

    creds_env = config.get("google_sheets", {}).get("credentials_env", "GOOGLE_SERVICE_ACCOUNT_JSON")
    creds_json = os.environ.get(creds_env, "")
    if not creds_json:
        logger.error("Environment variable '%s' is not set or empty.", creds_env)
        return None

    try:
        creds_data = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_data, scopes=_SCOPES)
        return gspread.authorize(creds)
    except json.JSONDecodeError:
        logger.error("'%s' does not contain valid JSON — check your secret.", creds_env)
    except Exception as exc:
        logger.error("Google authentication failed: %s", exc)
    return None


def _get_or_create_worksheet(spreadsheet: Any, title: str, rows: int = 1000, cols: int = 20) -> Any:
    """Return an existing worksheet or create it."""
    try:
        return spreadsheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        logger.info("Creating worksheet: '%s'", title)
        return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)


def _read_existing_jobs(ws: Any) -> Tuple[Dict[str, Dict], Set[str]]:
    """
    Read all rows from a worksheet.

    Returns:
        (id_to_tracking, seen_ids)
        id_to_tracking: job_id -> {"status": ..., "notes": ..., "last_verified": ...}
        seen_ids: set of job_ids already in the sheet
    """
    try:
        all_values = ws.get_all_values()
    except Exception as exc:
        logger.error("Failed to read existing jobs: %s", exc)
        return {}, set()

    if len(all_values) <= 1:
        return {}, set()

    id_to_tracking: Dict[str, Dict] = {}
    seen_ids: Set[str] = set()

    for row in all_values[1:]:  # skip header
        if not row:
            continue
        job_id = row[_COL_JOB_ID - 1].strip() if len(row) >= _COL_JOB_ID else ""
        if not job_id:
            continue
        seen_ids.add(job_id)
        status = row[_COL_STATUS - 1].strip() if len(row) >= _COL_STATUS else ""
        notes = row[_COL_NOTES - 1].strip() if len(row) >= _COL_NOTES else ""
        last_verified = row[_COL_LAST_VERIFIED - 1].strip() if len(row) >= _COL_LAST_VERIFIED else ""
        id_to_tracking[job_id] = {
            "status": status or "Not Applied",
            "notes": notes,
            "last_verified": last_verified,
        }

    return id_to_tracking, seen_ids


def _apply_preserved_tracking(job: JobListing, tracking: Dict[str, Dict]) -> JobListing:
    """
    Restore application status and notes from the tracking map.
    If the job is new, defaults are left as-is.
    """
    t = tracking.get(job.job_id)
    if t:
        job.application_status = t.get("status") or job.application_status
        job.notes = t.get("notes") or job.notes
        job.last_verified = today_iso()
    return job


def _ensure_header(ws: Any, headers: List[str]) -> None:
    """Write the header row if the sheet is empty."""
    try:
        first_cell = ws.cell(1, 1).value
        if not first_cell:
            ws.update("A1", [headers])
    except Exception as exc:
        logger.error("Failed to write header: %s", exc)


def update_sheets(
    new_jobs: List[JobListing],
    config: Dict[str, Any],
) -> None:
    """
    Main entry point.  Connects to Google Sheets and updates all worksheets.

    Args:
        new_jobs:  Jobs collected and filtered in this run.
        config:    Loaded config.json dict.
    """
    sheet_id_env = config.get("google_sheets", {}).get("sheet_id_env", "GOOGLE_SHEET_ID")
    sheet_id = os.environ.get(sheet_id_env, "")
    if not sheet_id:
        logger.error("Environment variable '%s' not set — cannot update sheets.", sheet_id_env)
        return

    client = _get_client(config)
    if not client:
        return

    try:
        spreadsheet = client.open_by_key(sheet_id)
    except Exception as exc:
        logger.error("Failed to open spreadsheet: %s", exc)
        return

    ws_names = config.get("google_sheets", {}).get("worksheets", {})
    all_jobs_title = ws_names.get("all_jobs", "All Jobs")
    today_title = ws_names.get("today_jobs", "Today's Jobs")
    high_match_title = ws_names.get("high_match", "High Match")
    tracker_title = ws_names.get("tracker", "Application Tracker")
    high_match_threshold = config.get("filters", {}).get("high_match_threshold", 65)

    # ── All Jobs worksheet ────────────────────────────────────────────────────
    ws_all = _get_or_create_worksheet(spreadsheet, all_jobs_title)
    _ensure_header(ws_all, JobListing.sheet_headers())

    tracking, seen_ids = _read_existing_jobs(ws_all)

    truly_new: List[JobListing] = []
    for job in new_jobs:
        job = _apply_preserved_tracking(job, tracking)
        if job.job_id not in seen_ids:
            truly_new.append(job)
            seen_ids.add(job.job_id)

    if truly_new:
        rows = [j.to_sheet_row() for j in truly_new]
        try:
            ws_all.append_rows(rows, value_input_option="USER_ENTERED")
            logger.info("All Jobs: appended %d new rows", len(rows))
        except Exception as exc:
            logger.error("Failed to append to All Jobs: %s", exc)
    else:
        logger.info("All Jobs: no new jobs to append")

    # ── Today's Jobs worksheet ────────────────────────────────────────────────
    ws_today = _get_or_create_worksheet(spreadsheet, today_title)
    headers = JobListing.sheet_headers()
    today_rows = [headers] + [j.to_sheet_row() for j in truly_new]
    try:
        ws_today.clear()
        ws_today.update("A1", today_rows, value_input_option="USER_ENTERED")
        logger.info("Today's Jobs: wrote %d rows", len(today_rows) - 1)
    except Exception as exc:
        logger.error("Failed to update Today's Jobs: %s", exc)

    # ── High Match worksheet ──────────────────────────────────────────────────
    # Show ALL jobs above threshold (from this run), not just today's new ones
    ws_high = _get_or_create_worksheet(spreadsheet, high_match_title)
    high_match_jobs = [j for j in new_jobs if j.match_score >= high_match_threshold]
    high_rows = [headers] + [j.to_sheet_row() for j in high_match_jobs]
    try:
        ws_high.clear()
        ws_high.update("A1", high_rows, value_input_option="USER_ENTERED")
        logger.info("High Match: wrote %d rows (threshold >= %d)", len(high_rows) - 1, high_match_threshold)
    except Exception as exc:
        logger.error("Failed to update High Match: %s", exc)

    # ── Application Tracker worksheet ─────────────────────────────────────────
    # Only create with header if brand new — never overwrite user's data.
    ws_tracker = _get_or_create_worksheet(spreadsheet, tracker_title)
    tracker_headers = [
        "Job ID", "Title", "Company", "Apply URL",
        "Date Applied", "Status", "Interview Stage", "Notes", "Follow-up Date",
    ]
    try:
        if not ws_tracker.cell(1, 1).value:
            ws_tracker.update("A1", [tracker_headers])
            logger.info("Application Tracker: created with headers (user-managed from here)")
    except Exception as exc:
        logger.error("Failed to initialise Application Tracker: %s", exc)

    logger.info("Google Sheets update complete.")
