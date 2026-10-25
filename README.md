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
