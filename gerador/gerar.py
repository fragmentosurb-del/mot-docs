#!/usr/bin/env python3
"""Gera, a partir da fonte única do e-book, o PDF completo e os documentos individuais.

Uso:  python3 gerador/gerar.py            (gera tudo em saida/)
      python3 gerador/gerar.py --so-conferir

Etapas:
  1. lê fonte/ebook.dc.html e separa os blocos de primeiro nível;
  2. confere termos aposentados (falha se encontrar algum);
  3. pagina o e-book completo e registra em que página começa e termina cada documento;
  4. para cada documento, monta capa + blocos e pagina com o mesmo paginador e o mesmo estilo;
  5. grava PDFs, um manifesto.json (versão, páginas, conferências) e as páginas HTML.
"""
import argparse, copy, html, json, re, sys
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString

RAIZ = Path(__file__).resolve().parent.parent
FONTE = RAIZ / "fonte" / "ebook.dc.html"
GER = RAIZ / "gerador"
SAIDA = RAIZ / "saida"

def texto(el):
    return re.sub(r"\s+", " ", el.get_text(" ") if el is not None else "").strip()

# ---------------------------------------------------------------- leitura da fonte
def ler_fonte():
    sopa = BeautifulSoup(FONTE.read_text(encoding="utf-8"), "lxml")
    dp = sopa.find("doc-page")
    blocos = [c for c in dp.find_all(recursive=False) if not c.get("slot")]
    estilos = "\n".join(str(s) for s in sopa.find("helmet").find_all("style"))
    return sopa, blocos, estilos

def tipo_bloco(b):
    st = b.get("style", "") or ""
    if b.name == "img" or (len(b.find_all(recursive=False)) == 1 and b.find().name == "img"):
        return "bleed"
    if "min-height:8.6in" in st:
        return "divisor"
    return "doc"

def versao(sopa):
    t = texto(sopa)
    m = re.search(r"Versão\s+(\d+(?:\.\d+)+)\s*·\s*([a-zç]+ de \d{4})", t)
    if not m:
        sys.exit("ERRO: não achei 'Versão X.Y · mês de ano' nos créditos do e-book.")
    return m.group(1), m.group(2)

def titulo_bloco(b):
    h = b.find(["h1", "h2", "h3"])
    return texto(h) if h else ""

def recortes(blocos, cfg):
    """Devolve, para cada documento, os índices dos blocos e o estágio (texto do divisor anterior)."""
    tipos = [tipo_bloco(b) for b in blocos]
    titulos = [titulo_bloco(b) for b in blocos]
    inicios = {}
    for d in cfg["documentos"]:
        achados = [i for i, t in enumerate(titulos) if tipos[i] == "doc" and t.startswith(d["inicio"])]
        if len(achados) != 1:
            sys.exit(f"ERRO: o início de '{d['arquivo']}' ({d['inicio']!r}) apareceu {len(achados)} vezes.")
        inicios[achados[0]] = d
    res = []
    for i0, d in sorted(inicios.items()):
        idx = [i0]
        for j in range(i0 + 1, len(blocos)):
            if tipos[j] != "doc" or j in inicios or any(titulos[j].startswith(p) for p in cfg["parar_em"]):
                break
            idx.append(j)
        estagio = next((texto(blocos[k]) for k in range(i0, -1, -1) if tipos[k] == "divisor"), "")
        estagio = re.sub(r"^[IVX]+\s+", "", estagio)                      # tira o numeral romano
        estagio = re.sub(r"^(Estágio \d+)\s+", r"\1 · ", estagio)          # "Estágio 2 · TECER O CASULO"
        res.append({**d, "blocos": idx, "estagio": estagio})
    return res

# ---------------------------------------------------------------- conferência
def conferir(sopa, cfg):
    t = texto(sopa.find("doc-page"))
    falhas = []
    for x in cfg["termos_aposentados"]:
        for m in re.finditer(re.escape(x["termo"]), t, flags=re.I):
            falhas.append({"termo": x["termo"], "motivo": x["motivo"],
                           "trecho": t[max(0, m.start() - 90): m.end() + 60]})
    return falhas

# ---------------------------------------------------------------- montagem do HTML paginável
def css_fontes():
    regras = []
    for peso in (200, 300, 400, 500, 600, 700):
        for sub, faixa in (("latin-ext", "U+0100-02AF,U+0304,U+0308,U+0329,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF"),
                           ("latin", "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD")):
            regras.append(f"@font-face{{font-family:Oswald;font-style:normal;font-weight:{peso};font-display:block;"
                          f"src:url('fontes/oswald-{sub}-{peso}-normal.woff2') format('woff2');unicode-range:{faixa};}}")
    # Fontes de reserva para os símbolos que a Oswald não tem, embutidas para que a paginação
    # seja igual em qualquer computador (sem elas, cada sistema escolhe a sua e o e-book muda de tamanho).
    for nome, pesos in (("liberation", (400, 700)), ("dejavu", (400, 700)), ("emoji", (None,))):
        for peso in pesos:
            arq = f"reserva-{nome}-{peso}.woff2" if peso else f"reserva-{nome}.woff2"
            w = f"font-weight:{peso};" if peso else "font-weight:100 900;"
            regras.append(f"@font-face{{font-family:'MOT Reserva';font-style:normal;{w}font-display:block;"
                          f"src:url('fontes/{arq}') format('woff2');unicode-range:{','.join(RESERVA[nome])};}}")
    return "\n".join(regras)

# caracteres que cada fonte de reserva cobre (os mesmos que o navegador escolhia na v1.3)
RESERVA = {
    "liberation": ["U+2192", "U+03A3", "U+03BA", "U+03B1", "U+2265", "U+2194", "U+2260"],
    "dejavu": ["U+2208", "U+1D62"],
    "emoji": ["U+2696", "U+FE0F", "U+1F534", "U+1F7E1", "U+1F7E2", "U+2705", "U+274C"],
}

def conferir_glifos(sopa):
    """Falha se o texto usar um caractere que nem a Oswald nem as fontes de reserva cobrem."""
    from fontTools.ttLib import TTFont
    cobertos = set()
    for f in (GER / "fontes").glob("oswald-*-400-normal.woff2"):
        cobertos |= set(TTFont(f).getBestCmap())
    for lista in RESERVA.values():
        cobertos |= {int(u[2:], 16) for u in lista}
    faltam = sorted({c for c in texto(sopa.find("doc-page")) if not c.isspace() and ord(c) not in cobertos})
    return [f"{c} (U+{ord(c):04X})" for c in faltam]

ESTILO_BASE = """
  doc-page:not(:defined) { visibility: hidden; }
  body { margin: 0; }
  #src, #src *, .page, .page * { font-family: Oswald, 'MOT Reserva', sans-serif !important; }
  a { color: #16181a; text-decoration: none; border-bottom: 1px solid rgba(22,24,26,.4); }
  sup { font-size: 62%; line-height: 0; vertical-align: super; }
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .page { position: relative; box-sizing: border-box; overflow: hidden; width: 210mm; height: 297mm; }
  .pg-inner { box-sizing: border-box; height: 100%; padding: 0.85in; display: flex; flex-direction: column; }
  .bleed .pg-inner { padding: 0; }
  .bleed .pg-hdr, .bleed .pg-ftr, .nochrome .pg-hdr, .nochrome .pg-ftr { display: none !important; }
  .pg-hdr { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; padding: 0 0 6px; margin: 0 0 22px; border-bottom: .5px solid #cfcbc4; font: 400 9.5px/1.4 Oswald, sans-serif; letter-spacing: .14em; text-transform: uppercase; color: #5f6367; flex: 0 0 auto; }
  .pg-body { flex: 1 1 auto; min-height: 0; }
  .pg-ftr { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; padding: 6px 0 0; margin: 22px 0 0; border-top: .5px solid #cfcbc4; font: 300 9.5px/1.4 Oswald, sans-serif; letter-spacing: .1em; color: #5f6367; flex: 0 0 auto; }
  .pg-ftr b { font-weight: 500; font-variant-numeric: tabular-nums; color: #26292c; }
  #src { position: absolute; left: -99999px; top: 0; width: 630px; }
  #status { position: fixed; z-index: 9; left: 12px; bottom: 12px; padding: 8px 12px; background: #16181a; color: #f4f2ee; font: 400 11px/1.4 Oswald, sans-serif; letter-spacing: .1em; text-transform: uppercase; }
  @media print { #status { display: none; } }
"""

def pagina_html(titulo, blocos_html, hdr, ftr):
    cfg = json.dumps({"hdr": hdr, "ftr": ftr}, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{html.escape(titulo)}</title>
<style>{css_fontes()}</style>
<script>window.MOT_CFG = {cfg};</script>
<script src="./doc-page.js"></script>
<style>{ESTILO_BASE}</style>
</head>
<body>
<div id="status">Paginando…</div>
<div id="src">
{blocos_html}
</div>
<doc-page size="a4" margin="0"></doc-page>
<script src="./paginador.js"></script>
</body>
</html>
"""

def capa_individual(d, ver, data, faixa, url_ebook, url_doc):
    p0, p1 = faixa
    est = html.escape(d["estagio"])
    return f"""<div data-nochrome="1" style="display:flex;flex-direction:column;min-height:8.6in;border-top:6px solid #16181a;padding:.35in 0 0;box-sizing:border-box">
    <div style="font:400 9.5px/1.9 Oswald,sans-serif;letter-spacing:.16em;text-transform:uppercase;color:#5f6367">
      <div>Universidade Tecnológica Federal do Paraná (UTFPR)</div>
      <div>Departamento de Arquitetura e Urbanismo (DEAAU)</div>
      <div style="color:#16181a">Fragmentos — Observatório Analítico de Intervenções Territoriais</div>
    </div>
    <div style="margin-top:1.1in">
      <p style="margin:0 0 14px;font:500 11px/1.4 Oswald,sans-serif;letter-spacing:.2em;text-transform:uppercase;color:#16181a">Método MOT · {est}</p>
      <h1 style="margin:0;font:600 44px/1.05 Oswald,sans-serif;letter-spacing:.005em;color:#16181a;text-transform:uppercase">{html.escape(d["titulo"])}</h1>
      <div style="height:2px;background:#16181a;margin:26px 0 0;width:150px"></div>
      <p style="margin:26px 0 0;font:200 17px/1.45 Oswald,sans-serif;color:#26292c;max-width:26em">Documento que integra o e-book <span style="font-weight:400">MOT — Nosso primeiro Plano Diretor</span>, versão {ver} ({data}), p. {p0}–{p1}.</p>
    </div>
    <div style="margin-top:auto;display:flex;flex-direction:column;gap:3px;font:300 12px/1.6 Oswald,sans-serif;color:#26292c">
      <div><span style="font-weight:500">Autor:</span> Arq. Orlando Ribeiro, Prof. Dr. (DEAAU / UTFPR)</div>
      <div>Curitiba, 2026</div>
    </div>
    <div style="margin-top:22px;padding-top:12px;border-top:.5px solid #cfcbc4;display:grid;grid-template-columns:1fr 1fr;gap:18px;font:300 9.5px/1.6 Oswald,sans-serif;color:#5f6367">
      <div><span style="text-transform:uppercase;letter-spacing:.12em;color:#26292c">Versão vigente</span><br />Este texto sai automaticamente do e-book, a fonte única do método, e muda junto com ele. A versão em vigor, deste documento e do e-book completo, está sempre em fragmentos.arq.br/mot-app.</div>
      <div><span style="text-transform:uppercase;letter-spacing:.12em;color:#26292c">Licenciamento</span><br />Conteúdo sob licença CC BY-NC 4.0 (Atribuição — Não Comercial). Projeto nº 3533 (UTFPR).</div>
    </div>
  </div>"""

def marcar(blocos):
    """Marca o primeiro e o último filho de cada bloco, para achar suas páginas depois da paginação."""
    for i, b in enumerate(blocos):
        filhos = [c for c in b.children if getattr(c, "name", None)]
        if filhos:
            filhos[0]["data-ini"] = str(i)
            filhos[-1]["data-fim"] = str(i)
        else:
            b["data-ini"] = str(i); b["data-fim"] = str(i)

# ---------------------------------------------------------------- impressão
def imprimir(html_path, pdf_path):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        # sem arredondamento da largura das letras: a paginação fica igual em qualquer sistema
        nav = p.chromium.launch(args=["--font-render-hinting=none"])
        pg = nav.new_page(viewport={"width": 1000, "height": 1400})
        pg.goto(html_path.resolve().as_uri())
        pg.wait_for_function("window.__pageIndex !== undefined", timeout=180000)
        status = pg.inner_text("#status")
        if status.startswith("ERRO"):
            sys.exit(f"ERRO de paginação em {html_path.name}: {status}")
        faixas = pg.evaluate("""() => {
          const pages = [...document.querySelectorAll('doc-page .page')];
          const ix = el => pages.indexOf(el.closest('.page')) + 1;
          const out = {};
          document.querySelectorAll('[data-ini]').forEach(el => { const k = el.dataset.ini; if (!(k in out)) out[k] = [ix(el), ix(el)]; });
          document.querySelectorAll('[data-fim]').forEach(el => { const k = el.dataset.fim; if (out[k]) out[k][1] = Math.max(out[k][1], ix(el)); });
          return {n: pages.length, faixas: out};
        }""")
        fonte_ok = pg.evaluate("document.fonts.check('300 14px Oswald')")
        pg.emulate_media(media="print")
        pg.pdf(path=str(pdf_path), width="210mm", height="297mm", print_background=True,
               margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        nav.close()
    return faixas, fonte_ok

# ---------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--so-conferir", action="store_true")
    ap.add_argument("--atualizar-referencia", action="store_true",
                    help="grava a paginação atual como referência (usar só depois de conferir o PDF)")
    ap.add_argument("--base-url", default="https://fragmentosurb-del.github.io/mot-docs")
    a = ap.parse_args()

    cfg = json.loads((GER / "documentos.json").read_text(encoding="utf-8"))
    sopa, blocos, _ = ler_fonte()
    ver, data = versao(sopa)
    falhas = conferir(sopa, cfg)
    docs = recortes(blocos, cfg)
    print(f"e-book versão {ver} ({data}) · {len(blocos)} blocos · {len(docs)} documentos")
    for d in docs:
        print(f"  {d['arquivo']:<28} blocos {d['blocos']}  [{d['estagio']}]")
    if falhas:
        print(f"\nTERMOS APOSENTADOS ENCONTRADOS: {len(falhas)}")
        for f in falhas:
            print(f"  - {f['termo']!r} ({f['motivo']}): …{f['trecho']}…")
        sys.exit(1)
    print("conferência de termos: ok")
    faltam = conferir_glifos(sopa)
    if faltam:
        sys.exit("ERRO: caracteres sem fonte embutida (acrescente em RESERVA e gere o recorte da fonte): " + ", ".join(faltam))
    print("conferência de fontes: ok")
    if a.so_conferir:
        return

    SAIDA.mkdir(exist_ok=True)
    (SAIDA / "fontes").mkdir(exist_ok=True)
    for f in (GER / "fontes").glob("*.woff2"):
        (SAIDA / "fontes" / f.name).write_bytes(f.read_bytes())
    for nome, origem in (("doc-page.js", RAIZ / "fonte" / "doc-page.js"), ("paginador.js", GER / "paginador.js")):
        (SAIDA / nome).write_bytes(origem.read_bytes())

    # 1. e-book completo
    marcados = [copy.copy(b) for b in blocos]
    marcar(marcados)
    hdr_ebook = ["Mutirão de Ordenamento Territorial", "E-book · edição consolidada"]
    ebook_html = SAIDA / "ebook-mot.html"
    ebook_html.write_text(pagina_html("E-book MOT", "\n\n".join(str(b) for b in marcados), hdr_ebook,
                                      "MOT · fragmentos.arq.br"), encoding="utf-8")
    info, fonte_ok = imprimir(ebook_html, SAIDA / "ebook-mot.pdf")
    if not fonte_ok:
        sys.exit("ERRO: a fonte Oswald não carregou.")
    print(f"\nebook-mot.pdf: {info['n']} páginas")
    faixa_bloco = {int(k): v for k, v in info["faixas"].items()}

    # 2. documentos individuais
    url_ebook = f"{a.base_url}/ebook-mot.pdf"
    manifesto = {"versao": ver, "data": data, "ebook": {"arquivo": "ebook-mot.pdf", "paginas": info["n"]}, "documentos": []}
    for d in docs:
        faixa = (faixa_bloco[d["blocos"][0]][0], faixa_bloco[d["blocos"][-1]][1])
        url_doc = f"{a.base_url}/{d['arquivo']}.pdf"
        corpo = capa_individual(d, ver, data, faixa, url_ebook, url_doc) + "\n\n" + \
                "\n\n".join(str(blocos[i]) for i in d["blocos"])
        h = SAIDA / f"{d['arquivo']}.html"
        h.write_text(pagina_html(f"{d['titulo']} — MOT", corpo,
                                 ["Mutirão de Ordenamento Territorial", d["curto"]],
                                 f"MOT · fragmentos.arq.br · e-book v{ver}"), encoding="utf-8")
        di, _ = imprimir(h, SAIDA / f"{d['arquivo']}.pdf")
        manifesto["documentos"].append({"arquivo": f"{d['arquivo']}.pdf", "titulo": d["titulo"],
                                        "paginas": di["n"], "paginas_no_ebook": list(faixa)})
        print(f"{d['arquivo']}.pdf: {di['n']} páginas (e-book p. {faixa[0]}–{faixa[1]})")
    # 3. conferência final: cada página do recorte (sem capa) tem o mesmo texto da página do e-book
    divergentes = verificar_recortes(manifesto)
    manifesto["conferencia"] = {"termos_aposentados": 0, "paginas_divergentes": divergentes}
    (SAIDA / "manifesto.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    if divergentes:
        sys.exit(f"ERRO: recortes diferentes do e-book: {divergentes}")
    print("conferência dos recortes contra o e-book: ok (todas as páginas iguais)")

    # 4. paginação igual à de referência (conferida contra o PDF oficial antes de ir para o main)
    atual = {"versao": ver, "ebook": info["n"],
             "documentos": {d["arquivo"]: d["paginas_no_ebook"] for d in manifesto["documentos"]}}
    ref_path = GER / "referencia.json"
    if a.atualizar_referencia:
        ref_path.write_text(json.dumps(atual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("referência de paginação gravada em gerador/referencia.json")
    elif ref_path.exists():
        ref = json.loads(ref_path.read_text(encoding="utf-8"))
        if ref != atual:
            sys.exit("ERRO: a paginação mudou em relação a gerador/referencia.json.\n"
                     f"  referência: {json.dumps(ref, ensure_ascii=False)}\n  agora:      {json.dumps(atual, ensure_ascii=False)}\n"
                     "Se a mudança de texto é intencional, gere de novo com --atualizar-referencia e confira as citações.")
        print("conferência da paginação contra a referência: ok")

def verificar_recortes(manifesto):
    from pypdf import PdfReader
    corpo = lambda t: re.sub(r"\s+", "", "".join((t or "").split("\n")[1:-1]))  # sem cabeçalho e rodapé
    eb = PdfReader(SAIDA / "ebook-mot.pdf")
    ruins = {}
    for d in manifesto["documentos"]:
        r = PdfReader(SAIDA / d["arquivo"]); a, b = d["paginas_no_ebook"]
        if len(r.pages) - 1 != b - a + 1:
            ruins[d["arquivo"]] = "número de páginas"; continue
        k = [i + 2 for i, p in enumerate(r.pages[1:]) if corpo(p.extract_text()) != corpo(eb.pages[a - 1 + i].extract_text())]
        if k:
            ruins[d["arquivo"]] = k
    return ruins

if __name__ == "__main__":
    main()
