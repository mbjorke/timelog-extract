from __future__ import annotations

from collections import defaultdict
from html import escape as html_escape

PDF_IMPORT_ERROR = (
    "PDF generation requires reportlab. Install with: python3 -m pip install reportlab"
)
PDF_TITLE = "Time report - invoice basis"
PDF_LABEL_PERIOD = "Period"
PDF_LABEL_CUSTOMER = "Customer"
PDF_LABEL_PROJECTS = "Projects"
PDF_LABEL_TOTAL_BILLABLE = "Total billable"
PDF_LABEL_RAW_TIME = "Raw time in period"
PDF_LABEL_TOTAL_ESTIMATED = "Total estimated"
PDF_TABLE_HEADER_SERVICE = "Description of service / deliverable"
PDF_TABLE_HEADER_SCOPE = "Scope"
PDF_FALLBACK_DESCRIPTION = "Ongoing implementation, analysis, and delivery within the project."
PDF_FALLBACK_SOURCE = "local work logs"
PDF_FALLBACK_EXAMPLES = "Ongoing implementation, analysis, and iteration."
PDF_FALLBACK_PROJECT_SUMMARY_TEMPLATE = (
    "Ongoing work in the project, summarized from {source}. "
    "Examples of delivered effort: {examples}"
)
PDF_SUMMARY_ROW = "Total"
PDF_DAILY_DATE = "Date"
PDF_DAILY_HOURS = "Hours"
PDF_DAILY_SPEC = "Daily breakdown"
PDF_DAILY_BILLABLE_NOTE = (
    "Daily hours are raw time; billable amounts in the table above are rounded up per project."
)


def invoice_projects_line(profiles, project_reports, customer_name):
    if project_reports:
        return ", ".join(sorted(project_reports.keys()))
    if customer_name:
        wanted = customer_name.strip().lower()
        names = [
            p["name"]
            for p in profiles
            if str(p.get("customer") or p["name"]).strip().lower() == wanted
        ]
        return ", ".join(sorted(names)) if names else "—"
    return ", ".join(p["name"] for p in profiles)


def build_invoice_pdf(
    overall_days,
    project_reports,
    profiles,
    dt_from,
    dt_to,
    output_path,
    local_tz,
    billable_total_hours_fn,
    empty_note=None,
    customer_name=None,
    billable_unit=0.0,
):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError(PDF_IMPORT_ERROR) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "InvoiceBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    total_raw_hours = sum(day_payload["hours"] for day_payload in overall_days.values())
    if billable_unit and billable_unit > 0:
        invoice_total_billable = sum(
            billable_total_hours_fn(
                sum(day_payload["hours"] for day_payload in project_reports[pn].values()),
                billable_unit,
            )
            for pn in project_reports
        )
    else:
        invoice_total_billable = total_raw_hours
    profile_by_name = {profile["name"]: profile for profile in profiles}
    period_text = f"{dt_from.astimezone(local_tz).date()} to {dt_to.astimezone(local_tz).date()}"
    projects_text = invoice_projects_line(profiles, project_reports, customer_name)

    elements = [
        Paragraph(PDF_TITLE, title_style),
        Paragraph(f"<b>{PDF_LABEL_PERIOD}:</b> {period_text}", body_style),
    ]
    if customer_name:
        elements.append(
            Paragraph(f"<b>{PDF_LABEL_CUSTOMER}:</b> {html_escape(customer_name.strip())}", body_style)
        )
    if billable_unit and billable_unit > 0:
        elements.extend(
            [
                Paragraph(f"<b>{PDF_LABEL_PROJECTS}:</b> {html_escape(projects_text)}", body_style),
                Paragraph(
                    f"<b>{PDF_LABEL_TOTAL_BILLABLE}:</b> {invoice_total_billable:.2f} hours<br/>"
                    f"<i>{PDF_LABEL_RAW_TIME}: {total_raw_hours:.2f} h</i>",
                    body_style,
                ),
            ]
        )
    else:
        elements.extend(
            [
                Paragraph(f"<b>{PDF_LABEL_PROJECTS}:</b> {html_escape(projects_text)}", body_style),
                Paragraph(f"<b>{PDF_LABEL_TOTAL_ESTIMATED}:</b> {total_raw_hours:.2f} hours", body_style),
            ]
        )
    if empty_note:
        elements.append(Paragraph(f"<i>{html_escape(empty_note)}</i>", body_style))
    elements.append(Spacer(1, 16))

    project_rows = [[
        Paragraph(f"<b>{PDF_TABLE_HEADER_SERVICE}</b>", body_style),
        Paragraph(f"<b>{PDF_TABLE_HEADER_SCOPE}</b>", body_style),
    ]]
    for project_name in sorted(project_reports):
        day_payloads = project_reports[project_name]
        hours = sum(day_payload["hours"] for day_payload in day_payloads.values())
        if hours <= 0:
            continue
        display_hours = billable_total_hours_fn(hours, billable_unit)
        profile = profile_by_name.get(project_name, {})
        invoice_title = str(profile.get("invoice_title", "")).strip()
        invoice_description = str(profile.get("invoice_description", "")).strip()

        if invoice_title or invoice_description:
            safe_title = html_escape(invoice_title or project_name)
            safe_description = html_escape(
                invoice_description or PDF_FALLBACK_DESCRIPTION
            )
            desc = f"<b>{safe_title}</b><br/>{safe_description}"
            project_rows.append([Paragraph(desc, body_style), Paragraph(f"{display_hours:.2f} h", body_style)])
            continue

        source_counts = defaultdict(int)
        sample_details = []
        for day_payload in day_payloads.values():
            for event in day_payload.get("entries", []):
                source_counts[event.get("source", "")] += 1
                detail = str(event.get("detail", "")).strip()
                if detail and detail not in sample_details:
                    sample_details.append(detail)
                if len(sample_details) >= 2:
                    break
            if len(sample_details) >= 2:
                break

        top_sources = sorted(source_counts.items(), key=lambda item: item[1], reverse=True)[:3]
        source_part = ", ".join(src for src, _ in top_sources if src) or PDF_FALLBACK_SOURCE
        examples_part = "; ".join(sample_details) if sample_details else PDF_FALLBACK_EXAMPLES
        safe_project_name = html_escape(project_name)
        safe_source_part = html_escape(source_part)
        safe_examples_part = html_escape(examples_part)
        summary_text = PDF_FALLBACK_PROJECT_SUMMARY_TEMPLATE.format(
            source=safe_source_part,
            examples=safe_examples_part,
        )
        desc = f"<b>{safe_project_name}</b><br/>{summary_text}"
        project_rows.append([Paragraph(desc, body_style), Paragraph(f"{display_hours:.2f} h", body_style)])

    project_rows.append(
        [
            Paragraph(f"<b>{PDF_SUMMARY_ROW}</b>", body_style),
            Paragraph(f"<b>{invoice_total_billable:.2f} h</b>", body_style),
        ]
    )
    project_table = Table(project_rows, colWidths=[4.8 * inch, 1.3 * inch])
    project_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.lightgrey),
                ("LINEABOVE", (0, -1), (-1, -1), 0.9, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(project_table)
    elements.append(Spacer(1, 18))

    daily_rows = [[Paragraph(f"<b>{PDF_DAILY_DATE}</b>", body_style), Paragraph(f"<b>{PDF_DAILY_HOURS}</b>", body_style)]]
    for day in sorted(overall_days):
        daily_rows.append([Paragraph(day, body_style), Paragraph(f"{overall_days[day]['hours']:.2f} h", body_style)])
    daily_table = Table(daily_rows, colWidths=[4.8 * inch, 1.3 * inch])
    daily_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F9FAFB")),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(Paragraph(f"<b>{PDF_DAILY_SPEC}</b>", body_style))
    elements.append(Spacer(1, 8))
    elements.append(daily_table)
    if billable_unit and billable_unit > 0:
        elements.append(Spacer(1, 6))
        elements.append(
            Paragraph(
                f"<i>{PDF_DAILY_BILLABLE_NOTE}</i>",
                body_style,
            )
        )

    doc.build(elements)
    return output_path
