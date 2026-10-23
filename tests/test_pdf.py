import collections
import copy
from pathlib import Path
import re
import pytest
import pymupdf
import pdfplumber
from config import get_default_settings
from data_parser import parse_pdf
from course_grouper import build_exams, normalize_name
from scheduler import schedule_exams
from models import Exam, Slot, ScheduledExam, Row, ParseResult, Schedule
from pdf_generator import (
    generate_audit_pdf,
    generate_timetable_pdf,
    generate_attendance_pdf,
    generate_hall_tickets_pdf,
    generate_complete_report_pdf,
)

REAL_PDF_PATH = Path("sample_input/Backlog_List.pdf")
SKIP_IF_NO_REAL_PDF = pytest.mark.skipif(
    not REAL_PDF_PATH.is_file(),
    reason="sample_input/Backlog_List.pdf not present"
)
DEBUG_DIR = Path("debug")
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

def _render_first_page_to_png(pdf_path: Path, output_png_path: Path):
    doc = pymupdf.open(str(pdf_path))
    assert len(doc) > 0
    page = doc[0]
    pix = page.get_pixmap(dpi=150)
    pix.save(str(output_png_path))
    doc.close()
    assert output_png_path.is_file()
    assert output_png_path.stat().st_size > 0

@SKIP_IF_NO_REAL_PDF
def test_audit_pdf_generation_and_tamper():
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    audit_path = Path("output/Audit_Report.pdf")
    generate_audit_pdf(parse_res, None, schedule, settings, audit_path)

    doc = pymupdf.open(str(audit_path))
    assert len(doc) > 0
    full_text = " ".join(page.get_text("text") for page in doc)
    doc.close()

    assert "PASS" in full_text
    assert "FAIL" not in full_text

    png_path = DEBUG_DIR / "audit_page1.png"
    _render_first_page_to_png(audit_path, png_path)

    # Tampered schedule test
    tampered_schedule = copy.deepcopy(schedule)
    removed_prn = tampered_schedule.items[0].exam.prns.pop(0)

    tampered_audit_path = Path("output/Audit_Tampered.pdf")
    generate_audit_pdf(parse_res, None, tampered_schedule, settings, tampered_audit_path)

    t_doc = pymupdf.open(str(tampered_audit_path))
    t_text = " ".join(page.get_text("text") for page in t_doc)
    t_doc.close()

    assert "FAIL" in t_text
    assert removed_prn in t_text

@SKIP_IF_NO_REAL_PDF
def test_timetable_pdf_generation():
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    tt_path = Path("output/Timetable.pdf")
    generate_timetable_pdf(schedule, settings, tt_path)

    doc = pymupdf.open(str(tt_path))
    assert len(doc) > 0
    full_text = " ".join(page.get_text("text") for page in doc)
    doc.close()

    assert "EXAMINATION TIMETABLE" in full_text
    assert "Morning" in full_text
    assert "Afternoon" in full_text

    png_path = DEBUG_DIR / "timetable_page1.png"
    _render_first_page_to_png(tt_path, png_path)

@SKIP_IF_NO_REAL_PDF
def test_attendance_pdf_generation_small_and_large():
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    single_exam = schedule.items[0].exam
    att_single_path = Path("output/Attendance_Single.pdf")
    generate_attendance_pdf(parse_res, schedule, settings, att_single_path, exam_key=single_exam.key)

    doc_single = pymupdf.open(str(att_single_path))
    assert len(doc_single) >= 1
    doc_single.close()

    large_exam = Exam(
        key="large_synth",
        name="Advanced Synthetic Engineering",
        codes=["SE1001"],
        spellings=["Advanced Synthetic Engineering"],
        prns=[f"PRN_{2000 + i}" for i in range(160)]
    )
    large_slot = Slot(date="2026-11-02", session="Morning", start="10:00", end="13:00")
    large_schedule = copy.deepcopy(schedule)
    large_schedule.items = [ScheduledExam(exam=large_exam, slot=large_slot)]

    att_large_path = Path("output/Attendance_Large.pdf")
    generate_attendance_pdf(parse_res, large_schedule, settings, att_large_path, exam_key="large_synth")

    doc_large = pymupdf.open(str(att_large_path))
    assert len(doc_large) > 1
    doc_large.close()

    png_path = DEBUG_DIR / "attendance_page1.png"
    _render_first_page_to_png(att_single_path, png_path)

@SKIP_IF_NO_REAL_PDF
def test_hall_tickets_pdf_generation_and_accents():
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    sample_prn = schedule.items[0].exam.prns[0]
    ht_path = Path("output/Hall_Ticket_Single.pdf")
    generate_hall_tickets_pdf(parse_res, schedule, settings, ht_path, target_prn=sample_prn)

    doc = pymupdf.open(str(ht_path))
    assert len(doc) == 1
    full_text = " ".join(page.get_text("text") for page in doc)
    doc.close()
    assert sample_prn in full_text
    assert "HALL TICKET" in full_text

    # Accented name test
    accent_row = Row(
        sr=999,
        prn="9999999999",
        name="René François-Müller",
        course_code="AC101",
        course_name="Accented Linguistics",
        program="BTECH.AIDS",
        year="Second Year",
        ay="2025-26",
        sem="1",
        page=1
    )
    accent_exam = Exam(
        key="accented_linguistics",
        name="Accented Linguistics",
        codes=["AC101"],
        spellings=["Accented Linguistics"],
        prns=["9999999999"]
    )
    accent_slot = Slot(date="2026-11-03", session="Morning", start="10:00", end="13:00")
    accent_schedule = copy.deepcopy(schedule)
    accent_schedule.items = [ScheduledExam(exam=accent_exam, slot=accent_slot)]
    accent_parse = ParseResult(rows=[accent_row])

    accent_ht_path = Path("output/Hall_Ticket_Accent.pdf")
    generate_hall_tickets_pdf(accent_parse, accent_schedule, settings, accent_ht_path, target_prn="9999999999")

    doc_accent = pymupdf.open(str(accent_ht_path))
    assert len(doc_accent) == 1
    doc_accent.close()

    png_path = DEBUG_DIR / "hall_ticket_page1.png"
    _render_first_page_to_png(ht_path, png_path)


@SKIP_IF_NO_REAL_PDF
def test_hall_tickets_page_count_equals_unique_students_152():
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    ht_all_path = Path("output/Hall_Tickets.pdf")
    generate_hall_tickets_pdf(parse_res, schedule, settings, ht_all_path)

    doc = pymupdf.open(str(ht_all_path))
    unique_prns = len(set(r.prn for r in parse_res.rows))
    assert unique_prns == 152
    assert len(doc) == 152
    doc.close()


def test_hall_tickets_twenty_exams_fit_on_one_page():
    test_prn = "9999888877"
    twenty_exams = []
    twenty_scheduled = []
    for i in range(1, 21):
        e = Exam(
            key=f"course_unit_{i}",
            name=f"Advanced Core Subject {i} With Long Multi-word Descriptor",
            codes=[f"CS9{i:02d}A", f"CS9{i:02d}B", f"CS9{i:02d}C"],
            spellings=[f"Advanced Core Subject {i}"],
            prns=[test_prn]
        )
        slot = Slot(date=f"2026-11-{(i%10)+1:02d}", session="Morning" if i % 2 == 1 else "Afternoon", start="10:00", end="13:00")
        twenty_exams.append(e)
        twenty_scheduled.append(ScheduledExam(exam=e, slot=slot))

    row = Row(
        sr=1,
        prn=test_prn,
        name="Maximum Load Candidate",
        course_code="CS901A",
        course_name="Advanced Core Subject 1",
        program="BTECH.CSE",
        year="Fourth Year",
        ay="2025-26",
        sem="1",
        page=1
    )
    test_parse = ParseResult(rows=[row])
    test_sched = Schedule(items=twenty_scheduled, slots_used=20, warnings=[])
    settings = get_default_settings()

    out_ht_20 = Path("output/Hall_Ticket_Twenty.pdf")
    generate_hall_tickets_pdf(test_parse, test_sched, settings, out_ht_20, target_prn=test_prn)

    doc_20 = pymupdf.open(str(out_ht_20))
    assert len(doc_20) == 1, f"Expected 20 exams to fit on exactly 1 page, got {len(doc_20)}"
    text = doc_20[0].get_text("text")
    assert test_prn in text
    assert "Maximum Load Candidate" in text
    doc_20.close()


@SKIP_IF_NO_REAL_PDF
def test_hall_ticket_student_own_course_code():
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    prn = "2081370016"
    ht_path = Path("output/Hall_Ticket_2081370016.pdf")
    generate_hall_tickets_pdf(parse_res, schedule, settings, ht_path, target_prn=prn)

    doc = pymupdf.open(str(ht_path))
    assert len(doc) == 1
    page_text = doc[0].get_text("text")
    doc.close()

    # The student's row for Computer Networks has code BTECAI503
    student_cn_row = next(r for r in parse_res.rows if r.prn == prn and "computer networks" in r.course_name.lower())
    assert student_cn_row.course_code == "BTECAI503"

    assert "BTECAI503" in page_text
    assert "+3" not in page_text
    assert "+2" not in page_text
    assert "+" not in page_text
    assert "Controller of Examinations" in page_text


@SKIP_IF_NO_REAL_PDF
def test_hall_ticket_gauri_sharma_twenty_exams_fits_one_page():
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    prn = "3123035010412"
    ht_path = Path("output/Hall_Ticket_3123035010412.pdf")
    generate_hall_tickets_pdf(parse_res, schedule, settings, ht_path, target_prn=prn)

    doc = pymupdf.open(str(ht_path))
    assert len(doc) == 1, f"Expected Gauri Manoj Sharma (20 exams) to fit on 1 page, got {len(doc)}"
    text = doc[0].get_text("text")
    assert "Gauri Manoj Sharma" in text
    assert prn in text
    assert "+N" not in text
    assert "+" not in text
    doc.close()


@SKIP_IF_NO_REAL_PDF
def test_complete_report_pdf_generation():
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    cr_path = Path("output/Complete_Report.pdf")
    generate_complete_report_pdf(parse_res, None, schedule, settings, cr_path)

    doc = pymupdf.open(str(cr_path))
    assert len(doc) > 100  # 93 exam pages in Section 3 + Cover + TOC + Sections 1, 2, 4
    full_text = " ".join(page.get_text("text") for page in doc)
    doc.close()

    assert "COMPLETE MASTER EXAMINATION REPORT" in full_text
    assert "TABLE OF CONTENTS" in full_text
    assert "SECTION 1: VERIFICATION & AUDIT SUMMARY" in full_text
    assert "SECTION 2: MASTER TIMETABLE" in full_text
    assert "SECTION 3: EXAM-WISE STUDENT LIST" in full_text
    assert "SECTION 4: STUDENT-WISE EXAMINATION SCHEDULE" in full_text

    png_path = DEBUG_DIR / "complete_report_page1.png"
    _render_first_page_to_png(cr_path, png_path)


@SKIP_IF_NO_REAL_PDF
def test_attendance_codes_match_student_own_row_666_rows():
    """Requirement 1: for every (PRN, exam), printed code equals student's own row for that exam."""
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    att_path = Path("output/Attendance_Sheets.pdf")
    generate_attendance_pdf(parse_res, schedule, settings, att_path)

    expected_codes = {}
    for r in parse_res.rows:
        k = normalize_name(r.course_name)
        if (r.prn, k) not in expected_codes:
            expected_codes[(r.prn, k)] = r.course_code

    doc_att = pymupdf.open(str(att_path))
    total_checked = 0
    mismatches = 0

    for page_idx in range(len(doc_att)):
        page = doc_att[page_idx]
        tabs = page.find_tables()
        if not tabs.tables:
            continue
        table_data = tabs.tables[0].extract()
        text = page.get_text()
        m = re.search(r"Course / Exam:\s*([^\n|]+)", text)
        if not m:
            continue
        raw_exam_name = m.group(1).strip()
        exam_name = re.sub(r"\s*\(Sheet \d+ of \d+\)", "", raw_exam_name).strip()
        ex_key = normalize_name(exam_name)

        for r in table_data[1:]:
            if len(r) >= 6 and r[1] and r[5]:
                prn_val = r[1].replace("\n", "").strip()
                code_val = r[5].replace("\n", "").strip()
                if not prn_val.isdigit():
                    continue
                exp = expected_codes.get((prn_val, ex_key))
                if not exp:
                    matched_ex = next((e for e in exams if e.key == ex_key or normalize_name(e.name) == ex_key), None)
                    if matched_ex:
                        for sp in matched_ex.spellings:
                            exp = expected_codes.get((prn_val, normalize_name(sp)))
                            if exp:
                                break
                assert exp == code_val, f"Mismatch on p.{page_idx+1}: PRN {prn_val}, Exam {exam_name}, Got {code_val}, Expected {exp}"
                total_checked += 1

    doc_att.close()
    assert mismatches == 0
    assert total_checked == 666


@SKIP_IF_NO_REAL_PDF
def test_audit_pdf_contains_all_prns_duplicates_and_all_srs():
    """Requirement 2: Audit text contains all 152 PRNs, 141 duplicate entries, and all SRs 1..807."""
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    audit_path = Path("output/Audit_Report.pdf")
    generate_audit_pdf(parse_res, None, schedule, settings, audit_path)

    doc = pymupdf.open(str(audit_path))
    audit_text = "".join(page.get_text() for page in doc)
    doc.close()

    unique_prns = sorted(list(set(r.prn for r in parse_res.rows)))
    assert len(unique_prns) == 152
    for prn in unique_prns:
        assert prn in audit_text, f"PRN {prn} missing from Audit PDF"

    assert "141 entries" in audit_text or "141" in audit_text
    assert "Removed Duplicate Rows" in audit_text
    assert "Student-wise Checklist" in audit_text
    assert "Pairs placed in timetable" in audit_text
    assert "Unparseable Rows" in audit_text
    assert "Course-Name Merges Applied" in audit_text

    for sr in range(1, 808):
        assert str(sr) in audit_text, f"SR {sr} missing from Audit PDF"


@SKIP_IF_NO_REAL_PDF
def test_no_pdf_contains_escaped_ampersand_artifact():
    """Requirement 3: No PDF text contains 'DS;)'."""
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    out_dir = Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)
    generate_attendance_pdf(parse_res, schedule, settings, out_dir / "Attendance_Sheets.pdf")
    generate_hall_tickets_pdf(parse_res, schedule, settings, out_dir / "Hall_Tickets.pdf")
    generate_complete_report_pdf(parse_res, None, schedule, settings, out_dir / "Complete_Report.pdf")
    generate_audit_pdf(parse_res, None, schedule, settings, out_dir / "Audit_Report.pdf")
    generate_timetable_pdf(schedule, settings, out_dir / "Timetable.pdf")

    for pdf_name in ["Attendance_Sheets.pdf", "Hall_Tickets.pdf", "Complete_Report.pdf", "Audit_Report.pdf", "Timetable.pdf"]:
        doc = pymupdf.open(str(out_dir / pdf_name))
        for p_idx, page in enumerate(doc):
            t = page.get_text()
            assert "DS;)" not in t, f"{pdf_name} p.{p_idx+1} contains 'DS;)'"
        doc.close()


@SKIP_IF_NO_REAL_PDF
def test_attendance_layout_no_page_lacks_exam_heading():
    """Requirement 4: Code column widened and no attendance page lacks the exam heading."""
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    att_path = Path("output/Attendance_Sheets.pdf")
    generate_attendance_pdf(parse_res, schedule, settings, att_path)

    doc = pymupdf.open(str(att_path))
    for p_idx, page in enumerate(doc):
        t = page.get_text()
        assert "EXAMINATION ATTENDANCE SHEET" in t, f"Attendance page {p_idx+1} lacks exam heading"
        assert "Course / Exam:" in t, f"Attendance page {p_idx+1} lacks course/exam info"
        assert "Sr" in t and "PRN" in t, f"Attendance page {p_idx+1} has no table content"
        assert "Second\nYear" not in t, f"Attendance page {p_idx+1} has wrapped 'Second Year'"
    doc.close()


@SKIP_IF_NO_REAL_PDF
def test_hall_ticket_multi_year_sorted_prn_2181370143():
    """Requirement 5: Student with backlogs in multiple years prints 'Year: Second, Third, Fourth'."""
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    prn = "2181370143"
    ht_path = Path("output/Hall_Ticket_MultiYear.pdf")
    generate_hall_tickets_pdf(parse_res, schedule, settings, ht_path, target_prn=prn)

    doc = pymupdf.open(str(ht_path))
    assert len(doc) == 1
    t = doc[0].get_text()
    doc.close()

    assert prn in t
    assert "Year: Second, Third, Fourth" in t


@SKIP_IF_NO_REAL_PDF
def test_year_column_no_newline_in_attendance_and_complete_report():
    """Assert with pdfplumber that 'Year' column in Attendance_Sheets and Complete_Report Section 3 has no newlines."""
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    att_path = Path("output/Attendance_Sheets.pdf")
    generate_attendance_pdf(parse_res, schedule, settings, att_path)

    # 1. Assert with pdfplumber on Attendance_Sheets.pdf
    with pdfplumber.open(att_path) as pdf_att:
        assert len(pdf_att.pages) > 0
        total_student_rows = 0
        for p_idx, page in enumerate(pdf_att.pages):
            tables = page.extract_tables()
            for t in tables:
                for r_idx, row in enumerate(t):
                    if len(row) >= 5 and row[1] and row[1].replace("\n", "").strip().isdigit():
                        year_val = row[4]
                        assert year_val is not None, f"Attendance page {p_idx+1} row {r_idx} Year is None"
                        assert "\n" not in str(year_val), f"Attendance page {p_idx+1} row {r_idx} Year has newline: {repr(year_val)}"
                        total_student_rows += 1
        assert total_student_rows == 666

    # Also keep PyMuPDF check
    doc_att = pymupdf.open(str(att_path))
    for p_idx, page in enumerate(doc_att):
        t = page.get_text()
        for y in ["Second\nYear", "Third\nYear", "Fourth\nYear", "First\nYear"]:
            assert y not in t, f"Attendance page {p_idx+1} contains wrapped year: {repr(y)}"
    doc_att.close()

    cr_path = Path("output/Complete_Report.pdf")
    generate_complete_report_pdf(parse_res, None, schedule, settings, cr_path)

    # 2. Assert with pdfplumber on Complete_Report.pdf Section 3
    with pdfplumber.open(cr_path) as pdf_cr:
        assert len(pdf_cr.pages) > 0
        cr_student_rows = 0
        for p_idx, page in enumerate(pdf_cr.pages):
            text = page.extract_text() or ""
            if "SECTION 3" in text:
                tables = page.extract_tables()
                for t in tables:
                    for r_idx, row in enumerate(t):
                        if len(row) >= 5 and row[1] and row[1].replace("\n", "").strip().isdigit():
                            year_val = row[4]
                            assert year_val is not None, f"Complete Report Section 3 page {p_idx+1} row {r_idx} Year is None"
                            assert "\n" not in str(year_val), f"Complete Report Section 3 page {p_idx+1} row {r_idx} Year has newline: {repr(year_val)}"
                            cr_student_rows += 1
        assert cr_student_rows > 0

    # Also keep PyMuPDF check
    doc_cr = pymupdf.open(str(cr_path))
    for p_idx, page in enumerate(doc_cr):
        t = page.get_text()
        if "SECTION 3: EXAM-WISE STUDENT LISTS" in t:
            for y in ["Second\nYear", "Third\nYear", "Fourth\nYear", "First\nYear"]:
                assert y not in t, f"Complete Report Section 3 page {p_idx+1} contains wrapped year: {repr(y)}"
    doc_cr.close()


@SKIP_IF_NO_REAL_PDF
def test_audit_report_headers_no_split_words():
    """Assert with pdfplumber that in Audit_Report.pdf, no header cell contains a newline inside a single word."""
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    audit_path = Path("output/Audit_Report.pdf")
    generate_audit_pdf(parse_res, None, schedule, settings, audit_path)

    # 1. Assert with pdfplumber that no header cell has a newline inside a word
    broken_fragments = ["ms", "us", "ved", "ents", "s"]
    broken_words = ["Remo\nved", "Stud\nents", "Student\ns", "Exa\nms", "Stat\nus", "Kept\nSR"]

    with pdfplumber.open(audit_path) as pdf_audit:
        assert len(pdf_audit.pages) > 0
        header_tables_checked = 0
        for p_idx, page in enumerate(pdf_audit.pages):
            tables = page.extract_tables()
            for t in tables:
                if t and t[0]:
                    header_row = t[0]
                    for cell in header_row:
                        if cell:
                            for bw in broken_words:
                                assert bw not in cell, f"Audit Report page {p_idx+1} header cell {cell!r} contains split word {bw!r}"
                            lines = [ln.strip() for ln in cell.split("\n") if ln.strip()]
                            for fragment in broken_fragments:
                                assert fragment not in lines, f"Audit Report page {p_idx+1} header cell {cell!r} has broken word fragment {fragment!r}"
                    header_tables_checked += 1
        assert header_tables_checked > 0

    # 2. Also assert with PyMuPDF text stream
    doc_audit = pymupdf.open(str(audit_path))
    assert len(doc_audit) > 0

    bad_patterns = [
        (r"Student\s*\n\s*s", "Student/s"),
        (r"Exa\s*\n\s*ms", "Exa/ms"),
        (r"Stat\s*\n\s*us", "Stat/us"),
        (r"Remo\s*\n\s*ved\s*SR", "Remo/ved SR"),
        (r"Stud\s*\n\s*ents", "Stud/ents"),
        (r"Kept\s*\n\s*SR", "Kept SR (split)"),
    ]

    for p_idx, page in enumerate(doc_audit):
        t = page.get_text()
        for pat, name in bad_patterns:
            m = re.findall(pat, t)
            assert not m, f"Audit Report page {p_idx+1} has broken header word {name}: {m}"
        assert "Remo\nved" not in t, f"Audit Report page {p_idx+1} contains 'Remo\\nved'"
        assert "Stud\nents" not in t, f"Audit Report page {p_idx+1} contains 'Stud\\nents'"
        assert "Exa\nms" not in t, f"Audit Report page {p_idx+1} contains 'Exa\\nms'"
        assert "Stat\nus" not in t, f"Audit Report page {p_idx+1} contains 'Stat\\nus'"
    doc_audit.close()

@SKIP_IF_NO_REAL_PDF
def test_audit_pdf_and_complete_report_show_holidays(tmp_path):
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    settings.holidays = ["2026-11-04", "2026-11-05"]
    schedule = schedule_exams(exams, settings)

    audit_path = tmp_path / "Audit_Report.pdf"
    complete_report_path = tmp_path / "Complete_Report.pdf"

    generate_audit_pdf(parse_res, None, schedule, settings, audit_path)
    generate_complete_report_pdf(parse_res, None, schedule, settings, complete_report_path)

    # 1. Audit PDF should show "Holidays excluded: 2026-11-04, 2026-11-05"
    with pdfplumber.open(audit_path) as pdf_audit:
        first_page_text = pdf_audit.pages[0].extract_text()
        assert "Holidays excluded: 2026-11-04, 2026-11-05" in first_page_text, (
            f"Expected 'Holidays excluded: 2026-11-04, 2026-11-05' in Audit PDF page 1 text, got:\n{first_page_text}"
        )

    # 2. Complete Report should show "Holidays Excluded:" on cover and "Holidays excluded: ..." in Section 1
    with pdfplumber.open(complete_report_path) as pdf_cr:
        cover_text = pdf_cr.pages[0].extract_text()
        assert "Holidays Excluded:" in cover_text
        assert "2026-11-04, 2026-11-05" in cover_text

        sec1_text = pdf_cr.pages[2].extract_text()
        assert "Holidays excluded: 2026-11-04, 2026-11-05" in sec1_text

@SKIP_IF_NO_REAL_PDF
def test_single_student_hall_ticket_three_cases(tmp_path):
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    # Generate full Hall_Tickets.pdf
    full_ht_path = tmp_path / "Hall_Tickets.pdf"
    generate_hall_tickets_pdf(parse_res, schedule, settings, full_ht_path)

    doc_full = pymupdf.open(str(full_ht_path))
    assert len(doc_full) == 152

    # Map each PRN to its full page index and page text
    full_pages = {}
    for p_idx, page in enumerate(doc_full):
        text = page.get_text()
        for r in parse_res.rows:
            if f"PRN: {r.prn}" in text:
                full_pages[r.prn] = (p_idx, text)

    # 1. Student with 1 exam
    stu_exams_map = collections.defaultdict(list)
    for it in schedule.items:
        for p in it.exam.prns:
            stu_exams_map[p].append(it)
    prn_1_exam = next(p for p in sorted(stu_exams_map.keys()) if len(stu_exams_map[p]) == 1)
    assert len(stu_exams_map[prn_1_exam]) == 1

    # 2. Student with 2 years
    stu_years_map = collections.defaultdict(set)
    for r in parse_res.rows:
        if r.year:
            stu_years_map[r.prn].add(r.year.strip())
    prn_2_years = next(p for p in sorted(stu_years_map.keys()) if len(stu_years_map[p]) == 2)
    assert len(stu_years_map[prn_2_years]) == 2

    # 3. 20-exam student
    prn_20_exams = "3123035010412"
    assert len(stu_exams_map[prn_20_exams]) == 20

    test_prns = [prn_1_exam, prn_2_years, prn_20_exams]

    for prn in test_prns:
        single_path = tmp_path / f"HallTicket_{prn}.pdf"
        generate_hall_tickets_pdf(parse_res, schedule, settings, single_path, target_prn=prn)

        # Assertion 1: Generated PDF has exactly ONE page
        doc_single = pymupdf.open(str(single_path))
        assert len(doc_single) == 1, f"Expected 1 page for PRN {prn}, got {len(doc_single)}"

        single_text = doc_single[0].get_text()

        # Assertion 2: Page contains the right PRN
        assert f"PRN: {prn}" in single_text or prn in single_text

        # Assertion 3: Page contains exactly that student's exams
        student_exams = stu_exams_map[prn]
        for it in student_exams:
            assert it.exam.name in single_text
            assert it.slot.date in single_text
            assert it.slot.session in single_text

        # Verify with pdfplumber that the table row count equals that student's exam count
        with pdfplumber.open(single_path) as p_single:
            tables = p_single.pages[0].extract_tables()
            # The second table is the exams table (first is student info)
            assert len(tables) >= 2
            exam_table = tables[1]
            # Header + student's exams
            assert len(exam_table) - 1 == len(student_exams)

        # Assertion 4: Page text is identical to the same student's page in the full Hall_Tickets.pdf
        assert prn in full_pages, f"PRN {prn} missing from full Hall_Tickets.pdf"
        full_idx, full_text = full_pages[prn]
        assert single_text == full_text, (
            f"Page text for PRN {prn} differs from full Hall_Tickets.pdf page {full_idx+1}"
        )
        doc_single.close()

    doc_full.close()

def test_app_download_single_hall_ticket_button():
    """Verify in Streamlit AppTest that selecting a student shows the button 'Download Hall Ticket (this student)'."""
    from streamlit.testing.v1 import AppTest
    r1 = Row(sr=1, prn="1111111111", name="Alice Smith", course_code="CS101", course_name="Data Structures", program="BTECH", year="Second Year", ay="2025-26", sem="1", page=1)
    r2 = Row(sr=2, prn="2222222222", name="Bob Jones", course_code="CS102", course_name="Algorithms", program="BTECH", year="Third Year", ay="2025-26", sem="1", page=1)
    parse_res = ParseResult(rows=[r1, r2])
    e1 = Exam(key="data_structures", name="Data Structures", codes=["CS101"], spellings=["Data Structures"], prns=["1111111111"])
    e2 = Exam(key="algorithms", name="Algorithms", codes=["CS102"], spellings=["Algorithms"], prns=["2222222222"])
    settings = get_default_settings()
    sched = schedule_exams([e1, e2], settings)

    app_path = str((Path(__file__).parent.parent / "app.py").resolve())
    at = AppTest.from_file(app_path)
    at.session_state["settings"] = settings
    at.session_state["parse_result"] = parse_res
    at.session_state["schedule"] = sched
    at.run(timeout=15)

    # Switch view to Student View
    for rad in at.radio:
        if "Student View" in rad.options:
            rad.set_value("Student View")
    at.run(timeout=15)

    # Find the single student download button
    dl_btn = next((b for b in at.download_button if b.label == "Download Hall Ticket (this student)"), None)
    assert dl_btn is not None
    assert dl_btn.key == "dl_ht_1111111111"
    assert dl_btn.disabled is False

    # Select another student (2222222222) and verify button updates
    for sb in at.selectbox:
        if sb.label == "Select Student PRN":
            matching = [opt for opt in sb.options if "2222222222" in opt]
            if matching:
                sb.set_value(matching[0])
    at.run(timeout=15)

    dl_btn_updated = next((b for b in at.download_button if b.label == "Download Hall Ticket (this student)"), None)
    assert dl_btn_updated is not None
    assert dl_btn_updated.key == "dl_ht_2222222222"

    # Also verify the all-students Hall Tickets PDF button remains unchanged
    all_ht_btn = next((b for b in at.download_button if b.label == "Hall Tickets PDF"), None)
    assert all_ht_btn is not None
    assert all_ht_btn.disabled is False




