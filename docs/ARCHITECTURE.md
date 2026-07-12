# Compare-Docs — Arquitetura e Contratos

App local: backend Python (FastAPI) + frontend HTML/JS puro servido pelo backend.
**Python 3.13+** (recomendado **3.14** via Homebrew) — todo arquivo `.py` começa com `from __future__ import annotations`;
proibido `match`, proibido `X | None` fora de annotations; usar `typing.Optional/List/Dict`.
Venv: `.venv/` na raiz. Libs: fastapi, uvicorn, python-docx, PyMuPDF (fitz), reportlab, openpyxl.

## Estrutura

```
app/
  models.py              # CONTRATO CENTRAL — leia antes de tudo. Não alterar.
  extract/
    extract/docx_extractor.py    # extract_docx(path) -> Document
    extract/pdf_extractor.py     # extract_pdf(path) -> Document
    extract/xlsx_extractor.py    # extract_xlsx(path) -> Document
    loader.py            # load_document(path) -> Document  (dispatch por extensão)
  engine/
    align.py             # alinhamento de blocos + detecção de movimentação
    worddiff.py          # diff palavra-a-palavra preservando formatação (runs)
    classify.py          # classificação ruído vs conteúdo
    compare.py           # compare_documents(base, compare) -> ComparisonResult
  output/
    naming.py            # nomes padronizados de saída
    redline_pdf.py       # write_redline_pdf(result, out_path, changed_pages_only=False)
    redline_docx.py      # write_redline_docx(result, out_path)
    report.py            # write_html_report / write_xlsx_report / write_json_report
  batch.py               # pair_files(base_dir, compare_dir) -> (pairs, unmatched_base, unmatched_compare)
  jobs.py                # JobManager: fila em thread, progresso, resiliência por item
  main.py                # FastAPI: rotas + serve web/index.html
desktop/
  app.py                 # UI nativa CustomTkinter (mesmo JobManager, sem HTTP)
  controller.py          # Orquestração local para a versão desktop
  theme.py               # Tema, fontes e animações
web/
  index.html             # SPA completa (CSS+JS inline), UI em pt-BR
tests/
  make_samples.py        # gera pares DOCX e PDF de exemplo com diferenças conhecidas
  test_e2e.py            # roda pipeline completo nos samples e valida
```

## Contratos de função (assinaturas exatas)

```python
# app/extract/loader.py
def load_document(path: str) -> Document  # .docx / .pdf / .xlsx; erro claro p/ outros

# app/engine/compare.py
def compare_documents(base: Document, compare: Document) -> ComparisonResult
# - chama assign_section_paths() nos dois documentos
# - alinha blocos (align.py), roda worddiff nos pares MODIFY, classifica tudo (classify.py)
# - preenche changes, render_blocks, stats (compared_at/duration ficam com o chamador)

# app/output/naming.py
def redline_pdf_name(base_path: str, compare_path: str) -> str      # "[Redline] {base} vs {compare}.pdf"
def changed_pages_pdf_name(base_path: str, compare_path: str) -> str  # "[Redline-Changed Pages] ..."
def redline_docx_name(...) -> str                                    # "[Redline] ....docx"
def report_name(base_path, compare_path, ext) -> str                 # "[Report] ....{html|xlsx|json}"
# {base}/{compare} = stem do arquivo sem extensão, sanitizado

# app/output/redline_pdf.py
def write_redline_pdf(result: ComparisonResult, out_path: str, changed_pages_only: bool = False) -> None

# app/output/redline_docx.py
def write_redline_docx(result: ComparisonResult, out_path: str) -> None

# app/output/report.py
def write_html_report(result: ComparisonResult, out_path: str) -> None
def write_xlsx_report(result: ComparisonResult, out_path: str) -> None
def write_json_report(result: ComparisonResult, out_path: str) -> None

# app/batch.py
def pair_files(base_dir: str, compare_dir: str) -> Tuple[List[Tuple[str, str]], List[str], List[str]]
# pareia em 3 passos: (1) stem normalizado igual (caixa/espaços/sufixos " v2", "_rev",
# "(1)" ignorados); (2) similaridade de nome >= 0.85; (3) CONTEÚDO — órfãos dos dois
# lados têm o texto inicial extraído (~6k chars) e pareiam por similaridade >= 0.55,
# guloso por melhor score, até 50 arquivos por lado. Dispensa renomear documentos.
# Retorna também não-pareados de cada lado.
```

## Motor de comparação — regras de qualidade (o coração do produto)

1. **Alinhamento em 3 passes** (align.py) — regras calibradas contra o Word Compare
   em contrato real (tests/fixtures/escorrega):
   - Pass 1: LCS/SequenceMatcher sobre `content_hash()` dos blocos → EQUAL exatos.
   - Pass 2: CONFINADO aos vãos entre âncoras do pass 1 (nunca cruza vãos), melhor
     ratio primeiro (threshold 0.55), com guarda de não-cruzamento dentro do vão.
     EQUAL exige hash igual; ratio alto (ex.: 0.99) ainda é MODIFY — senão edições
     de uma palavra em parágrafo longo somem do redline.
   - Pass 3: órfãos dos dois lados, hash igual → MOVE; ratio > 0.85 → MOVE_MODIFY.
   - Pós-passe: MOVE de verdade é INVERSÃO de ordem — par "movido" que não cruza
     nenhuma outra âncora foi só deslocado por inserções vizinhas e é rebaixado
     para EQUAL/MODIFY (nada de falso-movido). Índice absoluto NUNCA decide MOVE.
2. **Diff de palavras preservando formatação** (worddiff.py):
   - Tokeniza os runs em palavras+espaços SEM perder a formatação de cada token
     (cada token sabe de qual Run veio).
   - SequenceMatcher sobre a sequência de textos dos tokens; pontes equal de até
     2 palavras entre edições são absorvidas. REGRA DO PRODUTO (usuário,
     2026-07-12): nunca apresentar palavra idêntica como excluída+reinserida;
     destacar SOMENTE o efetivamente alterado; NUNCA omitir uma exclusão.
   - Replace com texto normalizado IGUAL nos dois lados vira equal (mata o diff
     "fantasma" causado por quebras de run/tab/espaçamento).
   - REGRA DOS 30% (usuário, 2026-07-12): dentro de um replace, palavras antigas
     e novas pareiam por semelhança usando 30% de caracteres alterados (sobre a
     maior palavra) como limiar. Par ≤30% → marca fina de caractere (com limpeza
     semântica: ilhas equal < 3 chars fundem); palavra sem par → excluída/inserida
     POR INTEIRO. Um único critério, uniforme: "Luís-MA"→"Luís/MA" marca só o
     hífen; "cool"→"cooler" (33%) e sinônimos trocam a palavra inteira;
     "as a result of"→"resulting from" nunca recicla letras.
   - NUMERAÇÃO AUTOMÁTICA (numbering.xml): o extrator DOCX resolve o rótulo
     efetivo de cada parágrafo numerado (Block.list_label; entra no content_hash
     como "rótulo texto", compatível com PDF). Renumeração ((a)→(b)) vira Change
     CONTENT "Numeração alterada de X para Y"; no DOCX fiel o rótulo antigo sai
     tachado após o auto-número novo (o insert do rótulo novo é aparado para não
     duplicar com a numeração do Word).
   - Saída: `List[Fragment]` — equal/insert usam formatação do doc revisado;
     delete usa formatação do doc base. Fragmentos adjacentes com mesmo op+estilo são fundidos.
3. **Classificação** (classify.py) — cada Change recebe UMA Category:
   - mesmo texto normalizado, formatação diferente → FORMATTING
   - diff só em datas (regex dd/mm/aaaa, "12 de março de 2026", ISO, etc.) → NOISE_DATE
   - diff só em padrões de versão (v1.2, "Versão 3", "Rev. B") → NOISE_VERSION
   - diff só em números de página ("Página X de Y", "p. 12") → NOISE_PAGENUM
   - diferença só de espaços → NOISE_WHITESPACE; só caixa/pontuação → NOISE_PUNCT
   - tabela → TABLE; imagem → IMAGE; resto → CONTENT
   - A decisão "só em X" = remova os trechos alterados que casam com o padrão;
     se não sobra alteração alguma, é ruído daquele tipo.
4. **Tabelas**: alinhamento de linhas com a MESMA arquitetura dos blocos
   (âncoras exatas → similaridade confinada aos vãos, sem cruzamento);
   linha inserida/removida/modificada; célula a célula diff de palavras →
   RenderBlock.rows com row_ops. CellChange registrado no Change.
   No redline DOCX in-place, linha excluída é INSERIDA fisicamente na tabela
   (tachada) — mapear por índice esconderia exclusões e marcaria linhas erradas.
5. **Imagens**: comparar por hash; trocada = MODIFY/IMAGE; summary tipo "Imagem substituída".
6. **render_blocks**: fluxo na ordem do doc revisado; DELETE entra na posição alinhada;
   MOVE aparece marcado na posição nova (e o Change registra de/para).
7. **Páginas**: PDF traz page real por bloco. DOCX não tem página na extração —
   page fica None e o redline_pdf calcula "páginas alteradas" pelo layout FINAL
   gerado (ver abaixo). Stats.changed_pages: páginas do doc revisado com mudança
   (PDF: direto dos blocos; DOCX: preenchido pelo redline_pdf após render — o
   orquestrador em jobs.py chama `write_redline_pdf` que RETORNA via
   `result.stats.changed_pages` quando a lista estiver vazia e houver mudanças).

## Redline PDF (ReportLab, platypus)

- Fluxo do documento com estilos: título do doc, headings por nível, parágrafos justificados.
- Marcação: INSERT = azul sublinhado; DELETE = vermelho tachado; MOVE = verde (± sufixo "[movido]");
  FORMATTING = realce discreto (fundo amarelo claro). Categorias de ruído têm a mesma
  marcação visual mas aparecem no sumário como "rotineiras".
- Tabelas renderizadas como Table do platypus com células marcadas; linha inserida com fundo
  azul-claro, removida com fundo vermelho-claro e texto tachado.
- **Página de síntese ao final** (sempre): tabela com data da comparação, arquivos, total por tipo,
  total conteúdo vs ruído vs formatação, páginas afetadas.
- `changed_pages_only=True`: renderiza apenas blocos com mudança + 1 bloco de contexto
  antes/depois + títulos da seção (breadcrumb), depois a página de síntese.
- Legenda das marcações na primeira página (faixa discreta).

## Relatório analítico

- HTML: arquivo único auto-contido, abas (Todas | Só mudanças de conteúdo | Tabelas/Imagens |
  Estatísticas), filtros por categoria/tipo, coluna de seção (breadcrumb), lado a lado
  old/new com diff inline, dark/light. Sem dependências externas.
- XLSX (openpyxl): aba "Mudanças" (id, tipo, categoria, seção, página, texto antigo, texto novo,
  resumo), aba "Estatísticas". Cabeçalho formatado, colunas largas, filtro automático.
- JSON: `result.to_dict()` com indent=2, ensure_ascii=False.

## API (main.py) — contrato frontend↔backend

```
GET  /                          → web/index.html
GET  /api/health                → {"ok": true}
POST /api/compare/single        → multipart: base_file, compare_file (uploads) e campos de opções
                                  OU JSON {base_path, compare_path, options} p/ caminhos locais
                                  → {"job_id": "..."}
POST /api/compare/batch         → JSON {base_dir, compare_dir, options} → {"job_id": "..."}
GET  /api/jobs/{job_id}         → {"status": "running|done|error", "progress": {"done": n, "total": m,
                                   "current": "nome"}, "items": [{"pair": [b,c], "status": "ok|error",
                                   "error": null|"msg", "outputs": {"pdf": path, ...},
                                   "stats": {...}}], "summary": {"ok": n, "failed": n, "seconds": s}}
GET  /api/jobs/{job_id}/result/{index} → ComparisonResult.to_dict() do par (p/ o visualizador)
POST /api/open                  → JSON {"path": ...} → abre com `open` (macOS) / xdg-open. Valida
                                  que o path foi gerado por um job desta sessão (whitelist em memória)
                                  OU consta nos outputs do histórico persistente (pós-restart).
GET    /api/history?limit=200   → {"entries": [...]} — histórico persistente, mais recente primeiro
                                  (app/history.py; arquivo ~/.comparedocs/history.json, cap 500,
                                  escrita atômica; jobs.py grava uma entrada por par processado)
DELETE /api/history/{id}        → remove uma entrada; DELETE /api/history limpa tudo
POST /api/batch/preview         → {base_dir, compare_dir, swap?} → {pairs: [{base, compare,
                                   base_name, compare_name, method: nome|similaridade|conteúdo}],
                                   unmatched_base, unmatched_compare} — prévia, nada é processado
GET/POST/DELETE /api/branding[/logo] → logo do escritório (white-label, feature "branding" do
                                   plano Equipe; app/branding.py; PNG/JPEG ≤1MB em
                                   ~/.comparedocs/branding/); aparece no PDF padronizado,
                                   resumo executivo e relatório HTML
GET  /api/license/status        → {state: trial|active|expired|locked, plan, email, key_hint,
                                   expires_at, features, device, trial:{days_left,comparisons_left}}
POST /api/license/activate      → {email, key} → status (assina no servidor, verifica Ed25519
                                   no app, grava ~/.comparedocs/license.json); 400 c/ detail pt-BR
POST /api/license/deactivate    → libera o slot de dispositivo no servidor e remove a local
GET  /api/plans                 → catálogo p/ a aba Planos (app/licensing/plans.py)
POST /api/compare/*             → retornam 402 {detail} quando trial esgotado/licença expirada
POST /api/swap-preview          → não existe; swap é client-side (o front só troca os campos)
```

Servidor de licenças: `licensing_server/` (FastAPI separado, porta 8390, SQLite em
~/.comparedocs-server/). Endpoints /v1/activate, /v1/validate, /v1/deactivate; payloads
assinados Ed25519 (privada no servidor, pública embutida em app/licensing/pubkey.py).
Cliente: app/licensing/client.py (estados trial/active/expired/locked, trial local
14 dias/25 comparações, revalidação online 1x/24h, tolerância offline de 7 dias).

Opções (`options`): `{"changed_pages_only": bool, "export_docx": bool, "exec_summary": bool,
"reports": ["html","xlsx","json"], "output_dir": str|null}`. `exec_summary` gera
"[Resumo] {base} vs {compare}.pdf" (1 página; app/output/exec_summary.py, reusa app/ai/insights).
`output_dir` default: `<raiz do projeto>/output/<timestamp>-<slug>/`.
Uploads vão para tempdir antes de processar.
Batch: falha em um par NÃO derruba o lote (try/except por item, erro registrado no item).
JobManager roda em `threading.Thread`, jobs em dict com lock, progress atualizado por item.

## Frontend (web/index.html) — pt-BR, arquivo único

- Visual profissional moderno: header com nome do produto, toggle dark/light (persistido em
  localStorage), duas abas: **Arquivo único** e **Lote (pastas)**.
- Arquivo único: duas dropzones (Base | Revisado) com estado visual (vazio/preenchido/erro),
  botão ⇄ para inverter, opções (checkboxes), botão "Comparar".
- Lote: dois inputs de caminho de pasta (Base | Revisada), botão ⇄, mesmas opções.
- Progresso: barra + "n de m — nome do arquivo atual", polling em /api/jobs/{id} a cada 700ms.
- Resultados: card por par com stats resumidas (X conteúdo, Y ruído, Z formatação), botões
  "Abrir PDF", "Abrir relatório", "Ver mudanças" e erros destacados sem bloquear o resto.
- "Ver mudanças": painel embutido que busca /api/jobs/{id}/result/{i} e mostra a lista de
  mudanças com filtros por categoria (chips), breadcrumb de seção, diff inline colorido
  e visão lado a lado (old | new).
- Guia de uso embutido (botão "?" abre modal com passo-a-passo).
- Zero dependências externas (sem CDN). CSS custom properties p/ tema.

## Convenções

- Mensagens de erro e UI em pt-BR; código/identificadores em inglês.
- Nenhum módulo importa de main.py. output/* e engine/* não importam FastAPI.
- Logging via `logging.getLogger(__name__)`.
