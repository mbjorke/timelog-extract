from __future__ import annotations

from collections import defaultdict
from html import escape as html_escape


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
        raise RuntimeError(
            "PDF-generering kraver reportlab. Installera med: python3 -m pip install reportlab"
        ) from exc

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
    period_text = f"{dt_from.astimezone(local_tz).date()} till {dt_to.astimezone(local_tz).date()}"
    projects_text = invoice_projects_line(profiles, project_reports, customer_name)

    elements = [
        Paragraph("Tidrapport - fakturaunderlag", title_style),
        Paragraph(f"<b>Period:</b> {period_text}", body_style),
    ]
    if customer_name:
        elements.append(Paragraph(f"<b>Kund:</b> {html_escape(customer_name.strip())}", body_style))
    if billable_unit and billable_unit > 0:
        elements.extend(
            [
                Paragraph(f"<b>Projekt:</b> {html_escape(projects_text)}", body_style),
                Paragraph(
                    f"<b>Totalt fakturerbart:</b> {invoice_total_billable:.2f} timmar<br/>"
                    f"<i>Råtid under perioden: {total_raw_hours:.2f} h</i>",
                    body_style,
                ),
            ]
        )
    else:
        elements.extend(
            [
                Paragraph(f"<b>Projekt:</b> {html_escape(projects_text)}", body_style),
                Paragraph(f"<b>Totalt estimerat:</b> {total_raw_hours:.2f} timmar", body_style),
            ]
        )
    if empty_note:
        elements.append(Paragraph(f"<i>{html_escape(empty_note)}</i>", body_style))
    elements.append(Spacer(1, 16))

    project_rows = [[
        Paragraph("<b>Beskrivning av tjänst / Leverabel</b>", body_style),
        Paragraph("<b>Omfattning</b>", body_style),
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
                invoice_description or "Löpande implementation, analys och leverans inom projektet."
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
        source_part = ", ".join(src for src, _ in top_sources if src) or "lokala arbetsloggar"
        examples_part = "; ".join(sample_details) if sample_details else "Löpande implementation, analys och iteration."
        safe_project_name = html_escape(project_name)
        safe_source_part = html_escape(source_part)
        safe_examples_part = html_escape(examples_part)
        desc = (
            f"<b>{safe_project_name}</b><br/>"
            f"Löpande arbete inom projektet, sammanställt från {safe_source_part}. "
            f"Exempel på utförda insatser: {safe_examples_part}"
        )
        project_rows.append([Paragraph(desc, body_style), Paragraph(f"{display_hours:.2f} h", body_style)])

    project_rows.append(
        [
            Paragraph("<b>Summa</b>", body_style),
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

    daily_rows = [[Paragraph("<b>Datum</b>", body_style), Paragraph("<b>Timmar</b>", body_style)]]
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
    elements.append(Paragraph("<b>Daglig specifikation</b>", body_style))
    elements.append(Spacer(1, 8))
    elements.append(daily_table)
    if billable_unit and billable_unit > 0:
        elements.append(Spacer(1, 6))
        elements.append(
            Paragraph(
                "<i>Dagliga timmar är råtid; fakturerbara belopp i tabellen ovan avrundas uppåt per projekt.</i>",
                body_style,
            )
        )

    doc.build(elements)
    return output_path
