# Daily DevOps Job Tracker 🚀

Automated job-tracking system that collects current DevOps and related
technical job vacancies across India (prioritising South India), scores
them against your profile, and writes the results to a Google Sheets
spreadsheet every morning.

---

## Table of Contents

1. [Features](#features)
2. [Project Structure](#project-structure)
3. [Job Sources](#job-sources)
4. [Quick Start (Local)](#quick-start-local)
5. [Google Sheets Setup](#google-sheets-setup)
6. [GitHub Repository Setup](#github-repository-setup)
7. [Credential Setup](#credential-setup)
8. [Configuration Reference](#configuration-reference)
9. [How Match Scoring Works](#how-match-scoring-works)
10. [Running Tests](#running-tests)
11. [Troubleshooting](#troubleshooting)
12. [Limitations & Known Issues](#limitations--known-issues)

---

## Features

- **Modular source system** — add new job APIs by dropping a file in `sources/`
- **Rule-based transparent scoring** (0–100) — skill overlap, role relevance, experience match, location priority, posting freshness
- **Four Google Sheets worksheets** — All Jobs, Today's Jobs, High Match, Application Tracker
- **Duplicate prevention** — SHA-256 ID + fuzzy (title, company, location) matching
- **Application status preserved** — existing notes/status never overwritten by re-runs
- **Unknown posting dates handled** — never rejects a job just because the date is missing
- **Partial source failure** — if one API fails, others still run
- **No paid AI API** — pure Python rule-based logic
- **Daily GitHub Actions** — 08:30 IST, with manual trigger support

---

## Project Structure

```
job-tracker/
├── main.py                      # Orchestrator entry point
├── config.json                  # All configuration (edit this)
├── requirements.txt
├── .gitignore
├── core/
│   ├── models.py                # JobListing dataclass
│   ├── date_utils.py            # Date parsing (handles missing dates)
│   ├── normalizer.py            # URL normalisation, HTML stripping
│   ├── deduplicator.py          # Duplicate detection
│   ├── filter.py                # Multi-stage job filter
│   └── scorer.py                # Rule-based match scorer
├── sources/
│   ├── base.py                  # Abstract base class
│   ├── remotive.py              # Remotive API
│   ├── arbeitnow.py             # Arbeitnow API
│   ├── greenhouse.py            # Greenhouse public boards
│   └── lever.py                 # Lever public boards
├── sheets/
│   └── writer.py                # Google Sheets read/write
├── tests/
│   ├── test_date_utils.py
│   ├── test_normalizer.py
│   ├── test_deduplicator.py
│   ├── test_filter.py
│   ├── test_scorer.py
│   ├── test_sources.py          # Mocked API tests
│   └── test_sheets_writer.py   # Mocked Sheets tests
└── .github/
    └── workflows/
        └── job_tracker.yml
```

---

## Job Sources

| Source | Auth | India Coverage | Notes |
|---|---|---|---|
| **Remotive** | None | Remote-worldwide | Filters for non-region-exclusive remote roles |
| **Arbeitnow** | None | Remote-worldwide | Europe-focused; accepts "worldwide" roles |
| **Greenhouse** | None | Company-specific | Configure which Indian companies to scan |
| **Lever** | None | Company-specific | Configure which Indian companies to scan |

> [!NOTE]
> No free API provides a comprehensive India-specific DevOps job feed.
> The system collects what is legitimately accessible and scores results
> by India / remote eligibility. All job data is real — no fake listings.

### Adding a New Source

1. Create `sources/my_source.py` inheriting from `BaseSource`.
2. Implement `fetch() -> List[JobListing]`.
3. Add your class to `ALL_SOURCES` in `sources/__init__.py`.
4. Add configuration under `"sources": {"my_source": {...}}` in `config.json`.

---

## Quick Start (Local)

```bash
# 1. Clone / navigate to the project
cd job-tracker

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Export credentials (see Credential Setup)
export GOOGLE_SHEET_ID="your_sheet_id_here"
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'

# 5. Run
python main.py
```

---

## Google Sheets Setup

### Step 1 — Create the Spreadsheet

1. Go to [sheets.google.com](https://sheets.google.com) and create a new spreadsheet.
2. Name it: **DevOps Job Tracker**.
3. Copy the **Sheet ID** from the URL:
   `https://docs.google.com/spreadsheets/d/**<SHEET_ID>**/edit`

### Step 2 — Enable the Google Sheets API

1. Go to [console.cloud.google.com](https://console.cloud.google.com).
2. Create a new project (or use an existing one).
3. Enable **Google Sheets API**: APIs & Services → Library → search "Google Sheets API" → Enable.
4. Enable **Google Drive API** in the same way.

### Step 3 — Create a Service Account

1. APIs & Services → Credentials → Create Credentials → Service Account.
2. Name it `job-tracker-bot`, click Create.
3. Skip optional fields, click Done.
4. Click the service account email → Keys → Add Key → Create new key → JSON.
5. Download the JSON file. **Keep this secret — never commit it.**

### Step 4 — Share the Spreadsheet

1. Open the downloaded JSON. Copy the `client_email` value.
2. Open your Google Sheet → Share → paste the service account email.
3. Grant **Editor** access.

### Step 5 — Worksheets

The script auto-creates these worksheets on first run:
- **All Jobs** — full history of every collected job
- **Today's Jobs** — only jobs discovered in the current run
- **High Match** — all jobs with score ≥ threshold (default 65)
- **Application Tracker** — your personal application log (never overwritten)

---

## GitHub Repository Setup

```bash
# Initialise git (if not already done)
git init
git add .
git commit -m "Initial job tracker setup"

# Create a GitHub repository and push
git remote add origin https://github.com/YOUR_USERNAME/devops-job-tracker.git
git branch -M main
git push -u origin main
```

---

## Credential Setup

### GitHub Secrets (for Actions)

1. Go to your GitHub repository → Settings → Secrets and Variables → Actions.
2. Add the following **Repository Secrets**:

| Secret Name | Value |
|---|---|
| `GOOGLE_SHEET_ID` | The Sheet ID from the URL |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | The entire contents of the service account JSON file |

> [!CAUTION]
> Never paste credentials into `config.json`, source code, or comments.
> Never commit the service account JSON file.
> The `.gitignore` already excludes `service-account*.json` and `credentials*.json`.

### Local Development

```bash
export GOOGLE_SHEET_ID="1BxiMV..."
export GOOGLE_SERVICE_ACCOUNT_JSON="$(cat /path/to/service-account.json)"
```

---

## Configuration Reference

Edit `config.json` to customise the tracker.

| Key | Description |
|---|---|
| `user_profile.years_experience` | Your years of experience (affects scoring) |
| `user_profile.skills` | Your skills list (drives skill-overlap score) |
| `job_titles` | Job titles to search for |
| `locations.priority` | South India cities (score = "High") |
| `filters.max_listing_age_days` | Ignore jobs older than this |
| `filters.high_match_threshold` | Min score for "High Match" sheet (0–100) |
| `filters.exclude_keywords` | Titles/descriptions that auto-exclude |
| `scoring.weights` | Weight of each scoring component |
| `sources.*.enabled` | Enable/disable each source |
| `sources.greenhouse.company_boards` | List of Greenhouse company slugs |
| `sources.lever.company_boards` | List of Lever company slugs |

---

## How Match Scoring Works

Scores are **rule-based** (0–100). This is NOT an AI prediction.

| Component | Max Points | How calculated |
|---|---|---|
| Skill overlap | 40 | (matched skills / total user skills) × 40 |
| Role relevance | 25 | Primary role (DevOps/SRE/Cloud) = 25; secondary = ~17; tangential = ~7 |
| Experience match | 15 | Meets requirement = 15; slightly below = 9; significantly below = 0 |
| Location priority | 15 | High (South India) = 15; Remote = ~13; Medium (other India) = 9; Low = 1 |
| Posting freshness | 5 | ≤3d = 5; ≤7d = 4; ≤14d = 3; ≤30d = 1; Unknown = 3 |

Each job's `Match Reason` column contains a human-readable breakdown.

---

## Running Tests

```bash
cd job-tracker
python -m pytest tests/ -v
```

Tests do **not** require real Google credentials or network access.
All API calls are mocked.

---

## Troubleshooting

### "GOOGLE_SHEET_ID not set"
Set the environment variable (see Credential Setup above).

### "GOOGLE_SERVICE_ACCOUNT_JSON is not set or empty"
Export the service account JSON as an environment variable.

### "gspread not available"
Run `pip install -r requirements.txt`.

### "Failed to open spreadsheet"
Ensure the service account email has been shared on the Google Sheet as Editor.

### GitHub Actions not running
- Check the workflow file path: `.github/workflows/job_tracker.yml`
- Verify that Actions is enabled in repo Settings → Actions → General.
- Verify the two secrets are set under Settings → Secrets → Actions.

### All sources return 0 jobs
- Check network / DNS from your environment.
- Try running a single source in isolation:
  ```python
  from sources.remotive import RemotiveSource
  import json
  config = json.load(open("config.json"))
  print(RemotiveSource(config).fetch())
  ```

### Job dates show "Unknown"
This is normal for sources that don't provide a posting date.
Unknown-date jobs are **not rejected** — they are included and given a
neutral freshness score.

---

## Limitations & Known Issues

1. **No India-specific job board API**: No free public API provides a
   comprehensive India-only DevOps feed. Remotive and Arbeitnow are
   global/remote-first boards filtered by India eligibility.

2. **Greenhouse / Lever coverage depends on configured companies**:
   Only companies explicitly listed in `config.json` are scanned.
   Expand the lists as needed.

3. **Rate limits**: Public APIs may throttle or block repeated requests.
   The `rate_limit_seconds` config helps, but a sudden blocking will
   cause a source to return 0 jobs for that run.

4. **Job listings change**: A job that was open when discovered may be
   closed by the time you apply. Always verify the `Apply URL` before
   submitting.

5. **Score is advisory only**: The match score is a rule-based estimate.
   Always read the full job description before applying.
