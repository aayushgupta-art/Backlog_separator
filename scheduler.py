import collections
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple
from models import Exam, Slot, ScheduledExam, Schedule, Settings
from config import validate_session_timings, parse_and_validate_holidays

def generate_dates(
    start_date_str: str,
    end_date_str: str,
    skip_sundays: bool,
    holidays: Any
) -> List[str]:
    start_d = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_d = datetime.strptime(end_date_str, "%Y-%m-%d").date()

    valid_h, _ = parse_and_validate_holidays(holidays)
    holiday_set = set(valid_h)
    dates: List[str] = []

    curr = start_d
    while curr <= end_d:
        if not (skip_sundays and curr.weekday() == 6) and (curr.isoformat() not in holiday_set):
            dates.append(curr.isoformat())
        curr += timedelta(days=1)

    return dates

def _next_valid_date(
    current: date,
    skip_sundays: bool,
    holidays: Any
) -> date:
    valid_h, _ = parse_and_validate_holidays(holidays)
    holiday_set = set(valid_h)
    nxt = current + timedelta(days=1)
    while (skip_sundays and nxt.weekday() == 6) or (nxt.isoformat() in holiday_set):
        nxt += timedelta(days=1)
    return nxt

def build_slots(dates: List[str], settings: Settings) -> List[Slot]:
    slots: List[Slot] = []
    for d_str in dates:
        slots.append(Slot(
            date=d_str,
            session="Morning",
            start=settings.morning_start,
            end=settings.morning_end,
        ))
        slots.append(Slot(
            date=d_str,
            session="Afternoon",
            start=settings.afternoon_start,
            end=settings.afternoon_end,
        ))
    return slots

def build_conflict_graph(
    exams: List[Exam],
    lab_separate_from_theory: bool
) -> Dict[str, Set[str]]:
    adj: Dict[str, Set[str]] = {e.key: set() for e in exams}

    for i in range(len(exams)):
        for j in range(i + 1, len(exams)):
            e1 = exams[i]
            e2 = exams[j]

            has_prn_overlap = bool(set(e1.prns) & set(e2.prns))
            is_lab_theory_pair = False
            if lab_separate_from_theory:
                if e1.key + " lab" == e2.key or e2.key + " lab" == e1.key:
                    is_lab_theory_pair = True

            if has_prn_overlap or is_lab_theory_pair:
                adj[e1.key].add(e2.key)
                adj[e2.key].add(e1.key)

    return adj

def schedule_exams(
    exams: List[Exam],
    settings: Settings
) -> Schedule:
    timing_errors = validate_session_timings(
        settings.morning_start,
        settings.morning_end,
        settings.afternoon_start,
        settings.afternoon_end
    )
    if timing_errors:
        raise ValueError("; ".join(timing_errors))

    valid_holidays, holiday_errors = parse_and_validate_holidays(settings.holidays)
    if holiday_errors:
        raise ValueError("; ".join(holiday_errors))

    if not exams:
        return Schedule(items=[], unscheduled=[], slots_used=0, min_slots_needed=0, warnings=[])

    dates = generate_dates(
        settings.start_date,
        settings.end_date,
        settings.skip_sundays,
        valid_holidays
    )
    slots = build_slots(dates, settings)

    adj = build_conflict_graph(exams, settings.lab_separate_from_theory)
    exam_by_key = {e.key: e for e in exams}

    student_backlog_counts: Dict[str, int] = collections.defaultdict(int)
    for e in exams:
        for prn in e.prns:
            student_backlog_counts[prn] += 1
    max_single_student_backlogs = max(student_backlog_counts.values()) if student_backlog_counts else 0

    unplaced_keys = set(e.key for e in exams)
    exam_slot_index: Dict[str, int] = {}
    saturation_slots: Dict[str, Set[int]] = {e.key: set() for e in exams}

    student_exams_by_date: Dict[str, Dict[str, int]] = collections.defaultdict(lambda: collections.defaultdict(int))
    slot_assigned_keys: Dict[int, List[str]] = collections.defaultdict(list)

    warnings: List[str] = []
    extended = False

    while unplaced_keys:
        best_key = None
        best_sat = -1
        best_unplaced_deg = -1
        best_student_count = -1

        for key in unplaced_keys:
            sat = len(saturation_slots[key])
            unplaced_deg = len(adj[key] & unplaced_keys)
            stu_cnt = len(exam_by_key[key].prns)

            if (sat > best_sat) or \
               (sat == best_sat and unplaced_deg > best_unplaced_deg) or \
               (sat == best_sat and unplaced_deg == best_unplaced_deg and stu_cnt > best_student_count):
                best_sat = sat
                best_unplaced_deg = unplaced_deg
                best_student_count = stu_cnt
                best_key = key

        target_exam = exam_by_key[best_key]

        slot_idx = 0
        assigned = False

        while True:
            if slot_idx >= len(slots):
                if settings.auto_extend_days:
                    extended = True
                    last_date_obj = datetime.strptime(slots[-1].date, "%Y-%m-%d").date() if slots else datetime.strptime(settings.start_date, "%Y-%m-%d").date()
                    next_d = _next_valid_date(last_date_obj, settings.skip_sundays, valid_holidays)
                    next_d_str = next_d.isoformat()
                    slots.append(Slot(date=next_d_str, session="Morning", start=settings.morning_start, end=settings.morning_end))
                    slots.append(Slot(date=next_d_str, session="Afternoon", start=settings.afternoon_start, end=settings.afternoon_end))
                else:
                    break

            cand_slot = slots[slot_idx]
            cand_date = cand_slot.date

            has_conflict = False
            for placed_k in slot_assigned_keys[slot_idx]:
                if placed_k in adj[best_key]:
                    has_conflict = True
                    break

            if has_conflict:
                slot_idx += 1
                continue

            per_day_conflict = False
            for prn in target_exam.prns:
                current_on_date = student_exams_by_date[cand_date][prn]
                if current_on_date >= settings.max_exams_per_day:
                    per_day_conflict = True
                    break

            if per_day_conflict:
                slot_idx += 1
                continue

            exam_slot_index[best_key] = slot_idx
            slot_assigned_keys[slot_idx].append(best_key)
            for prn in target_exam.prns:
                student_exams_by_date[cand_date][prn] += 1

            for neighbor_key in adj[best_key]:
                saturation_slots[neighbor_key].add(slot_idx)

            assigned = True
            break

        unplaced_keys.remove(best_key)

    placed_items: List[ScheduledExam] = []
    unscheduled_items: List[Exam] = []

    for e in exams:
        if e.key in exam_slot_index:
            s_idx = exam_slot_index[e.key]
            placed_items.append(ScheduledExam(exam=e, slot=slots[s_idx]))
        else:
            unscheduled_items.append(e)

    used_slot_indices = sorted(list(set(exam_slot_index.values())))
    slots_used = len(used_slot_indices)
    min_slots_needed = max(slots_used, max_single_student_backlogs)

    if unscheduled_items:
        warnings.append(f"Auto-extend is disabled and {len(unscheduled_items)} exams could not fit within the end date. Minimum slots needed: {min_slots_needed}.")

    if extended:
        used_dates = sorted(list(set(slots[idx].date for idx in used_slot_indices)))
        warnings.append(f"Schedule extended beyond end date {settings.end_date}. Total days used: {len(used_dates)}.")

    _balance_slots(placed_items, slots, adj, settings)

    slot_students: Dict[Tuple[str, str], int] = collections.defaultdict(int)
    for item in placed_items:
        slot_key = (item.slot.date, item.slot.session)
        slot_students[slot_key] += len(item.exam.prns)

    for (d_str, sess), count in slot_students.items():
        if count > settings.room_capacity:
            warnings.append(f"Slot {d_str} {sess} exceeds room capacity ({count} > {settings.room_capacity}).")

    return Schedule(
        items=placed_items,
        unscheduled=unscheduled_items,
        slots_used=slots_used,
        min_slots_needed=min_slots_needed,
        warnings=warnings,
    )

def _balance_slots(
    placed_items: List[ScheduledExam],
    slots: List[Slot],
    adj: Dict[str, Set[str]],
    settings: Settings
) -> None:
    slot_index_by_slot: Dict[Tuple[str, str], int] = {(s.date, s.session): idx for idx, s in enumerate(slots)}
    used_slot_indices = sorted(list(set(slot_index_by_slot[(item.slot.date, item.slot.session)] for item in placed_items)))
    if len(used_slot_indices) <= 1:
        return

    slot_exams: Dict[int, List[ScheduledExam]] = collections.defaultdict(list)
    student_exams_by_date: Dict[str, Dict[str, int]] = collections.defaultdict(lambda: collections.defaultdict(int))

    for item in placed_items:
        s_idx = slot_index_by_slot[(item.slot.date, item.slot.session)]
        slot_exams[s_idx].append(item)
        for prn in item.exam.prns:
            student_exams_by_date[item.slot.date][prn] += 1

    for _ in range(5):
        slot_sizes = [(sum(len(item.exam.prns) for item in slot_exams[idx]), idx) for idx in used_slot_indices]
        slot_sizes.sort(reverse=True)
        max_size, max_idx = slot_sizes[0]
        min_size, min_idx = slot_sizes[-1]

        if max_size - min_size <= 5 or len(slot_exams[max_idx]) <= 1:
            break

        moved = False
        target_slot = slots[min_idx]
        target_date = target_slot.date

        for item in sorted(slot_exams[max_idx], key=lambda it: len(it.exam.prns)):
            item_exam = item.exam
            item_prn_count = len(item_exam.prns)

            if max_size - item_prn_count < min_size + item_prn_count:
                continue

            has_conflict = any(placed_it.exam.key in adj[item_exam.key] for placed_it in slot_exams[min_idx])
            if has_conflict:
                continue

            source_date = item.slot.date
            per_day_conflict = False
            for prn in item_exam.prns:
                current_count = student_exams_by_date[target_date][prn]
                if target_date == source_date:
                    pass
                else:
                    if current_count >= settings.max_exams_per_day:
                        per_day_conflict = True
                        break

            if per_day_conflict:
                continue

            slot_exams[max_idx].remove(item)
            for prn in item_exam.prns:
                student_exams_by_date[source_date][prn] -= 1
                student_exams_by_date[target_date][prn] += 1

            item.slot = target_slot
            slot_exams[min_idx].append(item)
            moved = True
            break

        if not moved:
            break

def schedule_to_rows(schedule: Schedule) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    sorted_items = sorted(
        schedule.items,
        key=lambda it: (it.slot.date, 0 if it.slot.session == "Morning" else 1, it.exam.name)
    )

    for item in sorted_items:
        date_obj = datetime.strptime(item.slot.date, "%Y-%m-%d")
        weekday_name = date_obj.strftime("%A")
        time_str = f"{item.slot.start} - {item.slot.end}"
        codes_str = ", ".join(item.exam.codes)

        rows.append({
            "Date": item.slot.date,
            "Weekday": weekday_name,
            "Session": item.slot.session,
            "Time": time_str,
            "Exam": item.exam.name,
            "Codes": codes_str,
            "Students": len(item.exam.prns),
        })

    return rows
