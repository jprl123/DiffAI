# Mudanças futuras — Compare Docs

Roadmap alinhado à [VISAO_GERAL.md](VISAO_GERAL.md). Priorizado por impacto para o público jurídico/corporativo.

---

## Prioridade 1 — Qualidade do motor

| Item | Descrição | Status |
|------|-----------|--------|
| PDF mais fiel ao original | Preservar layout do DOCX no redline (in-place + LibreOffice) | **Parcial** |
| Cabeçalho/rodapé e metadados | Classificar e filtrar mudanças em headers, footers, propriedades | Parcial (`Category.METADATA`) |
| Tabelas complexas | Células mescladas, tabelas quebradas entre páginas | Planejado |
| Imagens reais no redline | Substituir placeholder por miniatura da imagem | Planejado |
| Movimentação mais precisa | Menos falsos positivos quando blocos deslocam por inserções | Em evolução |
| Score de confiança | Indicar similaridade do pareamento no relatório | Planejado |

---

## Prioridade 2 — Relatório analítico

| Item | Descrição | Status |
|------|-----------|--------|
| Excel com abas filtradas | "Só conteúdo", "Tabelas/Imagens", "Ruído", "Estatísticas" | **Futuro próximo** |
| Filtro padrão "só o que importa" | Abrir relatório já ocultando ruído rotineiro | Planejado |
| Resumo executivo exportável | "[Resumo] ….pdf" de 1 página (opção na UI; reusa insights) | **Feito** |
| Descrição em linguagem de negócio | "Multa alterada de 2% para 10%" — ver Análise IA | **Feito (heurística local)** |
| Comparação de planilhas (.xlsx) | Entrada Excel com diff por aba/célula | **Feito** |
| Redline XLSX de saída | Planilha marcada preservando estilos do base + Summary | **Feito** |

---

## Prioridade 3 — UX e interface

| Item | Descrição | Status |
|------|-----------|--------|
| Lote como fluxo principal | Prévia dos pares ("Ver pares" com método nome/similaridade/conteúdo) | **Feito** (lembrar últimas pastas: planejado) |
| Seletor nativo de pastas | Botão no desktop/lote em vez de só colar caminho | **Feito** |
| Histórico local de comparações | Reabrir PDF/Excel sem reprocessar | **Feito** |
| Visualização lado a lado | Base × Revisado alinhados, "Só mudanças", no painel de mudanças | **Feito** |
| Marca do escritório (white-label) | Logo nos PDFs/relatórios — exclusivo do plano Equipe | **Feito** |
| PDF digitalizado | Detecção com erro claro (OCR em si: ver Prioridade 1) | **Feito (detecção)** |
| Timeline por seção | Alterações agrupadas na hierarquia do documento | Planejado |
| App `.app` macOS | Duplo-clique sem terminal | Planejado |

---

## Prioridade 4 — Inteligência artificial

| Item | Descrição | Status |
|------|-----------|--------|
| Análise IA local | Resumo executivo, destaques e riscos sem enviar dados à nuvem | **Feito (heurística + UI)** |
| Perguntas em linguagem natural | "O que mudou no pagamento?" — filtro semântico | Planejado |
| IA generativa opcional | `COMPAREDOCS_AI_KEY` para resumos mais ricos (opt-in) | Planejado |
| Classificação de risco contratual | Sinalizar cláusulas críticas alteradas (multa, foro, prazo) | **Parcial** |

> **Princípio:** processamento e análise padrão permanecem 100% locais. IA externa só com chave explícita do usuário.

---

## Prioridade 5 — Escala e produto comercial

| Item | Descrição | Status |
|------|-----------|--------|
| Lote paralelo | Vários pares simultâneos em máquinas com mais CPU | Planejado |
| Documentos grandes | Contratos 200+ páginas sem travar a UI | Planejado |
| Testes com docs reais | Bateria anonimizada além das amostras sintéticas | Planejado |
| Licenciamento | Chave assinada (Ed25519), dispositivo, trial, planos, aba Conta | **Feito (v1 local)** |
| Logs por job | Tempo por etapa (extração → align → PDF) | Planejado |

### Checklist para vender de verdade (licenciamento v2)

| Item | Descrição | Status |
|------|-----------|--------|
| Novo par de chaves | `.venv/bin/python scripts/rotate_license_keys.py` — gera par fora do repo e atualiza `pubkey.py` em um comando | **Script pronto** — rodar antes do lançamento |
| Servidor em nuvem | Publicar `licensing_server/` com HTTPS (VPS, Railway, Fly.io…); app aponta via `COMPAREDOCS_LICENSE_SERVER` | Obrigatório (adiado — sem VPS ainda) |
| Pagamento (Stripe) | Brief completo p/ implementação: [STRIPE_CURSOR.md](STRIPE_CURSOR.md) — webhook → emite chave → e-mail; sandbox | **Brief pronto** — implementação no Cursor |
| Trial server-side | Hoje o trial é local (burlável apagando `~/.comparedocs/trial.json`); emitir trial vinculado a e-mail/dispositivo no servidor | Recomendado |
| Portal do cliente | Página web p/ ver chave, dispositivos ativos e trocar de plano | Recomendado |
| Empacotamento | `./scripts/build_desktop.sh` gera `dist/Compare Docs.app` (PyInstaller, deps dinâmicas coletadas) | **Build pronto** — falta assinatura/notarização Apple p/ distribuir |

---

## Organização do repositório

| Item | Descrição | Status |
|------|-----------|--------|
| Amostras unificadas | Um só lugar: `tests/samples/` via `scripts/generate_samples.sh` | **Feito** |
| Redline Excel de saída | Planilha com células destacadas (além do PDF) | **Feito** |
| Células mescladas no Excel | Extração e diff de ranges mesclados | Planejado |

---

## Fora do escopo (visão original)

- Editor de documentos
- Colaboração em tempo real
- Pixel-perfect de PDFs complexos
- Substituição da análise humana

---

*Última atualização: julho/2026*
