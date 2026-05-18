#!/usr/bin/env python3
"""Generate separate exam and answer-key PDFs from a JSON question set.

Key behavior: each normal question block is wrapped in ReportLab KeepTogether,
so a question that cannot fully fit at the bottom of a page is moved to the
next page instead of being split. A question taller than a whole page may split.
"""
from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

PAGE_SIZES = {"a4": A4, "letter": letter}

FONT_CANDIDATES = [
    ("NotoSansCJK", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ("NotoSerifCJK", "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
    ("SourceHanSans", "/usr/share/fonts/opentype/source-han-sans/SourceHanSansCN-Regular.otf"),
    ("WenQuanYiMicroHei", "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    ("ARPLUMing", "/usr/share/fonts/truetype/arphic/uming.ttc"),
    ("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]


def register_font() -> str:
    for name, path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name
            except Exception:
                continue
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        return "STSong-Light"
    except Exception:
        return "Helvetica"


def esc(value: Any) -> str:
    return html.escape(str(value), quote=False).replace("\n", "<br/>")


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def flatten_questions(data: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any], Dict[str, Any]]]:
    rows: List[Tuple[str, Dict[str, Any], Dict[str, Any]]] = []
    counter = 1
    for section in data.get("sections", []):
        title = section.get("title", "")
        for q in section.get("questions", []):
            q = dict(q)
            q.setdefault("number", str(counter))
            rows.append((title, section, q))
            counter += 1
    return rows


def build_styles(font_name: str) -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ExamTitle", parent=base["Title"], fontName=font_name, fontSize=18,
            leading=24, alignment=TA_CENTER, spaceAfter=6
        ),
        "subtitle": ParagraphStyle(
            "ExamSubtitle", parent=base["Normal"], fontName=font_name, fontSize=11,
            leading=16, alignment=TA_CENTER, textColor=colors.HexColor("#444444"), spaceAfter=8
        ),
        "meta": ParagraphStyle(
            "ExamMeta", parent=base["Normal"], fontName=font_name, fontSize=9,
            leading=13, alignment=TA_CENTER, textColor=colors.HexColor("#555555")
        ),
        "section": ParagraphStyle(
            "Section", parent=base["Heading2"], fontName=font_name, fontSize=13,
            leading=18, spaceBefore=10, spaceAfter=6, keepWithNext=True
        ),
        "normal": ParagraphStyle(
            "NormalCJK", parent=base["Normal"], fontName=font_name, fontSize=10.5,
            leading=16, alignment=TA_LEFT
        ),
        "question": ParagraphStyle(
            "Question", parent=base["Normal"], fontName=font_name, fontSize=10.5,
            leading=16, spaceAfter=4
        ),
        "small": ParagraphStyle(
            "Small", parent=base["Normal"], fontName=font_name, fontSize=9,
            leading=13, textColor=colors.HexColor("#555555")
        ),
        "right": ParagraphStyle(
            "Right", parent=base["Normal"], fontName=font_name, fontSize=9,
            leading=13, alignment=TA_RIGHT
        ),
    }


class NumberedDoc(BaseDocTemplate):
    def __init__(self, filename: str, pagesize: Tuple[float, float], font_name: str, **kwargs: Any):
        self.font_name = font_name
        super().__init__(filename, pagesize=pagesize, **kwargs)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="normal")
        template = PageTemplate(id="main", frames=[frame], onPage=self.draw_page_number)
        self.addPageTemplates([template])

    def draw_page_number(self, canvas, doc):
        canvas.saveState()
        canvas.setFont(self.font_name, 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawCentredString(self.pagesize[0] / 2, 10 * mm, f"第 {doc.page} 页")
        canvas.restoreState()


def header_story(data: Dict[str, Any], styles: Dict[str, ParagraphStyle], label: str) -> List[Any]:
    story: List[Any] = [Paragraph(esc(data.get("title", "试卷")), styles["title"])]
    if data.get("subtitle"):
        story.append(Paragraph(esc(data["subtitle"]), styles["subtitle"]))
    meta = data.get("metadata", {}) or {}
    meta_parts = []
    if meta.get("duration"):
        meta_parts.append(f"时间：{meta['duration']}")
    if meta.get("total_points"):
        meta_parts.append(f"满分：{meta['total_points']}")
    if meta.get("date"):
        meta_parts.append(f"日期：{meta['date']}")
    if meta_parts:
        story.append(Paragraph("　　".join(esc(x) for x in meta_parts), styles["meta"]))
    story.append(Paragraph(label, styles["subtitle"]))
    if data.get("instructions"):
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph("<b>注意事项</b>", styles["normal"]))
        for item in as_list(data.get("instructions")):
            story.append(Paragraph(f"• {esc(item)}", styles["small"]))
    story.append(Spacer(1, 5 * mm))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#999999")))
    story.append(Spacer(1, 5 * mm))
    return story


def question_block(q: Dict[str, Any], styles: Dict[str, ParagraphStyle], answer_mode: bool) -> List[Any]:
    num = esc(q.get("number", ""))
    points = f" <font color='#666666'>[{esc(q.get('points'))}]</font>" if q.get("points") else ""
    prompt = esc(q.get("prompt", ""))
    title = f"<b>{num}.</b> {prompt}{points}" if num else f"{prompt}{points}"
    block: List[Any] = [Paragraph(title, styles["question"])]

    for opt in as_list(q.get("options")):
        block.append(Paragraph(esc(opt), styles["normal"]))
    for idx, sub in enumerate(as_list(q.get("subquestions")), start=1):
        block.append(Paragraph(f"({idx}) {esc(sub)}", styles["normal"]))

    if answer_mode:
        answer = q.get("answer", "")
        explanation = q.get("explanation", "")
        if answer:
            block.append(Spacer(1, 1.5 * mm))
            block.append(Paragraph(f"<b>答案：</b>{esc(answer)}", styles["normal"]))
        if explanation:
            block.append(Paragraph(f"<b>解析：</b>{esc(explanation)}", styles["small"]))
    else:
        lines = int(q.get("answer_space_lines", 0) or 0)
        for _ in range(lines):
            block.append(Spacer(1, 5 * mm))
            block.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#BBBBBB")))

    block.append(Spacer(1, 5 * mm))
    return block


def build_story(data: Dict[str, Any], styles: Dict[str, ParagraphStyle], answer_mode: bool) -> List[Any]:
    story = header_story(data, styles, "答案卷" if answer_mode else "试题卷")
    for section in data.get("sections", []):
        title = section.get("title")
        questions = section.get("questions", [])
        if title:
            if questions:
                first_block = [Paragraph(esc(title), styles["section"])] + question_block(questions[0], styles, answer_mode)
                story.append(KeepTogether(first_block))
                rest = questions[1:]
            else:
                story.append(Paragraph(esc(title), styles["section"]))
                rest = []
        else:
            rest = questions
        for q in rest:
            story.append(KeepTogether(question_block(q, styles, answer_mode)))
    return story


def normalize_numbers(data: Dict[str, Any]) -> Dict[str, Any]:
    counter = 1
    for section in data.get("sections", []):
        for q in section.get("questions", []):
            if not q.get("number"):
                q["number"] = str(counter)
            counter += 1
    return data


def validate_input(data: Dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ValueError("input JSON must be an object")
    if not data.get("title"):
        raise ValueError("input JSON must include title")
    if not data.get("sections"):
        raise ValueError("input JSON must include at least one section")
    for si, section in enumerate(data.get("sections", []), start=1):
        if not section.get("questions"):
            raise ValueError(f"section {si} has no questions")
        for qi, q in enumerate(section.get("questions", []), start=1):
            if not q.get("prompt"):
                raise ValueError(f"section {si} question {qi} is missing prompt")


def generate(data: Dict[str, Any], out_dir: Path, page_size_name: str) -> Tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    data = normalize_numbers(data)
    validate_input(data)
    font_name = register_font()
    styles = build_styles(font_name)
    pagesize = PAGE_SIZES.get(page_size_name.lower(), A4)

    outputs = []
    for filename, answer_mode in [("exam.pdf", False), ("answers.pdf", True)]:
        path = out_dir / filename
        doc = NumberedDoc(
            str(path), pagesize=pagesize, font_name=font_name,
            leftMargin=18 * mm, rightMargin=18 * mm,
            topMargin=18 * mm, bottomMargin=18 * mm,
        )
        doc.build(build_story(data, styles, answer_mode))
        outputs.append(path)
    return outputs[0], outputs[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate separate exam and answer-key PDFs from JSON.")
    parser.add_argument("input_json", help="Path to UTF-8 JSON question set")
    parser.add_argument("--out-dir", default="./exam_output", help="Directory for exam.pdf and answers.pdf")
    parser.add_argument("--page-size", default="a4", choices=sorted(PAGE_SIZES.keys()), help="PDF page size")
    args = parser.parse_args()

    with open(args.input_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    exam, answers = generate(data, Path(args.out_dir), args.page_size)
    print(f"Generated: {exam}")
    print(f"Generated: {answers}")


if __name__ == "__main__":
    main()
