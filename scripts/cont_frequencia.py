from pathlib import Path
import os
ROOT = Path(__file__).resolve().parent.parent
TABELAS = ROOT / 'outputs_json' / 'tabelas'
RELATORIOS = ROOT / 'outputs_json' / 'relatorios'
MODELOS = ROOT / 'outputs_json' / 'modelos'

"""
GERADOR DE RELATÓRIO EM PDF SEPARADO POR ASSUNTO PARA O ORIENTADOR
Varre a base de dados, calcula a frequência dos movimentos de forma isolada
para cada um dos 3 assuntos e gera um PDF limpo e organizado.
"""
from collections import Counter
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

# Carrega a base de dados
df = pd.read_csv(TABELAS / "tabela_posicao_tempo_processos.csv")

# Lista dos 3 assuntos alvo
ASSUNTOS_ALVO = [
    
    "Multas e demais Sanções"

]

def assunto_bate(assunto):
    if pd.isna(assunto):
        return None
    assunto_lower = str(assunto).strip().lower()
    for alvo in ASSUNTOS_ALVO:
        if alvo.lower() in assunto_lower:
            return alvo
    return None

df["assunto_alvo"] = df["assunto"].apply(assunto_bate)
coluna_mov = "movimento_atual"

# Configura o PDF
pdf_path = str(RELATORIOS / "relatorio_movimentos_por_assunto.pdf")
doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    'TitleStyle', parent=styles['Heading1'],
    fontName='Helvetica-Bold', fontSize=13,
    textColor=colors.HexColor('#1a365d'), spaceAfter=6
)

subtitle_style = ParagraphStyle(
    'SubTitleStyle', parent=styles['Normal'],
    fontName='Helvetica', fontSize=9,
    textColor=colors.HexColor('#4a5568'), spaceAfter=10
)

cell_style = ParagraphStyle(
    'Cell', parent=styles['Normal'],
    fontName='Helvetica', fontSize=8, leading=10,
    textColor=colors.HexColor('#2d3748')
)

header_style = ParagraphStyle(
    'HeaderCell', parent=styles['Normal'],
    fontName='Helvetica-Bold', fontSize=9, leading=11,
    textColor=colors.white
)

elements = []

for idx, assunto_escolhido in enumerate(ASSUNTOS_ALVO):
    df_assunto = df[df["assunto_alvo"] == assunto_escolhido].copy()
    df_assunto = df_assunto.dropna(subset=[coluna_mov])
    df_assunto[coluna_mov] = df_assunto[coluna_mov].astype(str).str.strip()
    
    total_registros = len(df_assunto)
    contagem = Counter(df_assunto[coluna_mov])
    
    elements.append(Paragraph(f"Assunto: {assunto_escolhido}", title_style))
    elements.append(Paragraph(f"<b>Total de registros analisados neste assunto:</b> {total_registros}", subtitle_style))
    
    table_data = [[Paragraph("Movimento / Andamento", header_style), 
                   Paragraph("Frequência Absoluta", header_style), 
                   Paragraph("Percentual (%)", header_style)]]
    
    for mov, freq in contagem.most_common():
        pct = (freq / total_registros) * 100 if total_registros > 0 else 0
        table_data.append([
            Paragraph(mov, cell_style), 
            Paragraph(str(freq), cell_style), 
            Paragraph(f"{pct:.2f}%", cell_style)
        ])
        
    t = Table(table_data, colWidths=[300, 100, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2b6cb0')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,0), 5),
        ('TOPPADDING', (0,0), (-1,0), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f7fafc')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    
    elements.append(t)
    
    # Adiciona quebra de página entre os assuntos (exceto no último)
    if idx < len(ASSUNTOS_ALVO) - 1:
        elements.append(PageBreak())

doc.build(elements)
print("PDF separado por assunto gerado com sucesso!")
