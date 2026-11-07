#!/usr/bin/env python3
"""Vigia semanal da página de downloads do MOT.

Confere, sem mudar nada:
  1. a página fragmentos.arq.br/mot-app tem um link para o e-book e para cada um dos 10 documentos
     publicados por este repositório, e todos os links de PDF respondem;
  2. nenhum link de documento aponta para um PDF antigo guardado no Wix (salvo os de PDF_WIX_PERMITIDOS);
  3. o texto da página não tem termo aposentado (lista em documentos.json);
  4. o Pergunte ao MOT usa a mesma versão e a mesma paginação do e-book que está no ar.

Grava o relatório em vigia.md e termina com código 1 se encontrar algum problema.
Uso: python3 gerador/vigia.py
"""
import html, json, re, sys, urllib.request
from pathlib import Path

GER = Path(__file__).resolve().parent
PAGINA = "https://www.fragmentos.arq.br/mot-app"
DOCS = "https://fragmentosurb-del.github.io/mot-docs/"
STATUS = "https://motapp-production.up.railway.app/api/pergunte/status"
# PDFs do Wix que ainda podem ficar na página, com o motivo
PDF_WIX_PERMITIDOS = {
    "0fdb65_c0d985412ad843fe88640850f555fb3f": "Não existe fórmula pronta (fica no Wix até virar anexo do e-book)",
}
UA = {"User-Agent": "Mozilla/5.0 (vigia mot-docs; github.com/fragmentosurb-del/mot-docs)"}


def baixar(url, limite=None):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, (r.read(limite) if limite else r.read())


def main():
    cfg = json.loads((GER / "documentos.json").read_text(encoding="utf-8"))
    problemas, ok = [], []

    # e-book no ar (manifesto da última publicação)
    _, corpo = baixar(DOCS + "manifesto.json")
    man = json.loads(corpo)
    no_ar = {"versao": man["versao"], "ebook": man["ebook"]["paginas"],
             "documentos": {d["arquivo"]: d["paginas_no_ebook"] for d in man["documentos"]}}
    esperados = [DOCS + man["ebook"]["arquivo"]] + [DOCS + d["arquivo"] for d in man["documentos"]]

    # página do site
    _, corpo = baixar(PAGINA)
    pagina = corpo.decode("utf-8", "replace")
    links = sorted({html.unescape(h) for h in re.findall(r'href="([^"]+\.pdf)"', pagina)})
    for url in esperados:
        if url not in links:
            problemas.append(f"A página não tem link para `{url.rsplit('/', 1)[1]}`.")
    for url in links:
        wix = re.search(r"/_files/ugd/([0-9a-f]+_[0-9a-f]+)", url)
        if wix and wix.group(1) not in PDF_WIX_PERMITIDOS:
            problemas.append(f"Link para PDF antigo do Wix: {url} (deveria apontar para {DOCS}…).")
        try:
            st, ini = baixar(url, 8)
            if st != 200 or not ini.startswith(b"%PDF"):
                problemas.append(f"O link {url} não devolveu um PDF (código {st}).")
        except Exception as e:  # noqa: BLE001
            problemas.append(f"O link {url} não abriu: {e}.")
    ok.append(f"{len(links)} links de PDF na página; {len(esperados)} esperados do mot-docs.")

    # termos aposentados no texto visível
    texto = re.sub(r"<(script|style)\b.*?</\1>", " ", pagina, flags=re.S | re.I)
    texto = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", texto)))
    for x in cfg["termos_aposentados"] + cfg.get("termos_pagina", []):
        for m in re.finditer(re.escape(x["termo"]), texto, flags=re.I):
            problemas.append(f"Termo aposentado na página: “{x['termo']}” ({x['motivo']}) — …{texto[max(0, m.start()-70):m.end()+50]}…")

    # Pergunte ao MOT x e-book no ar
    try:
        _, corpo = baixar(STATUS)
        st = json.loads(corpo)
        base = st.get("paginacaoEbook")
        if base is None:
            problemas.append("O Pergunte ao MOT não informa a paginação da base (falta o PR #22 do mot_app?).")
        elif base != no_ar:
            problemas.append("A base do Pergunte ao MOT não corresponde ao e-book no ar: as citações podem abrir a página errada. "
                             "Regerar com `scripts/gerar_corpus_ebook.py ebook-mot.pdf referencia.json` no mot_app.\n"
                             f"  - base: `{json.dumps(base, ensure_ascii=False)}`\n  - no ar: `{json.dumps(no_ar, ensure_ascii=False)}`")
        else:
            ok.append(f"Pergunte ao MOT com a mesma paginação do e-book no ar (v{no_ar['versao']}, {no_ar['ebook']} p.).")
    except Exception as e:  # noqa: BLE001
        problemas.append(f"Não consegui consultar o status do Pergunte ao MOT: {e}.")

    linhas = [f"**Vigia da página mot-app** — e-book no ar: v{no_ar['versao']}, {no_ar['ebook']} páginas", ""]
    if problemas:
        linhas += [f"Encontrei {len(problemas)} problema(s):", ""] + [f"- [ ] {p}" for p in problemas]
    else:
        linhas += ["Tudo certo."]
    linhas += ["", "Conferido:"] + [f"- {o}" for o in ok]
    linhas += [f"- Permitidos no Wix: " + "; ".join(PDF_WIX_PERMITIDOS.values())]
    Path("vigia.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print("\n".join(linhas))
    sys.exit(1 if problemas else 0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 — o vigia nunca deve falhar em silêncio
        Path("vigia.md").write_text(f"**Vigia da página mot-app**\n\nO vigia não conseguiu terminar: `{e}`\n", encoding="utf-8")
        print(e); sys.exit(1)
