# Licenciamento — guia do dono do produto

Este guia é para VOCÊ operar e entender o sistema de licenças. Não é documentação de
código (isso está em [ARCHITECTURE.md](ARCHITECTURE.md)) nem o brief do Stripe
(isso está em [STRIPE_CURSOR.md](STRIPE_CURSOR.md)).

---

## A ideia em 30 segundos

```
 VOCÊ (ou o Stripe, depois)                  CLIENTE
 ┌──────────────────────┐                    ┌─────────────────────────┐
 │ emite uma CHAVE       │  e-mail com chave  │ digita e-mail + chave    │
 │ CDOC-XXXX-XXXX-...    │ ─────────────────▶ │ no app (modal Ativar)    │
 └──────────┬───────────┘                    └───────────┬─────────────┘
            │                                            │ POST /v1/activate
            ▼                                            ▼
 ┌─────────────────────────────────────────────────────────────────────┐
 │ SERVIDOR DE LICENÇAS (licensing_server/, porta 8390)                │
 │ 1. chave existe? e-mail bate? não expirou? tem slot de dispositivo? │
 │ 2. registra o dispositivo                                           │
 │ 3. devolve a licença ASSINADA (Ed25519)                             │
 └─────────────────────────────────────────────────────────────────────┘
            │
            ▼
 O app guarda a licença assinada em ~/.comparedocs/license.json e daí em diante
 valida a ASSINATURA localmente (funciona offline). Revalida online 1x por dia
 quando tem internet. Ninguém forja licença sem a chave privada do servidor.
```

**Por que assinatura e não senha?** Porque o app roda na máquina do cliente, até
offline. A assinatura Ed25519 permite ao app confiar na licença sem consultar o
servidor toda hora — e sem que o cliente consiga editar o arquivo para se dar um
plano melhor (qualquer byte alterado invalida a assinatura; tem teste cobrindo isso).

---

## Operação do dia a dia

### 1. Subir o servidor de licenças (hoje, local)

```bash
.venv/bin/python -m licensing_server.server        # porta 8390
```

O banco fica em `~/.comparedocs-server/licenses.db` (SQLite). O app procura o
servidor em `COMPAREDOCS_LICENSE_SERVER` (default `http://127.0.0.1:8390`).

### 2. Emitir uma chave para um cliente

```bash
.venv/bin/python -m licensing_server.issue --email cliente@firma.com --plan pro
# → Chave: CDOC-XXXX-XXXX-XXXX-XXXX  (envie por e-mail ao cliente)
```

Opções: `--plan pro|team|perpetual`, `--devices N`, `--months N`.
Defaults: pro = 2 dispositivos/12 meses; team = 5/12; perpetual = 2/sem validade.

### 3. O cliente ativa

No app: **Planos → "Já tem uma chave? Ativar agora"** (ou banner/aba Conta) →
digita e-mail + chave → pronto. A aba **Conta** passa a mostrar plano, validade,
dispositivo e última validação.

### 4. Ciclo de vida

| Situação | O que acontece |
|----------|----------------|
| Cliente troca de máquina | Conta → "Desativar neste dispositivo" libera o slot; ativa na nova |
| Limite de dispositivos | Ativação recusada com mensagem clara (409) até liberar um slot |
| Renovação | O Stripe (depois) estende `expires_at`; a revalidação diária do app pega a extensão sozinha |
| Cancelamento/reembolso | Revogue a chave; na próxima revalidação online o app derruba a licença |
| Cliente offline | Licença vale até a validade + 7 dias de tolerância, sem internet nenhuma |
| Trial | Automático na primeira execução: 14 dias / 25 comparações / lote máx. 5. Acabou → app bloqueia comparar e oferece ativação |

Revogar uma chave (hoje, direto no banco — um endpoint admin entra com o Stripe):

```bash
.venv/bin/python -c "from licensing_server.db import LicenseDB; print(LicenseDB().revoke('CDOC-....'))"
```

### 5. Onde cada coisa mora

| Arquivo | O que é |
|---------|---------|
| `~/.comparedocs/license.json` (máquina do cliente) | Licença assinada + chave (para revalidar) |
| `~/.comparedocs/trial.json` (máquina do cliente) | Estado da avaliação gratuita |
| `~/.comparedocs-server/licenses.db` (seu servidor) | Chaves emitidas e dispositivos ativos |
| `licensing_server/dev_signing_key.pem` | Chave PRIVADA de assinatura (DEV — trocar p/ produção) |
| `app/licensing/pubkey.py` | Chave PÚBLICA embutida no app |
| `app/licensing/plans.py` | Preços e textos da aba Planos |

---

## Antes de vender (nessa ordem)

1. **Trocar as chaves de assinatura** — as do repositório são de desenvolvimento:
   ```bash
   .venv/bin/python scripts/rotate_license_keys.py
   ```
   O script gera um par novo fora do repositório, atualiza `pubkey.py` e diz onde
   guardar a privada. Licenças antigas (da chave dev) param de valer — reative a sua.
2. **Stripe** — implementação pelo Cursor com o brief [STRIPE_CURSOR.md](STRIPE_CURSOR.md):
   checkout → webhook → emite chave → e-mail automático. Você já está no modo sandbox.
3. **Publicar o servidor** (quando decidir a VPS): rodar `licensing_server` atrás de
   HTTPS e apontar o app com `COMPAREDOCS_LICENSE_SERVER=https://licencas.seudominio.com`.
4. **Empacotar o desktop**: `scripts/build_desktop.sh` (PyInstaller). Para distribuir
   fora da sua máquina, o .app precisa de assinatura + notarização Apple (conta de
   desenvolvedor) — sem isso o Gatekeeper reclama.

## Perguntas que você vai se fazer

- **"E se o cliente apagar o trial.json?"** — ganha trial de novo. Conhecido e aceito
  na v1; a v2 emite trial no servidor (está no roadmap).
- **"Posso emitir chave sem internet no cliente?"** — a ATIVAÇÃO exige internet uma
  vez; depois o app funciona offline até a validade.
- **"O que o app manda para o servidor?"** — e-mail, chave e um HASH do identificador
  da máquina (o UUID real nunca sai do dispositivo). Nada de documentos: comparação é
  100% local.
- **"Mudei o preço no Stripe, preciso mudar o app?"** — o preço mostrado na aba Planos
  vem de `app/licensing/plans.py`; mantenha os dois alinhados.
