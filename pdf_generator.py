import collections
from datetime import datetime
import html
import math
from pathlib import Path
import re
from typing import List, Dict, Any, Optional, Tuple, Set

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    BaseDocTemplate,
    PageTemplate,
    Frame,
    NextPageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
    HRFlowable,
)

from models import ParseResult, Schedule, Settings, VerifyResult, Row
from verifier import verify
from course_grouper import normalize_name, build_exams
from config import parse_and_validate_holidays
from pdf_common import (
    NumberedCanvas,
    get_base_styles,
    DARK_BLUE,
    LIGHT_GREY,
    BORDER_GREY,
    PASS_GREEN,
    FAIL_RED,
    FONT_NAME,
    FONT_BOLD,
    KOLKATA_TZ,
)


def xml_escape(val: Any) -> str:
    """Escape text for safe usage inside ReportLab Paragraph XML."""
    if val is None:
        return ""
    return html.escape(str(val), quote=False)


def _build_header(elements: List[Any], settings: Settings, doc_title: str):
    _, _, _, title_style, subtitle_style = get_base_styles()
    elements.append(Paragraph(xml_escape(settings.college_name), title_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(f"{xml_escape(settings.department)}  |  {xml_escape(settings.exam_title)}", subtitle_style))
    elements.append(Spacer(1, 4))
    doc_header_style = ParagraphStyle(
        name="DocHeaderStyle",
        parent=subtitle_style,
        fontName=FONT_BOLD,
        fontSize=12,
        textColor=DARK_BLUE,
    )
    elements.append(Paragraph(doc_title, doc_header_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1, color=DARK_BLUE, spaceBefore=2, spaceAfter=12))


def generate_audit_pdf(
    parse_result: ParseResult,
    merge_map: Optional[Dict[str, str]],
    schedule: Schedule,
    settings: Settings,
    output_path: Path
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    v_res = verify(parse_result, merge_map, schedule, settings)
    exams, duplicates = build_exams(parse_result.rows, merge_map)
    _, body_style, header_cell_style, _, _ = get_base_styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=45
    )
    elements: List[Any] = []
    _build_header(elements, settings, "AUDIT AND RECONCILIATION REPORT")

    banner_color = PASS_GREEN if v_res.ok else FAIL_RED
    banner_text = "PASS: ALL STUDENTS SCHEDULED, 0 CONFLICTS" if v_res.ok else "FAIL: AUDIT CONFLICTS DETECTED"
    banner_style = ParagraphStyle(
        name="BannerStyle",
        parent=body_style,
        fontName=FONT_BOLD,
        fontSize=12,
        leading=16,
        textColor=colors.white,
        alignment=1
    )
    banner_table = Table([[Paragraph(banner_text, banner_style)]], colWidths=[523])
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), banner_color),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(banner_table)
    elements.append(Spacer(1, 8))

    valid_h, _ = parse_and_validate_holidays(settings.holidays)
    holidays_str = ", ".join(valid_h) if valid_h else "None"
    elements.append(Paragraph(f"<b>Holidays excluded:</b> {xml_escape(holidays_str)}", body_style))
    elements.append(Spacer(1, 8))

    summary_data = [
        [Paragraph("Metric", header_cell_style), Paragraph("Input File", header_cell_style), Paragraph("Schedule", header_cell_style), Paragraph("Difference", header_cell_style)],
        [Paragraph("Total Rows Read", body_style), Paragraph(str(v_res.rows_read), body_style), Paragraph("-", body_style), Paragraph("-", body_style)],
        [Paragraph("Duplicate Rows", body_style), Paragraph(str(v_res.duplicate_rows), body_style), Paragraph("-", body_style), Paragraph("-", body_style)],
        [Paragraph("Unique Students", body_style), Paragraph(str(v_res.unique_students), body_style), Paragraph(str(v_res.unique_students), body_style), Paragraph("0", body_style)],
        [Paragraph("Unique Student-Exam Pairs", body_style), Paragraph(str(v_res.unique_pairs), body_style), Paragraph(str(v_res.pairs_scheduled), body_style), Paragraph(str(v_res.unique_pairs - v_res.pairs_scheduled), body_style)],
        [Paragraph("Pairs placed in timetable", body_style), Paragraph(str(v_res.unique_pairs), body_style), Paragraph(str(v_res.pairs_scheduled), body_style), Paragraph(str(v_res.unique_pairs - v_res.pairs_scheduled), body_style)],
        [Paragraph("Exams", body_style), Paragraph(str(v_res.exams), body_style), Paragraph(str(len(schedule.items)), body_style), Paragraph(str(v_res.exams - len(schedule.items)), body_style)],
        [Paragraph("Missing Student Pairs", body_style), Paragraph("0", body_style), Paragraph(str(len(v_res.missing_pairs)), body_style), Paragraph(str(len(v_res.missing_pairs)), body_style)],
        [Paragraph("Extra Student Pairs", body_style), Paragraph("0", body_style), Paragraph(str(len(v_res.extra_pairs)), body_style), Paragraph(str(len(v_res.extra_pairs)), body_style)],
        [Paragraph("Students with Clash", body_style), Paragraph("0", body_style), Paragraph(str(len(v_res.clashes)), body_style), Paragraph(str(len(v_res.clashes)), body_style)],
    ]
    summary_table = Table(summary_data, colWidths=[200, 105, 105, 113])
    t_style = [
        ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    for row_idx in range(1, len(summary_data)):
        if row_idx % 2 == 0:
            t_style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), LIGHT_GREY))
    summary_table.setStyle(TableStyle(t_style))
    elements.append(summary_table)
    elements.append(Spacer(1, 14))

    if not v_res.ok:
        elements.append(Paragraph("<b>Discrepancies / Mismatches</b>", header_cell_style))
        for mp in v_res.missing_pairs[:10]:
            elements.append(Paragraph(f"Missing Pair: Student PRN {mp[0]} in Exam {mp[1]}", body_style))
        for cl in v_res.clashes:
            elements.append(Paragraph(f"Clash: PRN {cl['prn']} has multiple exams on {cl['date']} {cl['session']}: {cl['exams']}", body_style))
        elements.append(Spacer(1, 10))

    elements.append(Paragraph("<b>Exam-wise Schedule Verification</b>", ParagraphStyle('H2', parent=body_style, fontName=FONT_BOLD, fontSize=11, textColor=DARK_BLUE)))
    elements.append(Spacer(1, 6))

    exam_headers = [Paragraph(h, header_cell_style) for h in ["Exam Name", "Codes", "Count", "Date", "Session", "Status"]]
    exam_rows = [exam_headers]

    for it in schedule.items:
        e = it.exam
        status_txt = "Scheduled" if len(e.prns) > 0 else "Empty"
        exam_rows.append([
            Paragraph(xml_escape(e.name), body_style),
            Paragraph(xml_escape(", ".join(e.codes)), body_style),
            Paragraph(str(len(e.prns)), body_style),
            Paragraph(it.slot.date, body_style),
            Paragraph(it.slot.session, body_style),
            Paragraph(status_txt, body_style),
        ])

    exam_table = Table(exam_rows, colWidths=[145, 95, 60, 75, 75, 73], repeatRows=1)
    e_style = [
        ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 2.5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2.5),
    ]
    for r_idx in range(1, len(exam_rows)):
        if r_idx % 2 == 0:
            e_style.append(('BACKGROUND', (0, r_idx), (-1, r_idx), LIGHT_GREY))
    exam_table.setStyle(TableStyle(e_style))
    elements.append(exam_table)
    elements.append(Spacer(1, 14))

    # (b) Removed duplicate rows
    elements.append(Paragraph(
        f"<b>Removed Duplicate Rows ({len(duplicates)} entries)</b>",
        ParagraphStyle('H2_Dups', parent=body_style, fontName=FONT_BOLD, fontSize=11, textColor=DARK_BLUE)
    ))
    elements.append(Spacer(1, 6))

    dup_header_style = ParagraphStyle('DupHCell', parent=header_cell_style, fontSize=7, leading=8.5, textColor=colors.white)
    dup_headers = [Paragraph(h, dup_header_style) for h in ["Sr", "PRN", "Student Name", "Course Name", "Course Code", "Kept SR", "Removed SR"]]
    dup_rows = [dup_headers]
    dup_cell_style = ParagraphStyle('DupCell', parent=body_style, fontSize=7, leading=8.5)

    for d_idx, d in enumerate(duplicates, start=1):
        dup_rows.append([
            Paragraph(str(d_idx), dup_cell_style),
            Paragraph(d["prn"], dup_cell_style),
            Paragraph(xml_escape(d.get("name", "")), dup_cell_style),
            Paragraph(xml_escape(d.get("course_name", "")), dup_cell_style),
            Paragraph(xml_escape(d.get("course_code", "")), dup_cell_style),
            Paragraph(str(d["first_sr"]), dup_cell_style),
            Paragraph(str(d["sr"]), dup_cell_style),
        ])

    dup_table = Table(dup_rows, colWidths=[25, 70, 110, 135, 65, 58, 60], repeatRows=1)
    d_style = [
        ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]
    for r_i in range(1, len(dup_rows)):
        if r_i % 2 == 0:
            d_style.append(('BACKGROUND', (0, r_i), (-1, r_i), LIGHT_GREY))
    dup_table.setStyle(TableStyle(d_style))
    elements.append(dup_table)
    elements.append(Spacer(1, 14))

    # (c) Student-wise checklist sorted by PRN
    elements.append(Paragraph(
        "<b>Student-wise Checklist</b>",
        ParagraphStyle('H2_Checklist', parent=body_style, fontName=FONT_BOLD, fontSize=11, textColor=DARK_BLUE)
    ))
    elements.append(Spacer(1, 6))

    student_srs: Dict[str, List[int]] = collections.defaultdict(list)
    student_details: Dict[str, Row] = {}
    for r in parse_result.rows:
        student_srs[r.prn].append(r.sr)
        if r.prn not in student_details:
            student_details[r.prn] = r

    student_sched: Dict[str, List[Tuple[str, str, str]]] = collections.defaultdict(list)
    student_slot_counts: Dict[str, Dict[Tuple[str, str], int]] = collections.defaultdict(lambda: collections.defaultdict(int))
    for it in schedule.items:
        for prn in it.exam.prns:
            student_sched[prn].append((it.exam.name, it.slot.date, it.slot.session))
            student_slot_counts[prn][(it.slot.date, it.slot.session)] += 1

    chk_header_style = ParagraphStyle('ChkHCell', parent=header_cell_style, fontSize=7, leading=8.5, textColor=colors.white)
    chk_headers = [Paragraph(h, chk_header_style) for h in ["PRN", "Student Name", "Program", "Uploaded SRs", "Exams", "Scheduled Exams (Date & Session)", "Status"]]
    chk_rows = [chk_headers]
    chk_cell_style = ParagraphStyle('ChkCell', parent=body_style, fontSize=6.5, leading=8)
    chk_cell_red = ParagraphStyle('ChkCellRed', parent=chk_cell_style, textColor=FAIL_RED, fontName=FONT_BOLD)
    chk_cell_ok = ParagraphStyle('ChkCellOK', parent=chk_cell_style, textColor=PASS_GREEN, fontName=FONT_BOLD)

    chk_table_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]

    sorted_prns = sorted(list(student_details.keys()))
    for row_idx, prn in enumerate(sorted_prns, start=1):
        st_r = student_details[prn]
        srs_list = sorted(student_srs[prn])
        srs_str = ", ".join(str(s) for s in srs_list)

        has_clash = any(cnt > 1 for cnt in student_slot_counts[prn].values())
        sched_list = sorted(student_sched[prn], key=lambda x: (x[1], 0 if x[2] == "Morning" else 1, x[0]))
        sched_strs = [f"{xml_escape(en)} ({dt} {sess[:1]})" for en, dt, sess in sched_list]
        sched_display = "<br/>".join(sched_strs) if sched_strs else "None"

        status_para = Paragraph("FAIL", chk_cell_red) if has_clash else Paragraph("OK", chk_cell_ok)
        c_style = chk_cell_red if has_clash else chk_cell_style

        chk_rows.append([
            Paragraph(prn, c_style),
            Paragraph(xml_escape(st_r.name), c_style),
            Paragraph(xml_escape(st_r.program), c_style),
            Paragraph(srs_str, c_style),
            Paragraph(str(len(sched_list)), c_style),
            Paragraph(sched_display, c_style),
            status_para,
        ])
        if has_clash:
            chk_table_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#FED7D7")))
        elif row_idx % 2 == 0:
            chk_table_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), LIGHT_GREY))

    chk_table = Table(chk_rows, colWidths=[65, 85, 68, 65, 45, 150, 45], repeatRows=1)
    chk_table.setStyle(TableStyle(chk_table_styles))
    elements.append(chk_table)
    elements.append(Spacer(1, 14))

    # (d) Unparseable rows
    elements.append(Paragraph(
        "<b>Unparseable Rows</b>",
        ParagraphStyle('H2_Unparse', parent=body_style, fontName=FONT_BOLD, fontSize=11, textColor=DARK_BLUE)
    ))
    elements.append(Spacer(1, 4))
    if parse_result.failed:
        fail_headers = [Paragraph(h, header_cell_style) for h in ["Page", "Line / Error", "Raw Content"]]
        fail_rows = [fail_headers]
        for f in parse_result.failed:
            fail_rows.append([
                Paragraph(str(f.get("page", "-")), body_style),
                Paragraph(xml_escape(str(f.get("error", "-"))), body_style),
                Paragraph(xml_escape(str(f.get("raw", "-"))), body_style),
            ])
        fail_table = Table(fail_rows, colWidths=[50, 150, 323], repeatRows=1)
        fail_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(fail_table)
    else:
        elements.append(Paragraph("None", body_style))
    elements.append(Spacer(1, 14))

    # (e) Course-name merges applied
    elements.append(Paragraph(
        "<b>Course-Name Merges Applied</b>",
        ParagraphStyle('H2_Merges', parent=body_style, fontName=FONT_BOLD, fontSize=11, textColor=DARK_BLUE)
    ))
    elements.append(Spacer(1, 4))
    multi_spell_exams = [e for e in exams if len(e.spellings) > 1 or (merge_map and e.key in merge_map.values())]
    if multi_spell_exams:
        m_header_style = ParagraphStyle('MHCell', parent=header_cell_style, fontSize=7.5, leading=9, textColor=colors.white)
        m_headers = [Paragraph(h, m_header_style) for h in ["Sr", "Canonical Exam Name", "Course Codes", "Merged Spellings / Variants", "Students"]]
        m_rows = [m_headers]
        m_cell_style = ParagraphStyle('MCell', parent=body_style, fontSize=7, leading=8.5)
        for m_idx, e in enumerate(multi_spell_exams, start=1):
            m_rows.append([
                Paragraph(str(m_idx), m_cell_style),
                Paragraph(xml_escape(e.name), m_cell_style),
                Paragraph(xml_escape(", ".join(e.codes)), m_cell_style),
                Paragraph(xml_escape("; ".join(e.spellings)), m_cell_style),
                Paragraph(str(len(e.prns)), m_cell_style),
            ])
        m_table = Table(m_rows, colWidths=[25, 140, 80, 223, 55], repeatRows=1)
        m_style = [
            ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 2.5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2.5),
        ]
        for r_i in range(1, len(m_rows)):
            if r_i % 2 == 0:
                m_style.append(('BACKGROUND', (0, r_i), (-1, r_i), LIGHT_GREY))
        m_table.setStyle(TableStyle(m_style))
        elements.append(m_table)
    else:
        elements.append(Paragraph("None", body_style))
    elements.append(Spacer(1, 14))

    signoff_style = ParagraphStyle(name="Signoff", parent=body_style, fontName=FONT_BOLD)
    signoff_table = Table([
        [Paragraph("Verified By Examination Cell:", signoff_style), Paragraph("Controller of Examinations:", signoff_style)],
        [Spacer(1, 30), Spacer(1, 30)],
        [Paragraph("Signature & Date: ___________________", body_style), Paragraph(f"{xml_escape(settings.controller_name)}<br/>Signature & Seal: ___________________", body_style)]
    ], colWidths=[260, 263])
    signoff_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(KeepTogether([signoff_table]))

    doc.build(elements, canvasmaker=NumberedCanvas)
    return output_path


def generate_timetable_pdf(
    schedule: Schedule,
    settings: Settings,
    output_path: Path
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    _, body_style, header_cell_style, _, _ = get_base_styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=landscape(A4),
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=45
    )
    elements: List[Any] = []
    _build_header(elements, settings, "EXAMINATION TIMETABLE (MASTER GRID)")

    slot_exams: Dict[Tuple[str, str], List[Any]] = collections.defaultdict(list)
    dates_set = set()
    for it in schedule.items:
        slot_exams[(it.slot.date, it.slot.session)].append(it)
        dates_set.add(it.slot.date)

    sorted_dates = sorted(list(dates_set))
    grid_data = [
        [
            Paragraph("Date & Day", header_cell_style),
            Paragraph(f"Morning Session ({settings.morning_start} - {settings.morning_end})", header_cell_style),
            Paragraph(f"Afternoon Session ({settings.afternoon_start} - {settings.afternoon_end})", header_cell_style),
        ]
    ]

    for d_str in sorted_dates:
        d_obj = datetime.strptime(d_str, "%Y-%m-%d")
        day_label = f"<b>{d_str}</b><br/>{d_obj.strftime('%A')}"

        m_items = slot_exams.get((d_str, "Morning"), [])
        a_items = slot_exams.get((d_str, "Afternoon"), [])

        m_texts = [f"• <b>{xml_escape(it.exam.name)}</b> ({xml_escape(', '.join(it.exam.codes))}) - [{len(it.exam.prns)} students]" for it in m_items]
        a_texts = [f"• <b>{xml_escape(it.exam.name)}</b> ({xml_escape(', '.join(it.exam.codes))}) - [{len(it.exam.prns)} students]" for it in a_items]

        m_cell = "<br/>".join(m_texts) if m_texts else "<i>No exams scheduled</i>"
        a_cell = "<br/>".join(a_texts) if a_texts else "<i>No exams scheduled</i>"

        grid_data.append([
            Paragraph(day_label, body_style),
            Paragraph(m_cell, body_style),
            Paragraph(a_cell, body_style),
        ])

    grid_table = Table(grid_data, colWidths=[120, 325, 325], repeatRows=1)
    g_style = [
        ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]
    for r_idx in range(1, len(grid_data)):
        if r_idx % 2 == 0:
            g_style.append(('BACKGROUND', (0, r_idx), (-1, r_idx), LIGHT_GREY))
    grid_table.setStyle(TableStyle(g_style))
    elements.append(grid_table)

    doc.build(elements, canvasmaker=NumberedCanvas)
    return output_path


def generate_attendance_pdf(
    parse_result: ParseResult,
    schedule: Schedule,
    settings: Settings,
    output_path: Path,
    exam_key: Optional[str] = None
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    _, body_style, header_cell_style, _, _ = get_base_styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=40
    )
    elements: List[Any] = []

    # Map (prn, normalize_name(course_name)) -> Row for student's exact exam row
    student_exam_rows: Dict[Tuple[str, str], Row] = {}
    student_general: Dict[str, Row] = {}

    for r in parse_result.rows:
        if r.prn not in student_general:
            student_general[r.prn] = r
        k = normalize_name(r.course_name)
        if (r.prn, k) not in student_exam_rows:
            student_exam_rows[(r.prn, k)] = r

    def get_student_row_for_exam(prn_val: str, ex_obj: Any) -> Optional[Row]:
        matched = student_exam_rows.get((prn_val, ex_obj.key))
        if not matched:
            for sp in ex_obj.spellings:
                k_sp = normalize_name(sp)
                if (prn_val, k_sp) in student_exam_rows:
                    matched = student_exam_rows[(prn_val, k_sp)]
                    break
        return matched or student_general.get(prn_val)

    att_cell_style = ParagraphStyle(
        name="AttCell",
        parent=body_style,
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#2D3748")
    )
    att_hcell_style = ParagraphStyle(
        name="AttHCell",
        parent=header_cell_style,
        fontSize=7.5,
        leading=9.5,
        textColor=colors.white
    )

    items_to_render = schedule.items
    if exam_key:
        items_to_render = [it for it in schedule.items if it.exam.key == exam_key]

    # Available width = 595.27 - 72 = 523.27 pt
    # ColWidths: Sr 20, PRN 72, Name 115, Program 80, Year 80, Code 92, Sig 64 = 523 pt
    col_widths = [25, 72, 110, 90, 72, 90, 64]
    MAX_PER_PAGE = 20

    page_counter = 0

    for it in items_to_render:
        prns = it.exam.prns
        if not prns:
            chunks = [[]]
        elif len(prns) <= MAX_PER_PAGE:
            chunks = [prns]
        else:
            num_pages = math.ceil(len(prns) / MAX_PER_PAGE)
            chunk_size = math.ceil(len(prns) / num_pages)
            chunks = [prns[i : i + chunk_size] for i in range(0, len(prns), chunk_size)]

        overall_s_idx = 1
        for chunk_idx, prn_chunk in enumerate(chunks):
            if page_counter > 0:
                elements.append(PageBreak())
            page_counter += 1

            _build_header(elements, settings, "EXAMINATION ATTENDANCE SHEET")

            sheet_suffix = f" (Sheet {chunk_idx + 1} of {len(chunks)})" if len(chunks) > 1 else ""
            exam_info = (
                f"<b>Course / Exam:</b> {xml_escape(it.exam.name)}{sheet_suffix} &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"<b>Codes:</b> {xml_escape(', '.join(it.exam.codes))}<br/>"
                f"<b>Date:</b> {it.slot.date} ({it.slot.session}) &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"<b>Time:</b> {it.slot.start} - {it.slot.end} &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"<b>Total Candidates:</b> {len(it.exam.prns)}"
            )
            elements.append(Paragraph(exam_info, body_style))
            elements.append(Spacer(1, 6))

            headers = [Paragraph(h, att_hcell_style) for h in ["Sr", "PRN", "Student Name", "Program", "Year", "Code", "Signature"]]
            table_rows = [headers]

            for prn in prn_chunk:
                sample_r = get_student_row_for_exam(prn, it.exam)
                s_name = sample_r.name if sample_r else "Student"
                s_prog = sample_r.program if sample_r else "-"
                s_year = sample_r.year if sample_r else "-"
                s_code = sample_r.course_code if (sample_r and sample_r.course_code) else (it.exam.codes[0] if it.exam.codes else "-")

                table_rows.append([
                    Paragraph(str(overall_s_idx), att_cell_style),
                    Paragraph(prn, att_cell_style),
                    Paragraph(xml_escape(s_name), att_cell_style),
                    Paragraph(xml_escape(s_prog), att_cell_style),
                    Paragraph(xml_escape(s_year), att_cell_style),
                    Paragraph(xml_escape(s_code), att_cell_style),
                    Paragraph("", att_cell_style),
                ])
                overall_s_idx += 1

            att_table = Table(table_rows, colWidths=col_widths, repeatRows=1)
            a_style = [
                ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
                ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
                ('TOPPADDING', (0, 0), (-1, -1), 2.5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
                ('LEFTPADDING', (0, 0), (-1, -1), 2.5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2.5),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]
            for r_i in range(1, len(table_rows)):
                if r_i % 2 == 0:
                    a_style.append(('BACKGROUND', (0, r_i), (-1, r_i), LIGHT_GREY))
            att_table.setStyle(TableStyle(a_style))
            elements.append(att_table)
            elements.append(Spacer(1, 40))

            footer_stats = Table([
                [Paragraph("<b>Candidates Present:</b> _________", att_cell_style), Paragraph("<b>Candidates Absent:</b> _________", att_cell_style)],
                [Spacer(1, 10), Spacer(1, 10)],
                [Paragraph("<b>Junior Supervisor Name & Sign:</b> ___________________________", att_cell_style),
                 Paragraph("<b>Senior Supervisor Name & Sign:</b> ___________________________", att_cell_style)]
            ], colWidths=[260, 263])
            footer_stats.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEABOVE', (0, 0), (-1, 0), 0.5, BORDER_GREY)]))
            elements.append(KeepTogether([footer_stats]))

    doc.build(elements, canvasmaker=NumberedCanvas)
    return output_path


def generate_hall_tickets_pdf(
    parse_result: ParseResult,
    schedule: Schedule,
    settings: Settings,
    output_path: Path,
    target_prn: Optional[str] = None
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    _, body_style, header_cell_style, title_style, subtitle_style = get_base_styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=30,
        rightMargin=30,
        topMargin=25,
        bottomMargin=25
    )
    elements: List[Any] = []

    ht_title_style = ParagraphStyle(
        name="HTTitle",
        parent=title_style,
        fontSize=12,
        leading=14,
        alignment=1,
        textColor=DARK_BLUE,
    )
    ht_sub_style = ParagraphStyle(
        name="HTSub",
        parent=subtitle_style,
        fontSize=8,
        leading=10,
        alignment=1,
        textColor=colors.HexColor("#4A5568"),
    )
    ht_doc_title_style = ParagraphStyle(
        name="HTDocTitle",
        parent=ht_title_style,
        fontSize=10,
        leading=11.5,
        alignment=1,
        textColor=DARK_BLUE,
    )
    ht_body_style = ParagraphStyle(
        name="HTBody",
        parent=body_style,
        fontName=FONT_NAME,
        fontSize=7,
        leading=8.5,
        textColor=colors.HexColor("#2D3748")
    )
    ht_header_cell_style = ParagraphStyle(
        name="HTHeaderCell",
        parent=header_cell_style,
        fontName=FONT_BOLD,
        fontSize=7,
        leading=8.5,
        textColor=colors.white
    )
    ht_inst_style = ParagraphStyle(
        name="HTInst",
        parent=body_style,
        fontName=FONT_NAME,
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor("#4A5568")
    )

    student_exams: Dict[str, List[Any]] = collections.defaultdict(list)
    student_info: Dict[str, Any] = {}
    student_years: Dict[str, Set[str]] = collections.defaultdict(set)
    student_exam_codes: Dict[Tuple[str, str], List[str]] = collections.defaultdict(list)

    for it in schedule.items:
        for prn in it.exam.prns:
            student_exams[prn].append(it)

    for r in parse_result.rows:
        if r.prn not in student_info:
            student_info[r.prn] = r
        if r.year:
            student_years[r.prn].add(r.year.strip())
        if r.course_code:
            k = normalize_name(r.course_name)
            if r.course_code not in student_exam_codes[(r.prn, k)]:
                student_exam_codes[(r.prn, k)].append(r.course_code)

    prns_to_render = sorted(list(student_exams.keys()))
    if target_prn:
        prns_to_render = [target_prn] if target_prn in student_exams else []

    for idx, prn in enumerate(prns_to_render):
        if idx > 0:
            elements.append(PageBreak())

        elements.append(Paragraph(xml_escape(settings.college_name), ht_title_style))
        elements.append(Spacer(1, 1))
        elements.append(Paragraph(f"{xml_escape(settings.department)}  |  {xml_escape(settings.exam_title)}", ht_sub_style))
        elements.append(Spacer(1, 2))
        elements.append(Paragraph("EXAMINATION HALL TICKET / ADMIT CARD", ht_doc_title_style))
        elements.append(HRFlowable(width="100%", thickness=0.8, color=DARK_BLUE, spaceBefore=2, spaceAfter=4))

        r = student_info.get(prn)
        s_name = r.name if r else "Student"
        s_prog = r.program if r else "-"

        # Requirement 5: if backlogs in more than one year, print "Year: Second, Third, Fourth" (all years, sorted)
        raw_years = student_years.get(prn, set())
        if len(raw_years) > 1:
            cleaned_years = set()
            for y in raw_years:
                c = re.sub(r'(?i)\s*\byear\b\s*', '', y).strip()
                cleaned_years.add(c.capitalize())
            year_order = {"first": 1, "second": 2, "third": 3, "fourth": 4}
            sorted_years = sorted(list(cleaned_years), key=lambda x: year_order.get(x.lower(), 99))
            s_year = ", ".join(sorted_years)
        elif len(raw_years) == 1:
            s_year = list(raw_years)[0]
        else:
            s_year = "-"

        info_data = [
            [Paragraph(f"<b>Student Name:</b> {xml_escape(s_name)}", ht_body_style), Paragraph(f"<b>PRN:</b> {prn}", ht_body_style)],
            [Paragraph(f"<b>Program:</b> {xml_escape(s_prog)}", ht_body_style), Paragraph(f"<b>Year:</b> {xml_escape(s_year)}", ht_body_style)],
        ]
        info_table = Table(info_data, colWidths=[335, 200])
        info_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GREY),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 4))

        headers = [Paragraph(h, ht_header_cell_style) for h in ["Sr", "Course / Subject Name", "Course Code", "Date", "Session", "Time"]]
        ex_rows = [headers]

        sorted_exams = sorted(student_exams[prn], key=lambda x: (x.slot.date, 0 if x.slot.session == "Morning" else 1, x.exam.name))
        for e_idx, it in enumerate(sorted_exams, start=1):
            st_codes = student_exam_codes.get((prn, it.exam.key), [])
            if not st_codes:
                for row_item in parse_result.rows:
                    if row_item.prn == prn and (row_item.course_name in it.exam.spellings or (it.exam.codes and row_item.course_code in it.exam.codes)):
                        if row_item.course_code and row_item.course_code not in st_codes:
                            st_codes.append(row_item.course_code)
            code_disp = ", ".join(st_codes) if st_codes else (it.exam.codes[0] if it.exam.codes else "-")

            ex_rows.append([
                Paragraph(str(e_idx), ht_body_style),
                Paragraph(xml_escape(it.exam.name), ht_body_style),
                Paragraph(xml_escape(code_disp), ht_body_style),
                Paragraph(it.slot.date, ht_body_style),
                Paragraph(it.slot.session, ht_body_style),
                Paragraph(f"{it.slot.start} - {it.slot.end}", ht_body_style),
            ])

        ex_table = Table(ex_rows, colWidths=[20, 195, 100, 70, 70, 80])
        ht_style = [
            ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        for r_i in range(1, len(ex_rows)):
            if r_i % 2 == 0:
                ht_style.append(('BACKGROUND', (0, r_i), (-1, r_i), LIGHT_GREY))
        ex_table.setStyle(TableStyle(ht_style))
        elements.append(ex_table)
        elements.append(Spacer(1, 4))

        note_text = (
            "<b>Important Instructions for Candidate:</b> "
            "1. Must carry College Identity Card along with this Hall Ticket to examination hall. "
            "2. Report to hall at least 20 minutes prior to session time. "
            "3. Mobile phones, smartwatches, and unauthorized materials are strictly prohibited."
        )
        elements.append(Paragraph(note_text, ht_inst_style))
        elements.append(Spacer(1, 4))

        sign_table = Table([
            [Paragraph("Candidate Signature: _______________________", ht_body_style),
             Paragraph("___________________________<br/>Controller of Examinations", ht_body_style)]
        ], colWidths=[270, 265])
        sign_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(sign_table)

    doc.build(elements)
    return output_path


def generate_complete_report_pdf(
    parse_result: ParseResult,
    merge_map: Optional[Dict[str, str]],
    schedule: Schedule,
    settings: Settings,
    output_path: Path
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    v_res = verify(parse_result, merge_map, schedule, settings)
    _, body_style, header_cell_style, title_style, subtitle_style = get_base_styles()

    portrait_frame = Frame(
        36, 45, 523, 760,
        id='portrait_frame',
        topPadding=0, bottomPadding=0, leftPadding=0, rightPadding=0
    )
    landscape_frame = Frame(
        36, 45, 770, 510,
        id='landscape_frame',
        topPadding=0, bottomPadding=0, leftPadding=0, rightPadding=0
    )

    doc = BaseDocTemplate(
        str(output_path),
        pagesize=A4,
        pageTemplates=[
            PageTemplate(id='portrait', frames=[portrait_frame], pagesize=A4),
            PageTemplate(id='landscape', frames=[landscape_frame], pagesize=landscape(A4)),
        ]
    )

    elements: List[Any] = []

    # Map (prn, normalize_name(course_name)) -> Row for exact student row lookup
    student_exam_rows: Dict[Tuple[str, str], Row] = {}
    student_general: Dict[str, Row] = {}
    for r in parse_result.rows:
        if r.prn not in student_general:
            student_general[r.prn] = r
        k = normalize_name(r.course_name)
        if (r.prn, k) not in student_exam_rows:
            student_exam_rows[(r.prn, k)] = r

    def get_student_row_for_exam(prn_val: str, ex_obj: Any) -> Optional[Row]:
        matched = student_exam_rows.get((prn_val, ex_obj.key))
        if not matched:
            for sp in ex_obj.spellings:
                k_sp = normalize_name(sp)
                if (prn_val, k_sp) in student_exam_rows:
                    matched = student_exam_rows[(prn_val, k_sp)]
                    break
        return matched or student_general.get(prn_val)

    # 1. Cover Page
    elements.append(Spacer(1, 40))
    cover_inst_style = ParagraphStyle(
        name="CoverInst",
        parent=title_style,
        fontSize=20,
        leading=26,
        textColor=DARK_BLUE,
        alignment=1,
    )
    elements.append(Paragraph(xml_escape(settings.college_name), cover_inst_style))
    elements.append(Spacer(1, 10))
    cover_sub_style = ParagraphStyle(
        name="CoverSub",
        parent=subtitle_style,
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#4A5568"),
        alignment=1,
    )
    elements.append(Paragraph(f"{xml_escape(settings.department)}  |  {xml_escape(settings.exam_title)}", cover_sub_style))
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="80%", thickness=2, color=DARK_BLUE, spaceBefore=4, spaceAfter=25))

    cover_title_style = ParagraphStyle(
        name="CoverTitle",
        parent=title_style,
        fontSize=19,
        leading=24,
        textColor=DARK_BLUE,
        alignment=1,
    )
    elements.append(Paragraph("COMPLETE MASTER EXAMINATION REPORT", cover_title_style))
    elements.append(Spacer(1, 8))
    cover_desc_style = ParagraphStyle(
        name="CoverDesc",
        parent=subtitle_style,
        fontSize=11,
        leading=15,
        alignment=1,
        textColor=colors.HexColor("#2D3748"),
    )
    elements.append(Paragraph(f"Comprehensive Audit, Timetable, Attendance & Student Schedules<br/><b>{xml_escape(settings.exam_title)}</b>", cover_desc_style))
    elements.append(Spacer(1, 40))

    meta_style = ParagraphStyle(
        name="CoverMeta",
        parent=body_style,
        fontSize=9,
        leading=14,
        textColor=colors.HexColor("#4A5568"),
    )
    total_prns = len(set(r.prn for r in parse_result.rows))
    valid_h, _ = parse_and_validate_holidays(settings.holidays)
    cr_holidays_str = ", ".join(valid_h) if valid_h else "None"
    meta_data = [
        [Paragraph("<b>Report Generated On:</b>", meta_style), Paragraph(datetime.now(KOLKATA_TZ).strftime("%d %B %Y, %I:%M %p"), meta_style)],
        [Paragraph("<b>Total Unique Candidates:</b>", meta_style), Paragraph(str(total_prns), meta_style)],
        [Paragraph("<b>Total Backlog Exams:</b>", meta_style), Paragraph(str(len(schedule.items)), meta_style)],
        [Paragraph("<b>Examination Slots Utilized:</b>", meta_style), Paragraph(str(schedule.slots_used), meta_style)],
        [Paragraph("<b>Holidays Excluded:</b>", meta_style), Paragraph(xml_escape(cr_holidays_str), meta_style)],
        [Paragraph("<b>Controller of Examinations:</b>", meta_style), Paragraph(xml_escape(settings.controller_name), meta_style)],
    ]
    meta_table = Table(meta_data, colWidths=[200, 240])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GREY),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    elements.append(meta_table)
    elements.append(PageBreak())

    # 2. Table of Contents
    _build_header(elements, settings, "TABLE OF CONTENTS")
    toc_data = [
        [Paragraph("<b>Section</b>", header_cell_style), Paragraph("<b>Description</b>", header_cell_style)],
        [Paragraph("<b>Section 1</b>", body_style), Paragraph("Verification & Audit Summary", body_style)],
        [Paragraph("<b>Section 2</b>", body_style), Paragraph("Master Examination Timetable (Chronological)", body_style)],
        [Paragraph("<b>Section 3</b>", body_style), Paragraph("Course / Exam-wise Candidate Lists (Attendance Summary)", body_style)],
        [Paragraph("<b>Section 4</b>", body_style), Paragraph("Student-wise Personalized Schedules", body_style)],
    ]
    toc_table = Table(toc_data, colWidths=[120, 403])
    toc_style = [
        ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]
    for r_i in range(1, len(toc_data)):
        if r_i % 2 == 0:
            toc_style.append(('BACKGROUND', (0, r_i), (-1, r_i), LIGHT_GREY))
    toc_table.setStyle(TableStyle(toc_style))
    elements.append(toc_table)
    elements.append(PageBreak())

    # 3. Section 1: Verification Summary
    _build_header(elements, settings, "SECTION 1: VERIFICATION & AUDIT SUMMARY")
    elements.append(Paragraph(
        "This section documents the independent verification performed on the generated timetable. "
        "Every student-exam pairing has been verified against the raw input records to guarantee that no student exams are missed, "
        "no student has two exams in the same slot, and daily exam load constraints are satisfied.",
        body_style
    ))
    elements.append(Spacer(1, 6))
    valid_h, _ = parse_and_validate_holidays(settings.holidays)
    cr_sec1_holidays_str = ", ".join(valid_h) if valid_h else "None"
    elements.append(Paragraph(f"<b>Holidays excluded:</b> {xml_escape(cr_sec1_holidays_str)}", body_style))
    elements.append(Spacer(1, 10))

    audit_summary_data = [
        [Paragraph("Audit Metric", header_cell_style), Paragraph("Count", header_cell_style), Paragraph("Status", header_cell_style)],
        [Paragraph("Total Student-Exam Pairs Scheduled", body_style), Paragraph(str(v_res.pairs_scheduled), body_style), Paragraph("OK", body_style)],
        [Paragraph("Missing Student Pairs", body_style), Paragraph(str(len(v_res.missing_pairs)), body_style), Paragraph("OK" if not v_res.missing_pairs else "FAIL", body_style)],
        [Paragraph("Slot Clashes", body_style), Paragraph(str(len(v_res.clashes)), body_style), Paragraph("OK" if not v_res.clashes else "FAIL", body_style)],
        [Paragraph("Per-Day Limit Violations", body_style), Paragraph(str(len(v_res.per_day_violations)), body_style), Paragraph("OK" if not v_res.per_day_violations else "FAIL", body_style)],
    ]
    audit_table = Table(audit_summary_data, colWidths=[260, 130, 133])
    audit_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(audit_table)
    elements.append(PageBreak())

    # 4. Section 2: Master Timetable
    _build_header(elements, settings, "SECTION 2: MASTER TIMETABLE")
    tt_headers = [Paragraph(h, header_cell_style) for h in ["Date", "Session", "Time", "Exam Name", "Course Codes", "Students"]]
    tt_rows = [tt_headers]

    sorted_schedule = sorted(schedule.items, key=lambda it: (it.slot.date, 0 if it.slot.session == "Morning" else 1, it.exam.name))
    for it in sorted_schedule:
        tt_rows.append([
            Paragraph(it.slot.date, body_style),
            Paragraph(it.slot.session, body_style),
            Paragraph(f"{it.slot.start} - {it.slot.end}", body_style),
            Paragraph(xml_escape(it.exam.name), body_style),
            Paragraph(xml_escape(", ".join(it.exam.codes)), body_style),
            Paragraph(str(len(it.exam.prns)), body_style),
        ])

    tt_table = Table(tt_rows, colWidths=[66, 58, 78, 160, 108, 53], repeatRows=1)
    tt_style = [
        ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]
    for r_i in range(1, len(tt_rows)):
        if r_i % 2 == 0:
            tt_style.append(('BACKGROUND', (0, r_i), (-1, r_i), LIGHT_GREY))
    tt_table.setStyle(TableStyle(tt_style))
    elements.append(tt_table)
    elements.append(PageBreak())

    # 5. Section 3: Exam-wise Student Lists
    for idx, it in enumerate(sorted_schedule):
        if idx > 0:
            elements.append(PageBreak())

        _build_header(elements, settings, "SECTION 3: EXAM-WISE STUDENT LISTS")

        exam_meta = (
            f"<b>Course / Exam Name:</b> {xml_escape(it.exam.name)} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Course Codes:</b> {xml_escape(', '.join(it.exam.codes))}<br/>"
            f"<b>Date:</b> {it.slot.date} ({it.slot.session}) &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Time:</b> {it.slot.start} - {it.slot.end} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Total Candidates:</b> {len(it.exam.prns)}"
        )
        elements.append(Paragraph(exam_meta, body_style))
        elements.append(Spacer(1, 8))

        st_cell_style = ParagraphStyle(
            name="STCell",
            parent=body_style,
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor("#2D3748")
        )
        st_header_style = ParagraphStyle(
            name="STHeader",
            parent=header_cell_style,
            fontSize=7.5,
            leading=9.5,
            textColor=colors.white
        )

        st_headers = [Paragraph(h, st_header_style) for h in ["Sr", "PRN", "Student Name", "Program", "Year", "Course Code"]]
        st_rows = [st_headers]

        for s_num, prn in enumerate(it.exam.prns, start=1):
            sr_row = get_student_row_for_exam(prn, it.exam)
            s_name = sr_row.name if sr_row else "Student"
            s_prog = sr_row.program if sr_row else "-"
            s_year = sr_row.year if sr_row else "-"
            s_code = sr_row.course_code if (sr_row and sr_row.course_code) else (it.exam.codes[0] if it.exam.codes else "-")

            st_rows.append([
                Paragraph(str(s_num), st_cell_style),
                Paragraph(prn, st_cell_style),
                Paragraph(xml_escape(s_name), st_cell_style),
                Paragraph(xml_escape(s_prog), st_cell_style),
                Paragraph(xml_escape(s_year), st_cell_style),
                Paragraph(xml_escape(s_code), st_cell_style),
            ])

        st_table = Table(st_rows, colWidths=[20, 85, 147, 98, 87, 85], repeatRows=1)
        st_style = [
            ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 2.5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2.5),
        ]
        for r_i in range(1, len(st_rows)):
            if r_i % 2 == 0:
                st_style.append(('BACKGROUND', (0, r_i), (-1, r_i), LIGHT_GREY))
        st_table.setStyle(TableStyle(st_style))
        elements.append(st_table)

    elements.append(NextPageTemplate('landscape'))
    elements.append(PageBreak())

    # 6. Section 4: Student-wise Schedules (Grouped per student in Landscape)
    _build_header(elements, settings, "SECTION 4: STUDENT-WISE EXAMINATION SCHEDULE")
    elements.append(Paragraph(
        "This section lists all enrolled students with their complete personalized examination schedule, "
        "grouped per student with exact dates, sessions, and timings.",
        body_style
    ))
    elements.append(Spacer(1, 8))

    sw_body_style = ParagraphStyle(
        name="SWBody",
        parent=body_style,
        fontName=FONT_NAME,
        fontSize=7,
        leading=8.5,
        textColor=colors.HexColor("#2D3748")
    )
    sw_bold_style = ParagraphStyle(
        name="SWBold",
        parent=body_style,
        fontName=FONT_BOLD,
        fontSize=7,
        leading=8.5,
        textColor=colors.HexColor("#1A202C")
    )
    sw_header_style = ParagraphStyle(
        name="SWHeader",
        parent=header_cell_style,
        fontName=FONT_BOLD,
        fontSize=7.5,
        leading=9,
        textColor=colors.white
    )

    sw_headers = [Paragraph(h, sw_header_style) for h in ["Sr", "PRN", "Student Name", "Course / Exam Name", "Date", "Session", "Time"]]
    sw_rows = [sw_headers]

    student_exams: Dict[str, List[Any]] = collections.defaultdict(list)
    for it in sorted_schedule:
        for prn in it.exam.prns:
            student_exams[prn].append(it)

    sorted_prns = sorted(student_exams.keys())

    sw_style = [
        ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 2.5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2.5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]

    current_row = 1
    for s_idx, prn in enumerate(sorted_prns, start=1):
        sr_row = student_general.get(prn)
        s_name = sr_row.name if sr_row else "Student"
        ex_list = sorted(student_exams[prn], key=lambda x: (x.slot.date, 0 if x.slot.session == "Morning" else 1, x.exam.name))
        start_row = current_row

        for e_num, it in enumerate(ex_list):
            if e_num == 0:
                sr_cell = Paragraph(str(s_idx), sw_bold_style)
                prn_cell = Paragraph(prn, sw_bold_style)
                name_cell = Paragraph(xml_escape(s_name), sw_bold_style)
            else:
                sr_cell = Paragraph("", sw_body_style)
                prn_cell = Paragraph("", sw_body_style)
                name_cell = Paragraph("", sw_body_style)

            sw_rows.append([
                sr_cell,
                prn_cell,
                name_cell,
                Paragraph(xml_escape(it.exam.name), sw_body_style),
                Paragraph(it.slot.date, sw_body_style),
                Paragraph(it.slot.session, sw_body_style),
                Paragraph(f"{it.slot.start} - {it.slot.end}", sw_body_style),
            ])
            current_row += 1

        end_row = current_row - 1
        bg_col = LIGHT_GREY if (s_idx % 2 == 0) else colors.white
        sw_style.append(('BACKGROUND', (0, start_row), (-1, end_row), bg_col))
        sw_style.append(('LINEBELOW', (0, end_row), (-1, end_row), 0.75, DARK_BLUE))

    sw_col_widths = [8 * mm, 28 * mm, 50 * mm, 70 * mm, 22 * mm, 22 * mm, 28 * mm]
    sw_table = Table(sw_rows, colWidths=sw_col_widths, repeatRows=1)
    sw_table.setStyle(TableStyle(sw_style))
    elements.append(sw_table)

    doc.build(elements, canvasmaker=NumberedCanvas)
    return output_path
