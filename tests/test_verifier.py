import copy
from pathlib import Path
import pytest
from config import get_default_settings
from data_parser import parse_pdf
from course_grouper import build_exams
from scheduler import schedule_exams
from verifier import verify
from models import Slot, ScheduledExam

REAL_PDF_PATH = Path("sample_input/Backlog_List.pdf")
SKIP_IF_NO_REAL_PDF = pytest.mark.skipif(
    not REAL_PDF_PATH.is_file(),
    reason="sample_input/Backlog_List.pdf not present"
)

@SKIP_IF_NO_REAL_PDF
def test_verifier_good_schedule_passes():
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    res = verify(parse_res, None, schedule, settings)

    assert res.ok is True
    assert res.rows_read == 807
    assert res.duplicate_rows > 0
    assert res.unique_students > 0
    assert res.unique_pairs > 0
    assert res.exams == len(exams)
    assert res.pairs_scheduled == res.unique_pairs
    assert res.missing_pairs == []
    assert res.extra_pairs == []
    assert res.clashes == []
    assert res.per_day_violations == []
    assert res.exam_count_mismatches == []

@SKIP_IF_NO_REAL_PDF
def test_verifier_detects_removed_student_as_missing_pair():
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    tampered_schedule = copy.deepcopy(schedule)
    first_item = tampered_schedule.items[0]
    removed_prn = first_item.exam.prns.pop(0)

    res = verify(parse_res, None, tampered_schedule, settings)

    assert res.ok is False
    assert len(res.missing_pairs) >= 1
    missing_prns = [pair[0] for pair in res.missing_pairs]
    assert removed_prn in missing_prns
    assert len(res.exam_count_mismatches) >= 1

@SKIP_IF_NO_REAL_PDF
def test_verifier_detects_forced_clash():
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    settings = get_default_settings()
    schedule = schedule_exams(exams, settings)

    tampered_schedule = copy.deepcopy(schedule)

    item1 = None
    item2 = None
    shared_prn = None
    for i in range(len(tampered_schedule.items)):
        for j in range(i + 1, len(tampered_schedule.items)):
            common = set(tampered_schedule.items[i].exam.prns) & set(tampered_schedule.items[j].exam.prns)
            if common:
                item1 = tampered_schedule.items[i]
                item2 = tampered_schedule.items[j]
                shared_prn = next(iter(common))
                break
        if item1:
            break

    assert item1 is not None and item2 is not None

    item2.slot = Slot(
        date=item1.slot.date,
        session=item1.slot.session,
        start=item1.slot.start,
        end=item1.slot.end
    )

    res = verify(parse_res, None, tampered_schedule, settings)

    assert res.ok is False
    assert len(res.clashes) >= 1
    clashing_prns = [c["prn"] for c in res.clashes]
    assert shared_prn in clashing_prns
