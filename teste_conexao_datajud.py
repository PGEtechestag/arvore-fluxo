"""
Teste minimo de conectividade com a API Publica do DataJud (CNJ).

Faz UMA unica requisicao (sem retry, sem loop), igual ao exemplo oficial
da documentacao, so que com timeout explicito para nao ficar travado pra
sempre caso a API esteja fora do ar / sobrecarregada.

Uso:
    python teste_conexao_datajud.py
"""

import json
import time

import requests

url = "https://api-publica.datajud.cnj.jus.br/api_publica_tjsp/_search"

payload = json.dumps({
    "query": {
        "match": {
            "numeroProcesso": "10046481220218260053"
        }
    }
})

headers = {
    "Authorization": "ApiKey cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw==",
    "Content-Type": "application/json",
}

# print(f"[INFO] Enviando requisicao para {url} (timeout=30s)...")
# t0 = time.time()

response = requests.request("POST", url, headers=headers, data=payload)

with open("resposta_teste.json", "w", encoding="utf-8") as f:
    f.write(response.text)
print(f"[OK] resposta completa salva em resposta_teste.json (status={response.status_code})")

if "application/json" not in response.headers.get("Content-Type", ""):
    print(f"[AVISO] resposta nao e JSON (Content-Type={response.headers.get('Content-Type')!r}).")
    print("Provavelmente e uma pagina de erro do gateway/infra do CNJ (ex: 504 Gateway Time-out).")
    print("Veja o conteudo em resposta_teste.json. Tente novamente mais tarde.")
else:
    data = response.json()
    hits = data.get("hits", {}).get("hits", [])
    if hits:
        orgao = hits[0].get("_source", {}).get("orgaoJulgador")
        print("orgaoJulgador:", json.dumps(orgao, ensure_ascii=False))
    else:
        print("[SEM HITS] nenhum processo encontrado.")

# try:
#     # dt = time.time() - t0
#     # print(f"[OK] status={response.status_code} tempo={dt:.1f}s")
#     print(response.text[:3000])

# except requests.exceptions.SSLError as e:
#     dt = time.time() - t0
#     print(f"[ERRO SSL] tempo={dt:.1f}s")
#     print(repr(e))
#     print("\nIsso normalmente significa que algum antivirus/firewall (ex: Avast) esta")
#     print("interceptando o HTTPS e o Python nao confia no certificado dele.")
#     print("Solucao: pip install pip-system-certs")

# except requests.exceptions.Timeout as e:
#     dt = time.time() - t0
#     print(f"[TIMEOUT] tempo={dt:.1f}s")
#     print(repr(e))
#     print("\nO servidor nao respondeu dentro do prazo. Isso costuma indicar")
#     print("instabilidade/sobrecarga na propria API publica do DataJud, nao")
#     print("um problema local.")

# except requests.exceptions.RequestException as e:
#     dt = time.time() - t0
#     print(f"[ERRO] tempo={dt:.1f}s")
#     print(repr(e))
