from __future__ import annotations

import io
from html import escape
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from interviewsim.challenge import CHALLENGE_TITLE


def _plain(value: Any) -> str:
    normalized = str(value or "")
    normalized = "".join(char if char in "\n\t" or ord(char) >= 32 else " " for char in normalized)
    return normalized.encode("latin-1", errors="replace").decode("latin-1")


def _paragraph(value: Any, style: ParagraphStyle) -> Paragraph:
    safe = escape(_plain(value)).replace("\n", "<br/>")
    return Paragraph(safe, style)


def create_scorecard_pdf(scorecard: dict[str, Any], candidate_name: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title="InterviewSim scorecard",
        author="InterviewSim",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("InterviewTitle", parent=styles["Title"], alignment=TA_LEFT, textColor=colors.HexColor("#245e48"), spaceAfter=5)
    body = ParagraphStyle("InterviewBody", parent=styles["BodyText"], fontSize=9, leading=13, textColor=colors.HexColor("#35433b"), spaceAfter=6)
    small = ParagraphStyle("InterviewSmall", parent=body, fontSize=8, leading=11, textColor=colors.HexColor("#68746d"))
    heading = ParagraphStyle("InterviewHeading", parent=styles["Heading2"], fontSize=12, leading=15, textColor=colors.HexColor("#17211d"), spaceBefore=12, spaceAfter=7)

    technical = scorecard.get("technical", {})
    overall = scorecard.get("overall_percent")
    overall_label = f"{overall}%" if overall is not None else "Unavailable"
    story = [
        _paragraph("InterviewSim - Scorecard", title),
        _paragraph(CHALLENGE_TITLE, heading),
        _paragraph(f"Candidate: {candidate_name} | Completed: {scorecard.get('completed_at', '-')}", small),
        _paragraph(f"Overall score: {overall_label} | Hidden cases: {technical.get('passed', 0)}/{technical.get('total', 0)}", body),
        Spacer(1, 4),
        _paragraph("Summary", heading),
        _paragraph(scorecard.get("summary", "Evaluation complete."), body),
    ]

    story.append(_paragraph("Automated evaluation", heading))
    cases = technical.get("cases", [])
    if cases:
        rows = [[_paragraph("Case", small), _paragraph("Result", small)]]
        for case in cases:
            rows.append([_paragraph(case.get("name", "Case"), body), _paragraph("PASS" if case.get("passed") else "REVIEW", body)])
        table = Table(rows, colWidths=[5.7 * inch, 1.0 * inch], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5efe8")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#245e48")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#cad8ce")),
            ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#e2e4de")),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
    else:
        story.append(_paragraph(technical.get("error") or "No evaluator cases completed.", body))

    review = scorecard.get("interview_review", {})
    dimensions = review.get("dimensions", {})
    if dimensions:
        story.append(_paragraph("Interview rubric", heading))
        for key, item in dimensions.items():
            story.append(_paragraph(f"{key.replace('_', ' ').title()} - {item.get('score', '-')}/4", body))
            story.append(_paragraph(f"{item.get('feedback', '')} Evidence: {item.get('evidence', '')}", small))
    elif review.get("note"):
        story.append(_paragraph("Interview rubric", heading))
        story.append(_paragraph(review["note"], body))

    next_steps = scorecard.get("next_steps", [])
    if next_steps:
        story.append(_paragraph("Next steps", heading))
        for step in next_steps:
            story.append(_paragraph(f"- {step}", body))
    story.extend([Spacer(1, 12), _paragraph("Private report for the candidate. Share only with their consent.", small)])

    doc.build(story)
    return buffer.getvalue()
