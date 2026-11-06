"""
Unified Export Service for LessonForge AI.
Coordinates multi-format generation (GFM Markdown and ReportLab PDF),
enforces version selection, and links exact-version QC audit reports.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

from config import AppConfig
from core.exceptions import ExportError, LessonNotFoundError, VersionNotFoundError
from core.schemas import LessonPlan, QCReport
from export.markdown_exporter import MarkdownExporter
from export.pdf_exporter import PDFExporter
from quality_control.qc_schemas import DetailedQCReport
from storage.lesson_repository import LessonRepository

logger = logging.getLogger(__name__)


class ExportService:
    """
    Service facade for generating classroom-ready lesson export artifacts.
    Guarantees version traceability, preventing audit report crosstalk across versions.
    """

    def __init__(self, repo: Optional[LessonRepository] = None) -> None:
        self.repo = repo or LessonRepository()
        self.md_exporter = MarkdownExporter()
        self.pdf_exporter = PDFExporter()
        self.config = AppConfig()
        self.config.ensure_directories()

    def _resolve_lesson_and_reports(
        self,
        target: Union[str, LessonPlan],
        version: Optional[int] = None,
    ) -> tuple[LessonPlan, List[DetailedQCReport]]:
        """
        Resolve LessonPlan and corresponding version-matched QC reports.
        Enforces that reports match the exact requested version.
        """
        if isinstance(target, LessonPlan):
            lesson = target
            # If explicit version was specified and does not match lesson.version, warn or reject
            if version is not None and lesson.version != version:
                raise ExportError(
                    f"Passed LessonPlan has version {lesson.version}, which does not match requested version {version}."
                )
            # Try to fetch QC reports from repository if available
            try:
                qc_reports = self.repo.get_qc_reports(lesson.lesson_id, version_number=lesson.version)
            except Exception:
                qc_reports = []
            return lesson, qc_reports

        lesson_id = str(target)
        if version is not None:
            lesson = self.repo.get_lesson_version(lesson_id, version_number=version)
            if lesson is None:
                raise VersionNotFoundError(f"Version {version} for lesson '{lesson_id}' not found in storage.")
        else:
            lesson = self.repo.get_lesson(lesson_id)
            if lesson is None:
                raise LessonNotFoundError(f"Lesson '{lesson_id}' not found in storage.")

        # Retrieve QC reports strictly for this lesson version
        qc_reports = self.repo.get_qc_reports(lesson_id, version_number=lesson.version)
        return lesson, qc_reports

    def export_markdown(
        self,
        target: Union[str, LessonPlan],
        version: Optional[int] = None,
        output_dir: Optional[Union[Path, str]] = None,
    ) -> Path:
        """Export the selected lesson version as GitHub Flavored Markdown."""
        lesson, qc_reports = self._resolve_lesson_and_reports(target, version=version)
        out_dir = Path(output_dir) if output_dir else self.config.EXPORTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{lesson.lesson_id}_v{lesson.version}.md"
        out_path = out_dir / filename

        self.md_exporter.export(lesson, qc_reports=qc_reports, output_path=out_path)
        logger.info(f"Exported Markdown: {out_path}")
        return out_path

    def export_pdf(
        self,
        target: Union[str, LessonPlan],
        version: Optional[int] = None,
        output_dir: Optional[Union[Path, str]] = None,
    ) -> Path:
        """Export the selected lesson version as a styled PDF."""
        lesson, qc_reports = self._resolve_lesson_and_reports(target, version=version)
        out_dir = Path(output_dir) if output_dir else self.config.EXPORTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{lesson.lesson_id}_v{lesson.version}.pdf"
        out_path = out_dir / filename

        self.pdf_exporter.export(lesson, qc_reports=qc_reports, output_path=out_path)
        logger.info(f"Exported PDF: {out_path}")
        return out_path

    def export_lesson(
        self,
        target: Union[str, LessonPlan],
        format: str = "all",
        version: Optional[int] = None,
        output_dir: Optional[Union[Path, str]] = None,
    ) -> Dict[str, Path]:
        """
        Export a lesson plan in requested formats ('markdown', 'pdf', or 'all').
        Returns dictionary of format -> generated Path.
        """
        fmt = format.lower().strip()
        results: Dict[str, Path] = {}

        if fmt in ("markdown", "md", "all"):
            results["markdown"] = self.export_markdown(target, version=version, output_dir=output_dir)

        if fmt in ("pdf", "all"):
            results["pdf"] = self.export_pdf(target, version=version, output_dir=output_dir)

        if not results:
            raise ExportError(f"Unsupported export format '{format}'. Supported formats: 'markdown', 'pdf', 'all'.")

        return results
