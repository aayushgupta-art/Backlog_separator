# Backlog Exam Separator & Scheduler

A stream-lined examination timetable scheduling and document generation system built with Streamlit, NetworkX, ReportLab, and PyMuPDF.

## Features

- **Automated Parsing**: Ingests raw backlog registration lists from PDF, Excel, or CSV formats.
- **Smart Grouping & Conflict-Free Scheduling**: Merges matching courses and uses graph-coloring algorithms to ensure no student has clashing exams or exceeds per-day exam limits.
- **Publication-Ready Documents**: Generates downloadable timetables, exam-wise attendance sheets, individual/bulk hall tickets, Excel/CSV schedules, and audit verification reports.
- **Customizable Constraints**: Configurable morning and afternoon session timings, date windows, Sunday exclusions, and custom holiday calendars.

## Running Locally

1. **Install runtime dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Streamlit application**:
   ```bash
   streamlit run app.py
   ```

## Development & Testing

To run the test suite:
```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
```

## Data Privacy Notice

No real student data is stored in this repository. All candidate records (names, PRNs), exported documents (PDF, Excel, CSV, ZIP), and uploaded sample files are strictly excluded via `.gitignore`.
