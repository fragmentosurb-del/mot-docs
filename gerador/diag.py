"""Diagnóstico temporário: mede cada elemento do e-book paginado e compara com diag_local.json."""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
SAIDA = Path(__file__).resolve().parent.parent / "saida"
JS = """() => [...document.querySelectorAll('doc-page .page')].map((pg,i)=>({p:i+1,
  els:[...pg.querySelectorAll('.pg-body > *, .pg-body > * > *')].map(e=>{const r=e.getBoundingClientRect();
   return [e.tagName, (e.textContent||'').replace(/\\s+/g,' ').trim().slice(0,40), Math.round(r.height*10)/10, Math.round(r.width*10)/10];})}))"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1000, "height": 1400})
    pg.goto((SAIDA / "ebook-mot.html").resolve().as_uri())
    pg.wait_for_function("window.__pageIndex !== undefined", timeout=180000)
    dados = pg.evaluate(JS)
    fontes = pg.evaluate("[...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family+' '+f.weight)")
    print("chromium", b.version, "| fontes carregadas:", len(fontes))
    b.close()
if len(sys.argv) > 1 and sys.argv[1] == "--gravar":
    Path(__file__).with_name("diag_local.json").write_text(json.dumps(dados, ensure_ascii=False)); sys.exit()
loc = json.loads(Path(__file__).with_name("diag_local.json").read_text())
n = 0
for a, c in zip(loc, dados):
    for x, y in zip(a["els"], c["els"]):
        if x[1] != y[1] or abs(x[2] - y[2]) > 0.5 or abs(x[3] - y[3]) > 0.5:
            print(f"p.{a['p']} local={x} github={y}"); n += 1
            if n >= 25: sys.exit()
    if n: break
print("diferenças listadas:", n)
