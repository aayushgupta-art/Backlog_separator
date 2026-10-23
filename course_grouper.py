import collections
import re
import unicodedata
from typing import List, Dict, Any, Optional, Tuple
from rapidfuzz import fuzz
from models import Row, Exam

# Small words kept lowercase in display names
_SMALL_WORDS = {"and", "of", "for", "to", "in", "a", "an", "the", "at", "by", "or"}

# Roman numeral -> digit mapping (standalone tokens only)
_ROMAN_TO_DIGIT = {
    "i": "1",
    "ii": "2",
    "iii": "3",
    "iv": "4",
    "v": "5",
    "vi": "6",
    "vii": "7",
    "viii": "8",
    "ix": "9",
    "x": "10",
}

def normalize_name(name: str) -> str:
    norm = unicodedata.normalize('NFKC', name).lower()
    norm = norm.replace('&', ' and ')
    norm = re.sub(r'[^a-z0-9]+', ' ', norm)
    norm = re.sub(r'\s+', ' ', norm).strip()

    # Whole-word spelling aliases
    norm = re.sub(r'\bstatistcal\b', 'statistical', norm)
    norm = re.sub(r'\bdev\b', 'development', norm)
    norm = re.sub(r'\bsystems\b', 'system', norm)

    # Convert standalone Roman numerals to digits (whole word only)
    def replace_roman(m: re.Match) -> str:
        token = m.group(0).lower()
        return _ROMAN_TO_DIGIT.get(token, m.group(0))

    roman_pattern = r'\b(?:viii|vii|vi|iv|ix|iii|ii|i|v|x)\b'
    norm = re.sub(roman_pattern, replace_roman, norm)

    return norm


def _smart_title(text: str) -> str:
    """Title-case with small words kept lowercase (except first word)."""
    words = text.split()
    result = []
    for idx, word in enumerate(words):
        if idx == 0 or word.lower() not in _SMALL_WORDS:
            result.append(word.capitalize())
        else:
            result.append(word.lower())
    return " ".join(result)


def _format_display_name(raw_spelling: str) -> str:
    cleaned = re.sub(r'\s+', ' ', raw_spelling).strip()
    # If ALL CAPS or all lowercase, apply smart title case
    if cleaned.isupper() or cleaned.islower():
        return _smart_title(cleaned.lower())
    # Mixed case: use as-is (trust the original casing)
    return cleaned


def build_exams(
    rows: List[Row],
    merge_map: Optional[Dict[str, str]] = None
) -> Tuple[List[Exam], List[Dict[str, Any]]]:
    effective_map = merge_map or {}

    exam_prns: Dict[str, set] = collections.defaultdict(set)
    exam_codes: Dict[str, List[str]] = collections.defaultdict(list)
    exam_spellings: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)

    seen_pairs: Dict[Tuple[str, str], int] = {}
    duplicates: List[Dict[str, Any]] = []

    for r in rows:
        base_key = normalize_name(r.course_name)
        key = effective_map.get(base_key, base_key)
        pair = (r.prn, key)

        if pair in seen_pairs:
            duplicates.append({
                "sr": r.sr,
                "first_sr": seen_pairs[pair],
                "prn": r.prn,
                "name": r.name,
                "course_name": r.course_name,
                "course_code": r.course_code,
                "exam_key": key,
                "page": r.page,
            })
        else:
            seen_pairs[pair] = r.sr

        exam_prns[key].add(r.prn)
        if r.course_code and r.course_code not in exam_codes[key]:
            exam_codes[key].append(r.course_code)
        exam_spellings[key][r.course_name] += 1

    exams: List[Exam] = []
    for key in sorted(exam_prns.keys()):
        prns_sorted = sorted(list(exam_prns[key]))
        spelling_counter = exam_spellings[key]
        most_common_raw = spelling_counter.most_common(1)[0][0]
        display_name = _format_display_name(most_common_raw)
        spellings_list = list(spelling_counter.keys())

        exam = Exam(
            key=key,
            name=display_name,
            codes=exam_codes[key],
            spellings=spellings_list,
            prns=prns_sorted,
        )
        exams.append(exam)

    return exams, duplicates


def differ_only_by_number(name1: str, name2: str) -> bool:
    """Check if two course names differ only by a number or Roman numeral (e.g. I/II, 1/2)."""
    k1 = normalize_name(name1)
    k2 = normalize_name(name2)
    if k1 == k2:
        return False
    # Check if removing all digits makes them identical
    s1 = re.sub(r'\d+', '', k1).strip()
    s2 = re.sub(r'\d+', '', k2).strip()
    if s1 == s2:
        return True
    t1 = [w for w in k1.split() if not w.isdigit()]
    t2 = [w for w in k2.split() if not w.isdigit()]
    if t1 == t2:
        return True
    return False


def suggest_merges(
    exams: List[Exam],
    max_pairs: int = 25,
    min_score: float = 90.0
) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []

    for i in range(len(exams)):
        for j in range(i + 1, len(exams)):
            e1 = exams[i]
            e2 = exams[j]

            words1 = set(e1.key.split())
            words2 = set(e2.key.split())

            is_lab1 = "lab" in words1
            is_lab2 = "lab" in words2
            if is_lab1 != is_lab2:
                continue

            # Never suggest pairs whose names differ only by a number or Roman numeral
            if differ_only_by_number(e1.key, e2.key) or differ_only_by_number(e1.name, e2.name):
                continue

            score = fuzz.token_sort_ratio(e1.key, e2.key)
            if score >= min_score:
                common_prns = sorted(list(set(e1.prns) & set(e2.prns)))
                suggestions.append({
                    "key1": e1.key,
                    "name1": e1.name,
                    "codes1": e1.codes,
                    "students1": len(e1.prns),
                    "key2": e2.key,
                    "name2": e2.name,
                    "codes2": e2.codes,
                    "students2": len(e2.prns),
                    "score": round(float(score), 1),
                    "conflict_count": len(common_prns),
                    "conflict_prns": common_prns,
                })

    suggestions.sort(key=lambda s: s["score"], reverse=True)
    return suggestions[:max_pairs]


def unique_exam_count_per_student(
    rows: List[Row],
    merge_map: Optional[Dict[str, str]] = None
) -> Dict[str, int]:
    effective_map = merge_map or {}
    student_exams: Dict[str, set] = collections.defaultdict(set)

    for r in rows:
        base_key = normalize_name(r.course_name)
        key = effective_map.get(base_key, base_key)
        student_exams[r.prn].add(key)

    return {prn: len(keys) for prn, keys in student_exams.items()}


def search_students(rows: List[Row], query: str) -> List[str]:
    """Filter distinct student PRNs whose PRN or Name contains query (case-insensitive)."""
    student_prns = sorted(list(set(r.prn for r in rows)))
    if not query or not query.strip():
        return student_prns
    q = query.strip().lower()
    names_by_prn = {r.prn: r.name for r in rows}
    return [
        prn for prn in student_prns
        if q in prn.lower() or (prn in names_by_prn and q in names_by_prn[prn].lower())
    ]
