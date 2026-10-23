from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

@dataclass
class Row:
    sr: int
    prn: str
    name: str
    course_code: str
    course_name: str
    program: str
    year: str
    ay: str
    sem: str
    page: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ParseResult:
    rows: List[Row] = field(default_factory=list)
    failed: List[Dict[str, Any]] = field(default_factory=list)
    missing_sr: List[int] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Exam:
    key: str
    name: str
    codes: List[str] = field(default_factory=list)
    spellings: List[str] = field(default_factory=list)
    prns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Slot:
    date: str
    session: str
    start: str
    end: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ScheduledExam:
    exam: Exam
    slot: Slot

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Schedule:
    items: List[ScheduledExam] = field(default_factory=list)
    unscheduled: List[Exam] = field(default_factory=list)
    slots_used: int = 0
    min_slots_needed: int = 0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class VerifyResult:
    ok: bool
    rows_read: int
    duplicate_rows: int
    unique_students: int
    unique_pairs: int
    exams: int
    pairs_scheduled: int
    missing_pairs: List[Any] = field(default_factory=list)
    extra_pairs: List[Any] = field(default_factory=list)
    clashes: List[Any] = field(default_factory=list)
    per_day_violations: List[Any] = field(default_factory=list)
    exam_count_mismatches: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Settings:
    college_name: str
    department: str
    exam_title: str
    controller_name: str
    logo_path: str
    start_date: str
    end_date: str
    skip_sundays: bool
    holidays: List[str]
    morning_start: str
    morning_end: str
    afternoon_start: str
    afternoon_end: str
    max_exams_per_day: int
    lab_separate_from_theory: bool
    auto_extend_days: bool
    room_capacity: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        return cls(
            college_name=data.get("college_name", ""),
            department=data.get("department", ""),
            exam_title=data.get("exam_title", ""),
            controller_name=data.get("controller_name", ""),
            logo_path=data.get("logo_path", ""),
            start_date=data.get("start_date", ""),
            end_date=data.get("end_date", ""),
            skip_sundays=data.get("skip_sundays", True),
            holidays=data.get("holidays", []),
            morning_start=data.get("morning_start", "10:00"),
            morning_end=data.get("morning_end", "13:00"),
            afternoon_start=data.get("afternoon_start", "14:30"),
            afternoon_end=data.get("afternoon_end", "17:30"),
            max_exams_per_day=data.get("max_exams_per_day", 2),
            lab_separate_from_theory=data.get("lab_separate_from_theory", True),
            auto_extend_days=data.get("auto_extend_days", True),
            room_capacity=data.get("room_capacity", 100),
        )
