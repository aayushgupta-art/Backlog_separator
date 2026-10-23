import os
from datetime import datetime
from pathlib import Path
from typing import Tuple
from zoneinfo import ZoneInfo
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

KOLKATA_TZ = ZoneInfo("Asia/Kolkata")

FONT_NAME = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

def register_fonts() -> Tuple[str, str]:
    global FONT_NAME, FONT_BOLD
    fonts_dir = Path(__file__).parent / "fonts"
    dejavu_normal = fonts_dir / "DejaVuSans.ttf"
    dejavu_bold = fonts_dir / "DejaVuSans-Bold.ttf"

    if dejavu_normal.is_file() and dejavu_bold.is_file():
        try:
            pdfmetrics.registerFont(TTFont("DejaVuSans", str(dejavu_normal)))
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(dejavu_bold)))
            FONT_NAME = "DejaVuSans"
            FONT_BOLD = "DejaVuSans-Bold"
            return FONT_NAME, FONT_BOLD
        except Exception:
            pass

    win_arial = Path(r"C:\Windows\Fonts\arial.ttf")
    win_arial_bd = Path(r"C:\Windows\Fonts\arialbd.ttf")
    if win_arial.is_file() and win_arial_bd.is_file():
        try:
            pdfmetrics.registerFont(TTFont("Arial", str(win_arial)))
            pdfmetrics.registerFont(TTFont("Arial-Bold", str(win_arial_bd)))
            FONT_NAME = "Arial"
            FONT_BOLD = "Arial-Bold"
            return FONT_NAME, FONT_BOLD
        except Exception:
            pass

    FONT_NAME = "Helvetica"
    FONT_BOLD = "Helvetica-Bold"
    return FONT_NAME, FONT_BOLD

register_fonts()

DARK_BLUE = colors.HexColor("#1A365D")
LIGHT_GREY = colors.HexColor("#F7FAFC")
BORDER_GREY = colors.HexColor("#CBD5E0")
PASS_GREEN = colors.HexColor("#22543D")
FAIL_RED = colors.HexColor("#742A2A")

def get_base_styles():
    register_fonts()
    styles = getSampleStyleSheet()

    body_style = ParagraphStyle(
        name="CustomBody",
        parent=styles["Normal"],
        fontName=FONT_NAME,
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#2D3748")
    )
    header_cell_style = ParagraphStyle(
        name="CustomHeaderCell",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=9,
        leading=11,
        textColor=colors.white
    )
    title_style = ParagraphStyle(
        name="CustomTitle",
        parent=styles["Title"],
        fontName=FONT_BOLD,
        fontSize=16,
        leading=20,
        textColor=DARK_BLUE,
        alignment=1
    )
    subtitle_style = ParagraphStyle(
        name="CustomSubtitle",
        parent=styles["Normal"],
        fontName=FONT_NAME,
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#4A5568"),
        alignment=1
    )
    return styles, body_style, header_cell_style, title_style, subtitle_style

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont(FONT_NAME, 8)
        self.setFillColor(colors.HexColor("#718096"))

        timestamp_str = datetime.now(KOLKATA_TZ).strftime("%Y-%m-%d %H:%M:%S")
        footer_text = f"Page {self._pageNumber} of {page_count}  |  Generated on {timestamp_str}"
        self.drawRightString(self._pagesize[0] - 36, 20, footer_text)

        self.setStrokeColor(BORDER_GREY)
        self.setLineWidth(0.5)
        self.line(36, 30, self._pagesize[0] - 36, 30)
        self.restoreState()
