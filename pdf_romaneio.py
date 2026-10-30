"""Emissão de Romaneio de Envio em PDF."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

NAVY = colors.HexColor("#1B4F72")
GOLD = colors.HexColor("#C9A227")
CREAM = colors.HexColor("#F7F3EB")
ROW_ALT = colors.HexColor("#EEF3F8")
MUTED = colors.HexColor("#5D6D7E")

PDF_DIR = Path(__file__).resolve().parent / "pdfs"


def _brl(valor: float) -> str:
    txt = f"{valor:,.2f}"
    return "R$ " + txt.replace(",", "X").replace(".", ",").replace("X", ".")


def _data_br(iso: str) -> str:
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso


def gerar_pdf_romaneio(remessa: dict[str, Any]) -> bytes:
    cab = remessa["cabecalho"]
    itens = remessa["itens"]
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=f"Romaneio {cab['numero_romaneio']}",
        author="Controle de Produção Têxtil",
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "kicker",
            parent=styles["Normal"],
            fontName="Times-Roman",
            fontSize=9,
            textColor=GOLD,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            "titulo",
            parent=styles["Heading1"],
            fontName="Times-Bold",
            fontSize=20,
            textColor=NAVY,
            alignment=TA_CENTER,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            "sub",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            "meta",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=NAVY,
            alignment=TA_LEFT,
            leading=13,
        )
    )
    styles.add(
        ParagraphStyle(
            "cell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
        )
    )
    styles.add(
        ParagraphStyle(
            "rodape",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=MUTED,
            alignment=TA_CENTER,
        )
    )

    story: list[Any] = []
    story.append(Paragraph("FACÇÃO / CONFECÇÃO TÊXTIL", styles["kicker"]))
    story.append(Paragraph("ROMANEIO DE ENVIO", styles["titulo"]))
    story.append(
        Paragraph(
            "Documento de remessa de peças amarradas — 1ª e 2ª qualidade",
            styles["sub"],
        )
    )

    meta = [
        [
            Paragraph(f"<b>Romaneio:</b> {cab['numero_romaneio']}", styles["meta"]),
            Paragraph(f"<b>Data da remessa:</b> {_data_br(cab['data'])}", styles["meta"]),
            Paragraph(
                f"<b>Emitido em:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                styles["meta"],
            ),
        ]
    ]
    meta_table = Table(meta, colWidths=[60 * mm, 60 * mm, 58 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CREAM),
                ("BOX", (0, 0), (-1, -1), 0.6, NAVY),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 8 * mm))

    header = [
        "OP",
        "Ref.",
        "Cor",
        "Artigo",
        "Tam.",
        "1ª Qual.",
        "2ª Qual.",
        "Total",
        "Pç Unit.",
        "Valor",
    ]
    data = [header]
    tot_1a = tot_2a = tot_pecas = 0
    tot_valor = 0.0

    for item in itens:
        q1 = int(item["qtd_1a"])
        q2 = int(item["qtd_2a"])
        total = q1 + q2
        unit = float(item["preco_unitario"] or 0)
        valor = total * unit
        tot_1a += q1
        tot_2a += q2
        tot_pecas += total
        tot_valor += valor
        data.append(
            [
                str(item["op"]),
                Paragraph(str(item["referencia"]), styles["cell"]),
                Paragraph(str(item["cor"]), styles["cell"]),
                Paragraph(str(item["descricao"]), styles["cell"]),
                str(item["tamanho"]),
                str(q1),
                str(q2),
                str(total),
                _brl(unit),
                _brl(valor),
            ]
        )

    data.append(
        [
            "",
            "",
            "",
            Paragraph("<b>TOTAIS</b>", styles["cell"]),
            "",
            str(tot_1a),
            str(tot_2a),
            str(tot_pecas),
            "",
            _brl(tot_valor),
        ]
    )

    col_w = [16 * mm, 22 * mm, 22 * mm, 38 * mm, 14 * mm, 16 * mm, 16 * mm, 14 * mm, 20 * mm, 20 * mm]
    table = Table(data, colWidths=col_w, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7.5),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (4, 1), (-1, -1), "CENTER"),
        ("ALIGN", (-2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C5D0DA")),
        ("BACKGROUND", (0, -1), (-1, -1), CREAM),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEABOVE", (0, -1), (-1, -1), 1, GOLD),
    ]
    for i in range(1, len(data) - 1):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
    table.setStyle(TableStyle(style_cmds))
    story.append(table)

    if cab.get("observacao"):
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(f"<b>Observações:</b> {cab['observacao']}", styles["meta"]))

    story.append(Spacer(1, 16 * mm))
    assin = Table(
        [
            [
                Paragraph("________________________________", styles["rodape"]),
                Paragraph("________________________________", styles["rodape"]),
            ],
            [
                Paragraph("Conferência / Expedição", styles["rodape"]),
                Paragraph("Recebimento", styles["rodape"]),
            ],
        ],
        colWidths=[89 * mm, 89 * mm],
    )
    assin.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story.append(assin)
    story.append(Spacer(1, 8 * mm))
    story.append(
        Paragraph(
            "Documento gerado pelo sistema de controle de produção e remessa. "
            "Conferir quantidades no ato do carregamento.",
            styles["rodape"],
        )
    )

    def _header_line(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, A4[1] - 6 * mm, A4[0], 6 * mm, fill=1, stroke=0)
        canvas.setFillColor(GOLD)
        canvas.rect(0, A4[1] - 7.2 * mm, A4[0], 1.2 * mm, fill=1, stroke=0)
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, A4[0], 5 * mm, fill=1, stroke=0)
        canvas.restoreState()

    doc.build(story, onFirstPage=_header_line, onLaterPages=_header_line)
    return buffer.getvalue()


def salvar_pdf(remessa: dict[str, Any]) -> Path:
    PDF_DIR.mkdir(exist_ok=True)
    cab = remessa["cabecalho"]
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in cab["numero_romaneio"])
    path = PDF_DIR / f"{safe}_{cab['data']}.pdf"
    path.write_bytes(gerar_pdf_romaneio(remessa))
    return path
