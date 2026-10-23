import json
from datetime import date, timedelta
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from config import (
    get_default_settings,
    load_settings,
    save_settings,
    validate_session_timings,
    parse_and_validate_holidays,
    get_kolkata_today,
    get_kolkata_now,
    KOLKATA_TZ,
)
from models import Settings, Exam
from scheduler import schedule_exams

def test_default_settings_values():
    settings = get_default_settings()
    tomorrow = (get_kolkata_today() + timedelta(days=1)).isoformat()
    assert settings.start_date == tomorrow
    assert settings.morning_start == "10:00"
    assert settings.morning_end == "13:00"
    assert settings.afternoon_start == "14:30"
    assert settings.afternoon_end == "17:30"
    assert settings.skip_sundays is True
    assert settings.max_exams_per_day == 2
    assert settings.lab_separate_from_theory is True
    assert settings.auto_extend_days is True
    assert settings.room_capacity == 100

def test_timezone_asia_kolkata():
    now_kolkata = get_kolkata_now()
    today_kolkata = get_kolkata_today()
    assert str(now_kolkata.tzinfo) == "Asia/Kolkata"
    assert now_kolkata.date() == today_kolkata

    defaults = get_default_settings()
    expected_start = (today_kolkata + timedelta(days=1)).isoformat()
    assert defaults.start_date == expected_start

    # Verify formatting matches PDF timestamp patterns
    formatted = now_kolkata.strftime("%Y-%m-%d %H:%M:%S")
    assert len(formatted) == 19


def test_load_settings_nonexistent_returns_defaults(tmp_path):
    missing_file = tmp_path / "does_not_exist.json"
    settings = load_settings(missing_file)
    assert settings.skip_sundays is True
    assert settings.morning_start == "10:00"
    assert settings.afternoon_start == "14:30"

def test_save_and_load_settings_roundtrip(tmp_path):
    target_file = tmp_path / "custom_settings.json"
    settings = get_default_settings()
    settings.college_name = "Government Engineering College"
    settings.max_exams_per_day = 1
    settings.skip_sundays = False
    settings.room_capacity = 250
    settings.holidays = ["2026-11-15"]

    save_settings(settings, target_file)
    assert target_file.is_file()

    loaded = load_settings(target_file)
    assert loaded.college_name == "Government Engineering College"
    assert loaded.max_exams_per_day == 1
    assert loaded.skip_sundays is False
    assert loaded.room_capacity == 250
    assert loaded.holidays == ["2026-11-15"]
    assert loaded.morning_start == "10:00"

def test_settings_to_dict_and_from_dict():
    settings = get_default_settings()
    d = settings.to_dict()
    assert isinstance(d, dict)
    assert d["morning_start"] == "10:00"
    assert d["afternoon_end"] == "17:30"

    rebuilt = Settings.from_dict(d)
    assert rebuilt.morning_start == settings.morning_start
    assert rebuilt.afternoon_end == settings.afternoon_end
    assert rebuilt.max_exams_per_day == settings.max_exams_per_day

def test_validate_session_timings_morning_end_not_later_than_morning_start():
    # Equal times
    errs = validate_session_timings("10:00", "10:00", "14:30", "17:30")
    assert len(errs) == 1
    assert errs[0] == "Morning End must be later than Morning Start. Use 24-hour time, for example 15:30 for 3:30 PM."

    # Earlier times
    errs_earlier = validate_session_timings("10:00", "09:30", "14:30", "17:30")
    assert any("Morning End must be later than Morning Start" in e for e in errs_earlier)

def test_validate_session_timings_afternoon_start_not_later_than_morning_end():
    # Equal times
    errs = validate_session_timings("10:00", "13:00", "13:00", "17:30")
    assert len(errs) == 1
    assert errs[0] == "Afternoon Start must be later than Morning End. Use 24-hour time, for example 15:30 for 3:30 PM."

    # Earlier times
    errs_earlier = validate_session_timings("10:00", "13:00", "12:30", "17:30")
    assert any("Afternoon Start must be later than Morning End" in e for e in errs_earlier)

def test_validate_session_timings_afternoon_end_not_later_than_afternoon_start():
    # Equal times
    errs = validate_session_timings("10:00", "13:00", "14:30", "14:30")
    assert len(errs) == 1
    assert errs[0] == "Afternoon End must be later than Afternoon Start. Use 24-hour time, for example 15:30 for 3:30 PM."

    # 12-hour format entered (e.g. 03:30 instead of 15:30)
    errs_12hr = validate_session_timings("10:00", "13:00", "14:30", "03:30")
    assert len(errs_12hr) == 1
    assert errs_12hr[0] == "Afternoon End must be later than Afternoon Start. Use 24-hour time, for example 15:30 for 3:30 PM."

def test_schedule_exams_blocks_on_invalid_session_timings():
    dummy_exam = Exam(key="test", name="Test Exam", codes=["T1"], spellings=["Test Exam"], prns=["123"])
    settings = get_default_settings()

    # Case 1
    settings.morning_end = "10:00"
    with pytest.raises(ValueError, match="Morning End must be later than Morning Start"):
        schedule_exams([dummy_exam], settings)

    # Case 2
    settings = get_default_settings()
    settings.afternoon_start = "12:00"
    with pytest.raises(ValueError, match="Afternoon Start must be later than Morning End"):
        schedule_exams([dummy_exam], settings)

    # Case 3
    settings = get_default_settings()
    settings.afternoon_end = "03:30"
    with pytest.raises(ValueError, match="Afternoon End must be later than Afternoon Start"):
        schedule_exams([dummy_exam], settings)

def test_sidebar_and_timetable_block_case_1_morning_end():
    app_path = str((Path(__file__).parent.parent / "app.py").resolve())
    at = AppTest.from_file(app_path, default_timeout=15)
    at.session_state["settings"] = get_default_settings()
    at.run()
    for ti in at.sidebar.text_input:
        if ti.label == "Morning End":
            ti.set_value("10:00")
    at.sidebar.button[0].click().run()

    expected_msg = "Morning End must be later than Morning Start. Use 24-hour time, for example 15:30 for 3:30 PM."
    assert expected_msg in [e.value for e in at.sidebar.error]
    gen_btn = next((b for b in at.button if b.label == "Generate Timetable"), None)
    assert gen_btn is not None
    assert getattr(gen_btn, "disabled", False) is True

def test_sidebar_and_timetable_block_case_2_afternoon_start():
    app_path = str((Path(__file__).parent.parent / "app.py").resolve())
    at = AppTest.from_file(app_path, default_timeout=15)
    at.session_state["settings"] = get_default_settings()
    at.run()
    for ti in at.sidebar.text_input:
        if ti.label == "Afternoon Start":
            ti.set_value("12:00")
    at.sidebar.button[0].click().run()

    expected_msg = "Afternoon Start must be later than Morning End. Use 24-hour time, for example 15:30 for 3:30 PM."
    assert expected_msg in [e.value for e in at.sidebar.error]
    gen_btn = next((b for b in at.button if b.label == "Generate Timetable"), None)
    assert gen_btn is not None
    assert getattr(gen_btn, "disabled", False) is True

def test_sidebar_and_timetable_block_case_3_afternoon_end():
    app_path = str((Path(__file__).parent.parent / "app.py").resolve())
    at = AppTest.from_file(app_path, default_timeout=15)
    at.session_state["settings"] = get_default_settings()
    at.run()
    for ti in at.sidebar.text_input:
        if ti.label == "Afternoon End":
            ti.set_value("03:30")
    at.sidebar.button[0].click().run()

    expected_msg = "Afternoon End must be later than Afternoon Start. Use 24-hour time, for example 15:30 for 3:30 PM."
    assert expected_msg in [e.value for e in at.sidebar.error]
    gen_btn = next((b for b in at.button if b.label == "Generate Timetable"), None)
    assert gen_btn is not None
    assert getattr(gen_btn, "disabled", False) is True

def test_parse_and_validate_holidays_valid_and_duplicates():
    # String with duplicate dates, whitespace, and commas/newlines
    raw_input = "2026-11-04\n2026-11-05\n2026-11-04\n  2026-11-06  \n2026-11-05"
    valid, errors = parse_and_validate_holidays(raw_input)
    assert errors == []
    assert valid == ["2026-11-04", "2026-11-05", "2026-11-06"]

    # List with duplicate dates
    list_input = ["2026-12-25", "2026-12-25", "2026-01-01"]
    valid_list, errors_list = parse_and_validate_holidays(list_input)
    assert errors_list == []
    assert valid_list == ["2026-01-01", "2026-12-25"]

    # None or empty string
    assert parse_and_validate_holidays(None) == ([], [])
    assert parse_and_validate_holidays("") == ([], [])

def test_parse_and_validate_holidays_invalid_dates():
    raw_input = "2026-13-45\nnot-a-date\n15-11-2026\n2026/11/15"
    valid, errors = parse_and_validate_holidays(raw_input)
    assert valid == []
    assert len(errors) == 4
    assert "Invalid holiday date '2026-13-45'. Please use YYYY-MM-DD format." in errors
    assert "Invalid holiday date 'not-a-date'. Please use YYYY-MM-DD format." in errors
    assert "Invalid holiday date '15-11-2026'. Please use YYYY-MM-DD format." in errors
    assert "Invalid holiday date '2026/11/15'. Please use YYYY-MM-DD format." in errors

def test_schedule_exams_blocks_on_invalid_holiday_date():
    dummy_exam = Exam(key="test", name="Test Exam", codes=["T1"], spellings=["Test Exam"], prns=["123"])
    settings = get_default_settings()
    settings.holidays = ["2026-13-45"]

    with pytest.raises(ValueError, match="Invalid holiday date '2026-13-45'. Please use YYYY-MM-DD format."):
        schedule_exams([dummy_exam], settings)

def test_sidebar_and_timetable_block_case_invalid_holiday():
    app_path = str((Path(__file__).parent.parent / "app.py").resolve())
    at = AppTest.from_file(app_path, default_timeout=15)
    at.session_state["settings"] = get_default_settings()
    at.run()

    for ta in at.sidebar.text_area:
        if ta.label == "Holidays":
            ta.set_value("2026-13-45\ninvalid-date")
    at.sidebar.button[0].click().run()

    errors = [e.value for e in at.sidebar.error]
    assert any("Invalid holiday date '2026-13-45'. Please use YYYY-MM-DD format." in e for e in errors)
    assert any("Invalid holiday date 'invalid-date'. Please use YYYY-MM-DD format." in e for e in errors)

    gen_btn = next((b for b in at.button if b.label == "Generate Timetable"), None)
    assert gen_btn is not None
    assert getattr(gen_btn, "disabled", False) is True

