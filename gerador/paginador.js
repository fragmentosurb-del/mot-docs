// cabeçalho e rodapé vêm do gerador (window.MOT_CFG)
const HDR = (window.MOT_CFG && window.MOT_CFG.hdr) || ['Mutirão de Ordenamento Territorial', 'E-book · edição consolidada'];
const FTR = (window.MOT_CFG && window.MOT_CFG.ftr) || 'MOT · fragmentos.arq.br';
const MM = 96 / 25.4;
const PAGE_W = 210 * MM, PAGE_H = 297 * MM, MARGIN = 0.85 * 96;

function outerH(el) {
  const cs = getComputedStyle(el);
  return el.getBoundingClientRect().height + parseFloat(cs.marginTop || 0) + parseFloat(cs.marginBottom || 0);
}

function mkPage(bleed) {
  const s = document.createElement('section');
  s.className = 'page' + (bleed ? ' bleed' : '');
  s.innerHTML = '<div class="pg-inner"><div class="pg-hdr"><span>' + HDR[0] + '</span><span style="color:#16181a">' + HDR[1] + '</span></div>'
    + '<div class="pg-body"></div>'
    + '<div class="pg-ftr"><span>' + FTR + '</span><b></b></div></div>';
  return s;
}

async function paginate() {
  const t0 = performance.now();
  const placeholder = document.querySelector('doc-page');
  const src = document.getElementById('src');
  const status = document.getElementById('status');
  await document.fonts.ready;

  // régua de medição: mesma geometria da folha, fora do doc-page
  const ruler = document.createElement('div');
  ruler.style.cssText = 'position:absolute;left:-99999px;top:0;width:' + PAGE_W + 'px';
  document.body.appendChild(ruler);
  const probe = mkPage(false);
  probe.style.height = PAGE_H + 'px';
  ruler.appendChild(probe);
  probe.offsetHeight; // força o layout sem depender de rAF
  await new Promise(r => document.hidden ? setTimeout(r, 0) : requestAnimationFrame(() => requestAnimationFrame(r)));
  const band = probe.querySelector('.pg-body').getBoundingClientRect().height;
  probe.remove();
  if (!(band > 200)) { status.textContent = 'ERRO banda ' + Math.round(band); return; }

  // fase 1 — medição única de todos os elementos atômicos
  const items = [];
  for (const blk of [...src.children]) {
    const st = blk.getAttribute('style') || '';
    const isBleed = blk.tagName === 'IMG' || (blk.children.length === 1 && blk.firstElementChild.tagName === 'IMG');
    const isDivider = /min-height:8\.6in/.test(st);
    if (isBleed) { items.push({kind: 'bleed', node: blk.tagName === 'IMG' ? blk : blk.firstElementChild}); continue; }
    if (isDivider) { items.push({kind: 'divider', node: blk}); continue; }
    items.push({kind: 'docstart'});
    for (const k of [...blk.children]) {
      if (outerH(k) > band && k.children.length > 1) {
        for (const gk of [...k.children]) items.push({kind: 'node', node: gk, h: outerH(gk), shell: k});
      } else {
        items.push({kind: 'node', node: k, h: outerH(k)});
      }
    }
  }
  status.textContent = 'Montando… ' + items.length + ' elementos';

  // fase 2 — agrupa em folhas
  const groups = [];
  let g = null, used = 0;
  const flush = () => { if (g && g.items.length) groups.push(g); g = null; used = 0; };
  for (let ix = 0; ix < items.length; ix++) {
    const it = items[ix];
    if (it.kind === 'bleed') { flush(); groups.push({kind: 'bleed', node: it.node}); continue; }
    if (it.kind === 'divider') { flush(); groups.push({kind: 'divider', node: it.node}); continue; }
    if (it.kind === 'docstart') { flush(); g = {kind: 'flow', items: []}; used = 0; continue; }
    if (!g) { g = {kind: 'flow', items: []}; used = 0; }
    // v1.3: título não fica sozinho no pé da página — vai junto com o bloco seguinte
    const nx = items[ix + 1];
    const isHead = it.node && /^H[1-4]$/.test(it.node.tagName);
    const keep = isHead && nx && nx.kind === 'node' ? (it.h + nx.h <= band ? nx.h : 0) : 0;
    if (used + it.h + keep > band && g.items.length) { groups.push(g); g = {kind: 'flow', items: []}; used = 0; }
    g.items.push(it);
    used += it.h;
  }
  flush();

  // fase 3 — monta as folhas num doc-page NOVO, para o componente
  // enxergar as .page como filhos e entrar em modo paginado
  const dp = document.createElement('doc-page');
  dp.setAttribute('size', 'a4');
  dp.setAttribute('margin', '0');
  const pages = [];
  for (const gr of groups) {
    if (gr.kind === 'bleed') {
      const pg = mkPage(true);
      gr.node.style.cssText = 'display:block;width:100%;height:100%;object-fit:cover';
      pg.querySelector('.pg-body').appendChild(gr.node);
      pg.dataset.forced = '1';
      dp.appendChild(pg); pages.push(pg); continue;
    }
    if (gr.kind === 'divider') {
      const pg = mkPage(false);
      const bd = pg.querySelector('.pg-body');
      bd.style.display = 'flex';
      gr.node.style.minHeight = '0';
      gr.node.style.flex = '1 1 auto';
      bd.appendChild(gr.node);
      pg.dataset.forced = '1';
      if (gr.node.dataset && gr.node.dataset.nochrome === '1') pg.classList.add('nochrome');
      dp.appendChild(pg); pages.push(pg); continue;
    }
    const pg = mkPage(false);
    const bd = pg.querySelector('.pg-body');
    let shell = null, shellEl = null;
    for (const it of gr.items) {
      if (it.shell) {
        if (shell !== it.shell) { shell = it.shell; shellEl = it.shell.cloneNode(false); bd.appendChild(shellEl); }
        shellEl.appendChild(it.node);
      } else { shell = null; bd.appendChild(it.node); }
    }
    dp.appendChild(pg); pages.push(pg);
  }
  placeholder.replaceWith(dp);
  ruler.remove();
  // o componente detecta a paginação num requestAnimationFrame, que não
  // dispara em aba oculta — dispara a medição direto
  if (typeof dp._measure === 'function') dp._measure();
  dp.offsetHeight;
  await new Promise(r => document.hidden ? setTimeout(r, 0) : requestAnimationFrame(r));
  if (typeof dp._measure === 'function') dp._measure();
  window.__docPage = dp;

  // fase 4 — corrige transbordos com a geometria real da folha impressa
  for (let i = 0; i < pages.length; i++) {
    const pg = pages[i];
    if (pg.classList.contains('bleed')) continue;
    const bd = pg.querySelector('.pg-body');

    // tabela sozinha maior que a folha: fatia por linhas, repetindo o cabeçalho
    if (bd.childElementCount === 1 && bd.firstElementChild.tagName === 'TABLE' && bd.scrollHeight > bd.clientHeight + 1) {
      const tbl = bd.firstElementChild;
      const tb = tbl.tBodies[0];
      let g2 = 0;
      while (bd.scrollHeight > bd.clientHeight + 1 && tb && tb.rows.length > 1 && g2++ < 300) {
        const row = tb.rows[tb.rows.length - 1];
        let next = pages[i + 1];
        const contOf = (pp) => pp && pp.querySelector('.pg-body > table[data-cont="1"]');
        if (!next || next.classList.contains('bleed') || next.dataset.forced === '1' || !contOf(next)) {
          next = mkPage(false);
          pg.after(next);
          pages.splice(i + 1, 0, next);
          const cont = tbl.cloneNode(false);
          cont.dataset.cont = '1';
          if (tbl.tHead) cont.appendChild(tbl.tHead.cloneNode(true));
          cont.appendChild(document.createElement('tbody'));
          next.querySelector('.pg-body').appendChild(cont);
        }
        contOf(next).tBodies[0].prepend(row);
      }
    }

    let guard = 0;
    while (bd.scrollHeight > bd.clientHeight + 1 && bd.childElementCount > 1 && guard++ < 80) {
      const moved = bd.lastElementChild;
      let next = pages[i + 1];
      if (!next || next.classList.contains('bleed') || next.dataset.forced === '1') {
        next = mkPage(false);
        pg.after(next);
        pages.splice(i + 1, 0, next);
      }
      next.querySelector('.pg-body').prepend(moved);
    }
  }

  // remove folhas vazias e numera
  const live = pages.filter(pg => {
    const bd = pg.querySelector('.pg-body');
    if (!pg.classList.contains('bleed') && bd.childElementCount === 0) { pg.remove(); return false; }
    return true;
  });
  live.forEach((pg, i) => { const n = pg.querySelector('.pg-ftr b'); if (n) n.textContent = String(i + 1); });
  src.remove();

  // sumário: preenche os números reais
  const norm = t => (t || '').replace(/\s+/g, ' ').trim().toLowerCase();
  const titleMap = new Map();
  live.forEach((pg, i) => {
    pg.querySelectorAll('h2').forEach(h => {
      const k = norm(h.textContent);
      if (k && !titleMap.has(k)) titleMap.set(k, i + 1);
    });
  });
  const sumHead = [...document.querySelectorAll('doc-page .page h2')].find(h => norm(h.textContent) === 'sumário');
  if (sumHead) {
    const grid = sumHead.parentElement.querySelector('div');
    [...(grid ? grid.children : [])].forEach(row => {
      const raw = norm(row.textContent).replace(/^estágio \d+ · /, '');
      let n = titleMap.get(raw);
      if (!n) for (const [k, v] of titleMap) { if (k.startsWith(raw) || raw.startsWith(k)) { n = v; break; } }
      if (!n) return;
      const txt = row.textContent;
      row.textContent = '';
      row.style.display = 'flex';
      row.style.alignItems = 'baseline';
      row.style.gap = '8px';
      const s1 = document.createElement('span'); s1.textContent = txt;
      const s2 = document.createElement('span'); s2.style.cssText = 'flex:1;border-bottom:.5px dotted #b9b5ae';
      const s3 = document.createElement('span'); s3.textContent = String(n);
      s3.style.cssText = 'font-variant-numeric:tabular-nums;color:#5f6367';
      row.append(s1, s2, s3);
    });
    const nota = [...sumHead.parentElement.querySelectorAll('p')].find(x => /números de página são gerados/i.test(x.textContent));
    if (nota) nota.remove();
  }

  window.__pageIndex = live.map((pg, i) => ({n: i + 1, t: (pg.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60)}));
  status.textContent = live.length + ' páginas · ' + Math.round(performance.now() - t0) + 'ms';
}

let running = false;
async function ensurePaginated() {
  if (running || window.__pageIndex) return;
  running = true;
  try { await paginate(); } finally { running = false; }
}
if (document.readyState === 'complete') ensurePaginated(); else window.addEventListener('load', ensurePaginated);
document.addEventListener('visibilitychange', ensurePaginated);
window.addEventListener('beforeprint', () => {
  ensurePaginated();
  const dp = window.__docPage || document.querySelector('doc-page');
  if (dp && typeof dp._measure === 'function') dp._measure();
});
