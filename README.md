# DiffAI

App desktop local para **comparar documentos** (DOCX, PDF e Excel) e gerar
**redlines** com inserção, exclusão, movimentação e formatação — mais síntese
e relatório analítico (conteúdo vs. mudanças rotineiras).

Visão de produto: [docs/VISAO_GERAL.md](docs/VISAO_GERAL.md) · índice de docs:
[docs/README.md](docs/README.md).

**Site / downloads:** [diffai.app](https://diffai.app) ·
[Release v0.1.4 (Mac + Windows)](https://github.com/jprl123/DiffAI/releases/tag/v0.1.4)

| Plataforma | Pacote |
|------------|--------|
| macOS | [diffAI-mac.zip](https://github.com/jprl123/DiffAI/releases/download/v0.1.4/diffAI-mac.zip) |
| Windows | [diffAI-windows.zip](https://github.com/jprl123/DiffAI/releases/download/v0.1.4/diffAI-windows.zip) |

## Requisitos (desenvolvimento)

- **Python 3.13+** (recomendado **3.14**)
- macOS: Homebrew (`brew install python@3.14`)
- **LibreOffice** (recomendado) — PDF redline com o layout original do DOCX.
  Sem ele, o PDF sai em layout padronizado; o DOCX redline continua fiel.
  No app: Configurações → PDF fiel.

```bash
./scripts/setup_python.sh
```

Instala o Python (se preciso), recria `.venv/` e as dependências.

## Estrutura

```
DiffAI/
├── app/                 # Extração, motor, saídas, API FastAPI, licenças
├── web/                 # Interface (HTML/JS)
├── desktop/             # Janela nativa (pywebview)
├── landing/             # Site Next.js (Vercel)
├── licensing_server/    # API de licenças / Stripe (Railway)
├── tests/               # Testes e amostras
├── scripts/             # Setup, build Mac/Windows, samples
├── docs/                # Documentação — ver docs/README.md
├── assets/branding/     # Ícones (.icns / .ico / PNG)
├── .github/workflows/   # CI (build Windows)
├── output/              # Saídas locais (gitignored)
└── logs/                # Logs do desktop
```

## Como rodar (dev)

### Web (navegador)

```bash
./run.sh
```

Abra **http://127.0.0.1:8377**.

### Desktop

```bash
.venv/bin/python run_desktop.py
```

Janela nativa com a mesma UI. Tudo processa **localmente**.

Log: `logs/desktop.log`

### Amostras de teste

```bash
./scripts/generate_samples.sh
```

Pares em `tests/samples/base/` e `tests/samples/revised/`.

## Uso

Áreas da interface: **Comparar**, **Lote**, **Histórico**, **Planos** / Conta.

- **Par único** — base + revisado (`.docx`, `.pdf`, `.xlsx`) → Comparar.
- **Lote** — duas pastas; pareamento por nome e, se preciso, por conteúdo.
- **Histórico** — `~/.comparedocs/history.json` (sobrevive ao fechar o app).
- **Opções de comparação** — moves, formatação, headers/footers, tabelas, imagens
  (persistentes em Configurações).

Na **avaliação gratuita**, a comparação de **PDF e Excel** fica nos planos pagos;
Word (DOCX) está disponível no trial.

## Saídas

| Saída | Nome típico |
|------|-------------|
| PDF redline | `[Redline] {base} vs {revisado}.pdf` |
| DOCX redline fiel | `[Redline] {base} vs {revisado}.docx` |
| Excel redline | `[Redline] {base} vs {revisado}.xlsx` (+ aba Summary) |
| Só páginas alteradas (opc.) | `[Redline-Changed Pages] … .pdf` |
| Resumo executivo (opc.) | `[Resumo] … .pdf` |
| Relatório analítico (opc.) | `[Report] … .html / .xlsx / .json` |

No app empacotado, as saídas vão para `~/Documents/diffAI/`.

Todo redline termina com **Summary of Changes** (marca **DiffAI**). Documentos
**paisagem** preservam a orientação na pré-visualização e no PDF gerado.

> **PDF fiel = LibreOffice.** Pares DOCX (e PDF convertidos via pdf2docx) passam
> pelo redline in-place + conversão headless. Sem LibreOffice: PDF padronizado +
> aviso no resultado; o DOCX redline mantém a formatação.

## Licenciamento

Avaliação: **14 dias / 25 comparações / lote até 5 pares**. Desbloqueio com chave
`CDOC-XXXX-XXXX-XXXX-XXXX` (Ed25519, verificação offline).

```bash
.venv/bin/python -m licensing_server.server            # porta 8390
.venv/bin/python -m licensing_server.issue --email cliente@x.com --plan pro
```

URL do servidor no app: `COMPAREDOCS_LICENSE_SERVER`. Detalhes:
[docs/LICENCIAMENTO.md](docs/LICENCIAMENTO.md) · Stripe: [docs/STRIPE_CURSOR.md](docs/STRIPE_CURSOR.md).

## Build do desktop

### macOS

```bash
./scripts/build_desktop.sh                 # dist/diffAI.app + diffAI-mac.zip
./scripts/build_desktop.sh --unlimited     # build de teste sem limites de plano
```

Distribuição pública: codesign + notarização (Apple Developer) —
ver [docs/LICENCIAMENTO.md](docs/LICENCIAMENTO.md).

### Windows

No Windows (ou CI `windows-latest`):

```powershell
.\scripts\build_desktop_windows.ps1
```

Gera `dist\diffAI-windows.zip` (`diffAI\diffAI.exe`). Workflow:
`.github/workflows/build-windows.yml` (`gh workflow run "Build Windows"`).

Windows 10/11 com [WebView2](https://developer.microsoft.com/microsoft-edge/webview2/)
(na maioria das máquinas já vem instalado).

## Arquitetura

FastAPI + frontend HTML/JS. DOCX/PDF/Excel → modelo de blocos → alinhamento →
diff → classificação → redline / relatório.
Detalhes: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Testes

```bash
.venv/bin/python -m tests.test_e2e
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

## Roadmap

[docs/MUDANCAS_FUTURAS.md](docs/MUDANCAS_FUTURAS.md) — antes de vender de verdade:
rodar `scripts/rotate_license_keys.py`, HTTPS no servidor de licenças, Stripe e
assinatura dos instaladores.
