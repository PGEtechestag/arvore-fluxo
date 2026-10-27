# -*- coding: utf-8 -*-
"""Backend Flask — Árvore de fluxo interativa (caminhos mais comuns).

Serve o frontend (index.html) e uma pequena API JSON consumida por ele,
reaproveitando o motor de árvore já existente no projeto:
  - arvore_fluxo_top3.ler_assuntos()      -> lê os JSONs e separa por assunto
  - arvore_fluxo_multas.construir_arvore() -> trie (caminhos como prefixos)
  - arvore_fluxo_multas.montar_grafo()     -> grafo dirigido

Endpoints:
  GET  /                     -> index.html
  GET  /api/assuntos         -> ranking de assuntos (nº de processos)
  GET  /api/arvore           -> nós/arestas p/ vis-network
       ?assunto=<nome>&min_n=<int>&max_depth=<int>
       (cada aresta traz P(v|u) — Cadeia de Markov de 1ª ordem)
  POST /api/recarregar       -> limpa o cache e relê os JSONs

Rodar:
  py webapp/app.py           -> http://localhost:5000
"""
import os
import pickle
import sys
import threading
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
PROJ_DIR = BASE_DIR.parent
sys.path.insert(0, str(PROJ_DIR / "visualizacoes"))

import arvore_fluxo_top3 as core      # noqa: E402
import arvore_fluxo_multas as motor   # noqa: E402

app = Flask(__name__, static_folder=None)   # o front é servido sob demanda


@app.after_request
def _sem_cache(resp):
    """Impede o navegador de cachear o HTML e as respostas JSON.

    Sem isto, um index.html antigo (sem os campos de Markov) pode continuar
    em cache e "esconder" as métricas novas até um hard refresh (Ctrl+F5).
    """
    if request.path == "/" or request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
    return resp


CACHE_DIR = BASE_DIR / ".cache"
CACHE_FILE = CACHE_DIR / "dados.pkl"

# --------------------------------------------------------------------- cache
_LOCK = threading.Lock()
_DADOS = {"por_assunto": None, "ranking": None, "lidos": 0, "erros": 0}


def _assinatura():
    """(nº de JSONs, mtime máx.) — muda quando os dados em outputs_json mudam."""
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


def _aplicar(por_assunto, lidos, erros):
    ranking = sorted(((a, len(v)) for a, v in por_assunto.items()),
                     key=lambda kv: -kv[1])
    _DADOS.update(por_assunto=por_assunto, ranking=ranking,
                  lidos=lidos, erros=erros)
    return _DADOS


def carregar_dados(forcar=False):
    """Carrega {assunto: {proc: trilha}}.

    Ordem de busca: memória -> cache em disco (se a assinatura bater) ->
    leitura completa dos JSONs. O cache evita reprocessar a cada reinício.
    """
    with _LOCK:
        if _DADOS["por_assunto"] is not None and not forcar:
            return _DADOS

        assin = _assinatura()
        if not forcar and CACHE_FILE.exists():
            try:
                c = pickle.loads(CACHE_FILE.read_bytes())
                if c.get("assinatura") == assin:
                    return _aplicar(c["por_assunto"], c["lidos"], c["erros"])
            except Exception:
                pass  # cache corrompido/versão antiga: reprocessa

        por_assunto, lidos, erros = core.ler_assuntos()
        d = _aplicar(por_assunto, lidos, erros)
        try:
            CACHE_DIR.mkdir(exist_ok=True)
            CACHE_FILE.write_bytes(pickle.dumps({
                "assinatura": assin, "por_assunto": por_assunto,
                "ranking": d["ranking"], "lidos": lidos, "erros": erros}))
        except Exception:
            pass  # sem permissão de escrita: segue só com a memória
        return d


def montar_payload(assunto, trilhas, min_n, max_depth):
    """Converte a árvore (trie) em nós/arestas prontos para o vis-network.

    Além dos volumes/prazos, calcula as probabilidades de transição de uma
    Cadeia de Markov de 1ª ordem: P(v|u) = peso(u->v) / processos(u). Cada
    aresta sai com ``prob``/``prob_pct``/``prob_label`` e cada nó com
    ``prob_entrada``, ``p_saida`` (seguir adiante) e ``p_parada`` (encerrar).
    """
    total = len(trilhas)
    media_pos = sum(len(t) for t in trilhas.values()) / total if total else 0
    motor.ASSUNTO_ALVO = assunto
    raiz, tempo, gatilhos = motor.construir_arvore(trilhas, min_n=min_n,
                                                   max_depth=max_depth)
    G, _pos = motor.montar_grafo(raiz)

    # caminho dominante: segue sempre o filho mais volumoso até a folha
    raiz_id = next(n for n in G.nodes if n[0] == 0)
    dominantes = set()
    nid = raiz_id
    while G.out_degree(nid) > 0:
        nxt = max(G.successors(nid), key=lambda f: G.nodes[f]["n"])
        dominantes.add((nid, nxt))
        nid = nxt

    def pct(v):
        return round(100.0 * v / total, 1) if total else 0.0

    def fmt_prob(p):
        """Probabilidade (%) já formatada, sem casas decimais desnecessárias."""
        return f"{p:.0f}%" if abs(p - round(p)) < 0.05 else f"{p:.1f}%"

    # ------------------------- Cadeia de Markov (1ª ordem) ------------------
    for u, v, d in G.edges(data=True):
        n_u = G.nodes[u]["n"] or 0
        d["prob"] = min(1.0, max(0.0, (d["peso"] / n_u) if n_u else 0.0))
    for no in G.nodes:
        n_no = G.nodes[no]["n"] or 0
        saida = sum(d["peso"] for _, _, d in G.out_edges(no, data=True))
        p_saida = min(1.0, saida / n_no) if n_no else 0.0
        G.nodes[no]["p_saida"] = p_saida                 # chance de continuar
        G.nodes[no]["p_parada"] = max(0.0, 1.0 - p_saida)  # chance de encerrar

    # probabilidade de ENTRAR em cada nó (vindo do seu pai); a raiz = 1.
    prob_entrada = {v: d["prob"] for u, v, d in G.edges(data=True)}

    # Mapear e ordenar as rotas de saída possíveis (alternativas) para cada nó
    idx = {n: i for i, n in enumerate(G.nodes)}
    saidas_por_no = {}
    for u, v, d in G.edges(data=True):
        saidas_por_no.setdefault(u, []).append({
            "destino_id": idx[v],
            "destino_label": (G.nodes[v].get("origem") or G.nodes[v]["label"]).replace("\n", " "),
            "peso": d["peso"],
            "prob": round(d["prob"], 4),
            "prob_pct": round(100.0 * d["prob"], 1),
            "dias": round(d["dias"], 1) if d.get("dias") is not None else None,
            "gatilho": bool(G.nodes[v]["conclusao"]) and v[0] > 0
        })
    
    # Ordena as saídas do maior volume para o menor
    for u_node, lista_saidas in saidas_por_no.items():
        lista_saidas.sort(key=lambda x: -x["peso"])

    prof_max = max(n[0] for n in G.nodes)

    nos = []
    for n, d in G.nodes(data=True):
        prof = n[0]
        nos.append({
            "id": idx[n],
            "label": (d.get("origem") or d["label"]).replace("\n", " "),
            "n": d["n"],
            "pct": pct(d["n"]),
            "depth": prof,
            "conclusao": bool(d["conclusao"]) and prof > 0,
            "desfecho": bool(d["desfecho"]) and prof > 0,
            "outros": bool(d.get("outros")),
            "truncado": bool(d.get("truncado")),
            # --- Markov: probabilidades de chegar/seguir/encerrar neste estado ---
            "prob_entrada": round(prob_entrada.get(n, 1.0 if prof == 0 else 0.0), 4),
            "prob_entrada_label": fmt_prob(100.0 * prob_entrada.get(
                n, 1.0 if prof == 0 else 0.0)),
            "p_saida": round(d["p_saida"], 4),
            "p_parada": round(d["p_parada"], 4),
            # --- Rotas alternativas a partir deste nó ---
            "rotas_seguintes": saidas_por_no.get(n, []),
        })

    arestas = []
    for u, v, d in G.edges(data=True):
        arestas.append({
            "from": idx[u], "to": idx[v],
            "peso": d["peso"], "pct": pct(d["peso"]),
            # --- Markov: P(v|u) = peso da aresta / processos do nó pai ---
            "prob": round(d["prob"], 4),
            "prob_pct": round(100.0 * d["prob"], 1),
            "prob_label": fmt_prob(100.0 * d["prob"]),
            "p_parada": round(G.nodes[u]["p_parada"], 4),
            "dias": round(d["dias"], 1) if d.get("dias") is not None else None,
            "dominante": (u, v) in dominantes,
            "gatilho": bool(G.nodes[v]["conclusao"]) and v[0] > 0,
        })

    return {
        "assunto": assunto, "total": total,
        "profundidade_max": prof_max, "media_pos": round(media_pos, 1),
        "tempo": tempo, "gatilhos": gatilhos,
        "modelo": "markov-1",       # marca o formato do payload (o front valida)
        "nodes": nos, "edges": arestas,
    }

# --------------------------------------------------------------------- rotas
@app.get("/")
def raiz():
    """Entrega o frontend."""
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/api/assuntos")
def api_assuntos():
    """Ranking de assuntos (por nº de processos)."""
    d = carregar_dados()
    return jsonify({
        "lidos": d["lidos"],
        "erros": d["erros"],
        "assuntos": [{"assunto": a, "processos": n} for a, n in d["ranking"]],
    })


@app.get("/api/arvore")
def api_arvore():
    """Árvore de um assunto, no formato do vis-network.

    Parâmetros: assunto (obrigatório), min_n (default 2), max_depth (0 = todas).
    """
    assunto = (request.args.get("assunto") or "").strip()
    try:
        min_n = max(1, int(request.args.get("min_n", 2)))
        max_depth = int(request.args.get("max_depth", 0)) or None
    except ValueError:
        return jsonify({"erro": "min_n/max_depth devem ser números"}), 400

    d = carregar_dados()
    if not assunto:
        # sem assunto informado, usa o mais comum
        if not d["ranking"]:
            return jsonify({"erro": "Nenhum processo encontrado"}), 404
        assunto = d["ranking"][0][0]

    trilhas = d["por_assunto"].get(assunto)
    if not trilhas:
        return jsonify({"erro": f"Assunto não encontrado: {assunto}"}), 404

    return jsonify(montar_payload(assunto, trilhas, min_n, max_depth))


@app.post("/api/recarregar")
def api_recarregar():
    """Relê os JSONs (após mudar os dados em outputs_json/)."""
    carregar_dados(forcar=True)
    return jsonify({"ok": True, "assuntos": len(_DADOS["ranking"])})


if __name__ == "__main__":
    print("[app] Lendo os JSONs (aguarde na primeira execução)...")
    d = carregar_dados()
    print(f"[app] {d['lidos']} processos | {len(d['ranking'])} assuntos")
    print("[app] Abra http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)