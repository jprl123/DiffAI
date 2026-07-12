# diffAI — Railway passo a passo (clique a clique)

API de licenças (`licensing_server/`). Landing continua na Vercel.

**Antes de tudo:** o repo no GitHub precisa ter `Dockerfile` na raiz (commit `Add Railway deploy` ou mais recente). Sem isso o Railway não sabe como buildar.

---

## FASE 0 — O que você vai ver

Depois de importar o GitHub, a Railway abre um **projeto** com um **card** (caixa) no meio da tela. Esse card é o **serviço**. Tudo que importa está **dentro desse card**.

Abas do card (topo, ao clicar no serviço):

| Aba | Para quê |
|-----|----------|
| **Deployments** | Build passou ou falhou? Ver logs |
| **Variables** | Stripe, CORS, URLs — **aqui** |
| **Metrics** | CPU (ignore por enquanto) |
| **Settings** | Domínio, Build, Volume |

**Não existe** “Root Directory” no nosso caso — ignore.

**Build:** use **Dockerfile** (detectado automaticamente). **Não** mude para Nixpacks.

---

## FASE 1 — Criar o projeto (5 min)

### 1.1 Entrar

1. Abra https://railway.app  
2. Login com **GitHub** (conta **jprl123**)

### 1.2 Liberar repo privado (se DiffAI não aparecer)

1. https://github.com/settings/installations  
2. **Railway** → **Configure**  
3. **Repository access** → marque **DiffAI** (ou All repositories)  
4. **Save**

### 1.3 Importar

1. Railway → botão **+ New Project** (canto superior direito)  
2. **Deploy from GitHub repo**  
3. Lista → clique **jprl123/DiffAI**  
4. Aguarde — abre o canvas com um card (nome tipo `DiffAI` ou `web`)

### 1.4 Primeiro deploy

1. Clique no **card** do serviço  
2. Aba **Deployments**  
3. Clique no deploy mais recente (topo da lista)  
4. Leia **Build Logs** e **Deploy Logs**

**Sucesso:** status verde **Success** / **Active**  
**Falha comum:** build tenta rodar Python na raiz sem Dockerfile → confirme que `Dockerfile` existe no GitHub (branch `main`)

---

## FASE 2 — Domínio público (obrigatório)

Sem domínio a API não tem HTTPS para a Vercel usar.

1. Clique no **card** do serviço  
2. Aba **Settings** (⚙️ no topo do painel do serviço)  
3. Menu lateral esquerdo → **Networking**  
4. Seção **Public Networking**  
5. Botão **Generate Domain** (ou toggle para ativar rede pública + domínio)  
6. Copie a URL, exemplo:  
   `https://diffai-production-a1b2.up.railway.app`

### Teste no navegador

Cole no Chrome/Safari:

```
https://SUA-URL-AQUI.up.railway.app/v1/health
```

**Esperado:** JSON parecido com `{"ok":true,...}`  

Se der erro 502/503: volte em **Deployments** → veja se o serviço crashou nos logs.

---

## FASE 3 — Variáveis (aba Variables)

1. Clique no **card** do serviço  
2. Aba **Variables** (não Settings)  
3. Ambiente: **Production** (padrão)  
4. **+ New Variable** ou **RAW Editor**

### Mínimo para o serviço subir (sandbox / teste)

Cole **uma por uma** (nome = coluna esquerda, valor = direita):

| Nome | Valor (exemplo) |
|------|-----------------|
| `MAIL_BACKEND` | `console` |
| `PORTAL_ALLOWED_ORIGINS` | `https://comparedocs-landing.vercel.app` |

(substitua pela URL **exata** da sua landing na Vercel, **sem** barra no final)

Salve. O Railway **redeploya** sozinho.

### Quando for testar pagamento Stripe

Adicione também (valores do seu Stripe Dashboard → Developers):

| Nome | Onde achar |
|------|------------|
| `STRIPE_SECRET_KEY` | `sk_test_...` em API keys |
| `STRIPE_PRICE_PRO` | Products → price id `price_...` |
| `STRIPE_PRICE_TEAM` | idem |
| `STRIPE_WEBHOOK_SECRET` | Webhooks → signing secret `whsec_...` |
| `SUCCESS_URL` | `https://SUA-LANDING.vercel.app/conta?checkout=ok` |
| `CANCEL_URL` | `https://SUA-LANDING.vercel.app/#planos` |

**Não crie** variável `PORT` — a Railway injeta automaticamente.

---

## FASE 4 — Build (Settings → Build)

Só confira, **não mude** se já estiver certo:

1. Card → **Settings** → **Build**  
2. Deve aparecer:
   - **Builder:** Dockerfile  
   - **Dockerfile path:** `Dockerfile` (raiz do repo)

Se aparecer **Nixpacks** ou **Railpack**:

1. **Settings** → **Build**  
2. Mude builder para **Dockerfile**  
3. Dockerfile path: `Dockerfile`  
4. Salve → redeploy

**Start command:** deixe vazio — o `Dockerfile` já define o comando (`scripts/start_licensing_server.sh`).

---

## FASE 5 — Volume (opcional no primeiro teste)

Volume guarda o SQLite entre redeploys. **Pode pular** no primeiro teste; licenças somem se redeployar.

### Caminho A — Settings

1. Card → **Settings**  
2. Role a página até **Volumes**  
3. **Add Volume**  
4. Mount Path: `/data`  
5. Confirmar

### Caminho B — Command Palette

1. No canvas do projeto, pressione **⌘K** (Mac)  
2. Digite: `Add Volume`  
3. Escolha o serviço DiffAI  
4. Mount path: `/data`

Se **Volumes** não existir: plano trial pode limitar — continue sem volume para ver `/v1/health` funcionando.

---

## FASE 6 — Webhook Stripe (depois do domínio)

1. https://dashboard.stripe.com/test/webhooks  
2. **Add endpoint**  
3. URL: `https://SUA-URL.up.railway.app/v1/stripe/webhook`  
4. Eventos: `checkout.session.completed`, `invoice.paid`, `customer.subscription.deleted`, `charge.refunded`  
5. Copie `whsec_...` → Railway **Variables** → `STRIPE_WEBHOOK_SECRET`  
6. Aguarde redeploy

---

## FASE 7 — Ligar Vercel

Vercel → projeto landing → **Settings** → **Environment Variables**:

| Nome | Valor |
|------|--------|
| `NEXT_PUBLIC_LICENSE_API` | `https://SUA-URL.up.railway.app` |

**Deployments** → ⋮ no último → **Redeploy**.

---

## Ordem que funciona (não pule)

```
1. GitHub tem Dockerfile na main
2. Railway importa DiffAI → deploy Success
3. Settings → Networking → Generate Domain
4. /v1/health abre no browser
5. Variables → MAIL_BACKEND + PORTAL_ALLOWED_ORIGINS
6. Vercel → NEXT_PUBLIC_LICENSE_API + redeploy
7. (depois) Stripe + webhook + volume
```

---

## Deploy falhou? Leia o log

| Mensagem no log | Significado | Ação |
|-----------------|-------------|------|
| `Dockerfile not found` | GitHub sem Dockerfile | Push do repo atualizado |
| `docker VOLUME ... is not supported` | `VOLUME` no Dockerfile | Removido — use Railway Volumes (mount `/data`) |
| `ModuleNotFoundError` | build errado | Builder = Dockerfile |
| `Application failed to respond` | crash ao iniciar | Deploy Logs; teste health |
| `STRIPE_SECRET_KEY` | checkout sem env | Normal até configurar Stripe |
| CORS no browser | origem errada | `PORTAL_ALLOWED_ORIGINS` = URL exata Vercel |

---

## Copiar e colar — RAW Variables (sandbox)

No Railway → Variables → **RAW Editor**, pode colar (ajuste URLs):

```env
MAIL_BACKEND=console
PORTAL_ALLOWED_ORIGINS=https://comparedocs-landing.vercel.app
SUCCESS_URL=https://comparedocs-landing.vercel.app/conta?checkout=ok
CANCEL_URL=https://comparedocs-landing.vercel.app/#planos
```

Stripe: adicione depois quando tiver as chaves.
