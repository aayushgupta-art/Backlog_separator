import re
from pathlib import Path
import pytest
from data_parser import parse_pdf, parse_table_file, parse_text_stream

REAL_PDF_PATH = Path("sample_input/Backlog_List.pdf")
SKIP_IF_NO_REAL_PDF = pytest.mark.skipif(
    not REAL_PDF_PATH.is_file(),
    reason="sample_input/Backlog_List.pdf not present"
)

@SKIP_IF_NO_REAL_PDF
def test_real_pdf_parsing_full_suite():
    assert REAL_PDF_PATH.is_file()
    result = parse_pdf(REAL_PDF_PATH)

    assert len(result.rows) == 807
    assert result.failed == []
    assert result.missing_sr == []

    srs = [r.sr for r in result.rows]
    assert srs == list(range(1, 808))

    row_map = {r.sr: r for r in result.rows}

    for r in result.rows:
        assert r.sr > 0
        assert len(r.prn) >= 10
        assert len(r.name) > 0
        assert not any(ch.isdigit() for ch in r.name)
        assert len(r.course_code) >= 6
        assert len(r.course_name) > 0
        assert not re.search(r'\d{10}', r.course_name)
        assert "Year" not in r.course_name
        assert len(r.program) > 0
        assert len(r.year) > 0
        assert len(r.ay) == 7
        assert len(r.sem) > 0
        assert r.page >= 1

    row_29 = row_map[29]
    assert row_29.sem == "1"

    row_30 = row_map[30]
    assert row_30.prn == "3124047010069"

    row_31 = row_map[31]
    assert row_31.ay == "2025-26"
    assert row_31.sem == "2"

    row_122 = row_map[122]
    assert row_122.course_name == "Fundamentals of Human Anatomy and Physiology"

def test_small_string_wrapping_and_glued():
    sample_text = (
        "SR No. PRN Name Course Code Course Name Program Year AY sem "
        "1 2281370165 Student Alpha BTECAI21701 Advanced Machine "
        "Learning BTECH.AIDS Fourth Year 2024-25 1"
        "2 3124047010069 Student Beta AE24AI02A Campus to "
        "Corporate B.Tech. (AI&DS) Second Year 2025-262"
        "3 2181370143 Student Gamma BTECAI717 Project "
        "Stage - 2 BTECH.AIDS Fourth Year 2023-24 14 3124047010491 Student Delta BTECAD24301 Statistical Data Analysis B.Tech. (AI&DS) Second Year 2025-26 1"
    )
    res = parse_text_stream(sample_text, [(0, len(sample_text), 1)])
    assert len(res.rows) == 4
    assert res.failed == []
    assert res.missing_sr == []

    r1, r2, r3, r4 = res.rows
    assert r1.sr == 1
    assert r1.course_name == "Advanced Machine Learning"
    assert r1.sem == "1"

    assert r2.sr == 2
    assert r2.ay == "2025-26"
    assert r2.sem == "2"

    assert r3.sr == 3
    assert r3.sem == "1"

    assert r4.sr == 4
    assert r4.prn == "3124047010491"
    assert r4.sem == "1"

def test_parse_table_csv():
    csv_data = (
        "SR,PRN,Name,Course Code,Course Name,Program,Year,AY,Sem\n"
        "1,2281370165,Test User,BTECAI21701,Machine Learning,BTECH.AIDS,Fourth Year,2024-25,1\n"
        "2,3124047010069,Second User,AE24AI02A,Campus Corporate,B.Tech. (AI&DS),Second Year,2025-26,2\n"
    ).encode("utf-8")
    res = parse_table_file(csv_data, "sample.csv")
    assert len(res.rows) == 2
    assert res.failed == []
    assert res.rows[0].sr == 1
    assert res.rows[1].sr == 2
    assert res.rows[0].course_code == "BTECAI21701"
