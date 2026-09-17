# -*- coding: utf-8 -*-
"""App Streamlit — Árvore de fluxo processual por assunto.

Lê os JSONs brutos (outputs_json), SEPARA por assunto e recria a árvore de
fluxo (mesmo motor gráfico de arvore_fluxo_multas.py) com filtros na tela:
escolhe o assunto, ajusta --min-n / --max-depth e baixa PNG/SVG/CSV.

Rodar:
    py -m streamlit run visualizacoes/app_streamlit.py
"""
import hashlib
import os
import pickle
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / ".cache_arvore"
MANIFEST = CACHE_DIR / "manifest.pkl"
sys.path.insert(0, str(BASE_DIR))

import arvore_fluxo_top3 as core      # noqa: E402  (ler_assuntos, slug)
import arvore_fluxo_multas as motor   # noqa: E402  (motor gráfico da árvore)

st.set_page_config(page_title="Árvore de Fluxo por Assunto",
                   page_icon="🌳", layout="wide")


def _arquivo(assunto):
    """Caminho do cache em disco de um assunto (slug + hash estável)."""
    h = hashlib.md5(assunto.encode("utf-8")).hexdigest()[:8]
    return CACHE_DIR / f"{core.slug(assunto)}_{h}.pkl"


def _assinatura():
    """(nº de JSONs, mtime máx.) — muda quando os dados mudam."""
    n = 0
    mtime = 0.0
    for base, dirs, arquivos in os.walk(core.JSON_DIR):
        dirs[:] = [d for d in dirs if d not in core.IGNORAR]
        for nome in arquivos:
            if nome.lower().endswith(".json"):
                n += 1
                try:
                    mtime = max(mtime, os.path.getmtime(os.path.join(base, nome)))
                except OSError:
                    pass
    return (n, round(mtime, 3))


@st.cache_data(show_spinner="Lendo os JSONs de processo (só na 1ª vez)...")
def preparar():
    """Lê os JSONs, SEPARA por assunto e grava as sequências em disco.

    Assim o app mantém em memória apenas o ranking (leve) e, para desenhar,
    carrega só o assunto escolhido — evita estourar a RAM com árvores grandes.
    Um "manifest" evita reprocessar os JSONs a cada nova sessão.
    """
    CACHE_DIR.mkdir(exist_ok=True)
    assin = _assinatura()
    if MANIFEST.exists():
        try:
            dados = pickle.loads(MANIFEST.read_bytes())
            if dados.get("assinatura") == assin:
                return dados["ranking"], dados["lidos"], dados["erros"]
        except Exception:
            pass  # cache corrompido/versão antiga: reprocessa

    por_assunto, lidos, erros = core.ler_assuntos()
    ranking = []
    for assunto, trilhas in sorted(por_assunto.items(),
                                   key=lambda kv: -len(kv[1])):
        _arquivo(assunto).write_bytes(pickle.dumps(trilhas))
        ranking.append((assunto, len(trilhas)))
    MANIFEST.write_bytes(pickle.dumps({
        "assinatura": assin, "ranking": ranking,
        "lidos": lidos, "erros": erros}))
    return ranking, lidos, erros


@st.cache_data(show_spinner="Carregando as sequências do assunto...",
               max_entries=2)
def obter_trilhas(assunto):
    """Carrega do disco apenas as sequências do assunto escolhido."""
    return pickle.loads(_arquivo(assunto).read_bytes())


def limpar_nome(txt):
    return re.sub(r"\s+", " ", str(txt)).strip()


def montar(assunto, trilhas, min_n, max_depth):
    """Constrói e desenha a árvore; devolve (G, tempo, gatilhos, total, png, svg)."""
    total = len(trilhas)
    media_pos = sum(len(t) for t in trilhas.values()) / total if total else 0
    motor.ASSUNTO_ALVO = assunto          # garante o título correto na figura
    raiz, tempo, gatilhos = motor.construir_arvore(trilhas, min_n=min_n,
                                                   max_depth=max_depth)
    G, pos = motor.montar_grafo(raiz)
    pasta = tempfile.mkdtemp(prefix="arvore_")
    png, svg = os.path.join(pasta, "a.png"), os.path.join(pasta, "a.svg")
    # dpi menor: a figura dessas árvores é muito larga (muitas folhas) e ficaria
    # com dezenas de milhões de pixels na tela do navegador.
    motor.desenhar(G, pos, tempo, media_pos, total, png, svg,
                   gatilhos=gatilhos, dpi=70)
    return (G, tempo, gatilhos, total, media_pos,
            Path(png).read_bytes(), Path(svg).read_bytes())


def tabela(G):
    """DataFrame de nós e arestas (para exibir e baixar em CSV)."""
    linhas = []
    for n, d in G.nodes(data=True):
        linhas.append({
            "tipo": "no", "profundidade": n[0],
            "movimento": limpar_nome(d.get("origem") or d["label"]),
            "processos": d["n"],
            "conclusao": "sim" if d["conclusao"] else "",
            "desfecho": "sim" if d["desfecho"] else "",
            "dias_medios_aresta": ""})
    for u, v, d in G.edges(data=True):
        linhas.append({
            "tipo": "aresta", "profundidade": v[0],
            "movimento": f"{limpar_nome(u[1])} -> {limpar_nome(v[1])}",
            "processos": d["peso"], "conclusao": "", "desfecho": "",
            "dias_medios_aresta": (f"{d['dias']:.1f}"
                                   if d.get("dias") is not None else "")})
    return pd.DataFrame(linhas)


def main():
    st.title("🌳 Árvore de Fluxo Processual — por assunto")
    st.caption("Fonte: JSONs em `outputs_json` · motor gráfico de "
               "`arvore_fluxo_multas.py` · separação automática por assunto.")

    ranking, lidos, erros = preparar()

    with st.sidebar:
        st.header("⚙️ Filtros")
        st.caption(f"{lidos} processos · {len(ranking)} assuntos"
                   + (f" · {erros} erros de leitura" if erros else ""))
        if st.button("🔄 Recarregar dados (limpar cache)"):
            preparar.clear()
            obter_trilhas.clear()
            shutil.rmtree(CACHE_DIR, ignore_errors=True)
            st.rerun()

        opcoes = [f"{n:>5} · {a}" for a, n in ranking]
        idx = st.selectbox("Assunto", options=range(len(opcoes)),
                           format_func=lambda i: opcoes[i])
        assunto = ranking[idx][0]

        min_n = st.slider(
            "min-n — mín. processos p/ o ramo ter nó próprio", 1, 20, 5,
            help="Aumente para a árvore ficar mais enxuta (ramos menores "
                 "entram em 'Outros'). Diminua para ver tudo (árvore grande).")
        md = st.slider("max-depth — profundidade máx. (0 = todas)", 0, 30, 0)
        max_depth = None if md == 0 else md

    trilhas = obter_trilhas(assunto)
    if not trilhas:
        st.warning("Assunto sem processos.")
        return

    try:
        with st.spinner("Montando a árvore..."):
            G, tempo, gatilhos, total, media_pos, png, svg = montar(
                assunto, trilhas, min_n, max_depth)
    except MemoryError:
        st.error("Memória insuficiente para esta árvore. Aumente o `min-n` "
                 "(poda mais) ou reduza o `max-depth` e tente de novo.")
        st.stop()

    base = core.slug(assunto)
    st.subheader(assunto)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Processos", total)
    c2.metric("Nós", G.number_of_nodes())
    c3.metric("Arestas", G.number_of_edges())
    c4.metric("Posições (média)", f"{media_pos:.1f}")
    c5.metric("1ª Conclusão (μ dias)", f"{tempo['media']:.1f}")

    abas = st.tabs(["🌳 Imagem", "🔍 SVG interativo", "📋 Nós e arestas",
                    "🎯 Gatilhos", "📊 Ranking"])

    with abas[0]:
        st.image(png)
        st.download_button("⬇️ Baixar PNG", png,
                           file_name=f"arvore_fluxo_{base}.png",
                           mime="image/png")

    with abas[1]:
        st.caption("Dá para ampliar com Ctrl+scroll do navegador.")
        st.html(
            '<div style="width:100%;height:80vh;overflow:auto;'
            'border:1px solid #e0e0e0;border-radius:6px;background:#fff">'
            + svg.decode("utf-8") + "</div>")
        st.download_button("⬇️ Baixar SVG", svg,
                           file_name=f"arvore_fluxo_{base}.svg",
                           mime="image/svg+xml")

    with abas[2]:
        df = tabela(G)
        st.dataframe(df, height=460)
        st.download_button(
            "⬇️ Baixar CSV", df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"arvore_fluxo_{base}_dados.csv", mime="text/csv")

    with abas[3]:
        if gatilhos:
            gdf = pd.DataFrame(gatilhos).rename(columns={
                "movimento": "Andamento", "n": "Processos",
                "dias": "μ dias até conclusão", "prof": "Posição média"})
            gdf["μ dias até conclusão"] = pd.to_numeric(
                gdf["μ dias até conclusão"], errors="coerce").round(1)
            gdf["Posição média"] = pd.to_numeric(
                gdf["Posição média"], errors="coerce").round(1)
            st.caption("Principais andamentos imediatamente anteriores à "
                       "conclusão (gatilhos).")
            st.dataframe(gdf, height=300)
        else:
            st.info("Nenhum gatilho pré-conclusão detectado.")

    with abas[4]:
        rdf = pd.DataFrame(ranking, columns=["assunto", "processos"])
        st.caption("20 assuntos mais frequentes (todos os anos e órgãos).")
        st.bar_chart(rdf.set_index("assunto").head(20), height=460)

    st.caption(f"min-n={min_n} · max-depth={max_depth or 'todas'} · "
               f"base do arquivo: arvore_fluxo_{base}")


if __name__ == "__main__":
    main()