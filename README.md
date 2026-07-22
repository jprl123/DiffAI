# DiffAI

Ferramenta local para **comparar documentos** (DOCX, PDF e Excel) e gerar **PDFs redline**
com marcação de inserções, exclusões, movimentações e formatação — além de relatório
analítico com separação entre mudanças de conteúdo e mudanças rotineiras.

Baseado na visão descrita em [docs/VISAO_GERAL.md](docs/VISAO_GERAL.md).

## Requisitos

- **Python 3.13+** (recomendado **3.14**)
- macOS: Homebrew (`brew install python@3.14`)

Primeira configuração ou atualização do Python:

```bash
./scripts/setup_python.sh
```

Isso instala o Python via Homebrew (se necessário), recria `.venv/` e instala as dependências.

## Estrutura do projeto

```
Compare-docs/
├── app/              # Backend: extração, motor, saídas, API
├── web/              # Interface (HTML/JS)
├── desktop/          # App nativo (pywebview)
├── tests/            # Testes e gerador de amostras
│   ├── make_samples.py
│   ├── test_e2e.py
│   └── samples/      # gerado por scripts/generate_samples.sh
├── docs/             # Documentação (visão, arquitetura, deploy) — ver docs/README.md
├── assets/           # Branding (ícones)
├── scripts/          # Build desktop, setup Python, utilitários
├── output/           # Saídas locais das comparações (gitignored)
└── logs/             # Logs do desktop
```

Documentação completa: **[docs/README.md](docs/README.md)**.

## Como rodar

### Versão web (navegador)

```bash
./run.sh
```

Depois abra **http://127.0.0.1:8377** no navegador.

### Versão desktop (app nativo)

```bash
.venv/bin/python run_desktop.py
```

Abre uma **janela nativa** com a mesma interface web. Tudo continua local.

**Log de diagnóstico:** `logs/desktop.log`

### Arquivos de teste

```bash
./scripts/generate_samples.sh
```

Gera pares em `tests/samples/base/` e `tests/samples/revised/` — contrato DOCX,
política PDF, proposta comercial e planilha Excel.

## Modos de uso

A interface tem três áreas: **Comparar** (par único), **Lote** (pastas) e **Histórico** —
todas as comparações ficam registradas em `~/.comparedocs/history.json` e sobrevivem ao
fechamento do app; da aba Histórico dá para reabrir os arquivos gerados, filtrar por
status e limpar o registro.

- **Arquivo único** — arraste o documento base e o revisado (`.docx`, `.pdf` ou `.xlsx`)
  e clique em Comparar.
- **Lote (pastas)** — informe a pasta dos originais e a dos revisados; o sistema pareia
  os arquivos por nome e, quando os nomes não têm relação nenhuma, pelo **próprio
  conteúdo** dos documentos — não é preciso renomear nada antes de comparar.

## O que é gerado

| Saída | Nome |
|-------|------|
| PDF redline completo | `[Redline] {base} vs {revisado}.pdf` |
| DOCX redline fiel (entrada .docx) | `[Redline] {base} vs {revisado}.docx` — mesma formatação do revisado, só com marcas |
| Excel redline (entrada .xlsx) | `[Redline] {base} vs {revisado}.xlsx` + aba Summary |
| Só páginas alteradas (opcional) | `[Redline-Changed Pages] {base} vs {revisado}.pdf` |
| Resumo executivo (opcional) | `[Resumo] {base} vs {revisado}.pdf` — 1 página com síntese, destaques e riscos |
| DOCX editável (opcional) | `[Redline] {base} vs {revisado}.docx` |
| Relatório analítico (opcional) | `[Report] {base} vs {revisado}.html / .xlsx / .json` |

Todo redline (PDF fiel, PDF padronizado e DOCX) termina com uma página de síntese
**Summary of Changes** — data, arquivos, totais por tipo e conteúdo vs rotineiras —
em página própria, limpa, com a marca Compare Docs.

> **PDF fiel requer LibreOffice.** Para pares `.docx`, o PDF redline é gerado convertendo o
> DOCX redline fiel via LibreOffice headless (perfil de usuário dedicado — funciona mesmo com
> o LibreOffice aberto). Sem LibreOffice instalado, o PDF sai em layout padronizado e o
> resultado exibe um aviso ⚠ no card.

## Licenciamento comercial

O app roda em **avaliação gratuita** (14 dias / 25 comparações / lote de até 5 pares) e é
desbloqueado com **chave de licença** (formato `CDOC-XXXX-XXXX-XXXX-XXXX`) vinculada a
e-mail e dispositivo. As licenças são payloads **assinados (Ed25519)** — o app verifica a
assinatura offline com a chave pública embutida; forjar exige a chave privada do servidor.

- **Servidor de licenças** (`licensing_server/`): roda separado do app — hoje local, depois
  em nuvem (o app só precisa da URL em `COMPAREDOCS_LICENSE_SERVER`).

  ```bash
  .venv/bin/python -m licensing_server.server            # porta 8390
  .venv/bin/python -m licensing_server.issue --email cliente@x.com --plan pro
  ```

- **No app**: aba **Planos** (assinaturas), **Conta** (estado da licença, dispositivo,
  desativação) e modal **Ativar licença**. Sem licença e sem avaliação, os endpoints de
  comparação retornam 402 e a UI abre a ativação.
- **Offline**: licença ativada funciona sem internet até a validade (+7 dias de
  tolerância); revalidação online oportunista a cada 24 h.
- Preços/textos dos planos: [app/licensing/plans.py](app/licensing/plans.py). URLs de
  checkout via `COMPAREDOCS_CHECKOUT_PRO` / `COMPAREDOCS_CHECKOUT_TEAM`.

**Guia completo do fluxo de licenças (para o dono do produto):**
[docs/LICENCIAMENTO.md](docs/LICENCIAMENTO.md).
**Integração Stripe (brief para implementação no Cursor):**
[docs/STRIPE_CURSOR.md](docs/STRIPE_CURSOR.md).

## Executável (desktop empacotado)

```bash
./scripts/build_desktop.sh     # gera dist/Compare Docs.app (PyInstaller)
open "dist/Compare Docs.app"
```

No app empacotado, saídas vão para `~/Documents/Compare Docs/` e logs para
`~/.comparedocs/logs/`. Para distribuir fora da sua máquina é preciso assinar e
notarizar (conta Apple Developer).

> **Antes de vender de verdade** (checklist em [docs/MUDANCAS_FUTURAS.md](docs/MUDANCAS_FUTURAS.md)):
> rotacionar as chaves de assinatura (`.venv/bin/python scripts/rotate_license_keys.py`),
> publicar o servidor de licenças com HTTPS, concluir o Stripe (brief acima) e
> assinar/notarizar o executável.

## Arquitetura

Backend Python (FastAPI) + frontend HTML/JS. O pipeline normaliza DOCX, PDF e Excel
para o mesmo modelo de blocos, alinha, faz diff palavra a palavra e classifica cada
mudança. Detalhes em [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Testes

```bash
.venv/bin/python -m tests.test_e2e
```

## Roadmap

Ver [docs/MUDANCAS_FUTURAS.md](docs/MUDANCAS_FUTURAS.md).
# DiffAI
