# Brief para o Cursor — Integração Stripe do Compare Docs

> **Contexto para o agente/dev**: este repositório é um app local de comparação de
> documentos com licenciamento por chave (`CDOC-XXXX-XXXX-XXXX-XXXX`). O servidor de
> licenças (`licensing_server/`, FastAPI + SQLite, porta 8390) já emite, ativa,
> valida e revoga chaves — **a emissão programática já existe**:
> `licensing_server.db.LicenseDB().issue(email, plan, max_devices, months)`.
> Sua tarefa é SÓ a ponte Stripe → emissão → e-mail. Leia antes:
> `docs/LICENCIAMENTO.md`, `licensing_server/server.py`, `licensing_server/db.py`,
> `app/licensing/plans.py`. Ambiente: Stripe **test mode** (sandbox), chaves em mãos.
> Python 3.13+, venv em `.venv/`. NÃO commitar segredos.

## Objetivo

Cliente paga no Stripe → recebe a chave de licença por e-mail em segundos → ativa no
app. Renovou: validade estende sozinha. Cancelou/reembolsou: chave revogada. Tudo
idempotente e à prova de replay.

## Arquitetura pedida

Tudo dentro de `licensing_server/` (mesmo processo do servidor de licenças — sem
serviço novo):

1. **`licensing_server/stripe_integration.py`** — módulo com:
   - `create_checkout_session(plan: str) -> str` (URL) usando a lib oficial `stripe`.
     `mode="subscription"` para pro/team. Anexar `metadata={"plan": plan}` e
     `subscription_data.metadata` idem. `customer_email` coletado pelo próprio Checkout.
   - Handler de webhook (ver rota abaixo) com **verificação de assinatura**
     (`stripe.Webhook.construct_event` + `STRIPE_WEBHOOK_SECRET`). Rejeitar sem
     assinatura válida (400).
2. **Rotas novas em `licensing_server/server.py`**:
   - `POST /v1/stripe/webhook` — corpo RAW (atenção: FastAPI precisa do body bruto
     para verificar assinatura).
   - `GET /v1/checkout/{plan}` → redirect 303 para a URL do Checkout (o app já abre
     URLs de checkout via `COMPAREDOCS_CHECKOUT_PRO`/`_TEAM` — essas variáveis vão
     apontar para esta rota).
3. **Eventos a tratar** (ignorar o resto com 200):
   - `checkout.session.completed` → e-mail do cliente + plano do metadata →
     `LicenseDB().issue(...)` (pro: 2 dispositivos; team: 5; months=1 se assinatura
     mensal — ver renovação abaixo) → gravar mapeamento `subscription_id ↔ key` →
     enviar e-mail com a chave.
   - `invoice.paid` (renovação) → localizar a chave pelo `subscription_id` → estender
     `expires_at` (+1 mês/ano conforme o price). Criar método novo
     `LicenseDB.extend(key, months)` com teste.
   - `customer.subscription.deleted` e `charge.refunded` → `LicenseDB().revoke(key)`.
4. **Idempotência**: tabela `stripe_events (event_id TEXT PRIMARY KEY, processed_at)`;
   evento já visto → 200 sem reprocessar. Falha no processamento → 500 (o Stripe
   reenvia).
5. **Mapeamento plano↔price**: env vars `STRIPE_PRICE_PRO`, `STRIPE_PRICE_TEAM`
   (price IDs do sandbox). Criar os produtos/preços no dashboard (Pro R$ 59/mês,
   Equipe R$ 49/mês — valores placeholder, confirmar com o dono) e documentar os IDs
   em `.env.example`.
6. **E-mail com a chave**: implementar `licensing_server/mailer.py` com interface
   única `send_license_email(email, key, plan)` e dois backends escolhidos por env:
   `MAIL_BACKEND=console` (default dev: imprime no log) e `MAIL_BACKEND=resend`
   (HTTP API, `RESEND_API_KEY`). Template pt-BR curto: chave em destaque, passos de
   ativação (abrir app → Ativar licença), link de suporte.
7. **Segredos**: `.env` na raiz (python-dotenv ou leitura manual), `.env.example`
   versionado com placeholders, `.env` no `.gitignore`. Variáveis:
   `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO`,
   `STRIPE_PRICE_TEAM`, `MAIL_BACKEND`, `RESEND_API_KEY`, `SUCCESS_URL`, `CANCEL_URL`.

## Fluxo de teste (sandbox, sem VPS)

```bash
pip install stripe                     # adicionar a requirements.txt
stripe login                           # CLI do Stripe
stripe listen --forward-to localhost:8390/v1/stripe/webhook   # dá o whsec_...
# abrir GET /v1/checkout/pro → pagar com cartão 4242 4242 4242 4242
# conferir: chave emitida no SQLite + e-mail no log + ativação no app funciona
stripe trigger invoice.paid            # simula renovação → expires_at estendeu
stripe trigger customer.subscription.deleted  # → chave revogada
```

## Critérios de aceite

- [ ] Pagamento sandbox concluído gera chave e "envia" e-mail (backend console).
- [ ] Webhook com assinatura inválida → 400; evento repetido → 200 sem duplicar chave.
- [ ] `invoice.paid` estende validade; `subscription.deleted` revoga.
- [ ] Nenhum segredo commitado; `.env.example` completo.
- [ ] Testes: estender `tests/test_licensing.py` ou criar `tests/test_stripe.py`
  usando payloads de webhook FIXOS (não chamar a API real nos testes; mockar
  `stripe.Webhook.construct_event`).
- [ ] Sem quebrar nada: `.venv/bin/python -m tests.test_licensing` e
  `-m tests.test_e2e` continuam verdes.

## Fora do escopo (não fazer)

- Portal do cliente, upgrades/downgrades de plano, trial server-side, deploy/VPS.
- Mudar o app desktop/frontend (as variáveis `COMPAREDOCS_CHECKOUT_*` já são lidas).
- Trocar o par de chaves Ed25519 (processo separado: `scripts/rotate_license_keys.py`).
