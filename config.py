import json
from datetime import date, timedelta, datetime
from pathlib import Path
from typing import Union, List, Optional, Tuple
from zoneinfo import ZoneInfo
from models import Settings

KOLKATA_TZ = ZoneInfo("Asia/Kolkata")

def get_kolkata_now() -> datetime:
    """Return the current datetime in Asia/Kolkata timezone."""
    return datetime.now(KOLKATA_TZ)

def get_kolkata_today() -> date:
    """Return the current date in Asia/Kolkata timezone."""
    return get_kolkata_now().date()

def parse_time_to_minutes(t_str: str) -> Optional[int]:
    """Parse a time string (HH:MM or H:MM) into minutes since midnight (0..1439)."""
    if not t_str or not isinstance(t_str, str):
        return None
    parts = t_str.strip().split(":")
    if len(parts) == 2:
        try:
            h = int(parts[0])
            m = int(parts[1])
            if 0 <= h < 24 and 0 <= m < 60:
                return h * 60 + m
        except ValueError:
            return None
    return None

def validate_session_timings(
    morning_start: str,
    morning_end: str,
    afternoon_start: str,
    afternoon_end: str
) -> List[str]:
    """Validate that:
    1. Morning End is later than Morning Start.
    2. Afternoon Start is later than Morning End.
    3. Afternoon End is later than Afternoon Start.
    Returns a list of human-readable error messages.
    """
    errors: List[str] = []
    m_start = parse_time_to_minutes(morning_start)
    m_end = parse_time_to_minutes(morning_end)
    a_start = parse_time_to_minutes(afternoon_start)
    a_end = parse_time_to_minutes(afternoon_end)

    suffix = " Use 24-hour time, for example 15:30 for 3:30 PM."

    if m_start is None or m_end is None or m_end <= m_start:
        errors.append(f"Morning End must be later than Morning Start.{suffix}")

    if (m_end is not None and a_start is not None and a_start <= m_end) or (a_start is None and m_end is not None):
        errors.append(f"Afternoon Start must be later than Morning End.{suffix}")

    if (a_start is not None and a_end is not None and a_end <= a_start) or (a_end is None and a_start is not None):
        errors.append(f"Afternoon End must be later than Afternoon Start.{suffix}")

    return errors

def parse_and_validate_holidays(
    holiday_input: Union[str, List[str], None]
) -> Tuple[List[str], List[str]]:
    """Parse holiday input (multiline string or list of strings) into a sorted list of unique YYYY-MM-DD date strings.
    Returns (valid_holidays, error_messages).
    Duplicate dates are silently ignored.
    Invalid dates produce descriptive error messages.
    """
    if holiday_input is None:
        return [], []

    if isinstance(holiday_input, str):
        lines = [line.strip() for line in holiday_input.replace(",", "\n").splitlines()]
    elif isinstance(holiday_input, list):
        lines = [str(item).strip() for item in holiday_input]
    else:
        return [], [f"Invalid holidays input type: {type(holiday_input).__name__}"]

    valid_set = set()
    errors = []

    for raw in lines:
        if not raw:
            continue
        try:
            d = datetime.strptime(raw, "%Y-%m-%d").date()
            valid_set.add(d.isoformat())
        except ValueError:
            errors.append(f"Invalid holiday date '{raw}'. Please use YYYY-MM-DD format.")

    return sorted(list(valid_set)), errors

DEFAULT_SETTINGS_PATH = Path(__file__).parent / "settings.json"

def get_default_settings() -> Settings:
    start_date = get_kolkata_today() + timedelta(days=1)
    end_date = start_date + timedelta(days=14)
    return Settings(
        college_name="College of Engineering and Technology",
        department="Examination Cell",
        exam_title="Backlog Examination Schedule",
        controller_name="Controller of Examinations",
        logo_path="",
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        skip_sundays=True,
        holidays=[],
        morning_start="10:00",
        morning_end="13:00",
        afternoon_start="14:30",
        afternoon_end="17:30",
        max_exams_per_day=2,
        lab_separate_from_theory=True,
        auto_extend_days=True,
        room_capacity=100,
    )

def load_settings(path: Union[str, Path] = DEFAULT_SETTINGS_PATH) -> Settings:
    file_path = Path(path)
    if not file_path.is_file():
        return get_default_settings()

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    defaults = get_default_settings().to_dict()
    defaults.update(data)
    return Settings.from_dict(defaults)

def save_settings(settings: Settings, path: Union[str, Path] = DEFAULT_SETTINGS_PATH) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(settings.to_dict(), f, indent=2)
