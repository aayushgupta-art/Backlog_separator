import collections
from typing import Dict, Any, Optional, Set, Tuple, List
from models import ParseResult, Schedule, Settings, VerifyResult
from course_grouper import normalize_name

def verify(
    parse_result: ParseResult,
    merge_map: Optional[Dict[str, str]],
    schedule: Schedule,
    settings: Settings
) -> VerifyResult:
    effective_map = merge_map or {}

    expected_pairs: Set[Tuple[str, str]] = set()
    expected_students: Set[str] = set()
    expected_exam_prns: Dict[str, Set[str]] = collections.defaultdict(set)

    seen_pairs_raw: Set[Tuple[str, str]] = set()
    duplicate_rows_count = 0

    for r in parse_result.rows:
        base_key = normalize_name(r.course_name)
        key = effective_map.get(base_key, base_key)
        pair = (r.prn, key)

        if pair in seen_pairs_raw:
            duplicate_rows_count += 1
        else:
            seen_pairs_raw.add(pair)

        expected_pairs.add(pair)
        expected_students.add(r.prn)
        expected_exam_prns[key].add(r.prn)

    placed_pairs: Set[Tuple[str, str]] = set()
    scheduled_exam_prns: Dict[str, Set[str]] = collections.defaultdict(set)
    student_slot_exams: Dict[Tuple[str, str, str], List[str]] = collections.defaultdict(list)
    student_date_exams: Dict[Tuple[str, str], List[str]] = collections.defaultdict(list)

    for item in schedule.items:
        key = item.exam.key
        slot_date = item.slot.date
        slot_sess = item.slot.session

        for prn in item.exam.prns:
            placed_pairs.add((prn, key))
            scheduled_exam_prns[key].add(prn)
            student_slot_exams[(prn, slot_date, slot_sess)].append(item.exam.name)
            student_date_exams[(prn, slot_date)].append(item.exam.name)

    missing_pairs = sorted(list(expected_pairs - placed_pairs))
    extra_pairs = sorted(list(placed_pairs - expected_pairs))

    clashes: List[Dict[str, Any]] = []
    for (prn, s_date, s_sess), exam_names in student_slot_exams.items():
        if len(exam_names) > 1:
            clashes.append({
                "prn": prn,
                "date": s_date,
                "session": s_sess,
                "exams": exam_names
            })

    per_day_violations: List[Dict[str, Any]] = []
    for (prn, s_date), exam_names in student_date_exams.items():
        if len(exam_names) > settings.max_exams_per_day:
            per_day_violations.append({
                "prn": prn,
                "date": s_date,
                "count": len(exam_names),
                "exams": exam_names
            })

    exam_count_mismatches: List[Dict[str, Any]] = []
    all_keys = set(expected_exam_prns.keys()) | set(scheduled_exam_prns.keys())
    for key in sorted(all_keys):
        expected_cnt = len(expected_exam_prns.get(key, set()))
        sched_cnt = len(scheduled_exam_prns.get(key, set()))
        if expected_cnt != sched_cnt:
            exam_count_mismatches.append({
                "exam_key": key,
                "expected": expected_cnt,
                "scheduled": sched_cnt
            })

    ok = (
        len(missing_pairs) == 0 and
        len(extra_pairs) == 0 and
        len(clashes) == 0 and
        len(per_day_violations) == 0 and
        len(exam_count_mismatches) == 0
    )

    return VerifyResult(
        ok=ok,
        rows_read=len(parse_result.rows),
        duplicate_rows=duplicate_rows_count,
        unique_students=len(expected_students),
        unique_pairs=len(expected_pairs),
        exams=len(expected_exam_prns),
        pairs_scheduled=len(placed_pairs),
        missing_pairs=missing_pairs,
        extra_pairs=extra_pairs,
        clashes=clashes,
        per_day_violations=per_day_violations,
        exam_count_mismatches=exam_count_mismatches
    )
