import pytest
from models import (
    Row,
    ParseResult,
    Exam,
    Slot,
    ScheduledExam,
    Schedule,
    VerifyResult,
    Settings,
)

def test_row_instantiation_and_to_dict():
    row = Row(
        sr=1,
        prn="2281370165",
        name="Adane Krushna",
        course_code="BTECAI21701",
        course_name="Advanced Machine Learning",
        program="BTECH.AIDS",
        year="Fourth Year",
        ay="2024-25",
        sem="1",
        page=1,
    )
    assert row.sr == 1
    assert row.prn == "2281370165"
    assert row.course_code == "BTECAI21701"
    assert row.sem == "1"
    assert row.page == 1

    d = row.to_dict()
    assert isinstance(d, dict)
    assert d["sr"] == 1
    assert d["prn"] == "2281370165"
    assert d["name"] == "Adane Krushna"
    assert d["course_code"] == "BTECAI21701"
    assert d["course_name"] == "Advanced Machine Learning"

def test_parse_result_to_dict():
    row = Row(
        sr=2,
        prn="3124047010069",
        name="Arya Chaudhari",
        course_code="AE24AI02A",
        course_name="Campus to Corporate",
        program="B.Tech. (AI&DS)",
        year="Second Year",
        ay="2025-26",
        sem="2",
        page=2,
    )
    res = ParseResult(
        rows=[row],
        failed=[{"page": 3, "raw_text": "corrupt", "reason": "unmatched"}],
        missing_sr=[1],
        stats={"total_pages": 3},
    )
    assert len(res.rows) == 1
    assert res.missing_sr == [1]
    assert len(res.failed) == 1

    d = res.to_dict()
    assert len(d["rows"]) == 1
    assert d["rows"][0]["sr"] == 2
    assert d["failed"][0]["reason"] == "unmatched"
    assert d["missing_sr"] == [1]
    assert d["stats"]["total_pages"] == 3

def test_exam_and_slot_and_scheduled_exam():
    exam = Exam(
        key="machine_learning",
        name="Machine Learning",
        codes=["BTECAI21701", "BTECAI21702"],
        spellings=["Machine Learning", "MACHINE LEARNING"],
        prns=["2281370165", "3124047010069"],
    )
    assert exam.key == "machine_learning"
    assert len(exam.codes) == 2
    assert len(exam.prns) == 2

    slot = Slot(
        date="2026-11-01",
        session="Morning",
        start="10:00",
        end="13:00",
    )
    assert slot.date == "2026-11-01"
    assert slot.session == "Morning"
    assert slot.start == "10:00"
    assert slot.end == "13:00"

    scheduled = ScheduledExam(exam=exam, slot=slot)
    assert scheduled.exam.key == "machine_learning"
    assert scheduled.slot.session == "Morning"

    sched_dict = scheduled.to_dict()
    assert sched_dict["exam"]["key"] == "machine_learning"
    assert sched_dict["slot"]["start"] == "10:00"

def test_schedule_to_dict():
    exam = Exam(key="chem", name="Chemistry", codes=["CH101"], spellings=["Chemistry"], prns=["101"])
    slot = Slot(date="2026-11-01", session="Morning", start="10:00", end="13:00")
    scheduled = ScheduledExam(exam=exam, slot=slot)
    unscheduled_exam = Exam(key="phy", name="Physics", codes=["PH101"], spellings=["Physics"], prns=["102"])

    sch = Schedule(
        items=[scheduled],
        unscheduled=[unscheduled_exam],
        slots_used=1,
        min_slots_needed=2,
        warnings=["Room capacity reached"],
    )
    assert sch.slots_used == 1
    assert sch.min_slots_needed == 2
    assert len(sch.unscheduled) == 1

    d = sch.to_dict()
    assert len(d["items"]) == 1
    assert len(d["unscheduled"]) == 1
    assert d["unscheduled"][0]["name"] == "Physics"
    assert d["warnings"] == ["Room capacity reached"]

def test_verify_result_to_dict():
    vr = VerifyResult(
        ok=False,
        rows_read=807,
        duplicate_rows=12,
        unique_students=350,
        unique_pairs=420,
        exams=95,
        pairs_scheduled=419,
        missing_pairs=[("2281370165", "machine_learning")],
        extra_pairs=[],
        clashes=[{"prn": "111", "slot": "2026-11-01 Morning"}],
        per_day_violations=[],
        exam_count_mismatches=[],
    )
    assert vr.ok is False
    assert vr.rows_read == 807
    assert len(vr.missing_pairs) == 1
    assert len(vr.clashes) == 1

    d = vr.to_dict()
    assert d["ok"] is False
    assert d["rows_read"] == 807
    assert d["duplicate_rows"] == 12
    assert len(d["missing_pairs"]) == 1
