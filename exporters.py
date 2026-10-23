import collections
import io
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import pandas as pd
from models import ParseResult, Schedule, Settings
from scheduler import schedule_to_rows
from course_grouper import normalize_name
from pdf_generator import (
    generate_audit_pdf,
    generate_timetable_pdf,
    generate_attendance_pdf,
    generate_hall_tickets_pdf,
    generate_complete_report_pdf,
)

def to_excel(
    parse_result: ParseResult,
    schedule: Schedule,
    output_path: Union[str, Path]
) -> Path:
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    rows_by_prn: Dict[str, Any] = {r.prn: r for r in parse_result.rows}

    # Sheet 1: Timetable
    tt_rows = schedule_to_rows(schedule)
    df_timetable = pd.DataFrame(tt_rows)

    # Sheet 2: Exam-wise students
    exam_students_data: List[Dict[str, Any]] = []
    for it in schedule.items:
        for idx, prn in enumerate(it.exam.prns, start=1):
            r = rows_by_prn.get(prn)
            exam_students_data.append({
                "Exam Name": it.exam.name,
                "Course Codes": ", ".join(it.exam.codes),
                "Slot Date": it.slot.date,
                "Slot Session": it.slot.session,
                "Sr": idx,
                "PRN": prn,
                "Student Name": r.name if r else "Student",
                "Program": r.program if r else "-",
                "Year": r.year if r else "-",
            })
    df_exam_students = pd.DataFrame(exam_students_data)

    # Sheet 3: Student-wise schedule
    student_exams_map: Dict[str, List[Any]] = collections.defaultdict(list)
    for it in schedule.items:
        for prn in it.exam.prns:
            student_exams_map[prn].append(it)

    student_schedule_data: List[Dict[str, Any]] = []
    for prn in sorted(student_exams_map.keys()):
        r = rows_by_prn.get(prn)
        s_name = r.name if r else "Student"
        s_prog = r.program if r else "-"
        s_year = r.year if r else "-"
        items_list = student_exams_map[prn]

        for it in sorted(items_list, key=lambda x: (x.slot.date, x.slot.session)):
            student_schedule_data.append({
                "PRN": prn,
                "Student Name": s_name,
                "Program": s_prog,
                "Year": s_year,
                "Total Backlogs": len(items_list),
                "Exam Name": it.exam.name,
                "Course Codes": ", ".join(it.exam.codes),
                "Slot Date": it.slot.date,
                "Slot Session": it.slot.session,
                "Slot Time": f"{it.slot.start} - {it.slot.end}",
            })
    df_student_schedule = pd.DataFrame(student_schedule_data)

    with pd.ExcelWriter(out_p, engine="openpyxl") as writer:
        df_timetable.to_excel(writer, sheet_name="Timetable", index=False)
        df_exam_students.to_excel(writer, sheet_name="Exam-wise students", index=False)
        df_student_schedule.to_excel(writer, sheet_name="Student-wise schedule", index=False)

    return out_p

def to_csv(
    parse_result: ParseResult,
    schedule: Schedule,
    output_path: Union[str, Path]
) -> Path:
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    rows_by_prn: Dict[str, Any] = {r.prn: r for r in parse_result.rows}
    student_exams_map: Dict[str, List[Any]] = collections.defaultdict(list)
    for it in schedule.items:
        for prn in it.exam.prns:
            student_exams_map[prn].append(it)

    student_schedule_data: List[Dict[str, Any]] = []
    for prn in sorted(student_exams_map.keys()):
        r = rows_by_prn.get(prn)
        s_name = r.name if r else "Student"
        s_prog = r.program if r else "-"
        s_year = r.year if r else "-"
        items_list = student_exams_map[prn]

        for it in sorted(items_list, key=lambda x: (x.slot.date, x.slot.session)):
            student_schedule_data.append({
                "PRN": prn,
                "Student Name": s_name,
                "Program": s_prog,
                "Year": s_year,
                "Total Backlogs": len(items_list),
                "Exam Name": it.exam.name,
                "Course Codes": ", ".join(it.exam.codes),
                "Slot Date": it.slot.date,
                "Slot Session": it.slot.session,
                "Slot Time": f"{it.slot.start} - {it.slot.end}",
            })

    df = pd.DataFrame(student_schedule_data)
    df.to_csv(out_p, index=False, encoding="utf-8-sig")
    return out_p

def build_zip(
    pdf_paths: List[Path],
    excel_path: Path,
    csv_path: Path,
    output_zip_path: Union[str, Path]
) -> Path:
    out_zip = Path(output_zip_path)
    out_zip.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in pdf_paths:
            if p.is_file():
                zf.write(p, arcname=p.name)
        if excel_path.is_file():
            zf.write(excel_path, arcname=excel_path.name)
        if csv_path.is_file():
            zf.write(csv_path, arcname=csv_path.name)

    return out_zip

def export_all(
    parse_result: ParseResult,
    merge_map: Optional[Dict[str, str]],
    schedule: Schedule,
    settings: Settings,
    output_dir: Union[str, Path]
) -> Dict[str, Any]:
    out_d = Path(output_dir)
    out_d.mkdir(parents=True, exist_ok=True)

    audit_pdf = generate_audit_pdf(parse_result, merge_map, schedule, settings, out_d / "Audit_Report.pdf")
    timetable_pdf = generate_timetable_pdf(schedule, settings, out_d / "Timetable.pdf")
    attendance_pdf = generate_attendance_pdf(parse_result, schedule, settings, out_d / "Attendance_Sheets.pdf")
    hall_tickets_pdf = generate_hall_tickets_pdf(parse_result, schedule, settings, out_d / "Hall_Tickets.pdf")
    complete_report_pdf = generate_complete_report_pdf(parse_result, merge_map, schedule, settings, out_d / "Complete_Report.pdf")

    excel_path = to_excel(parse_result, schedule, out_d / "Backlog_Schedule.xlsx")
    csv_path = to_csv(parse_result, schedule, out_d / "Backlog_Schedule.csv")

    all_pdfs = [audit_pdf, timetable_pdf, attendance_pdf, hall_tickets_pdf, complete_report_pdf]
    zip_path = build_zip(all_pdfs, excel_path, csv_path, out_d / "Everything_Export.zip")

    return {
        "audit_pdf": audit_pdf,
        "timetable_pdf": timetable_pdf,
        "attendance_pdf": attendance_pdf,
        "hall_tickets_pdf": hall_tickets_pdf,
        "complete_report_pdf": complete_report_pdf,
        "excel_path": excel_path,
        "csv_path": csv_path,
        "zip_path": zip_path,
    }
