"""
Professional PDF Document Exporter for LessonForge AI using ReportLab.
Renders publication-quality, classroom-ready teaching guides with
custom palettes, timed agenda tables, visual callouts, selectable typography,
and two-pass "Page X of Y" pagination.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.exceptions import ExportError
from core.schemas import LessonPlan, QCReport
from quality_control.qc_schemas import DetailedQCReport

# Page Geometry: Letter is 612 x 792 pt. With 36pt (0.5in) margins, usable width = 540 pt.
PAGE_WIDTH, PAGE_HEIGHT = letter
MARGIN = 36
USABLE_WIDTH = PAGE_WIDTH - (2 * MARGIN)

# Academic Color Palette
COLOR_PRIMARY_NAVY = colors.HexColor("#1A365D")
COLOR_SECONDARY_TEAL = colors.HexColor("#0D9488")
COLOR_DARK_SLATE = colors.HexColor("#1E293B")
COLOR_LIGHT_BG = colors.HexColor("#F8FAFC")
COLOR_BORDER = colors.HexColor("#E2E8F0")
COLOR_ALT_ROW = colors.HexColor("#F1F5F9")
COLOR_PASS = colors.HexColor("#166534")
COLOR_WARN = colors.HexColor("#991B1B")


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas for dynamic total page counting and running headers/footers.
    Renders 'Page X of Y' and document running metadata.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: List[dict[str, Any]] = []
        self.doc_title = "LessonForge AI Teaching Guide"
        self.doc_version = 1

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(COLOR_DARK_SLATE)

        # Header (Pages > 1)
        if self._pageNumber > 1:
            self.drawString(MARGIN, PAGE_HEIGHT - 28, f"LessonForge AI — {self.doc_title} (v{self.doc_version})")
            self.drawRightString(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 28, "Classroom Teaching Guide")
            self.setStrokeColor(COLOR_BORDER)
            self.setLineWidth(0.5)
            self.line(MARGIN, PAGE_HEIGHT - 32, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 32)

        # Footer (All pages)
        self.setStrokeColor(COLOR_BORDER)
        self.setLineWidth(0.5)
        self.line(MARGIN, 36, PAGE_WIDTH - MARGIN, 36)

        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawString(MARGIN, 24, "Peer-Reviewed & Evidence-Grounded Instructional Material")
        self.drawRightString(PAGE_WIDTH - MARGIN, 24, page_str)

        self.restoreState()


class PDFExporter:
    """
    Constructs high-aesthetic, selectable PDF documents for classroom execution.
    Handles long code examples, wrapping tables, and rigorous duration budgeting.
    """

    def __init__(self) -> None:
        self.styles = self._build_stylesheet()

    def _build_stylesheet(self) -> dict[str, ParagraphStyle]:
        base = getSampleStyleSheet()

        styles = {
            "DocTitle": ParagraphStyle(
                "DocTitle",
                parent=base["Title"],
                fontName="Helvetica-Bold",
                fontSize=22,
                leading=26,
                textColor=COLOR_PRIMARY_NAVY,
                alignment=0,
                spaceAfter=6,
            ),
            "DocSubtitle": ParagraphStyle(
                "DocSubtitle",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=11,
                leading=15,
                textColor=COLOR_DARK_SLATE,
                spaceAfter=12,
            ),
            "MetaBanner": ParagraphStyle(
                "MetaBanner",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=9,
                leading=13,
                textColor=colors.white,
            ),
            "Heading1": ParagraphStyle(
                "Heading1",
                parent=base["Heading1"],
                fontName="Helvetica-Bold",
                fontSize=14,
                leading=18,
                textColor=COLOR_PRIMARY_NAVY,
                spaceBefore=14,
                spaceAfter=6,
                keepWithNext=True,
            ),
            "Heading2": ParagraphStyle(
                "Heading2",
                parent=base["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=12,
                leading=16,
                textColor=COLOR_SECONDARY_TEAL,
                spaceBefore=10,
                spaceAfter=4,
                keepWithNext=True,
            ),
            "Heading3": ParagraphStyle(
                "Heading3",
                parent=base["Heading3"],
                fontName="Helvetica-Bold",
                fontSize=10,
                leading=14,
                textColor=COLOR_DARK_SLATE,
                spaceBefore=8,
                spaceAfter=3,
                keepWithNext=True,
            ),
            "Body": ParagraphStyle(
                "Body",
                parent=base["BodyText"],
                fontName="Helvetica",
                fontSize=9.5,
                leading=13.5,
                textColor=COLOR_DARK_SLATE,
                spaceAfter=6,
            ),
            "Bullet": ParagraphStyle(
                "Bullet",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=13,
                textColor=COLOR_DARK_SLATE,
                leftIndent=15,
                firstLineIndent=-10,
                spaceAfter=3,
            ),
            "CalloutText": ParagraphStyle(
                "CalloutText",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=13,
                textColor=COLOR_DARK_SLATE,
            ),
            "CodeBlock": ParagraphStyle(
                "CodeBlock",
                parent=base["Normal"],
                fontName="Courier",
                fontSize=8,
                leading=10.5,
                textColor=colors.HexColor("#0F172A"),
            ),
            "TableHeader": ParagraphStyle(
                "TableHeader",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8.5,
                leading=11.5,
                textColor=colors.white,
                alignment=0,
            ),
            "TableCell": ParagraphStyle(
                "TableCell",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=8,
                leading=11,
                textColor=COLOR_DARK_SLATE,
            ),
            "TableCellBold": ParagraphStyle(
                "TableCellBold",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=11,
                textColor=COLOR_DARK_SLATE,
            ),
        }
        return styles

    def _sanitize_text(self, text: str) -> str:
        """Escape raw XML characters while preserving clean formatting."""
        if not text:
            return ""
        # Escape ampersands not already part of an entity
        text = re.sub(r"&(?![a-zA-Z]+;)", "&amp;", text)
        # Protect specific markdown formatting before escaping
        text = text.replace("<", "&lt;").replace(">", "&gt;")
        # Convert markdown bold and italic to ReportLab tags
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
        text = re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', text)
        return text

    def _markdown_to_flowables(self, md_text: str) -> List[Any]:
        """Convert arbitrary section markdown into ReportLab flowable elements."""
        flowables: List[Any] = []
        lines = md_text.strip().split("\n")
        in_code_block = False
        code_lines: List[str] = []
        in_table = False
        table_lines: List[str] = []

        for line in lines:
            stripped = line.strip()

            # Code Block Boundaries
            if stripped.startswith("```"):
                if in_code_block:
                    code_content = "<br/>".join(self._sanitize_text(c) for c in code_lines)
                    code_p = Paragraph(code_content, self.styles["CodeBlock"])
                    t = Table([[code_p]], colWidths=[USABLE_WIDTH])
                    t.setStyle(
                        TableStyle([
                            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
                            ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                            ("TOPPADDING", (0, 0), (-1, -1), 6),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                            ("LEFTPADDING", (0, 0), (-1, -1), 8),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ])
                    )
                    flowables.append(t)
                    flowables.append(Spacer(1, 6))
                    code_lines = []
                    in_code_block = False
                else:
                    in_code_block = True
                continue

            if in_code_block:
                code_lines.append(line)
                continue

            # Markdown Table Handling
            if stripped.startswith("|") and stripped.endswith("|"):
                in_table = True
                table_lines.append(stripped)
                continue
            elif in_table:
                # Table ended
                flowables.extend(self._render_markdown_table(table_lines))
                table_lines = []
                in_table = False

            if not stripped:
                continue

            # Headings
            if stripped.startswith("### "):
                flowables.append(Paragraph(self._sanitize_text(stripped[4:]), self.styles["Heading3"]))
            elif stripped.startswith("## "):
                flowables.append(Paragraph(self._sanitize_text(stripped[3:]), self.styles["Heading2"]))
            elif stripped.startswith("# "):
                flowables.append(Paragraph(self._sanitize_text(stripped[2:]), self.styles["Heading1"]))
            # Blockquotes / Callouts
            elif stripped.startswith("> "):
                callout_p = Paragraph(self._sanitize_text(stripped[2:]), self.styles["CalloutText"])
                t = Table([[callout_p]], colWidths=[USABLE_WIDTH])
                t.setStyle(
                    TableStyle([
                        ("BACKGROUND", (0, 0), (-1, -1), COLOR_LIGHT_BG),
                        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_SECONDARY_TEAL),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ])
                )
                flowables.append(t)
                flowables.append(Spacer(1, 4))
            # Bullets
            elif stripped.startswith("- ") or stripped.startswith("* "):
                bullet_text = f"&bull; {self._sanitize_text(stripped[2:])}"
                flowables.append(Paragraph(bullet_text, self.styles["Bullet"]))
            # Regular Paragraph
            else:
                flowables.append(Paragraph(self._sanitize_text(line), self.styles["Body"]))

        if in_table and table_lines:
            flowables.extend(self._render_markdown_table(table_lines))

        return flowables

    def _render_markdown_table(self, lines: List[str]) -> List[Any]:
        """Convert markdown table lines to a styled ReportLab Table."""
        rows: List[List[Paragraph]] = []
        header_parsed = False

        for l in lines:
            # Skip separator line like | :--- | :---: |
            if re.match(r"^\|(\s*:?-+:?\s*\|)+$", l):
                continue
            cells = [c.strip() for c in l.split("|")[1:-1]]
            if not cells:
                continue

            if not header_parsed:
                row_cells = [Paragraph(self._sanitize_text(c), self.styles["TableHeader"]) for c in cells]
                header_parsed = True
            else:
                row_cells = [Paragraph(self._sanitize_text(c), self.styles["TableCell"]) for c in cells]
            rows.append(row_cells)

        if not rows:
            return []

        col_count = max(len(r) for r in rows)
        col_width = USABLE_WIDTH / col_count
        col_widths = [col_width] * col_count

        # Pad shorter rows
        for r in rows:
            while len(r) < col_count:
                r.append(Paragraph("", self.styles["TableCell"]))

        table = Table(rows, colWidths=col_widths, repeatRows=1)
        t_style = [
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY_NAVY),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]
        # Alternating row colors
        for i in range(1, len(rows)):
            if i % 2 == 0:
                t_style.append(("BACKGROUND", (0, i), (-1, i), COLOR_ALT_ROW))

        table.setStyle(TableStyle(t_style))
        return [table, Spacer(1, 8)]

    def export(
        self,
        lesson: LessonPlan,
        qc_reports: Optional[List[DetailedQCReport | QCReport]] = None,
        output_path: Optional[Path | str] = None,
    ) -> Path:
        """
        Generate PDF teaching document from LessonPlan and optional audit reports.
        Writes to output_path and returns the Path object.
        """
        if not isinstance(lesson, LessonPlan):
            raise ExportError("Expected a valid LessonPlan object for PDF export.")

        if output_path is None:
            from config import AppConfig
            config = AppConfig()
            config.ensure_directories()
            output_path = config.EXPORTS_DIR / f"{lesson.lesson_id}_v{lesson.version}.pdf"

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(out_path),
            pagesize=letter,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=MARGIN,
            bottomMargin=MARGIN,
        )

        story: List[Any] = []

        # -------------------------------------------------------------------
        # 1. Header Banner & Title Block
        # -------------------------------------------------------------------
        story.append(Paragraph(self._sanitize_text(lesson.title), self.styles["DocTitle"]))
        sub_text = (
            f"<b>Target Audience:</b> {lesson.learner_level.value.capitalize()} &nbsp;|&nbsp; "
            f"<b>Duration:</b> {lesson.total_duration_minutes} Minutes (Strict Ceiling: 45m) &nbsp;|&nbsp; "
            f"<b>Version:</b> v{lesson.version}"
        )
        story.append(Paragraph(sub_text, self.styles["DocSubtitle"]))

        # Metadata banner box
        meta_html = (
            f"<b>Lesson ID:</b> {lesson.lesson_id} &nbsp;&bull;&nbsp; "
            f"<b>Generated:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        )
        meta_p = Paragraph(meta_html, self.styles["MetaBanner"])
        meta_table = Table([[meta_p]], colWidths=[USABLE_WIDTH])
        meta_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_PRIMARY_NAVY),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        story.append(meta_table)
        story.append(Spacer(1, 10))

        # Learning Objective Callout
        obj_html = f"<b>Core Learning Objective:</b><br/>{self._sanitize_text(lesson.learning_objective)}"
        obj_p = Paragraph(obj_html, self.styles["CalloutText"])
        obj_table = Table([[obj_p]], colWidths=[USABLE_WIDTH])
        obj_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_LIGHT_BG),
                ("BOX", (0, 0), (-1, -1), 1, COLOR_SECONDARY_TEAL),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        story.append(obj_table)
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------------
        # 2. Measurable Learning Outcomes
        # -------------------------------------------------------------------
        story.append(Paragraph("Measurable Learning Outcomes", self.styles["Heading2"]))
        for outcome in lesson.learning_outcomes:
            story.append(Paragraph(f"&bull; {self._sanitize_text(outcome)}", self.styles["Bullet"]))
        story.append(Spacer(1, 8))

        # -------------------------------------------------------------------
        # 3. Timed Agenda / 45-Minute Classroom Allocation Table
        # -------------------------------------------------------------------
        story.append(Paragraph("Classroom Agenda & Time Allocation (45-Minute Budget)", self.styles["Heading2"]))
        agenda_data = [
            [
                Paragraph("Phase / Instructional Module", self.styles["TableHeader"]),
                Paragraph("Cognitive Focus", self.styles["TableHeader"]),
                Paragraph("Duration", self.styles["TableHeader"]),
                Paragraph("% Class", self.styles["TableHeader"]),
            ]
        ]
        for s in lesson.sections:
            pct = round((s.duration_minutes / lesson.total_duration_minutes) * 100, 1)
            agenda_data.append([
                Paragraph(self._sanitize_text(s.title), self.styles["TableCell"]),
                Paragraph(self._sanitize_text(s.cognitive_focus), self.styles["TableCell"]),
                Paragraph(f"{s.duration_minutes} min", self.styles["TableCellBold"]),
                Paragraph(f"{pct}%", self.styles["TableCell"]),
            ])

        if lesson.guided_activity:
            act = lesson.guided_activity
            act_pct = round((act.duration_minutes / lesson.total_duration_minutes) * 100, 1)
            agenda_data.append([
                Paragraph(f"<b>Guided Lab:</b> {self._sanitize_text(act.title)}", self.styles["TableCellBold"]),
                Paragraph("Hands-On Guided Activity", self.styles["TableCell"]),
                Paragraph(f"{act.duration_minutes} min", self.styles["TableCellBold"]),
                Paragraph(f"{act_pct}%", self.styles["TableCell"]),
            ])

        agenda_data.append([
            Paragraph("<b>Total Classroom Delivery</b>", self.styles["TableCellBold"]),
            Paragraph("Comprehensive Synthesis", self.styles["TableCell"]),
            Paragraph(f"<b>{lesson.total_duration_minutes} min</b>", self.styles["TableCellBold"]),
            Paragraph("<b>100%</b>", self.styles["TableCellBold"]),
        ])

        agenda_table = Table(agenda_data, colWidths=[220, 180, 70, 70])
        agenda_style = [
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY_NAVY),
            ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, -1), (-1, -1), 1, COLOR_PRIMARY_NAVY),
        ]
        for i in range(1, len(agenda_data) - 1):
            if i % 2 == 0:
                agenda_style.append(("BACKGROUND", (0, i), (-1, i), COLOR_ALT_ROW))
        agenda_table.setStyle(TableStyle(agenda_style))
        story.append(agenda_table)
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------------
        # 4. Introduction
        # -------------------------------------------------------------------
        story.append(Paragraph("Introduction & Conceptual Orientation", self.styles["Heading2"]))
        story.append(Paragraph(self._sanitize_text(lesson.introduction), self.styles["Body"]))
        story.append(Spacer(1, 6))

        # -------------------------------------------------------------------
        # 5. Core Sequential Modules
        # -------------------------------------------------------------------
        for idx, sec in enumerate(lesson.sections, start=1):
            header_text = f"{self._sanitize_text(sec.title)} &nbsp;<font size=8 color='#0D9488'>({sec.duration_minutes} min | {self._sanitize_text(sec.cognitive_focus)})</font>"
            story.append(Paragraph(header_text, self.styles["Heading1"]))
            story.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_SECONDARY_TEAL, spaceBefore=2, spaceAfter=6))

            # Parse and append markdown flowables
            sec_flowables = self._markdown_to_flowables(sec.content_markdown)
            story.extend(sec_flowables)

            if sec.citations:
                cites_html = "<b>Authoritative Citations:</b> " + ", ".join(f"[{c}]" for c in sec.citations)
                story.append(Paragraph(cites_html, self.styles["CalloutText"]))
                story.append(Spacer(1, 6))

        # -------------------------------------------------------------------
        # 6. Guided Hands-On Activity
        # -------------------------------------------------------------------
        if lesson.guided_activity:
            act = lesson.guided_activity
            act_header = f"Guided Hands-On Lab: {self._sanitize_text(act.title)} ({act.duration_minutes} min)"
            act_elements = [
                Paragraph(act_header, self.styles["Heading1"]),
                HRFlowable(width="100%", thickness=0.5, color=COLOR_SECONDARY_TEAL, spaceBefore=2, spaceAfter=6),
                Paragraph("<b>Instructions:</b>", self.styles["Heading3"]),
                Paragraph(self._sanitize_text(act.instructions), self.styles["Body"]),
                Spacer(1, 4),
                Paragraph(f"<b>Expected Deliverable:</b> {self._sanitize_text(act.deliverable)}", self.styles["CalloutText"]),
            ]
            if act.evaluation_criteria:
                act_elements.append(Spacer(1, 4))
                act_elements.append(Paragraph("<b>Evaluation Rubric:</b>", self.styles["Heading3"]))
                for crit in act.evaluation_criteria:
                    act_elements.append(Paragraph(f"[ ] {self._sanitize_text(crit)}", self.styles["Bullet"]))

            story.append(KeepTogether(act_elements))
            story.append(Spacer(1, 10))

        # -------------------------------------------------------------------
        # 7. Knowledge Checks & Answer Key
        # -------------------------------------------------------------------
        if lesson.knowledge_checks:
            kc_elements = [
                Paragraph("Formative Knowledge Checks", self.styles["Heading1"]),
                HRFlowable(width="100%", thickness=0.5, color=COLOR_SECONDARY_TEAL, spaceBefore=2, spaceAfter=6),
            ]
            for i, kc in enumerate(lesson.knowledge_checks, start=1):
                kc_elements.append(Paragraph(f"<b>Q{i}:</b> {self._sanitize_text(kc.question)}", self.styles["Heading3"]))
                for opt in kc.options:
                    kc_elements.append(Paragraph(f"&bull; {self._sanitize_text(opt)}", self.styles["Bullet"]))
                # Answer Box
                ans_text = f"<b>Answer:</b> {self._sanitize_text(kc.correct_answer)} &nbsp;|&nbsp; <b>Rationale:</b> {self._sanitize_text(kc.explanation)}"
                ans_p = Paragraph(ans_text, self.styles["CalloutText"])
                ans_tbl = Table([[ans_p]], colWidths=[USABLE_WIDTH])
                ans_tbl.setStyle(
                    TableStyle([
                        ("BACKGROUND", (0, 0), (-1, -1), COLOR_LIGHT_BG),
                        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ])
                )
                kc_elements.append(Spacer(1, 3))
                kc_elements.append(ans_tbl)
                kc_elements.append(Spacer(1, 6))

            story.append(KeepTogether(kc_elements))

        # -------------------------------------------------------------------
        # 8. Summary & Key Takeaways
        # -------------------------------------------------------------------
        story.append(Paragraph("Summary & Key Takeaways", self.styles["Heading1"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_SECONDARY_TEAL, spaceBefore=2, spaceAfter=6))
        story.append(Paragraph(self._sanitize_text(lesson.summary), self.styles["Body"]))
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------------
        # 9. Research References & Provenance Table
        # -------------------------------------------------------------------
        story.append(Paragraph("Authoritative Research Bibliography & Provenance", self.styles["Heading1"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_SECONDARY_TEAL, spaceBefore=2, spaceAfter=6))

        ref_data = [
            [
                Paragraph("ID", self.styles["TableHeader"]),
                Paragraph("Resource Title", self.styles["TableHeader"]),
                Paragraph("Type", self.styles["TableHeader"]),
                Paragraph("Provenance", self.styles["TableHeader"]),
                Paragraph("Credibility", self.styles["TableHeader"]),
                Paragraph("Reference Link", self.styles["TableHeader"]),
            ]
        ]
        for ref in lesson.references:
            cred_str = f"{round(ref.credibility_score * 100)}%"
            ref_data.append([
                Paragraph(f"<code>{ref.id}</code>", self.styles["TableCellBold"]),
                Paragraph(self._sanitize_text(ref.title), self.styles["TableCell"]),
                Paragraph(ref.source_type.value, self.styles["TableCell"]),
                Paragraph(f"<b>{ref.provenance.value}</b>", self.styles["TableCell"]),
                Paragraph(cred_str, self.styles["TableCellBold"]),
                Paragraph(self._sanitize_text(ref.url), self.styles["TableCell"]),
            ])

        # Widths sum to 540 pt: 50 + 170 + 50 + 80 + 50 + 140 = 540
        ref_table = Table(ref_data, colWidths=[50, 170, 50, 80, 50, 140], repeatRows=1)
        ref_style = [
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY_NAVY),
            ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]
        for i in range(1, len(ref_data)):
            if i % 2 == 0:
                ref_style.append(("BACKGROUND", (0, i), (-1, i), COLOR_ALT_ROW))
        ref_table.setStyle(TableStyle(ref_style))
        story.append(ref_table)
        story.append(Spacer(1, 14))

        # -------------------------------------------------------------------
        # 10. Quality Control Audit Appendix
        # -------------------------------------------------------------------
        story.append(Paragraph(f"Appendix: Quality Control Audit Reports (Version {lesson.version})", self.styles["Heading1"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_SECONDARY_TEAL, spaceBefore=2, spaceAfter=6))

        if qc_reports:
            matching_reports = [r for r in qc_reports if r.version_audited == lesson.version]
            if matching_reports:
                for rep in matching_reports:
                    layer_name = (
                        "QC Layer 1: Research & Factual Accuracy"
                        if rep.layer.value == "FACTUAL_ACCURACY"
                        else "QC Layer 2: Instructional Quality"
                    )
                    status_col = COLOR_PASS if rep.status.value == "PASSED" else COLOR_WARN
                    badge_html = f"<b>{layer_name}</b> &nbsp;|&nbsp; Score: <b>{rep.overall_score}/100</b> &nbsp;|&nbsp; Status: <b>{rep.status.value}</b>"
                    badge_p = Paragraph(badge_html, self.styles["CalloutText"])
                    badge_tbl = Table([[badge_p]], colWidths=[USABLE_WIDTH])
                    badge_tbl.setStyle(
                        TableStyle([
                            ("BACKGROUND", (0, 0), (-1, -1), COLOR_LIGHT_BG),
                            ("BOX", (0, 0), (-1, -1), 1, status_col),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ])
                    )
                    story.append(badge_tbl)
                    story.append(Spacer(1, 4))
                    story.append(Paragraph(f"<b>Executive Summary:</b> {self._sanitize_text(rep.summary)}", self.styles["Body"]))

                    if rep.findings:
                        story.append(Paragraph(f"<b>Audit Findings ({len(rep.findings)} items):</b>", self.styles["Heading3"]))
                        for f in rep.findings:
                            f_text = f"&bull; <b>[{f.severity.value}] {self._sanitize_text(f.criterion)}:</b> {self._sanitize_text(f.description)}"
                            story.append(Paragraph(f_text, self.styles["Bullet"]))
                    story.append(Spacer(1, 8))
            else:
                notice = f"<i>Notice: No Quality Control audit records found matching version {lesson.version}. Existing reports correspond to other revisions.</i>"
                story.append(Paragraph(notice, self.styles["Body"]))
        else:
            notice = f"<i>Notice: Independent Quality Control audit has not yet been conducted for Version {lesson.version}.</i>"
            story.append(Paragraph(notice, self.styles["Body"]))

        # Build Document using NumberedCanvas
        def build_canvas(*args: Any, **kwargs: Any) -> NumberedCanvas:
            c = NumberedCanvas(*args, **kwargs)
            c.doc_title = lesson.title
            c.doc_version = lesson.version
            return c

        doc.build(story, canvasmaker=build_canvas)
        return out_path
