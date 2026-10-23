import io
import re
from pathlib import Path
from typing import Union, Optional, List, Dict, Any, Tuple
import pandas as pd
import pymupdf
from models import Row, ParseResult

PROGRAM_PATTERN = r'(?:BTECH\.AIDS|B\.Tech\.\s*\(AI&DS\)|B\.Tech\.\s*\(CSE-AI&ML\)|BTech\s*-\s*CSE\s*\(AI\)|BTech\s*-\s*CSE\s*\(AI\s*&\s*ML\))'
YEAR_PATTERN = r'(?:First|Second|Third|Fourth)\s+Year'
AY_PATTERN = r'\d{4}-\d{2}'

RECORD_REGEX = re.compile(
    r'(?P<sr>\d{1,4})\s+'
    r'(?P<prn>\d{10}(?:\d{3})?)\s+'
    r'(?P<name>[^\d]+?)\s+'
    r'(?P<course_code>(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{6,15})\s+'
    r'(?P<course_name>.+?)\s+'
    rf'(?P<program>{PROGRAM_PATTERN})\s+'
    rf'(?P<year>{YEAR_PATTERN})\s+'
    rf'(?P<ay>{AY_PATTERN})\s*'
    r'(?P<sem>\d)\s*'
    r'(?=\d{1,4}\s+\d{10}(?:\d{3})?|$)'
)

HEADER_REGEX = re.compile(
    r'SR\s*No\.?\s*PRN\s*Name\s*Course\s*Code\s*Course\s*Name\s*Program\s*Year\s*AY\s*sem',
    re.IGNORECASE
)

def _clean_spaces(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()

def parse_text_stream(full_text: str, page_ranges: List[Tuple[int, int, int]]) -> ParseResult:
    cleaned_full_text = HEADER_REGEX.sub(" ", full_text)

    def get_page(pos: int) -> int:
        for start_pos, end_pos, page_num in page_ranges:
            if start_pos <= pos < end_pos:
                return page_num
        return page_ranges[-1][2] if page_ranges else 1

    matches = list(RECORD_REGEX.finditer(cleaned_full_text))
    rows: List[Row] = []
    failed: List[Dict[str, Any]] = []

    last_end = 0
    for m in matches:
        gap = cleaned_full_text[last_end:m.start()].strip()
        if gap:
            failed.append({
                "page": get_page(last_end),
                "raw_text": gap,
                "reason": "unmatched leftover"
            })
        last_end = m.end()

        sr = int(m.group("sr"))
        prn = m.group("prn").strip()
        name = _clean_spaces(m.group("name"))
        course_code = _clean_spaces(m.group("course_code"))
        course_name = _clean_spaces(m.group("course_name"))
        program = _clean_spaces(m.group("program"))
        year = _clean_spaces(m.group("year"))
        ay = _clean_spaces(m.group("ay"))
        sem = m.group("sem").strip()
        page = get_page(m.start())

        row = Row(
            sr=sr,
            prn=prn,
            name=name,
            course_code=course_code,
            course_name=course_name,
            program=program,
            year=year,
            ay=ay,
            sem=sem,
            page=page
        )
        rows.append(row)

    trailing = cleaned_full_text[last_end:].strip()
    if trailing:
        failed.append({
            "page": get_page(last_end),
            "raw_text": trailing,
            "reason": "unmatched leftover"
        })

    missing_sr: List[int] = []
    if rows:
        min_sr = rows[0].sr
        max_sr = rows[-1].sr
        present_srs = {r.sr for r in rows}
        for expected in range(min_sr, max_sr + 1):
            if expected not in present_srs:
                missing_sr.append(expected)

    stats = {
        "total_rows": len(rows),
        "total_pages": page_ranges[-1][2] if page_ranges else 1,
        "failed_count": len(failed),
        "missing_sr_count": len(missing_sr),
        "unique_prns": len({r.prn for r in rows}),
    }

    return ParseResult(
        rows=rows,
        failed=failed,
        missing_sr=missing_sr,
        stats=stats
    )

def parse_pdf(file_input: Union[str, Path, bytes]) -> ParseResult:
    if isinstance(file_input, bytes):
        doc = pymupdf.open(stream=file_input, filetype="pdf")
    else:
        doc = pymupdf.open(str(file_input))

    full_text = ""
    page_ranges: List[Tuple[int, int, int]] = []

    for page_idx, page in enumerate(doc):
        page_num = page_idx + 1
        raw_text = page.get_text("text").replace("\r\n", " ").replace("\n", " ")
        cleaned_text = HEADER_REGEX.sub(" ", raw_text)

        start_pos = len(full_text)
        full_text += cleaned_text + " "
        end_pos = len(full_text)
        page_ranges.append((start_pos, end_pos, page_num))

    doc.close()
    return parse_text_stream(full_text, page_ranges)

def parse_table_file(file_bytes: bytes, filename: str) -> ParseResult:
    lower_fn = filename.lower()
    if lower_fn.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes), dtype=str)
    else:
        df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)

    col_map: Dict[str, str] = {}
    for c in df.columns:
        clean_c = re.sub(r'[^a-z0-9]', '', str(c).lower())
        if clean_c in {"sr", "srno", "sno", "serialno"}:
            col_map["sr"] = c
        elif clean_c in {"prn", "prnno", "prnnumber"}:
            col_map["prn"] = c
        elif clean_c in {"name", "studentname"}:
            col_map["name"] = c
        elif clean_c in {"coursecode", "code", "subjectcode"}:
            col_map["course_code"] = c
        elif clean_c in {"coursename", "subjectname", "subject", "course"}:
            col_map["course_name"] = c
        elif clean_c in {"program", "programme", "branch", "department", "dept"}:
            col_map["program"] = c
        elif clean_c in {"year"}:
            col_map["year"] = c
        elif clean_c in {"ay", "academicyear"}:
            col_map["ay"] = c
        elif clean_c in {"sem", "semester"}:
            col_map["sem"] = c

    rows: List[Row] = []
    failed: List[Dict[str, Any]] = []

    required_keys = ["sr", "prn", "name", "course_code", "course_name", "program", "year", "ay", "sem"]
    missing_cols = [k for k in required_keys if k not in col_map]
    if missing_cols:
        failed.append({
            "page": 1,
            "raw_text": f"Missing columns in table file: {missing_cols}",
            "reason": "missing_columns"
        })
        return ParseResult(rows=[], failed=failed, missing_sr=[], stats={"error": "missing_columns"})

    for index, record in df.iterrows():
        try:
            sr_val = int(record[col_map["sr"]])
            prn_val = str(record[col_map["prn"]]).strip()
            name_val = _clean_spaces(str(record[col_map["name"]]))
            cc_val = _clean_spaces(str(record[col_map["course_code"]]))
            cn_val = _clean_spaces(str(record[col_map["course_name"]]))
            prog_val = _clean_spaces(str(record[col_map["program"]]))
            year_val = _clean_spaces(str(record[col_map["year"]]))
            ay_val = _clean_spaces(str(record[col_map["ay"]]))
            sem_val = str(record[col_map["sem"]]).strip()

            row = Row(
                sr=sr_val,
                prn=prn_val,
                name=name_val,
                course_code=cc_val,
                course_name=cn_val,
                program=prog_val,
                year=year_val,
                ay=ay_val,
                sem=sem_val,
                page=1
            )
            rows.append(row)
        except Exception as e:
            failed.append({
                "page": 1,
                "raw_text": str(record.to_dict()),
                "reason": f"Row conversion error: {str(e)}"
            })

    missing_sr: List[int] = []
    if rows:
        min_sr = rows[0].sr
        max_sr = rows[-1].sr
        present_srs = {r.sr for r in rows}
        for expected in range(min_sr, max_sr + 1):
            if expected not in present_srs:
                missing_sr.append(expected)

    stats = {
        "total_rows": len(rows),
        "total_pages": 1,
        "failed_count": len(failed),
        "missing_sr_count": len(missing_sr),
        "unique_prns": len({r.prn for r in rows}),
    }

    return ParseResult(
        rows=rows,
        failed=failed,
        missing_sr=missing_sr,
        stats=stats
    )
