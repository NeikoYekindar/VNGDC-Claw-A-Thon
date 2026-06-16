from __future__ import annotations

from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from infra_log_sentinel.analysis.runbook import recommend_commands
from infra_log_sentinel.models import LogEvent


SEVERITY_ORDER = {"critical": 0, "error": 1, "warning": 2, "info": 3}
SEVERITY_COLORS = {
    "critical": colors.HexColor("#B91C1C"),
    "error": colors.HexColor("#DC2626"),
    "warning": colors.HexColor("#D97706"),
    "info": colors.HexColor("#2563EB"),
}
DOMAIN_COLORS = {
    "network": colors.HexColor("#0F766E"),
    "linux": colors.HexColor("#4F46E5"),
    "windows": colors.HexColor("#0369A1"),
    "vmware": colors.HexColor("#7C3AED"),
}
INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#6B7280")
LINE = colors.HexColor("#D1D5DB")
SURFACE = colors.HexColor("#F8FAFC")
HEADER = colors.HexColor("#0F172A")


def build_pdf_report(
    events: list[LogEvent],
    output_dir: Path,
    alert_levels: tuple[str, ...],
    generated_at: datetime | None = None,
    report_window_label: str | None = None,
) -> Path:
    generated_at = generated_at or datetime.now()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"infra-log-sentinel-report-{generated_at:%Y%m%d-%H%M%S}.pdf"

    doc = SimpleDocTemplate(
        str(report_path),
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="Infrastructure Log Sentinel Report",
    )

    styles = _styles()
    severity_counts = Counter(event.severity for event in events)
    domain_counts = Counter(event.domain for event in events)
    alert_events = _alert_events(events, alert_levels)
    critical_count = severity_counts.get("critical", 0)

    story = [
        _hero(generated_at, styles, report_window_label=report_window_label),
        Spacer(1, 8),
        _kpi_cards(
            [
                ("Total Events", len(events), "#1F2937"),
                ("Alert Events", len(alert_events), "#7C2D12"),
                ("Critical", critical_count, "#B91C1C"),
                ("Domains", len(domain_counts), "#0F766E"),
            ],
            styles,
        ),
        Spacer(1, 10),
        _section_title("Visual Summary", styles),
        _two_column(
            _bar_chart("Severity Distribution", [(key, severity_counts.get(key, 0)) for key in ["critical", "error", "warning", "info"]], SEVERITY_COLORS, styles),
            _bar_chart("Domain Distribution", sorted(domain_counts.items()), DOMAIN_COLORS, styles),
        ),
        Spacer(1, 10),
        _section_title("Top Findings", styles),
        _top_findings(alert_events, styles),
        Spacer(1, 10),
        _section_title("Alert Inventory", styles),
        _event_table(alert_events, styles) if alert_events else Paragraph("No warning, error, or critical events were detected.", styles["Body"]),
    ]

    if alert_events:
        story.extend([PageBreak(), _section_title("Action Plan", styles)])
        for index, event in enumerate(alert_events, start=1):
            story.append(KeepTogether(_event_detail(index, event, styles)))

    doc.build(story, onFirstPage=_decorate_page, onLaterPages=_decorate_page)
    return report_path


def _alert_events(events: list[LogEvent], alert_levels: tuple[str, ...]) -> list[LogEvent]:
    alert_set = set(alert_levels)
    return sorted(
        [event for event in events if event.severity in alert_set],
        key=lambda event: (SEVERITY_ORDER.get(event.severity, 99), event.domain, event.source),
    )


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=21,
            leading=25,
            textColor=colors.white,
            alignment=0,
        ),
        "Subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#E5E7EB"),
        ),
        "Section": ParagraphStyle(
            "ReportSection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=INK,
            spaceBefore=4,
            spaceAfter=6,
        ),
        "Body": ParagraphStyle(
            "ReportBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=INK,
        ),
        "Small": ParagraphStyle(
            "ReportSmall",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.3,
            leading=9,
            textColor=MUTED,
        ),
        "SmallBold": ParagraphStyle(
            "ReportSmallBold",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.3,
            leading=9,
            textColor=INK,
        ),
        "Mono": ParagraphStyle(
            "ReportMono",
            parent=base["BodyText"],
            fontName="Courier",
            fontSize=6.7,
            leading=8.5,
            textColor=colors.HexColor("#0F172A"),
        ),
    }


def _hero(generated_at: datetime, styles: dict[str, ParagraphStyle], report_window_label: str | None) -> Table:
    window_text = report_window_label or "Scope: current parsed dataset"
    body = [
        [
            Paragraph("Infrastructure Log Sentinel", styles["Title"]),
            Paragraph("Daily infrastructure log intelligence report", styles["Subtitle"]),
        ],
        [
            Paragraph(f"{escape(window_text)} | Network | Windows | Linux | VMware", styles["Subtitle"]),
            Paragraph(f"Generated: {generated_at:%Y-%m-%d %H:%M:%S}", styles["Subtitle"]),
        ],
    ]
    table = Table(body, colWidths=[112 * mm, 58 * mm], rowHeights=[18 * mm, 10 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HEADER),
                ("SPAN", (0, 0), (0, 0)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _kpi_cards(cards: list[tuple[str, int, str]], styles: dict[str, ParagraphStyle]) -> Table:
    row = []
    for label, value, color in cards:
        row.append(
            [
                Paragraph(str(value), ParagraphStyle("KpiValue", parent=styles["Section"], fontSize=18, leading=20, textColor=colors.HexColor(color))),
                Paragraph(label, styles["SmallBold"]),
            ]
        )
    table = Table([row], colWidths=[42.5 * mm] * len(cards))
    style_commands = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    table.setStyle(TableStyle(style_commands))
    return table


def _section_title(title: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(title, styles["Section"])


def _two_column(left, right) -> Table:
    table = Table([[left, right]], colWidths=[84 * mm, 84 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _bar_chart(
    title: str,
    rows: list[tuple[str, int]],
    palette: dict[str, colors.Color],
    styles: dict[str, ParagraphStyle],
) -> Table:
    max_value = max([value for _, value in rows] or [1])
    table_rows = [[Paragraph(title, styles["SmallBold"]), "", ""]]
    for label, value in rows:
        color = palette.get(label, colors.HexColor("#64748B"))
        table_rows.append(
            [
                Paragraph(label.upper(), styles["Small"]),
                Paragraph(str(value), styles["SmallBold"]),
                _bar(value=value, max_value=max_value, color=color),
            ]
        )

    table = Table(table_rows, colWidths=[26 * mm, 10 * mm, 42 * mm])
    table.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (-1, 0)),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.4, LINE),
                ("LINEBELOW", (0, 0), (-1, 0), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _bar(value: int, max_value: int, color: colors.Color) -> Drawing:
    width = 40 * mm
    height = 5 * mm
    filled = 0 if max_value <= 0 else max(1.2 * mm, width * (value / max_value)) if value else 0
    drawing = Drawing(width, height)
    drawing.add(Rect(0, 1, width, height - 2, fillColor=colors.HexColor("#E5E7EB"), strokeColor=None))
    if filled:
        drawing.add(Rect(0, 1, filled, height - 2, fillColor=color, strokeColor=None))
    return drawing


def _top_findings(events: list[LogEvent], styles: dict[str, ParagraphStyle]) -> Table:
    top_events = events[:5]
    if not top_events:
        top_events = []
    rows = [["Priority", "Finding", "Impact"]]
    for index, event in enumerate(top_events, start=1):
        rows.append(
            [
                Paragraph(f"{index}. {event.severity.upper()}", styles["SmallBold"]),
                Paragraph(f"{escape(event.domain)}/{escape(event.source)} - {escape(event.event_type)}<br/>{escape(_trim(event.message, 130))}", styles["Small"]),
                Paragraph(escape(_trim(event.impact, 110)), styles["Small"]),
            ]
        )

    if len(rows) == 1:
        rows.append(["-", Paragraph("No alert findings.", styles["Small"]), "-"])

    table = Table(rows, colWidths=[25 * mm, 88 * mm, 57 * mm], repeatRows=1)
    table.setStyle(_table_style(header_color=HEADER))
    return table


def _event_table(events: list[LogEvent], styles: dict[str, ParagraphStyle]) -> Table:
    rows = [["Severity", "Domain", "Source", "Type", "Message"]]
    for event in events:
        rows.append(
            [
                Paragraph(event.severity.upper(), styles["SmallBold"]),
                Paragraph(escape(event.domain), styles["Small"]),
                Paragraph(escape(event.source), styles["Small"]),
                Paragraph(escape(event.event_type), styles["Small"]),
                Paragraph(escape(_trim(event.message, 150)), styles["Small"]),
            ]
        )

    table = Table(rows, repeatRows=1, colWidths=[20 * mm, 21 * mm, 33 * mm, 35 * mm, 61 * mm])
    style = _table_style(header_color=HEADER)
    for row_index, event in enumerate(events, start=1):
        style.add("BACKGROUND", (0, row_index), (0, row_index), _severity_tint(event.severity))
        style.add("TEXTCOLOR", (0, row_index), (0, row_index), colors.white if event.severity in {"critical", "error"} else INK)
    table.setStyle(style)
    return table


def _event_detail(index: int, event: LogEvent, styles: dict[str, ParagraphStyle]) -> list:
    commands = recommend_commands(event)
    detail = [
        Paragraph(
            f"{index}. [{escape(event.severity.upper())}] {escape(event.domain)}/{escape(event.source)} - {escape(event.event_type)}",
            styles["Section"],
        ),
        _detail_table(
            [
                ("Timestamp", event.timestamp),
                ("Message", event.message),
                ("Probable Cause", event.probable_cause),
                ("Impact", event.impact),
                ("Recommended Action", event.recommended_action),
            ],
            styles,
        ),
        Spacer(1, 5),
        _command_table(commands, styles),
        Spacer(1, 8),
    ]
    return detail


def _detail_table(rows: list[tuple[str, str]], styles: dict[str, ParagraphStyle]) -> Table:
    table_rows = [
        [Paragraph(label, styles["SmallBold"]), Paragraph(escape(value), styles["Small"])]
        for label, value in rows
    ]
    table = Table(table_rows, colWidths=[34 * mm, 136 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, LINE),
                ("BACKGROUND", (0, 0), (0, -1), SURFACE),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _command_table(commands, styles: dict[str, ParagraphStyle]) -> Table:
    rows = [["Phase", "Command", "Why"]]
    for item in commands[:5]:
        rows.append(
            [
                Paragraph(escape(item.phase), styles["SmallBold"]),
                Paragraph(escape(item.command), styles["Mono"]),
                Paragraph(escape(item.purpose), styles["Small"]),
            ]
        )
    table = Table(rows, colWidths=[23 * mm, 92 * mm, 55 * mm], repeatRows=1)
    table.setStyle(_table_style(header_color=colors.HexColor("#1E293B")))
    return table


def _table_style(header_color: colors.Color) -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), header_color),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.25, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ]
    )


def _severity_tint(severity: str):
    return {
        "critical": colors.HexColor("#B91C1C"),
        "error": colors.HexColor("#F87171"),
        "warning": colors.HexColor("#FBBF24"),
        "info": colors.HexColor("#93C5FD"),
    }.get(severity, colors.HexColor("#CBD5E1"))


def _decorate_page(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(HEADER)
    canvas.rect(0, height - 5 * mm, width, 5 * mm, stroke=0, fill=1)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(12 * mm, 7 * mm, "Infrastructure Log Sentinel Agent")
    canvas.drawRightString(width - 12 * mm, 7 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _trim(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."
