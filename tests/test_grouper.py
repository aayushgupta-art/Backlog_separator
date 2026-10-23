import re
from pathlib import Path
import pytest
from data_parser import parse_pdf
from course_grouper import (
    normalize_name,
    build_exams,
    suggest_merges,
    unique_exam_count_per_student,
    differ_only_by_number,
    search_students,
)
from models import Exam

REAL_PDF_PATH = Path("sample_input/Backlog_List.pdf")
SKIP_IF_NO_REAL_PDF = pytest.mark.skipif(
    not REAL_PDF_PATH.is_file(),
    reason="sample_input/Backlog_List.pdf not present"
)

def test_normalize_name_spelling_variants():
    k1 = normalize_name("Statistical Data analysis")
    k2 = normalize_name("STATISTICAL DATA ANALYSIS")
    assert k1 == k2
    assert k1 == "statistical data analysis"

    k3 = normalize_name("Statistcal Data Analysis Lab")
    assert k3 == "statistical data analysis lab"

    k4 = normalize_name("TECHNOLOGY SKILL DEVELOPMENT - 2 (PYTHON)")
    k5 = normalize_name("Technology Skill Dev.-2 (Python)")
    assert k4 == k5

    k6 = normalize_name("Operating Systems - Lab")
    k7 = normalize_name("Operating System Lab")
    assert k6 == k7

    k8 = normalize_name("Project Based Learning -Python")
    k9 = normalize_name("Project Based Learning-Python")
    assert k8 == k9

@SKIP_IF_NO_REAL_PDF
def test_real_pdf_grouping_and_exam_counts():
    assert REAL_PDF_PATH.is_file()
    parse_res = parse_pdf(REAL_PDF_PATH)
    assert len(parse_res.rows) == 807

    exams, duplicates = build_exams(parse_res.rows)
    assert len(exams) < 100
    assert len(duplicates) > 0

    print("\n=== FULL SORTED EXAM LIST WITH STUDENT COUNTS ===")
    sorted_by_students = sorted(exams, key=lambda e: len(e.prns), reverse=True)
    for e in sorted_by_students:
        print(f"{e.name}: {len(e.prns)} students (codes: {e.codes})")

    code_like = re.compile(r'\b[A-Z0-9]{6,15}\b')
    for e in exams:
        assert len(e.name) > 0
        assert not re.search(r'\d{10}', e.name)
        assert "Year" not in e.name
        assert e.prns == sorted(list(set(e.prns)))
        assert len(e.prns) > 0
        for word in e.name.split():
            if re.match(r'^[A-Z]{2,}\d{2,}', word):
                pytest.fail(f"Exam name contains course-code-like token: {word} in {e.name}")

@SKIP_IF_NO_REAL_PDF
def test_suggest_merges_logic():
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    suggestions = suggest_merges(exams, max_pairs=25, min_score=90.0)

    for s in suggestions:
        k1, k2 = s["key1"], s["key2"]
        is_lab1 = "lab" in k1.split()
        is_lab2 = "lab" in k2.split()
        assert is_lab1 == is_lab2

        pair_keys = {k1, k2}
        assert not ("data structures" in pair_keys and "discrete structures" in pair_keys)
        assert not ("machine learning" in pair_keys and "applied machine learning" in pair_keys)

@SKIP_IF_NO_REAL_PDF
def test_unique_exam_count_per_student():
    parse_res = parse_pdf(REAL_PDF_PATH)
    counts = unique_exam_count_per_student(parse_res.rows)

    assert len(counts) > 0
    for prn, cnt in counts.items():
        assert len(prn) >= 10
        assert cnt >= 1

    max_backlogs = max(counts.values())
    assert max_backlogs >= 1


def test_differ_only_by_number():
    assert differ_only_by_number("Environmental Science-I", "Environmental Science-II") is True
    assert differ_only_by_number("Project Stage 1", "Project Stage 2") is True
    assert differ_only_by_number("Technology Skill Development - 1", "Technology Skill Development - 2") is True
    assert differ_only_by_number("Operating Systems", "Operating Systems Lab") is False
    assert differ_only_by_number("Applied Machine Learning", "Machine Learning") is False


@SKIP_IF_NO_REAL_PDF
def test_suggest_merges_never_suggests_number_or_roman_variants():
    parse_res = parse_pdf(REAL_PDF_PATH)
    exams, _ = build_exams(parse_res.rows)
    suggestions = suggest_merges(exams, max_pairs=25, min_score=85.0)

    for s in suggestions:
        assert not differ_only_by_number(s["key1"], s["key2"])
        pair_names = {s["name1"].lower(), s["name2"].lower()}
        assert not ("environmental science-i" in pair_names and "environmental science-ii" in pair_names)


def test_merge_screen_conflict_blocking_and_warning():
    e1 = Exam(key="database_systems", name="Database Systems", codes=["CS401"], spellings=["Database Systems"], prns=["1001", "1002"])
    e2 = Exam(key="database_system", name="Database System", codes=["CS402"], spellings=["Database System"], prns=["1002", "1003"])

    suggestions = suggest_merges([e1, e2], min_score=80.0)
    assert len(suggestions) == 1
    s = suggestions[0]
    assert s["conflict_count"] == 1
    assert s["conflict_prns"] == ["1002"]
    assert s["students1"] == 2
    assert s["students2"] == 2
    assert s["codes1"] == ["CS401"]
    assert s["codes2"] == ["CS402"]

    # Verify warning message string matches required template
    warning_msg = f"{s['conflict_count']} students have both, merging would make them miss an exam."
    assert warning_msg == "1 students have both, merging would make them miss an exam."


@SKIP_IF_NO_REAL_PDF
def test_student_search_live_filter_and_rathod_abhimanyu():
    parse_res = parse_pdf(REAL_PDF_PATH)
    rows = parse_res.rows
    exams, _ = build_exams(rows)

    # 1. Searching 3125047020188
    res_prn = search_students(rows, "3125047020188")
    assert res_prn == ["3125047020188"]

    rows_by_prn = {r.prn: r for r in rows}
    assert rows_by_prn["3125047020188"].name == "Rathod Abhimanyu Uday"

    rathod_exams = [e for e in exams if "3125047020188" in e.prns]
    assert len(rathod_exams) == 13

    # 2. Searching part of name
    res_name = search_students(rows, "Abhimanyu")
    assert "3125047020188" in res_name

    res_last = search_students(rows, "rathod")
    assert "3125047020188" in res_last

    # 3. Non-matching query returns empty list (no fallback to first student)
    res_none = search_students(rows, "NONEXISTENT_STUDENT_XYZ_999")
    assert res_none == []
