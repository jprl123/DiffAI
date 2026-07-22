# Handoff — o que fizemos depois do Claude (landing + Railway + app)

Documento para retomar o fio: o Claude tinha começado a landing; a partir daí fechámos deploy, licenças, Stripe, e-mail, download do Mac e builds de teste.

Última atualização: 2026-07-13.

---

## 1. Visão geral do produto

| Peça | Onde | URL / pasta |
|------|------|-------------|
| Landing Next.js | **Vercel** | https://comparedocs-landing.vercel.app — código em `landing/` |
| API de licenças | **Railway** | https://diffai-production.up.railway.app |
| App desktop Mac | PyInstaller → GitHub Releases | `diffAI.app` / ZIP |
| Repo GitHub | público (para downloads) | https://github.com/jprl123/DiffAI |
| Domínio próprio | GoDaddy → Vercel (DNS ainda a fechar) | `diffai.app` |

**Regra de ouro:** landing na Vercel; API **não** é serverless — fica na Railway (processo longo + SQLite).

```
Site (Vercel)
  ├─ Baixar Mac     → GitHub Release (ZIP)
  ├─ Assinar        → Railway /v1/checkout/{pro|team} → Stripe
  └─ /conta         → Railway (ativar chave, dispositivos)

App desktop
  └─ ativa/valida   → mesma API Railway (HTTPS embutida)
```

---

## 2. O que o Claude tinha começado

- Landing Next.js (pasta que depois virou `landing/`; antes tinha nome longo tipo template).
- UI de marketing, planos, CTAs.
- Ainda **não** estava: Root Directory certo na Vercel, API Railway estável, Stripe/webhook, Resend, download real do `.app`, Gatekeeper, bug dos templates `python-docx`.

---

## 3. O que fechámos depois (cronologia útil)

### 3.1 Landing / Vercel
- Root Directory do projeto = **`landing`** (senão build 404).
- Install: **`npm ci`** (não pnpm — lock desatualizado).
- Marca **diffAI** / domínio `diffai.app`.
- Portal **`/conta`**: e-mail + chave `CDOC-…` (sem senha).
- Confirmação pós-checkout: `/conta?checkout=ok`.
- Env pública crítica:
  - `NEXT_PUBLIC_LICENSE_API=https://diffai-production.up.railway.app`  
    (**sem** `/` no final — senão vira `//v1/...` e 404)
  - Download Mac (fallback no código): release **v0.1.1** ZIP  
    `https://github.com/jprl123/DiffAI/releases/download/v0.1.1/diffAI-mac.zip`
- Windows: ainda sem build (`NEXT_PUBLIC_DOWNLOAD_URL_WINDOWS` vazio).

### 3.2 Railway (API de licenças)
- Serviço a partir do repo + **Dockerfile** na raiz (não Nixpacks).
- Removido `VOLUME` do Dockerfile (Railway não aceita; volume monta-se no painel em `/data`).
- Health: `GET https://diffai-production.up.railway.app/v1/health`  
  (raiz `/` = `Not Found` é **normal**).
- Checkout: `/v1/checkout/pro` (e team).
- Webhook Stripe: `…/v1/stripe/webhook`.
- Health expandido mostra flags se Stripe/Resend estão configurados.

### 3.3 Stripe + e-mail da chave
- Stripe em **test mode** (`sk_test_…`, prices `price_…`).
- Após pagamento: webhook → emite chave → e-mail via **Resend**.
- Em teste, `MAIL_TO_OVERRIDE` pode redirecionar todos os e-mails para o teu endereço.
- **E-mail da chave já funcionou** no fluxo real de teste.

### 3.4 App desktop
- `DEFAULT_SERVER_URL` embutida:  
  `https://diffai-production.up.railway.app` (`app/licensing/server_url.py`).
- Build: `./scripts/build_desktop.sh` → `dist/diffAI.app` + ZIP (+ DMG se `hdiutil` ok).
- Release pública: **v0.1.0** (ZIP ok; DMG no CDN GitHub deu 404) e **v0.1.1** (ZIP com fix docx).
- Landing aponta para ZIP (não DMG).
- Gatekeeper: Mac diz “danificado” sem notarização →  
  `xattr -cr ~/Downloads/diffAI.app`
- Bug corrigido no v0.1.1: templates `python-docx` (`default-header.xml`) — pasta `parts` em falta no bundle → ENOENT ao comparar DOCX.

### 3.5 Motor / Summary (mudanças no código)
- Total no **Summary of Changes** = **inserções + exclusões + movimentações** (não `len(changes)`).
- Linha avulsa “Modificações” (in-place) saiu da tabela final da síntese.
- **PDF×PDF pelo pipeline Word (PRONTO, 2026-07-13)**: par `.pdf` converte via `pdf2docx`
  (`app/extract/pdf_to_docx.py`) e segue o fluxo fiel (redline in-place + LibreOffice).
  Fallback p/ layout padronizado se PDF escaneado/protegido. Testes em `tests/test_e2e.py`.
  ⚠ Release nova do `.app` precisa incluir `pdf2docx` (+~50 MB por opencv-headless).

### 3.5a Aceite automático de track changes pendentes (2026-07-13)
- Documento de entrada com marcas de revisão NÃO aceitas (caso real: doc da
  Sharpi) quebrava a comparação: texto em `w:ins` era invisível ao extrator e
  as marcas antigas poluíam o redline in-place.
- Agora `app/jobs.py::_accept_pending_revisions` detecta e aceita TODAS as
  revisões de ambos os lados em cópia temporária antes de extrair/comparar
  (`app/extract/docx_revisions.py`, nível zip/XML: document + headers/footers/
  footnotes; unwrap de w:ins/moveTo, remoção de w:del/moveFrom, merge de
  parágrafo com marca deletada, linha de tabela deletada, registros *Change).
- O arquivo original do usuário NUNCA é modificado; o item ganha warning
  informativo na UI. Falha no aceite → segue com o arquivo como está.
- Testes: `tests/test_docx_revisions.py`.

### 3.5a2 PDF nativo: pseudo-tabelas achatadas (B3, 2026-07-15)
- Sintoma: redline de par PDF×PDF "quebrado" (parágrafos com palavras
  espalhadas/partidas, vãos enormes) — ex.: CONSIDERANDOS do Teste_30.
- Causa: em PDF NATIVO, o pdf2docx envolve parágrafos corridos em TABELAS
  (uma palavra por célula). Não é stream-table (esse já vem off por default);
  é detecção de borda espúria (lattice). 10 "tabelas" onde havia 3 reais.
- Fix: `app/extract/pdf_to_docx.py::_flatten_pseudo_tables` roda após a
  conversão e desmonta as pseudo-tabelas de volta a parágrafos, preservando
  runs. Critério `_is_pseudo_table`: 1 linha, OU ≥5 colunas com ≥60% de
  células de uma palavra. Tabelas reais (2–4 col, multi-linha) intactas.
  Também deduplica células idênticas adjacentes (pdf2docx duplica palavras
  em cláusulas densas — origem do B1 na 11.1/confidencialidade).
- Verificado no par Teste_30 (prosa legível, tabela de pagamentos preservada
  com redline). Testes: `tests/test_pdf_flatten.py`.
- Backlog do relatório `Analise_Redlines_PDF_45_testes.md` (pendente, motor
  compartilhado c/ DOCX — fazer 1 a 1 com validação): B2 (del+ins de texto
  idêntico), B4 (espaços colados na extração), B1 (invariante não-perda),
  B5 (comentários/anotações), exportador (tabelas/imagens), padronizações da
  Rodada 2 (regra dos 30%, números inteiros).

### 3.5a3 Contagem do Summary — trechos contínuos (2026-07-15)
- Sintoma (relatório Analise_Redline_Consolidado, testes 01–20): o rodapé
  subestimava — mostrava "5 (2/1/2)" onde a regra dá "22 (10/10/2)". Contava
  só parágrafos INSERT/DELETE inteiros e ignorava todo trecho inline (valor,
  data, %, prazo, caixa-alta, célula, nova linha de tabela).
- Fix em `app/engine/compare.py::_build_stats` (+ `_count_fragment_runs`,
  `_count_block_runs`): inserções/exclusões agora contam TRECHOS CONTÍNUOS de
  fragmentos nos render_blocks — parágrafo inteiro, inline, célula alterada
  (1 del + 1 ins), linha de tabela nova/removida. Movimentações e categorias
  seguem por Change. Blocos movidos não inflam ins/del. total = ins+del+mov.
- Verificado: Teste_01 DOCX 11/10/2=23 (esperado 10/10/2=22) e Teste_03
  11/9/2=22 (esperado 21) — o +1 é a cláusula de arbitragem (título+parágrafo
  = 2 blocos inseridos), que o gabarito manual contou como 1. Antes: ~5.
  Testes: `tests/test_stats_counting.py`. test_e2e (19) e invariante intactos.

### 3.5a4 Números trocados por inteiro + B2 resolvido (2026-07-15)
- **Números/valores/datas (Rodada 2)**: em `app/engine/worddiff.py`, tokens com
  dígito nunca recebem marca fina de caractere — sai o antigo inteiro + entra o
  novo inteiro. Fim de "R$ 12.06.500,00" e "20256"; agora "~~12.000,00~~
  16.500,00" e "~~2025~~ 2026". Regra dos 30% mantida para TEXTO. Números
  pareiam por posição (troca inteira, ordem delete→insert). Testes novos em
  `tests/test_worddiff.py`.
- **B2 (del+ins de texto idêntico) — verificado RESOLVIDO pelo B3**: no
  Teste_30 (nativo) a frase-símbolo da 17.1 ("perdas e danos suplementares")
  voltou a ser bloco `equal` sem marcação. O flatten das pseudo-tabelas
  limpou o desalinhamento perto do bloco movido. Nenhum fix adicional feito.
- **B4 (espaços colados) — NÃO corrigir por regex**: a origem é quebra de
  linha (PyMuPDF: "sob o nº\n39.129"), e o pdf2docx junta as linhas sem
  espaço. Um regex-fix quebraria hifenização ("estabele-\ncidas") e criaria
  DIFERENÇAS FALSAS entre v1/v2. Fica como cosmético do caminho PDF nativo.
- **Regra dos 30% MANTIDA (decisão do usuário 2026-07-15)**: os 5 testes de
  `tests/test_worddiff.py` que contradiziam a regra foram REESCRITOS para
  fixar o comportamento da regra (marca fina p/ mudança pequena; miolo
  idêntico fica equal). Suíte de motor agora 44/44 (zero falhas).
- Bônus: guarda em `_refine_replace` — região sem NENHUM par ≤30% devolve
  None → replace inteiro na ordem convencional (delete antigo → insert novo);
  corrige a ordem invertida que aparecia em troca total de múltiplas palavras.

### 3.5b Pareamento do lote — 100% local (IA REMOVIDA em 2026-07-14)
- O pareamento por embeddings OpenAI foi **removido a pedido do usuário** (item 4
  do roadmap Smart Compare): mais previsível, rápido e sem depender de API/chave.
  Apagados `app/ai/pairing.py`, o passo 4 em `batch.py`, o teste mockado e a seção
  `OPENAI_API_KEY` do `.env` (chave estava comprometida). `app/ai/insights.py`
  (insights locais) NÃO tem relação e permanece.
- `pair_files` agora tem 3 passos, todos locais: nome → similaridade de nome →
  conteúdo (difflib). Métodos na prévia: "nome" | "similaridade" | "conteúdo".
- **Auto-descoberta da pasta revisada** (lógica pura, mantida): ao definir só a pasta
  base no Lote, o app sugere a pasta irmã (`find_compare_dir` em `app/batch.py`,
  endpoint `POST /api/batch/suggest-compare`, auto-preenchimento + toast). Cobertura
  de nomes + dica no nome da pasta + semelhança; sem candidato confiável → manual.

### 3.5b-i18n Fundação: settings + i18n PT/EN (2026-07-14)
- **Backend de settings**: `app/settings.py` (`~/.comparedocs/settings.json`, atômico,
  como history.py) + `GET/POST /api/settings`. Chaves: `language` (pt|en|null),
  `onboarding_done` (bool), `default_features` (toggles de saída, todos off).
- **i18n na UI** (`web/index.html`): dicionário `STRINGS` pt/en, `t(key)`, aplicação
  via atributos `data-i18n` / `data-i18n-attr`, persistência via `/api/settings`
  (cache em localStorage p/ evitar flash). Modal de escolha de idioma na 1ª execução
  (language==null → obrigatório) + botão "Idioma" na barra lateral p/ trocar depois.
- Cobertura ATUAL (verificada em EN no browser): nav + rodapé; telas Comparar e
  Lote (cabeçalhos, cartões, dropzones single+pasta, opções de saída, botão/nota);
  telas History (cabeçalho, busca, filtros, vazio, "Clear history", rótulos de data
  Hoje/Ontem), Plans (cabeçalho + "Activate now") e Account (cabeçalho); modal de
  ativação de licença; rótulo de tema. Engine suporta `data-i18n`, `data-i18n-html`
  (p/ HTML inline) e `data-i18n-attr` ("attr:chave"). `setLanguage` re-renderiza as
  superfícies dinâmicas (dropzones, botão comparar, histórico).
- **Long tail pendente** (mecânico, próximo incremento): corpo do modal "Guia de uso"
  (bloco grande de prosa), cards da tela Plans e corpo da Account (render em JS),
  telas de "comparando…"/resultado, linhas da prévia de pares do lote, e os toasts.
  Padrão para migrar: trocar `"texto"` por `t("chave")` e adicionar a chave em
  STRINGS pt/en (ou `data-i18n` no HTML estático).

### 3.5c Landing v2 — template completo em inglês (2026-07-13)
- `landing/app/page.tsx` reescrita com as seções/transições do template (RevealText,
  BentoCard c/ glow, marquee, CTA de vidro). Site 100% EN; `/account` = alias de
  `/conta` (SUCCESS_URL do Stripe continua válida); anchor `#planos` mantido.
- Card "sanfona" = `stacking-change-cards.tsx`: 4 tipos de alteração (insertion azul,
  deletion vermelho, move verde, formatting amarelo) com preview de redline em CSS.
- Slots de imagem: `landing/lib/images.ts` mapeia nomes fixos em `public/images/`
  (soltar o arquivo com o nome certo = aparece; sem arquivo = placeholder rotulado).
  Vídeo do hero ainda é o blob remoto do template — trocar via `HERO_VIDEO`.

### 3.6 Build de teste ilimitado (para enviar a alguém)
```bash
./scripts/build_desktop.sh --unlimited
```
- Gera `dist/diffAI-mac-test-unlimited.zip` (também copiado para Downloads).
- Plano **beta**, sem trial, sem limite de lote, sem chave.
- **Não** publicar na landing (é unlock permanente).
- Flag: `app/licensing/build_flags.py` (`UNLIMITED`); o script põe `True` só no empacotamento.

---

## 4. Configuração Railway (checklist)

Detalhe passo a passo: [`docs/RAILWAY.md`](RAILWAY.md).

### Contas / projeto
- Conta GitHub: **jprl123**
- Repo: **DiffAI** (público)
- Builder: **Dockerfile** (path `Dockerfile` na raiz)
- Start: via `scripts/start_licensing_server.sh` (não forçar start command à mão)
- Domínio gerado: `diffai-production.up.railway.app`

### Variáveis (Production) — nomes; valores no painel / `.env` local

| Variável | Função |
|----------|--------|
| `PORTAL_ALLOWED_ORIGINS` | Origens CORS da landing (URL Vercel **exata**, sem `/`) |
| `MAIL_BACKEND` | `resend` (ou `console` em debug) |
| `RESEND_API_KEY` | Chave Resend |
| `MAIL_FROM` | Remetente verificado no Resend |
| `MAIL_TO_OVERRIDE` | (opcional teste) força destino do e-mail da chave |
| `STRIPE_SECRET_KEY` | `sk_test_…` |
| `STRIPE_PRICE_PRO` / `STRIPE_PRICE_TEAM` | `price_…` |
| `STRIPE_WEBHOOK_SECRET` | `whsec_…` do endpoint Railway |
| `SUCCESS_URL` | `https://comparedocs-landing.vercel.app/conta?checkout=ok` |
| `CANCEL_URL` | `https://comparedocs-landing.vercel.app/#planos` |
| `COMPAREDOCS_SIGNING_KEY_PEM` | Chave privada Ed25519 (secret) |
| `COMPAREDOCS_LICENSE_DB` | Tipicamente sob `/data` se houver volume |

**Não** criar `PORT` (Railway injeta).  
**Atenção:** no painel, o valor da env é só o valor — **não** colar `NOME=valor` dentro do campo valor.

### Volume (persistência SQLite)
- Mount path: **`/data`**
- Sem volume: redeploy pode apagar licenças emitidas (aceitável em sandbox; mau em “produção”).

### Endpoints úteis
| Método | Path |
|--------|------|
| GET | `/v1/health` |
| GET | `/v1/checkout/pro` |
| GET | `/v1/checkout/team` |
| POST | `/v1/stripe/webhook` |
| POST | `/v1/activate` / `/v1/validate` / `/v1/deactivate` |
| (portal) | rotas usadas por `/conta` |

---

## 5. Configuração Vercel (landing)

Projeto: **comparedocs-landing** (team `jprl123s-projects`).

| Setting | Valor |
|---------|--------|
| Root Directory | `landing` |
| Framework | Next.js |
| Env | `NEXT_PUBLIC_LICENSE_API` = URL Railway **sem** `/` final |
| Env opcional | `NEXT_PUBLIC_DOWNLOAD_URL_MAC` = URL do ZIP no GitHub Releases |

DNS `diffai.app` (GoDaddy): A `@` → `76.76.21.21` (Vercel) — ainda a estabilizar se não resolver.

Guias: [`docs/VERCEL_CURSOR.md`](VERCEL_CURSOR.md), Stripe [`docs/STRIPE_CURSOR.md`](STRIPE_CURSOR.md).

---

## 6. Licenciamento (modelo)

- Login no app / portal: **e-mail + chave `CDOC-…`** (sem password).
- Assinatura Ed25519; app verifica com `app/licensing/pubkey.py`.
- Trial local: 14 dias / 25 comparações / lote máx. 5 (burlável apagando `~/.comparedocs/trial.json` — conhecido).
- Planos: trial / pro / team / perpetual (features em payload + `licensing_server`).
- Docs: [`docs/LICENCIAMENTO.md`](LICENCIAMENTO.md).

---

## 7. Downloads Mac — estado atual

| Artefacto | Estado |
|-----------|--------|
| ZIP v0.1.1 | Público, botão da landing |
| DMG no GitHub | CDN deu 404 (mesmo listado na release) — usar ZIP |
| Gatekeeper | Sem notarização Apple → `xattr -cr` |
| Windows | Ainda não há instalador |
| Build teste ilimitado | `diffAI-mac-test-unlimited.zip` (local / Downloads) |

Instruções para quem testa o ZIP comercial:
1. Descompactar  
2. `xattr -cr ~/Downloads/diffAI.app`  
3. Abrir / arrastar para Aplicativos  
4. Ativar com e-mail + chave do Resend  

---

## 8. Contas / IDs úteis

| Serviço | Conta / nota |
|---------|----------------|
| GitHub | `jprl123` / repo `DiffAI` |
| Vercel | projeto `comparedocs-landing` |
| Railway | serviço DiffAI → `diffai-production.up.railway.app` |
| Stripe | test mode |
| Resend | e-mail da chave |
| Domínio | GoDaddy `diffai.app` |

---

## 9. Pendências (bom pedir a seguir)

1. **Volume `/data` na Railway** — persistir SQLite de licenças.  
2. **DNS GoDaddy** — `diffai.app` → Vercel estável.  
3. **Notarização Apple** — acabar com “app danificado”.  
4. **Build Windows** + URL na landing.  
5. **Reupload / abandonar DMG** no GitHub (ficar só no ZIP).  
6. **Rodar chaves Ed25519 de produção** se ainda for o par `dev_signing_key` no app (`pubkey.py`).  
7. **Publicar release comercial** com as últimas mudanças do motor (summary, pdf2docx, etc.) — o unlimited local já as inclui; o Release v0.1.1 pode estar atrás do working tree.  
8. Alinhar copy da landing (Gatekeeper / ZIP) se ainda não estiver no deploy de produção.
9. ~~Rotacionar chave OpenAI / proxy de embeddings~~ — **cancelado**: pareamento IA
   removido em 2026-07-14 (item 4). Revogar a chave antiga na OpenAI mesmo assim
   (ela vazou em chat) é higiene, mas o app não usa mais nenhuma chave OpenAI.
10. **Deploy da landing EN na Vercel** + gerar as imagens dos slots (nomes e sugestões
    em `landing/lib/images.ts`; prompts p/ Gemini já entregues em chat 2026-07-13) e
    trocar `HERO_VIDEO` p/ arquivo local quando o vídeo ficar pronto.
11. **Release nova do `.app` com pdf2docx** (PDF×PDF fiel) — rebuild + upload GitHub.

### Roadmap "Smart Compare" (lista do usuário 2026-07-14) — status 2026-07-14

| Item | Status |
|------|--------|
| 1. Idioma PT/EN (1ª abertura + Settings) | **Feito** — `app/settings.py` + modal + seletor |
| 2. Tutorial guiado | **Feito** — walkthrough, “não mostrar de novo”, rever em Configurações |
| 3. Default Features | **Feito** — painel em Configurações; aceite de revisões continua automático |
| 4. Remover IA do pareamento | **Feito** — `app/ai/pairing.py` removido; só lógica local |
| 5. Nomes dos 2 PDFs | **Feito** — distintos + sufixo localizado em `app/output/naming.py` |
| 6. Fluxo Compare sempre gera redline | **Feito** — extras aditivos (não bloqueiam) |
| 7. First-run (idioma → tutorial → defaults) | **Feito** |
| i18n long tail (JS dinâmico) | **Feito no essencial** (2026-07-14, retomada pós-Claude): domínio (tipos/categorias/saídas), core loop, histórico, conta/branding, guia EN. Resíduo aceitável: comentários JS e copy muito longa do guia PT (EN tem versão condensada). |

---

## 10. Comandos rápidos

```bash
# API local (se precisares)
# ver scripts/start_licensing_server.sh + docs/LICENCIAMENTO.md

# Build Mac comercial
./scripts/build_desktop.sh

# Build Mac teste sem limites (para beta tester)
./scripts/build_desktop.sh --unlimited

# Health produção
curl -s https://diffai-production.up.railway.app/v1/health

# Gatekeeper
xattr -cr /caminho/para/diffAI.app
```

---

## 11. Onde está o código relevante

| Assunto | Path |
|---------|------|
| Landing config | `landing/lib/config.ts` |
| CTAs download | `landing/components/download-ctas.tsx` |
| Portal conta | `landing/app/conta/page.tsx` |
| API licenças | `licensing_server/` |
| Cliente licença no app | `app/licensing/client.py` |
| URL Railway no app | `app/licensing/server_url.py` |
| Flag teste ilimitado | `app/licensing/build_flags.py` |
| Build desktop | `scripts/build_desktop.sh` |
| Dockerfile API | `Dockerfile` (raiz) |
| Summary of Changes | `app/output/summary.py` |

---

*Este ficheiro é o mapa para voltares a pedir coisas (DNS, volume, Windows, notarização, nova release, etc.) sem reexplicar o contexto.*
