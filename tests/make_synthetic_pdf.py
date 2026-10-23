import random
from pathlib import Path
from typing import List, Union
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from pdf_common import get_base_styles, DARK_BLUE, LIGHT_GREY, BORDER_GREY
from models import Row

COURSE_NAMES_POOL = [
    "Advanced Machine Learning",
    "Advanced Machine Learning Lab",
    "Cluster Computing",
    "Cluster Computing Lab",
    "From Campus to Corporate-I",
    "Natural Language Processing",
    "Natural Language Processing Lab",
    "Digital Forensics",
    "Digital Forensics Lab",
    "Social, Web and Mobile Analytics",
    "Social, Web and Mobile Analytics Lab",
    "Fundamentals of Human Anatomy and Physiology",
    "Data Warehouse and Multidimensional Modeling",
    "Statistical Data Analysis",
    "STATISTICAL DATA ANALYSIS",
    "Statistcal Data Analysis Lab",
    "Operating Systems - Lab",
    "Operating System Lab",
    "Project Based Learning -Python",
    "Project Based Learning-Python",
    "Financial Literacy and Banking",
    "Cyber Security and Ethical Hacking",
    "Cloud Computing and Virtualization",
    "Internet of Things - Applications",
    "Deep Learning Fundamentals",
    "Quantum Computing Principles",
    "Robotics and Automation - 1",
    "Computer Vision and Image Processing",
    "High Performance Computing Lab",
    "Business Intelligence - II",
    "Big Data Analytics and Mining",
    "Wireless Sensor Networks",
    "Blockchain Technologies and Security",
    "Artificial Intelligence in Healthcare",
    "Software Engineering and Agile Practices",
    "Design Thinking and Innovation",
    "Emotional Intelligence",
    "Environmental Studies and Sustainability",
    "Universal Human Values",
    "Effective Technical Communication",
    "Engineering Economics and Management",
    "Optimization Techniques in Machine Learning",
    "Neural Networks and Fuzzy Logic",
    "Mobile Application Development",
    "Web Technologies and Frameworks",
    "Embedded Systems Design",
    "Database Management Systems",
    "Database Management Systems Lab",
    "Object Oriented Programming with Java",
    "Python for Data Science",
    "Data Structures and Algorithms",
    "Theory of Computation",
    "Compiler Design Lab",
    "Computer Networks",
    "Computer Networks Lab",
    "Information Security and Cryptography",
    "Distributed Systems and Cloud",
    "Bioinformatics and Computational Biology",
    "Virtual and Augmented Reality",
    "Game Development and Simulation",
    "Speech and Audio Processing",
    "Reinforcement Learning Applications",
]

PROGRAMS_POOL = [
    "BTECH.AIDS",
    "B.Tech. (AI&DS)",
    "B.Tech. (CSE-AI&ML)",
    "BTech - CSE (AI)",
    "BTech - CSE (AI & ML)",
]

FIRST_NAMES = ["Aarav", "Arya", "Aditya", "Krushna", "Sufyan", "Mihil", "Swapnil", "Krish", "Affan", "Atharv", "Yash", "Shivam", "Purushottam", "Gyanoba", "Vasudeo"]
LAST_NAMES = ["Patil", "Chaudhari", "Deshmukh", "Kulkarni", "Sharma", "Memon", "Gangale", "Chorge", "Deore", "Pardeshi", "Selokar", "Rathod", "Pujari", "Joshi", "Bipin"]

YEARS_POOL = ["First Year", "Second Year", "Third Year", "Fourth Year"]
AYS_POOL = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]

def generate_synthetic_rows(
    count: int,
    seed: int = 42,
    duplicate_ratio: float = 0.05,
    start_sr: int = 1
) -> List[Row]:
    rng = random.Random(seed)
    rows: List[Row] = []

    students = []
    for i in range(max(10, count // 3)):
        if rng.random() < 0.5:
            prn = f"218137{rng.randint(1000, 9999)}"
        else:
            prn = f"3124047{rng.randint(100000, 999999)}"
        fname = rng.choice(FIRST_NAMES)
        lname = rng.choice(LAST_NAMES)
        case_type = rng.choice(["title", "upper", "lower"])
        full_name = f"{fname} {lname}"
        if case_type == "upper":
            full_name = full_name.upper()
        elif case_type == "lower":
            full_name = full_name.lower()
        students.append((prn, full_name, rng.choice(PROGRAMS_POOL), rng.choice(YEARS_POOL)))

    dup_count = int(count * duplicate_ratio)
    standard_count = count - dup_count

    for idx in range(standard_count):
        sr = start_sr + idx
        prn, name, prog, yr = rng.choice(students)
        c_name = rng.choice(COURSE_NAMES_POOL)
        c_code = f"BT{rng.choice(['EC', 'CS', 'AI'])}{rng.randint(21000, 24999)}"
        ay = rng.choice(AYS_POOL)
        sem = str(rng.choice([1, 2]))

        rows.append(Row(
            sr=sr,
            prn=prn,
            name=name,
            course_code=c_code,
            course_name=c_name,
            program=prog,
            year=yr,
            ay=ay,
            sem=sem,
            page=1
        ))

    for idx in range(dup_count):
        orig = rng.choice(rows[:standard_count])
        sr = start_sr + standard_count + idx
        rows.append(Row(
            sr=sr,
            prn=orig.prn,
            name=orig.name,
            course_code=orig.course_code,
            course_name=orig.course_name,
            program=orig.program,
            year=orig.year,
            ay=orig.ay,
            sem=orig.sem,
            page=1
        ))

    rows.sort(key=lambda r: r.sr)
    return rows

def make_pdf(
    rows: List[Row],
    path: Union[str, Path],
    rows_per_page: int = 45,
    wrap_width: int = 25,
    glue_mode: str = "normal"
) -> List[Row]:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    _, body_style, header_cell_style, _, _ = get_base_styles()
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=20,
        rightMargin=20,
        topMargin=20,
        bottomMargin=20
    )

    headers = [
        Paragraph("SR No. PRN", header_cell_style),
        Paragraph("Name", header_cell_style),
        Paragraph("Course Code", header_cell_style),
        Paragraph("Course Name", header_cell_style),
        Paragraph("Program", header_cell_style),
        Paragraph("Year", header_cell_style),
        Paragraph("AY", header_cell_style),
        Paragraph("sem", header_cell_style),
    ]

    table_data = [headers]

    for idx, r in enumerate(rows):
        ay_text = r.ay
        sem_text = r.sem

        if glue_mode == "glued_sem":
            ay_text = f"{r.ay}{r.sem}"
            sem_text = ""
        elif glue_mode == "glued_sr" and idx < len(rows) - 1:
            sem_text = f"{r.sem}{rows[idx + 1].sr}"

        table_data.append([
            Paragraph(f"{r.sr}\n{r.prn}", body_style),
            Paragraph(r.name, body_style),
            Paragraph(r.course_code, body_style),
            Paragraph(r.course_name, body_style),
            Paragraph(r.program, body_style),
            Paragraph(r.year, body_style),
            Paragraph(ay_text, body_style),
            Paragraph(sem_text, body_style),
        ])

    pdf_table = Table(table_data, colWidths=[65, 95, 65, 130, 80, 50, 40, 30], repeatRows=1)
    t_style = [
        ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]
    for r_i in range(1, len(table_data)):
        if r_i % 2 == 0:
            t_style.append(('BACKGROUND', (0, r_i), (-1, r_i), LIGHT_GREY))
    pdf_table.setStyle(TableStyle(t_style))

    doc.build([pdf_table])
    return rows
