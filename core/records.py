"""Surplus food record in the layout of FSSAI Schedule II.

The Food Safety and Standards (Recovery and Distribution of Surplus Food) Regulations, 2019 ask the
food donor and the surplus food distribution organisation to keep a record with twelve items.
This module fills those twelve items from what was entered in the app and renders a one-page PDF.
It is a convenience copy, not a legal certificate: check the current regulation text and keep a
signed copy.
"""
import html
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.db import now

NOT_RECORDED = "Not recorded"
NOT_YET = "Not yet recorded"


def _dt(value: datetime | None, fallback: str = NOT_YET) -> str:
    return f"{value:%d %b %Y, %H:%M}" if value else fallback


def _org(user, address: str | None, fssai_label: str) -> str:
    parts = [user.display_name]
    if address:
        parts.append(address)
    line = ", ".join(parts)
    extra = []
    if getattr(user, "fssai_number", None):
        extra.append(f"{fssai_label}: {user.fssai_number}")
    if getattr(user, "darpan_id", None):
        extra.append(f"NGO Darpan ID: {user.darpan_id}")
    return line + ("\n" + "; ".join(extra) if extra else "")


def schedule2_rows(listing) -> list[tuple[str, str]]:
    """The twelve items, in the order of the schedule."""
    donor, ngo = listing.donor, listing.ngo
    donation_date = listing.picked_up_at or listing.claimed_at or listing.created_at
    return [
        ("Name and address of the food donor organisation", _org(donor, listing.address, "FSSAI licence or registration")),
        ("Name and address of the surplus food distribution organisation",
         _org(ngo, ngo.address, "FSSAI registration") if ngo is not None else "Not yet claimed"),
        ("Donation date", _dt(donation_date)),
        ("Name of the food product (item)", f"{listing.title} ({listing.category})"),
        ("Batch number of food product (item)", listing.batch_ref or "Not assigned"),
        ("Date of manufacturing (date and time prepared)", _dt(listing.cooked_at)),
        ("Best before date or expiry date", f"{_dt(listing.safe_until)} (planning limit set in SurplusLink)"),
        ("Quantity donated by food donor", f"{listing.quantity_meals} meals"),
        ("Temperature of food", f"{listing.temperature_c:.1f} degrees C" if listing.temperature_c is not None else NOT_RECORDED),
        ("Quantity distributed by surplus food distribution organisation",
         f"{listing.qty_distributed} meals" if listing.qty_distributed is not None else NOT_YET),
        ("Area where food is distributed", listing.area_distributed or NOT_YET),
        ("Date of distribution", _dt(listing.delivered_at)),
    ]


def _p(text: str, style) -> Paragraph:
    return Paragraph(html.escape(text).replace("\n", "<br/>"), style)


def schedule2_pdf(listing) -> bytes:
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13)
    bold = ParagraphStyle("bold", parent=base, fontName="Helvetica-Bold")
    small = ParagraphStyle("small", parent=base, fontSize=8, leading=11, textColor=colors.HexColor("#555555"))
    title = ParagraphStyle("title", parent=base, fontName="Helvetica-Bold", fontSize=15, leading=19)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                            bottomMargin=1.6 * cm, title=f"Surplus food record {listing.batch_ref or listing.id}")
    story = [
        _p("Record of surplus food", title),
        _p("Laid out in the format of Schedule II, Food Safety and Standards (Recovery and Distribution of Surplus Food) "
           "Regulations, 2019", small),
        Spacer(1, 4),
        _p(f"Record reference: {listing.batch_ref or listing.id}", bold),
        Spacer(1, 10),
    ]
    data = [[_p("No.", bold), _p("Item", bold), _p("Entry", bold)]]
    for i, (label, value) in enumerate(schedule2_rows(listing), 1):
        data.append([_p(str(i), base), _p(label, base), _p(value, base)])
    table = Table(data, colWidths=[1.1 * cm, 6.6 * cm, 9.3 * cm], repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9AA5AB")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8ECEE")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [table, Spacer(1, 26)]

    sign = Table([[_p("Signature of donor representative", small), _p("Signature of distribution organisation representative", small)],
                  [_p("Name and date:", small), _p("Name and date:", small)]],
                 colWidths=[8.5 * cm, 8.5 * cm], rowHeights=[1.6 * cm, 0.7 * cm])
    sign.setStyle(TableStyle([("LINEABOVE", (0, 0), (0, 0), 0.5, colors.black), ("LINEABOVE", (1, 0), (1, 0), 0.5, colors.black),
                              ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [sign, Spacer(1, 18),
              _p(f"Prepared by SurplusLink on {now():%d %b %Y, %H:%M} from information entered by the donor and the NGO. "
                 "The expiry entry is a planning limit used by this tool, not a figure set by the regulation. "
                 "This sheet does not replace the regulation or legal advice. Please keep a signed copy.", small)]
    doc.build(story)
    return buf.getvalue()
