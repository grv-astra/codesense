#!/usr/bin/env python3
"""Render the Bank Deployment Dossier Markdown into a professional PDF (ReportLab).

Usage:
  python render_dossier_pdf.py --input docs/Code_Sense_Bank_Deployment_Dossier.md \
                               --output Code_Sense_Bank_Deployment_Dossier_v1.4.pdf \
                               --version v1.4

Tailored to the dossier's Markdown subset: ATX headings (##, ###), pipe tables,
bullet/numbered lists, blockquotes, fenced code, ``---`` rules, **bold**, `code`.
"""
import argparse
import html
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
    Preformatted, HRFlowable, PageBreak, KeepTogether,
)

NAVY = colors.HexColor("#1F2A44")
SLATE = colors.HexColor("#2D2D2D")
ACCENT = colors.HexColor("#BF0000")
LIGHT = colors.HexColor("#F2F3F5")
ZEBRA = colors.HexColor("#F7F8FA")
BORDER = colors.HexColor("#C8CDD6")

# Map non-WinAnsi glyphs to safe equivalents so they don't render as black boxes.
_GLYPHS = {
    "→": "->", "←": "<-", "▶": ">", "◀": "<", "≥": ">=", "≤": "<=", "✓": "Yes",
    "─": "-", "│": "|", "┌": "+", "┐": "+", "└": "+", "┘": "+",
    "├": "+", "┤": "+", "┬": "+", "┴": "+", "┼": "+",
}
_GLYPH_TABLE = {ord(k): v for k, v in _GLYPHS.items()}


def winansi(s: str) -> str:
    s = s.translate(_GLYPH_TABLE)
    # Drop anything still outside WinAnsi so ReportLab's base fonts never box.
    return s.encode("cp1252", "replace").decode("cp1252")


def inline(s: str) -> str:
    s = winansi(s)
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`([^`]+?)`", r'<font face="Courier" size=8>\1</font>', s)
    return s


def styles():
    ss = getSampleStyleSheet()
    out = {
        "title": ParagraphStyle("dTitle", parent=ss["Title"], fontSize=26, leading=30,
                                textColor=SLATE, spaceAfter=6),
        "subtitle": ParagraphStyle("dSub", parent=ss["Normal"], fontSize=13, leading=17,
                                   textColor=ACCENT, spaceAfter=2),
        "h1": ParagraphStyle("dH1", parent=ss["Heading1"], fontSize=15, leading=19,
                             textColor=NAVY, spaceBefore=16, spaceAfter=6),
        "h2": ParagraphStyle("dH2", parent=ss["Heading2"], fontSize=11.5, leading=15,
                             textColor=SLATE, spaceBefore=10, spaceAfter=4),
        "body": ParagraphStyle("dBody", parent=ss["Normal"], fontSize=9.5, leading=13.5,
                               spaceAfter=5),
        "bullet": ParagraphStyle("dBullet", parent=ss["Normal"], fontSize=9.5, leading=13.5,
                                 leftIndent=14, bulletIndent=2, spaceAfter=2),
        "note": ParagraphStyle("dNote", parent=ss["Normal"], fontSize=9, leading=13,
                               textColor=SLATE, backColor=colors.HexColor("#FFF6E6"),
                               borderColor=colors.HexColor("#E6C200"), borderWidth=0.6,
                               borderPadding=6, spaceBefore=4, spaceAfter=8),
        "th": ParagraphStyle("dTh", parent=ss["Normal"], fontSize=8.5, leading=11,
                             textColor=colors.white, fontName="Helvetica-Bold"),
        "td": ParagraphStyle("dTd", parent=ss["Normal"], fontSize=8.5, leading=11),
        "code": ParagraphStyle("dCode", parent=ss["Code"], fontSize=7.8, leading=9.6,
                               backColor=LIGHT, borderColor=BORDER, borderWidth=0.5,
                               borderPadding=6, textColor=SLATE),
        "meta": ParagraphStyle("dMeta", parent=ss["Normal"], fontSize=10.5, leading=16),
    }
    return out


def col_widths(ncols, avail):
    if ncols == 2:
        return [avail * 0.30, avail * 0.70]
    if ncols == 3:
        return [avail * 0.40, avail * 0.22, avail * 0.38]
    return [avail / ncols] * ncols


def build_table(rows, st, avail):
    header, body = rows[0], rows[1:]
    data = [[Paragraph(inline(c), st["th"]) for c in header]]
    for r in body:
        data.append([Paragraph(inline(c), st["td"]) for c in r])
    t = Table(data, colWidths=col_widths(len(header), avail), repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), SLATE),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    t.setStyle(TableStyle(style))
    return t


def parse_body(lines, st, avail):
    flow = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # fenced code
        if stripped.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(winansi(lines[i].rstrip("\n")))
                i += 1
            i += 1  # closing fence
            flow.append(Preformatted("\n".join(buf), st["code"]))
            flow.append(Spacer(1, 4))
            continue

        # table block
        if stripped.startswith("|"):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            rows = []
            for b in block:
                cells = [c.strip() for c in b.strip("|").split("|")]
                if all(set(c) <= set("-: ") and c for c in cells):
                    continue  # separator row
                rows.append(cells)
            if rows:
                flow.append(build_table(rows, st, avail))
                flow.append(Spacer(1, 8))
            continue

        if stripped.startswith("### "):
            flow.append(Paragraph(inline(stripped[4:]), st["h2"]))
        elif stripped.startswith("## "):
            flow.append(Paragraph(inline(stripped[3:]), st["h1"]))
        elif stripped.startswith("# "):
            flow.append(Paragraph(inline(stripped[2:]), st["h1"]))
        elif stripped.startswith(">"):
            flow.append(Paragraph(inline(stripped.lstrip("> ").strip()), st["note"]))
        elif stripped == "---":
            flow.append(Spacer(1, 2))
            flow.append(HRFlowable(width="100%", thickness=0.6, color=BORDER))
            flow.append(Spacer(1, 4))
        elif re.match(r"^[-*]\s+", stripped):
            flow.append(Paragraph(inline(re.sub(r"^[-*]\s+", "", stripped)),
                                  st["bullet"], bulletText="•"))
        elif re.match(r"^\d+\.\s+", stripped):
            num = re.match(r"^(\d+)\.", stripped).group(1)
            flow.append(Paragraph(inline(re.sub(r"^\d+\.\s+", "", stripped)),
                                  st["bullet"], bulletText=f"{num}."))
        else:
            flow.append(Paragraph(inline(stripped), st["body"]))
        i += 1
    return flow


def title_page(st, version):
    el = [Spacer(1, 5 * cm)]
    el.append(Paragraph("Code Sense", st["title"]))
    el.append(Paragraph("Deployment &amp; Security Dossier", st["subtitle"]))
    el.append(Paragraph("Offline AI Code-Review &amp; SBOM Scanner (Desktop)", st["subtitle"]))
    el.append(Spacer(1, 0.3 * cm))
    el.append(HRFlowable(width="40%", thickness=2, color=ACCENT, hAlign="LEFT"))
    el.append(Spacer(1, 1.6 * cm))
    meta = [
        f"<b>Document version:</b> {version}",
        "<b>Date:</b> 2026-05-28",
        "<b>Classification:</b> Confidential",
        "<b>Prepared for:</b> Bank Information Security / Vendor Risk / Endpoint Engineering",
        "<b>Deployment model:</b> Single self-contained Windows desktop application, fully offline",
    ]
    for m in meta:
        el.append(Paragraph(m, st["meta"]))
    el.append(Spacer(1, 1.0 * cm))
    el.append(Paragraph(
        "<i>This document contains the product Bill of Materials, security posture, data-handling "
        "model, and risk register for review prior to endpoint deployment. Items marked "
        "<b>[VERIFY]</b> require vendor confirmation before sign-off.</i>", st["note"]))
    el.append(PageBreak())
    return el


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--version", default="v1.4")
    args = ap.parse_args()

    st = styles()
    text = open(args.input, encoding="utf-8").read()
    lines = text.splitlines()
    # Body starts at the first numbered section heading.
    start = next((idx for idx, l in enumerate(lines) if l.strip().startswith("## 1.")), 0)
    body_lines = lines[start:]

    margin = 2 * cm
    avail = A4[0] - 2 * margin

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(margin, 1.1 * cm, "Code Sense - Deployment & Security Dossier")
        canvas.drawRightString(A4[0] - margin, 1.1 * cm,
                               f"{args.version}  -  Confidential  -  Page {canvas.getPageNumber()}")
        canvas.setStrokeColor(BORDER)
        canvas.line(margin, 1.4 * cm, A4[0] - margin, 1.4 * cm)
        canvas.restoreState()

    doc = BaseDocTemplate(args.output, pagesize=A4, topMargin=margin, bottomMargin=1.7 * cm,
                          leftMargin=margin, rightMargin=margin,
                          title="Code Sense - Deployment & Security Dossier",
                          author="Astra / Code Sense")
    frame = Frame(margin, 1.7 * cm, avail, A4[1] - margin - 1.7 * cm, id="main")
    doc.addPageTemplates([PageTemplate(id="content", frames=[frame], onPage=footer)])

    story = title_page(st, args.version) + parse_body(body_lines, st, avail)
    doc.build(story)
    print(f"PDF written: {args.output}")


if __name__ == "__main__":
    main()
