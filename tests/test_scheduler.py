import random
from pathlib import Path
import pytest
import networkx as nx
from config import get_default_settings
from data_parser import parse_pdf
from course_grouper import build_exams
from models import Exam, Settings
from scheduler import schedule_exams, schedule_to_rows

REAL_PDF_PATH = Path("sample_input/Backlog_List.pdf")
SKIP_IF_NO_REAL_PDF = pytest.mark.skipif(
    not REAL_PDF_PATH.is_file(),
    reason="sample_input/Backlog_List.pdf not present"
)

@SKIP_IF_NO_REAL_PDF
def test_real_pdf_scheduling_default_settings():
    assert REAL_PDF_PATH.is_file()
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()

    schedule = schedule_exams(exams, settings)

    assert len(schedule.items) == len(exams)
    assert len(schedule.unscheduled) == 0

    scheduled_keys = [it.exam.key for it in schedule.items]
    assert len(scheduled_keys) == len(set(scheduled_keys))

    slot_students_map = {}
    student_slots_map = {}
    exams_per_slot = {}
    students_per_slot = {}

    for it in schedule.items:
        slot_id = (it.slot.date, it.slot.session)
        exams_per_slot[slot_id] = exams_per_slot.get(slot_id, 0) + 1
        students_per_slot[slot_id] = students_per_slot.get(slot_id, 0) + len(it.exam.prns)

        if slot_id not in slot_students_map:
            slot_students_map[slot_id] = set()

        for prn in it.exam.prns:
            if prn in slot_students_map[slot_id]:
                pytest.fail(f"Student clash found in slot {slot_id} for PRN {prn}")
            slot_students_map[slot_id].add(prn)

            if prn not in student_slots_map:
                student_slots_map[prn] = []
            student_slots_map[prn].append(slot_id)

    for prn, slots_list in student_slots_map.items():
        if len(slots_list) >= 3:
            assert len(slots_list) == len(set(slots_list))

    # Independent NetworkX DSATUR coloring verification
    G = nx.Graph()
    for e in exams:
        G.add_node(e.key)
    for i in range(len(exams)):
        for j in range(i + 1, len(exams)):
            e1, e2 = exams[i], exams[j]
            if set(e1.prns) & set(e2.prns):
                G.add_edge(e1.key, e2.key)
            elif settings.lab_separate_from_theory and (e1.key + " lab" == e2.key or e2.key + " lab" == e1.key):
                G.add_edge(e1.key, e2.key)

    coloring = nx.coloring.greedy_color(G, strategy="DSATUR")
    best_independent = max(coloring.values()) + 1

    max_backlogs = max(len(slots_list) for slots_list in student_slots_map.values())

    assert schedule.slots_used <= best_independent + 3
    assert schedule.slots_used >= max_backlogs

    unique_dates = set(it.slot.date for it in schedule.items)

    # Print required statistics
    print(f"\n--- REAL PDF SCHEDULE STATS ---")
    print(f"Exams: {len(exams)}")
    print(f"Slots used: {schedule.slots_used}")
    print(f"Days used: {len(unique_dates)}")
    print(f"Exams per slot distribution: {sorted(list(exams_per_slot.values()))}")
    print(f"Students per slot min/max: {min(students_per_slot.values())} / {max(students_per_slot.values())}")

    # Check slots used with lab toggle off
    settings_no_lab = get_default_settings()
    settings_no_lab.lab_separate_from_theory = False
    schedule_no_lab = schedule_exams(exams, settings_no_lab)
    print(f"Slots with lab toggle ON: {schedule.slots_used}, OFF: {schedule_no_lab.slots_used}")

    rows = schedule_to_rows(schedule)
    assert len(rows) == len(exams)
    assert "Date" in rows[0]
    assert "Weekday" in rows[0]

def test_handmade_six_exams_two_slots():
    eA = Exam(key="a", name="A", codes=["C_A"], spellings=["A"], prns=["P1"])
    eB = Exam(key="b", name="B", codes=["C_B"], spellings=["B"], prns=["P1"])
    eC = Exam(key="c", name="C", codes=["C_C"], spellings=["C"], prns=["P2"])
    eD = Exam(key="d", name="D", codes=["C_D"], spellings=["D"], prns=["P3"])
    eE = Exam(key="e", name="E", codes=["C_E"], spellings=["E"], prns=["P4"])
    eF = Exam(key="f", name="F", codes=["C_F"], spellings=["F"], prns=["P5"])

    settings = get_default_settings()
    schedule = schedule_exams([eA, eB, eC, eD, eE, eF], settings)

    assert schedule.slots_used == 2
    assert len(schedule.items) == 6
    assert len(schedule.unscheduled) == 0

@SKIP_IF_NO_REAL_PDF
def test_max_exams_per_day_constraint():
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    settings.max_exams_per_day = 1

    schedule = schedule_exams(exams, settings)

    student_dates_map = {}
    for it in schedule.items:
        d = it.slot.date
        for prn in it.exam.prns:
            if prn not in student_dates_map:
                student_dates_map[prn] = []
            student_dates_map[prn].append(d)

    for prn, dates_list in student_dates_map.items():
        assert len(dates_list) == len(set(dates_list))

@SKIP_IF_NO_REAL_PDF
def test_end_date_and_auto_extend():
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)

    settings_fixed = get_default_settings()
    settings_fixed.auto_extend_days = False
    settings_fixed.end_date = settings_fixed.start_date

    sched_fixed = schedule_exams(exams, settings_fixed)
    assert len(sched_fixed.unscheduled) > 0
    assert len(sched_fixed.warnings) > 0

    settings_auto = get_default_settings()
    settings_auto.auto_extend_days = True
    settings_auto.end_date = settings_auto.start_date

    sched_auto = schedule_exams(exams, settings_auto)
    assert len(sched_auto.unscheduled) == 0
    assert len(sched_auto.items) == len(exams)

def test_random_stress_300_students_40_exams():
    rng = random.Random(42)
    students = [f"PRN_{1000 + i}" for i in range(300)]
    exams = []
    for i in range(40):
        k = f"exam_{i}"
        cnt = rng.randint(5, 35)
        prns = sorted(rng.sample(students, cnt))
        exams.append(Exam(key=k, name=f"Subject {i}", codes=[f"SUB{i}"], spellings=[f"Subject {i}"], prns=prns))

    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    assert len(schedule.items) == 40
    assert len(schedule.unscheduled) == 0

    slot_students = {}
    for it in schedule.items:
        slot_id = (it.slot.date, it.slot.session)
        if slot_id not in slot_students:
            slot_students[slot_id] = set()
        for prn in it.exam.prns:
            assert prn not in slot_students[slot_id]
            slot_students[slot_id].add(prn)

@SKIP_IF_NO_REAL_PDF
def test_holiday_inside_range_is_never_used():
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    settings.start_date = "2026-11-02"
    settings.end_date = "2026-11-20"
    holiday_date = "2026-11-04"
    settings.holidays = [holiday_date]

    schedule = schedule_exams(exams, settings)

    assert len(schedule.items) == len(exams)
    used_dates = {it.slot.date for it in schedule.items}
    assert holiday_date not in used_dates, f"Holiday date {holiday_date} must never be used in scheduled exams"

    from scheduler import generate_dates
    gen_dates = generate_dates(settings.start_date, settings.end_date, settings.skip_sundays, settings.holidays)
    assert holiday_date not in gen_dates

@SKIP_IF_NO_REAL_PDF
def test_two_holidays_in_a_row():
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    settings.start_date = "2026-11-02"
    settings.end_date = "2026-11-20"
    consecutive_holidays = ["2026-11-04", "2026-11-05"]
    settings.holidays = consecutive_holidays

    schedule = schedule_exams(exams, settings)

    assert len(schedule.items) == len(exams)
    used_dates = {it.slot.date for it in schedule.items}
    for h in consecutive_holidays:
        assert h not in used_dates, f"Consecutive holiday {h} must never be scheduled"

    from scheduler import generate_dates
    gen_dates = generate_dates(settings.start_date, settings.end_date, settings.skip_sundays, settings.holidays)
    assert "2026-11-03" in gen_dates
    assert "2026-11-04" not in gen_dates
    assert "2026-11-05" not in gen_dates
    assert "2026-11-06" in gen_dates
    idx_before = gen_dates.index("2026-11-03")
    idx_after = gen_dates.index("2026-11-06")
    assert idx_after == idx_before + 1, "Working days must advance directly past consecutive holidays"

@SKIP_IF_NO_REAL_PDF
def test_holiday_on_a_sunday():
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    settings.start_date = "2026-11-02"
    settings.end_date = "2026-11-20"
    sunday_holiday = "2026-11-08"  # 2026-11-08 is a Sunday
    settings.holidays = [sunday_holiday]

    # Test with skip_sundays = True
    settings.skip_sundays = True
    sched1 = schedule_exams(exams, settings)
    used_dates1 = {it.slot.date for it in sched1.items}
    assert sunday_holiday not in used_dates1

    # Test with skip_sundays = False (Sunday allowed generally, but this Sunday is a holiday)
    settings.skip_sundays = False
    sched2 = schedule_exams(exams, settings)
    used_dates2 = {it.slot.date for it in sched2.items}
    assert sunday_holiday not in used_dates2, "Sunday holiday must be excluded even if skip_sundays is False"

def test_auto_extend_past_end_date_skips_holidays():
    # 4 exams with conflict (all same student)
    e1 = Exam(key="e1", name="Exam 1", codes=["C1"], spellings=["Exam 1"], prns=["P100"])
    e2 = Exam(key="e2", name="Exam 2", codes=["C2"], spellings=["Exam 2"], prns=["P100"])
    e3 = Exam(key="e3", name="Exam 3", codes=["C3"], spellings=["Exam 3"], prns=["P100"])
    e4 = Exam(key="e4", name="Exam 4", codes=["C4"], spellings=["Exam 4"], prns=["P100"])

    settings = get_default_settings()
    settings.start_date = "2026-11-02"
    settings.end_date = "2026-11-02"  # Only 1 day (2 slots)
    settings.max_exams_per_day = 1     # Needs at least 4 distinct days
    settings.auto_extend_days = True
    # Days 2026-11-03 and 2026-11-04 are holidays
    settings.holidays = ["2026-11-03", "2026-11-04"]

    schedule = schedule_exams([e1, e2, e3, e4], settings)
    assert len(schedule.items) == 4
    used_dates = sorted(list(set(it.slot.date for it in schedule.items)))
    # Days should be 2026-11-02, 2026-11-05, 2026-11-06, 2026-11-07
    assert "2026-11-03" not in used_dates
    assert "2026-11-04" not in used_dates
    assert used_dates[0] == "2026-11-02"
    assert used_dates[1] == "2026-11-05"

