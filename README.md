# Documentos do MOT

Fonte única do e-book do Método MOT e gerador dos documentos para download em
[fragmentos.arq.br/mot-app](https://www.fragmentos.arq.br/mot-app).

- `fonte/ebook.dc.html` — o e-book (projeto do Claude Design). **É o único lugar onde o texto muda.**
- `gerador/documentos.json` — onde começa cada documento individual e a lista de termos aposentados.
- `gerador/gerar.py` — gera o e-book completo e os 10 documentos, com a mesma paginação e identidade visual.

A cada merge no `main`, o GitHub gera tudo e publica em endereços fixos
(`https://fragmentosurb-del.github.io/mot-docs/<arquivo>.pdf`). Os links do site apontam
para esses endereços, então não é preciso subir PDF no Wix.

Antes de publicar, o gerador **falha** se:
- encontrar um termo aposentado no texto (ex.: "princípio conservador");
- não achar o começo de algum documento;
- alguma página de um documento individual diferir da página correspondente do e-book.

Gerar localmente: `python3 gerador/gerar.py` (requer `beautifulsoup4`, `lxml`, `pypdf`, `playwright`).

## Vigia semanal

Toda segunda-feira, às 8h37 (Brasília), `gerador/vigia.py` confere:
- se a página [mot-app](https://www.fragmentos.arq.br/mot-app) tem link para o e-book e para os 10 documentos, e se todos os links abrem;
- se algum link ainda aponta para um PDF antigo do Wix;
- se o texto da página tem termo aposentado (`termos_aposentados` e `termos_pagina`, em `gerador/documentos.json`);
- se o Pergunte ao MOT usa a mesma versão e a mesma paginação do e-book no ar.

Se achar algum problema, o vigia abre uma issue com a etiqueta `vigia` e o GitHub avisa por e-mail. Enquanto o problema continuar, ele comenta na mesma issue; quando tudo estiver certo, ele fecha a issue sozinho. Para rodar fora da agenda: Actions → "Vigia semanal da página mot-app" → Run workflow.
