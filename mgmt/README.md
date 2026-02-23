# mgmt — Project Management Tools

Scripts and generated artifacts for tracking Jinkies issues and burndown progress.

## Scripts

| Script | Output | Dependency |
|---|---|---|
| `gen_issues_pdf.py` | `jinkies-issues.pdf` | `fpdf2` |
| `gen_issues_xlsx.py` | `jinkies-issues.xlsx` | `openpyxl` |

Both scripts fetch live data from GitHub via `gh api` and output to this directory.

## Usage

```bash
# One-time setup
python -m venv .venv && .venv/bin/pip install fpdf2 openpyxl

# Regenerate reports
.venv/bin/python mgmt/gen_issues_pdf.py
.venv/bin/python mgmt/gen_issues_xlsx.py
```

## Excel Workbook Sheets

- **Issues** — Full issue table with open/closed counters and completion percentage
- **Burndown** — Open vs closed by priority with stacked bar chart
- **By Label** — Issue distribution per label with chart

Re-run the scripts periodically (or after closing issues) to update the burndown.
