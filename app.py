import hashlib
import io
from pathlib import Path
from datetime import datetime, date, timedelta
import pandas as pd
import streamlit as st
from typing import Any, Dict, List, Optional, Tuple
from config import (
    load_settings,
    save_settings,
    get_default_settings,
    validate_session_timings,
    parse_and_validate_holidays,
    get_kolkata_today,
)
from models import Settings, ParseResult, Schedule, Exam
from data_parser import parse_pdf, parse_table_file
from course_grouper import build_exams, suggest_merges, unique_exam_count_per_student, normalize_name, search_students
from scheduler import schedule_exams, schedule_to_rows
from verifier import verify
from pdf_generator import (
    generate_audit_pdf,
    generate_timetable_pdf,
    generate_attendance_pdf,
    generate_hall_tickets_pdf,
    generate_complete_report_pdf,
)
from exporters import to_excel, to_csv, build_zip

st.set_page_config(page_title="Backlog Exam Scheduler", layout="wide")

if "settings" not in st.session_state:
    st.session_state.settings = load_settings()

if "merge_map" not in st.session_state:
    st.session_state.merge_map = {}

if "keep_set" not in st.session_state:
    st.session_state.keep_set = set()

if "parse_result" not in st.session_state:
    st.session_state.parse_result = None

if "schedule" not in st.session_state:
    st.session_state.schedule = None

if "file_hash" not in st.session_state:
    st.session_state.file_hash = None

settings: Settings = st.session_state.settings

# ----------------- SIDEBAR: SETTINGS -----------------
with st.sidebar:
    st.title("Settings")
    with st.form("settings_form"):
        st.subheader("Institution Details")
        college_name = st.text_input("College Name", value=settings.college_name)
        department = st.text_input("Department", value=settings.department)
        exam_title = st.text_input("Examination Title", value=settings.exam_title)
        controller_name = st.text_input("Controller of Examinations", value=settings.controller_name)

        st.subheader("Schedule Window")
        start_d_val = datetime.strptime(settings.start_date, "%Y-%m-%d").date() if settings.start_date else (get_kolkata_today() + timedelta(days=1))
        end_d_val = datetime.strptime(settings.end_date, "%Y-%m-%d").date() if settings.end_date else (start_d_val + timedelta(days=14))

        start_date = st.date_input("Start Date", value=start_d_val)
        end_date = st.date_input("End Date", value=end_d_val)

        skip_sundays = st.checkbox("Skip Sundays", value=settings.skip_sundays)
        holidays_default = "\n".join(settings.holidays) if settings.holidays else ""
        holidays_text = st.text_area(
            "Holidays",
            value=holidays_default,
            help="Enter one holiday date per line in YYYY-MM-DD format (e.g. 2026-11-15)",
            placeholder="2026-11-15\n2026-11-16",
            height=85,
        )
        valid_holidays, holiday_errors = parse_and_validate_holidays(holidays_text)
        for h_err in holiday_errors:
            st.error(h_err)

        auto_extend_days = st.checkbox("Auto-Extend Beyond End Date If Needed", value=settings.auto_extend_days)

        st.subheader("Session Timings")
        morning_start = st.text_input("Morning Start", value=settings.morning_start)
        morning_end = st.text_input("Morning End", value=settings.morning_end)
        afternoon_start = st.text_input("Afternoon Start", value=settings.afternoon_start)
        afternoon_end = st.text_input("Afternoon End", value=settings.afternoon_end)

        timing_errors = validate_session_timings(morning_start, morning_end, afternoon_start, afternoon_end)
        for err in timing_errors:
            st.error(err)

        st.subheader("Constraints")
        max_exams_per_day = st.selectbox(
            "Max Exams per Student per Day",
            options=[1, 2],
            index=0 if settings.max_exams_per_day == 1 else 1
        )
        lab_separate_from_theory = st.checkbox("Separate Lab from Theory in Different Slots", value=settings.lab_separate_from_theory)
        room_capacity = st.number_input("Room Capacity per Slot", min_value=10, max_value=2000, value=settings.room_capacity, step=10)

        saved = st.form_submit_button("Save Settings")
        if saved:
            if not timing_errors and not holiday_errors:
                new_settings = Settings(
                    college_name=college_name,
                    department=department,
                    exam_title=exam_title,
                    controller_name=controller_name,
                    logo_path=settings.logo_path,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    skip_sundays=skip_sundays,
                    holidays=valid_holidays,
                    morning_start=morning_start,
                    morning_end=morning_end,
                    afternoon_start=afternoon_start,
                    afternoon_end=afternoon_end,
                    max_exams_per_day=max_exams_per_day,
                    lab_separate_from_theory=lab_separate_from_theory,
                    auto_extend_days=auto_extend_days,
                    room_capacity=int(room_capacity),
                )
                save_settings(new_settings)
                st.session_state.settings = new_settings
                st.success("Settings saved successfully!")

# ----------------- MAIN TABS -----------------
st.title("Backlog Exam Scheduler")
tab_upload, tab_review, tab_generate, tab_results = st.tabs([
    "1. Upload Data",
    "2. Review Course Names",
    "3. Generate Timetable",
    "4. Results & Downloads"
])

# TAB 1: UPLOAD
with tab_upload:
    st.subheader("Upload Backlog Examination File")
    uploaded_file = st.file_uploader("Upload Backlog PDF / CSV / XLSX", type=["pdf", "csv", "xlsx"])

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        file_md5 = hashlib.md5(file_bytes).hexdigest()

        if st.session_state.file_hash != file_md5:
            try:
                fn = uploaded_file.name.lower()
                if fn.endswith(".pdf"):
                    res = parse_pdf(file_bytes)
                else:
                    res = parse_table_file(file_bytes, uploaded_file.name)

                st.session_state.parse_result = res
                st.session_state.file_hash = file_md5
                st.session_state.schedule = None
                st.session_state.merge_map = {}
                st.session_state.keep_set = set()
            except Exception as e:
                st.error(f"Error parsing uploaded file: {str(e)}")

    res: Optional[ParseResult] = st.session_state.parse_result
    if res is not None:
        exams_preview, duplicates_preview = build_exams(res.rows, st.session_state.merge_map)
        unique_students_cnt = len(set(r.prn for r in res.rows))

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Rows Read", len(res.rows))
        col2.metric("Unique Students", unique_students_cnt)
        col3.metric("Unique Exams", len(exams_preview))
        col4.metric("Duplicate Rows", len(duplicates_preview))

        if len(res.failed) == 0:
            col5.metric("Unparseable Rows", 0)
        else:
            col5.metric("Unparseable Rows", len(res.failed))
            st.error(f"Found {len(res.failed)} unparseable row(s):")
            for f in res.failed:
                st.write(f"Page {f.get('page')}: {f.get('raw_text')} ({f.get('reason')})")

        st.subheader("Data Preview (First 50 Rows)")
        preview_rows = [r.to_dict() for r in res.rows[:50]]
        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True)

        if duplicates_preview:
            with st.expander(f"View Flagged Duplicate Rows ({len(duplicates_preview)} items)"):
                st.dataframe(pd.DataFrame(duplicates_preview), use_container_width=True)
    else:
        st.info("Please upload a backlog document to begin.")

# TAB 2: REVIEW COURSE NAMES
with tab_review:
    st.subheader("Review & Normalization of Course Names")
    if res is not None:
        exams, _ = build_exams(res.rows, st.session_state.merge_map)

        st.write(f"Identified **{len(exams)}** distinct exams from raw course names.")
        exam_table_data = []
        for e in exams:
            exam_table_data.append({
                "Exam Key": e.key,
                "Display Name": e.name,
                "Course Codes": ", ".join(e.codes),
                "Student Count": len(e.prns),
                "Raw Spellings": " | ".join(e.spellings),
            })
        st.dataframe(pd.DataFrame(exam_table_data), use_container_width=True, height=280)

        st.divider()
        st.subheader("Possible duplicate subject names")
        st.info("Merge = same subject (one exam for everyone). Keep separate = different subjects. If unsure, keep separate.")

        suggestions = suggest_merges(exams, max_pairs=25, min_score=90.0)

        active_suggestions = [
            s for s in suggestions
            if (s["key1"], s["key2"]) not in st.session_state.keep_set
            and (s["key2"], s["key1"]) not in st.session_state.keep_set
            and s["key1"] != s["key2"]
        ]

        if not active_suggestions:
            st.success("No pending duplicate subject names found. All subjects are kept separate by default.")
        else:
            for idx, s in enumerate(active_suggestions):
                with st.container():
                    st.markdown(f"#### Pair #{idx + 1} &nbsp;*(Similarity: {s['score']}%)*")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"**Subject 1:** {s['name1']}")
                        st.markdown(f"- **Codes:** {', '.join(s['codes1']) if s['codes1'] else 'None'}")
                        st.markdown(f"- **Students:** {s['students1']}")
                    with col_b:
                        st.markdown(f"**Subject 2:** {s['name2']}")
                        st.markdown(f"- **Codes:** {', '.join(s['codes2']) if s['codes2'] else 'None'}")
                        st.markdown(f"- **Students:** {s['students2']}")

                    conflict_cnt = s.get("conflict_count", 0)
                    if conflict_cnt > 0:
                        st.error(f"{conflict_cnt} students have both, merging would make them miss an exam.")

                    def make_keep_callback(k1, k2):
                        def cb():
                            st.session_state.keep_set.add((k1, k2))
                        return cb

                    def make_merge_callback(k1, k2):
                        def cb():
                            st.session_state.merge_map[k2] = k1
                            st.session_state.schedule = None
                        return cb

                    bcol1, bcol2, _ = st.columns([1.5, 1.5, 5])
                    bcol1.button("Keep Separate (Default)", key=f"btn_keep_{idx}", on_click=make_keep_callback(s["key1"], s["key2"]))
                    if conflict_cnt > 0:
                        bcol2.button("Merge", key=f"btn_merge_{idx}", disabled=True, help=f"Blocked: {conflict_cnt} students enrolled in both")
                    else:
                        bcol2.button("Merge", key=f"btn_merge_{idx}", on_click=make_merge_callback(s["key1"], s["key2"]))
                    st.divider()
    else:
        st.info("Upload data in Tab 1 to review course names.")

# TAB 3: GENERATE TIMETABLE
with tab_generate:
    st.subheader("Generate & Verify Examination Timetable")
    active_timing_errors = timing_errors if ("timing_errors" in locals() and timing_errors) else validate_session_timings(
        st.session_state.settings.morning_start,
        st.session_state.settings.morning_end,
        st.session_state.settings.afternoon_start,
        st.session_state.settings.afternoon_end
    )
    active_holiday_errors = holiday_errors if ("holiday_errors" in locals() and holiday_errors) else parse_and_validate_holidays(st.session_state.settings.holidays)[1]
    all_blocking_errors = active_timing_errors + active_holiday_errors

    if all_blocking_errors:
        st.error("Generating timetable is blocked because settings contain errors:")
        for err in all_blocking_errors:
            st.error(err)
        st.button("Generate Timetable", type="primary", disabled=True)
    elif res is not None:
        if st.button("Generate Timetable", type="primary"):
            try:
                exams, _ = build_exams(res.rows, st.session_state.merge_map)
                sched = schedule_exams(exams, st.session_state.settings)
                st.session_state.schedule = sched
            except Exception as e:
                st.error(f"Error generating timetable: {str(e)}")

        sched: Optional[Schedule] = st.session_state.schedule
        if sched is not None:
            v_result = verify(res, st.session_state.merge_map, sched, st.session_state.settings)

            if v_result.ok:
                st.success("PASS: All students scheduled with 0 conflicts! Every exam scheduled exactly once.")
            else:
                st.error("FAIL: Verification conflicts detected! Please check details below.")
                if v_result.clashes:
                    st.write("Clashes:", v_result.clashes)
                if v_result.missing_pairs:
                    st.write("Missing pairs:", v_result.missing_pairs)

            for w in sched.warnings:
                st.warning(w)

            used_dates = sorted(list(set(it.slot.date for it in sched.items)))
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Days Used", len(used_dates))
            mc2.metric("Slots Used", sched.slots_used)
            mc3.metric("Total Exams Scheduled", len(sched.items))

            st.subheader("Master Timetable Grid")
            rows = schedule_to_rows(sched)
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.info("Upload data in Tab 1 to generate timetable.")

# TAB 4: RESULTS AND DOWNLOADS
with tab_results:
    st.subheader("Results Exploration & Official Downloads")
    sched = st.session_state.schedule
    if res is not None and sched is not None:
        view_mode = st.radio("Explorer View", ["Exam View", "Student View"], horizontal=True)

        rows_by_prn = {r.prn: r for r in res.rows}
        student_backlogs = unique_exam_count_per_student(res.rows, st.session_state.merge_map)

        if view_mode == "Exam View":
            exam_names = [it.exam.name for it in sched.items]
            selected_exam_name = st.selectbox("Select Exam", options=exam_names)
            selected_item = next(it for it in sched.items if it.exam.name == selected_exam_name)

            st.markdown(
                f"**Exam:** {selected_item.exam.name} &nbsp;|&nbsp; "
                f"**Slot:** {selected_item.slot.date} ({selected_item.slot.session}) &nbsp;|&nbsp; "
                f"**Time:** {selected_item.slot.start} - {selected_item.slot.end} &nbsp;|&nbsp; "
                f"**Codes:** {', '.join(selected_item.exam.codes)}"
            )

            student_rows = []
            for s_idx, prn in enumerate(selected_item.exam.prns, start=1):
                sr_row = rows_by_prn.get(prn)
                student_rows.append({
                    "Sr": s_idx,
                    "PRN": prn,
                    "Name": sr_row.name if sr_row else "-",
                    "Program": sr_row.program if sr_row else "-",
                    "Year": sr_row.year if sr_row else "-",
                    "Total Backlogs": student_backlogs.get(prn, 1)
                })
            st.dataframe(pd.DataFrame(student_rows), use_container_width=True)

        else:
            search_query = st.text_input("Search Student by PRN or Name")
            filtered = search_students(res.rows, search_query)

            if not filtered:
                st.warning("No student found")
            else:
                selected_prn = st.selectbox(
                    "Select Student PRN",
                    options=filtered,
                    format_func=lambda p: f"{p} - {rows_by_prn[p].name}" if p in rows_by_prn else p
                )
                if selected_prn:
                    sr_row = rows_by_prn.get(selected_prn)
                    name_str = sr_row.name if sr_row else "-"
                    b_count = student_backlogs.get(selected_prn, 1)

                    st.markdown(f"**Student:** {name_str} (PRN: {selected_prn})")
                    if b_count > 1:
                        st.warning(f"Notice: This student has {b_count} backlog exams. All are confirmed in conflict-free slots.")
                    else:
                        st.info("Student has 1 backlog exam.")

                    student_sched_items = [it for it in sched.items if selected_prn in it.exam.prns]
                    st_data = []
                    for it in sorted(student_sched_items, key=lambda x: (x.slot.date, x.slot.session)):
                        st_data.append({
                            "Exam Name": it.exam.name,
                            "Codes": ", ".join(it.exam.codes),
                            "Date": it.slot.date,
                            "Session": it.slot.session,
                            "Time": f"{it.slot.start} - {it.slot.end}",
                        })
                    st.dataframe(pd.DataFrame(st_data), use_container_width=True)

                    single_ht_path = Path("output") / f"HallTicket_{selected_prn}.pdf"
                    generate_hall_tickets_pdf(res, sched, st.session_state.settings, single_ht_path, target_prn=selected_prn)
                    with open(single_ht_path, "rb") as f:
                        single_ht_bytes = f.read()

                    st.download_button(
                        "Download Hall Ticket (this student)",
                        data=single_ht_bytes,
                        file_name=f"HallTicket_{selected_prn}.pdf",
                        mime="application/pdf",
                        key=f"dl_ht_{selected_prn}"
                    )

        st.divider()
        st.subheader("Official Downloads")
        st.write("Generate and download official PDF reports, attendance sheets, hall tickets, Excel sheets, and complete zip bundles.")

        out_tmp = Path("output")
        out_tmp.mkdir(parents=True, exist_ok=True)

        dcol1, dcol2, dcol3, dcol4 = st.columns(4)

        audit_p = out_tmp / "Audit_Report.pdf"
        generate_audit_pdf(res, st.session_state.merge_map, sched, st.session_state.settings, audit_p)
        with open(audit_p, "rb") as f:
            dcol1.download_button("Audit Report PDF", data=f.read(), file_name="Audit_Report.pdf", mime="application/pdf")

        cr_p = out_tmp / "Complete_Report.pdf"
        generate_complete_report_pdf(res, st.session_state.merge_map, sched, st.session_state.settings, cr_p)
        with open(cr_p, "rb") as f:
            dcol2.download_button("Complete Report PDF", data=f.read(), file_name="Complete_Report.pdf", mime="application/pdf")

        tt_p = out_tmp / "Timetable.pdf"
        generate_timetable_pdf(sched, st.session_state.settings, tt_p)
        with open(tt_p, "rb") as f:
            dcol3.download_button("Timetable PDF", data=f.read(), file_name="Timetable.pdf", mime="application/pdf")

        att_p = out_tmp / "Attendance_Sheets.pdf"
        generate_attendance_pdf(res, sched, st.session_state.settings, att_p)
        with open(att_p, "rb") as f:
            dcol4.download_button("Attendance Sheets PDF", data=f.read(), file_name="Attendance_Sheets.pdf", mime="application/pdf")

        dcol5, dcol6, dcol7, dcol8 = st.columns(4)

        ht_p = out_tmp / "Hall_Tickets.pdf"
        generate_hall_tickets_pdf(res, sched, st.session_state.settings, ht_p)
        with open(ht_p, "rb") as f:
            dcol5.download_button("Hall Tickets PDF", data=f.read(), file_name="Hall_Tickets.pdf", mime="application/pdf")

        xl_p = out_tmp / "Backlog_Schedule.xlsx"
        to_excel(res, sched, xl_p)
        with open(xl_p, "rb") as f:
            dcol6.download_button("Excel Workbook (.xlsx)", data=f.read(), file_name="Backlog_Schedule.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        csv_p = out_tmp / "Backlog_Schedule.csv"
        to_csv(res, sched, csv_p)
        with open(csv_p, "rb") as f:
            dcol7.download_button("CSV Schedule (.csv)", data=f.read(), file_name="Backlog_Schedule.csv", mime="text/csv")

        zip_p = out_tmp / "Everything_Export.zip"
        build_zip([audit_p, cr_p, tt_p, att_p, ht_p], xl_p, csv_p, zip_p)
        with open(zip_p, "rb") as f:
            dcol8.download_button("Everything ZIP Bundle", data=f.read(), file_name="Everything_Export.zip", mime="application/zip")
    else:
        st.info("Upload data and generate timetable to view results and downloads.")
