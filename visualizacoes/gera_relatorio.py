# -*- coding: utf-8 -*-
"""Gera relatórios (HTML e PDF) com as árvores de rotas por assunto."""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE_DIR, "rotas_por_assunto.json")
IMG_DIR = os.path.join(BASE_DIR, "imagens")
HTML_PATH = os.path.join(BASE_DIR, "relatorio_arvores.html")

ORDER = ["Anulação de Débito Fiscal", "Multas e demais Sanções",
         "Valor da Execução / Cálculo / Atualização"]

NOME_CURTO = {
    "Anulação de Débito Fiscal": "Anulação de Débito Fiscal",
    "Multas e demais Sanções": "Multas e demais Sanções",
    "Valor da Execução / Cálculo / Atualização": "Valor da Execução",
}

COR_HTML = {
    "Anulação de Débito Fiscal": "#0B5D6B",
    "Multas e demais Sanções": "#B45309",
    "Valor da Execução / Cálculo / Atualização": "#6D28D9",
}

INSIGHTS = {
    "Anulação de Débito Fiscal":
        "Rota de maior extensão: média de 22,9 movimentações (mediana 20). O ingresso é "
        "tripartido — Execução/Cumprimento de Sentença Iniciada (27,2%), Distribuição "
        "(26,4%) e Recebimento (20,3%) — e o trâmite é dominado pelo ciclo cartorário "
        "Remessa → Publicação → Expedição de documento → Petição → Conclusão. Os desfechos "
        "se distribuem principalmente entre Publicação (20,3%), Expedição de documento "
        "(19,9%) e Ato ordinatório (18,0%).",
    "Multas e demais Sanções":
        "Cerca de 41,6% dos processos ingressam por Distribuição. O caminho "
        "representativo é: Distribuição → Expedição de documento + Outras Decisões + "
        "Conclusão → Remessa → Publicação → Expedição de documento (família do caminho "
        "mais frequente, ~7,4%). O desfecho dominante é Expedição de documento (38,6%), "
        "seguido de Petição (16,1%) e Publicação (14,1%). A retenção cai para ~62% na "
        "10ª posição.",
    "Valor da Execução / Cálculo / Atualização":
        "Metade dos processos (50,4%) nasce com Distribuição, em rota mais curta "
        "(média de 12,0 posições; mediana 10). A retenção declina mais rápido "
        "(67,6% na 6ª posição) e os desfechos concentram-se em Ato ordinatório (23,9%), "
        "Publicação (22,5%) e Petição (19,7%) — rotinas de cálculo e atualização.",
}


def slugify(nome):
    trocas = {"ã": "a", "á": "a", "é": "e", "ê": "e", "í": "i", "ó": "o",
              "õ": "o", "ô": "o", "ú": "u", "ç": "c", "/": "-", " ": "-"}
    return "".join(trocas.get(c, c) for c in nome).lower()


def fmt(n):
    return f"{n:,}".replace(",", ".")


def fl(n):
    """Número com vírgula decimal (padrão pt-BR)."""
    return str(n).replace(".", ",")


def porc(x):
    """Percentual formatado no padrão pt-BR."""
    return fl(x) + "%"


def cabecalho_html():
    return """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rotas de movimentação por assunto — DataJud/CNJ</title>
<style>
 body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f4f6f8;color:#1f2937;}
 .wrap{max-width:1080px;margin:0 auto;padding:28px 20px 60px;}
 header{background:linear-gradient(135deg,#0b5d6b,#114c5c 60%,#6d28d9);color:#fff;
        padding:34px 20px 26px;}
 h1{margin:0 0 6px;font-size:26px;}
 p.sub{margin:0;opacity:.92;font-size:14px;}
 h2{font-size:20px;margin:34px 0 10px;border-left:5px solid #0b5d6b;padding-left:10px;}
 .card{background:#fff;border:1px solid #e2e8ee;border-radius:10px;
       padding:18px 20px;margin:14px 0;}
 .grid{display:flex;gap:14px;flex-wrap:wrap;}
 .stat{flex:1 1 160px;background:#fff;border-radius:10px;padding:14px 16px;
       border:1px solid #e2e8ee;}
 .stat b{font-size:26px;display:block;color:#0b5d6b;}
 .stat span{font-size:13px;color:#475569;}
 table{border-collapse:collapse;width:100%;font-size:12.5px;margin:10px 0;}
 th,td{border:1px solid #dee4ea;padding:6px 9px;text-align:left;vertical-align:top;}
 th{background:#eef2f7;color:#334155;}
 tr:nth-child(even) td{background:#fafbfc;}
 img.tree{display:block;max-width:100%;border:1px solid #e2e8ee;
          border-radius:8px;margin:8px 0;}
 .ley{font-size:12px;color:#64748b;margin-top:4px;}
 footer{margin-top:40px;padding-top:16px;border-top:1px solid #e2e8ee;
        font-size:12px;color:#64748b;}
</style>
</head><body>
<header><div class="wrap">
  <h1>Rotas de Movimentação Processual — Análise por Assunto</h1>
  <p class="sub">Árvore de fluxo real extraída de <b>tabela_posicao_tempo_processos.csv</b>
  (base DataJud/CNJ) — sequências ponta a ponta com percentuais observados.</p>
</div></header>
<div class="wrap">
  <h2 style="border-left-color:#6d28d9">1. Metodologia</h2>
  <div class="card">
    <p>Para cada processo (<i>num_processo</i>) de cada assunto, extraiu-se a sequência
    ordenada de movimentações (posição 1 a N). Cada nó da árvore representa um
    <i>movimento</i> observado em uma <i>posição</i>; o percentual indicado é a fração
    do total de processos do assunto que percorreu aquele caminho. As arestas contínuas
    ligam movimentos consecutivos realmente observados; as linhas tracejadas ligam a
    última posição exibida aos desfechos mais comuns.</p>
    <p class="ley">Observação: movimentos compostos (ex.: “Expedição de documento + Outras
    Decisões + Conclusão”) foram mantidos conforme a base; variações raras foram omitidas
    da árvore para legibilidade.</p>
  </div>
  <h2 style="border-left-color:#b45309">2. Resumo comparativo</h2>
  <div class="card"><table>
    <tr><th>Assunto</th><th>Processos</th><th>Média de posições</th><th>Mediana</th>
        <th>Desfecho mais frequente</th></tr>"""
def build_html(res):
    out = [cabecalho_html()]

    for ass in ORDER:
        d = res[ass]
        if d["ultimo_movimento"]:
            mov_top, cnt = next(iter(d["ultimo_movimento"].items()))
            topo = f"{mov_top[:46]} ({porc(100*cnt/d['n_processos'])})"[:80]
        else:
            topo = "-"
        out.append(f'<tr><td><b>{ass}</b></td><td>{fmt(d["n_processos"])}</td>'
                   f'<td>{fl(d["media_posicoes"])}</td><td>{fl(d["mediana_posicoes"])}</td>'
                   f'<td>{topo}</td></tr>')
    out.append("</table></div>")

    for ass in ORDER:
        d = res[ass]
        cor = COR_HTML[ass]
        n = d["n_processos"]
        arq = "imagens/arvore_" + slugify(ass) + ".png"
        cob_des = sum(c for _, c in d["ultimo_movimento"].items()) / n * 100
        out.append(f'''
  <h2 id="{slugify(ass)}">{NOME_CURTO[ass]}</h2>
  <div class="grid">
    <div class="stat"><b>{fmt(n)}</b><span>processos analisados</span></div>
    <div class="stat"><b>{fl(d["media_posicoes"])}</b><span>média de posições</span></div>
    <div class="stat"><b>{fl(d["mediana_posicoes"])}</b><span>mediana de posições</span></div>
    <div class="stat"><b>{cob_des:.0f}%</b><span>desfechos no topo-8</span></div>
  </div>
  <div class="card">
    <p>{INSIGHTS[ass]}</p>
    <img class="tree" src="{arq}" alt="árvore {NOME_CURTO[ass]}">
    <p class="ley"><b>Figura.</b> Fluxo real de movimentações — {NOME_CURTO[ass]}:
    percentuais em cada nó e sobre as arestas (transições reais).</p>
  </div>
  <div class="grid"><div class="card" style="flex:2 1 430px"><b>Passo a passo — funil por posição</b>
    <table><tr><th>Pos.</th><th>Chegam</th><th>% do total</th>
    <th>Movimentos mais comuns</th></tr>''')
        funcional = d["funil_por_posicao"][:10]
        for f in funcional:
            top3 = "; ".join(f"{m[:44]} ({porc(p)})" for m, c, p in f["top_movimentos"][:2])
            out.append(f'<tr><td>{f["posicao"]}ª</td><td>{fmt(f["n_alcance"])}</td>'
                       f'<td>{porc(f["pct_retencao"])}</td><td>{top3}</td></tr>')
        out.append("</table></div>")

        out.append('<div class="card" style="flex:1 1 250px"><b>Desfechos (%)</b>'
                   '<table><tr><th>Último movimento</th><th>%</th></tr>')
        for mv, cnt in list(d["ultimo_movimento"].items())[:6]:
            out.append(f'<tr><td>{mv[:52]}</td><td>{porc(100*cnt/n)}</td></tr>')
        out.append("</table></div></div>")

        out.append(f'<div class="card"><b>Caminho representativo mais frequente</b><p>'
                   f'{" → ".join(d["caminhos_top"][0]["seq"][:6])} '
                   f'(... {d["caminhos_top"][0]["n"]} processos, '
                   f'{porc(d["caminhos_top"][0]["pct"])})</p></div>')

    out.append("""
  <footer>Fonte: <b>outputs_json/tabela_posicao_tempo_processos.csv</b> · sequência por
    processo a partir da coluna <i>posicao</i> · árvores geradas automaticamente a partir
    dos dados reais.</footer>
</div></body></html>""")
    return "\n".join(out)
def limpa_para_pdf(t):
    return (t.replace("\u2192", "->").replace("—", "-").replace("“", '"')
             .replace("”", '"').replace("…", "...").replace("·", "|"))


def build_pdf(res):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Image, Table, TableStyle, PageBreak)

    pdf_path = os.path.join(BASE_DIR, "relatorio_arvores.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            leftMargin=16*mm, rightMargin=16*mm,
                            topMargin=16*mm, bottomMargin=16*mm)
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=ss["Title"], fontSize=20, leading=24,
                        textColor=colors.HexColor("#0b5d6b"), spaceAfter=6)
    h2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=14, leading=18,
                        spaceBefore=10, spaceAfter=6)
    body = ParagraphStyle("Body", parent=ss["BodyText"], fontSize=10, leading=14)
    caption = ParagraphStyle("Cap", parent=ss["BodyText"], fontSize=8.5,
                             textColor=colors.HexColor("#64748b"))

    def titulo(ass):
        return f'<font color="#0b5d6b">{NOME_CURTO[ass]}</font>'

    elementos = []
    elementos.append(Paragraph("Rotas de Movimentação Processual por Assunto", h1))
    elementos.append(Paragraph("Análise de fluxo real a partir de "
                               "tabela_posicao_tempo_processos.csv (DataJud/CNJ)", body))
    elementos.append(Spacer(1, 8))
    elementos.append(Paragraph(
        "Este relatório organiza, em forma de árvore e passo a passo, as sequências "
        "reais de movimentações (ponta a ponta) de três assuntos. Cada nodo indica o "
        "movimento observado em uma posicao e o percentual de processos que percorreu "
        "aquele caminho; as arestas representam transições efetivamente observadas.",
        body))
    elementos.append(Spacer(1, 12))
    elementos.append(Paragraph("Resumo comparativo", h2))

    dados = [["Assunto", "Processos", "Média", "Mediana", "Desfecho mais frequente"]]
    for ass in ORDER:
        d = res[ass]
        mv, ct = next(iter(d["ultimo_movimento"].items()))
        dados.append([NOME_CURTO[ass], str(d["n_processos"]),
                      fl(d["media_posicoes"]), fl(d["mediana_posicoes"]),
                      f"{limpa_para_pdf(mv)[:48]} ({porc(100*ct/d['n_processos'])})"])
    t = Table(dados, colWidths=[52*mm, 22*mm, 18*mm, 18*mm, 62*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elementos.append(t)
    elementos.append(Spacer(1, 6))
    elementos.append(Paragraph(limpa_para_pdf(INSIGHTS["Multas e demais Sanções"]), body))
    elementos.append(PageBreak())

    for ass in ORDER:
        d = res[ass]
        n = d["n_processos"]
        elementos.append(Paragraph(titulo(ass), h2))
        elementos.append(Paragraph(
            f"n = {n} processos | média de posições: {fl(d['media_posicoes'])} | "
            f"mediana: {fl(d['mediana_posicoes'])}", body))
        elementos.append(Spacer(1, 6))
        elementos.append(Paragraph(limpa_para_pdf(INSIGHTS[ass]), body))
        elementos.append(Spacer(1, 6))

        arq = os.path.join(IMG_DIR, "arvore_" + slugify(ass) + ".png")
        img = Image(arq, width=doc.width, height=doc.width * 1140 / 8660)
        elementos.append(img)
        elementos.append(Paragraph(
            "Fig.: fluxo real de movimentações. Cobertura dos ramos exibidos na 1a "
            + f"posicao: {sum(c for _, c in d['primeiro_movimento'].items())*100.0/n:.0f}%.",
            caption))
        elementos.append(Spacer(1, 10))

        fun = [["Pos.", "Chegam", "% total", "Movimentos mais comuns"]]
        for f in d["funil_por_posicao"][:8]:
            top2 = "; ".join(f"{limpa_para_pdf(m)[:38]} ({porc(p)})"
                             for m, c, p in f["top_movimentos"][:2])
            fun.append([f'{f["posicao"]}a', str(f["n_alcance"]),
                        porc(f["pct_retencao"]), top2])
        t1 = Table(fun, colWidths=[12*mm, 18*mm, 16*mm, 126*mm])
        t1.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elementos.append(Paragraph("Passo a passo (funil por posição)", h2))
        elementos.append(t1)

        des = [["Desfecho", "%"]]
        for mv, ct in list(d["ultimo_movimento"].items())[:6]:
            des.append([limpa_para_pdf(mv)[:54], porc(100*ct/n)])
        t2 = Table(des, colWidths=[130*mm, 30*mm])
        t2.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        elementos.append(Paragraph("Desfechos mais frequentes", h2))
        elementos.append(t2)
        elementos.append(PageBreak())

    doc.build(elementos)
    print("PDF:", pdf_path)


def main():
    with open(JSON_PATH, encoding="utf-8") as f:
        res = json.load(f)
    html = build_html(res)
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML:", HTML_PATH)
    build_pdf(res)


if __name__ == "__main__":
    main()