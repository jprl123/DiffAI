# diffAI — Guia completo: landing (Vercel) + API de licenças + downloads

Landing: https://comparedocs-landing.vercel.app  
Código da landing: `agentic-build-and-orchestrate-ai-agents-while-you-sleep/`  
API de licenças: `licensing_server/` (FastAPI + SQLite — **não** vai na Vercel)

---

## 0. Como as peças se encaixam

```
Usuário no site (Vercel)
   │  clica Baixar Mac / Windows  →  arquivo no GitHub Releases / Blob / S3
   │  clica Assinar               →  Stripe Checkout via API de licenças
   │  entra em /conta             →  e-mail + chave → API de licenças
   ▼
App desktop (Mac .dmg / Windows .exe)
   └── ativa / valida licença  →  mesma API de licenças (HTTPS)
```

| Peça | Onde hospeda | Por quê |
|------|--------------|---------|
| Landing Next.js | **Vercel** | Já conectada no Cursor (plugin Vercel) |
| Servidor de licenças | **Railway** ou **Render** ou **Azure** | Precisa processo longo + disco (SQLite). Serverless da Vercel mata isso |
| Instaladores | GitHub Releases / Vercel Blob / R2 | Só URLs públicas nos botões |

### Plugins no Cursor hoje

- **Vercel** — sim (já usamos para deploy da landing)
- **Stripe** — sim (checkout / preços)
- **Azure** — sim (alternativa à Railway para a API)
- **Railway / Render** — **não há plugin** neste workspace. Deploy pelo site deles (5–10 min) ou via CLI. Não dá para “conectar Railway” como a Vercel aqui.

Recomendação prática: **Railway** para a API (volume + HTTPS fácil). Se preferir ficar no ecossistema Cursor, use **Azure Container Apps** com o plugin Azure.

---

## 1. Por que o botão “Baixar” não fazia nada

O link era `#download` / env vazia — âncora sem seção.  
Agora:

1. Hero e CTAs têm **Mac** e **Windows**
2. Ambos levam a `#baixar` enquanto o arquivo não existe
3. Em `#baixar`, se não houver URL, aparece **“Avise-me no e-mail”** (mailto)
4. Quando você setar as envs na Vercel com URLs reais, o botão baixa o arquivo

---

## 2. Variáveis na Vercel (passo a passo com prints mentais)

1. Abra https://vercel.com → projeto **comparedocs-landing**
2. **Settings** → **Environment Variables**
3. Adicione (Production + Preview):

| Nome | Exemplo | O que é |
|------|---------|---------|
| `NEXT_PUBLIC_LICENSE_API` | `https://diffai-api.up.railway.app` | URL HTTPS da API de licenças (sem barra no final) |
| `NEXT_PUBLIC_DOWNLOAD_URL_MAC` | `https://github.com/SEU_USER/diffAI/releases/download/v1.0.0/diffAI-mac.dmg` | Link direto do .dmg |
| `NEXT_PUBLIC_DOWNLOAD_URL_WINDOWS` | `https://github.com/.../diffAI-windows.exe` | Link direto do .exe |
| `NEXT_PUBLIC_SALES_EMAIL` | `vendas@diffai.app` | Opcional |

4. **Importante:** nomes `NEXT_PUBLIC_*` só entram no **build**. Depois de salvar → **Deployments** → ⋮ no último → **Redeploy** (ou peça redeploy pelo Cursor).
5. Sem a API pública, checkout e `/conta` falham no browser (CORS + localhost). A landing em si abre normalmente.

Checklist rápido depois do redeploy:

- Abrir o site → **Baixar** → deve ir para `#baixar` (ou baixar se a URL existir)
- Em `/conta`, login só funciona se `NEXT_PUBLIC_LICENSE_API` apontar para a API no ar e `PORTAL_ALLOWED_ORIGINS` incluir a origem da landing

---

## 3. Subir a API de licenças no Railway (recomendado, sem plugin)

### 3.1 Conta e projeto

1. Crie conta em https://railway.app  
2. **New Project** → **Deploy from GitHub** (repo deste código) **ou** **Empty Project** + deploy via CLI  
3. Root / start: pasta do repo com `licensing_server`

### 3.2 Comando e porta

No serviço Railway:

- **Start command:**  
  `uvicorn licensing_server.server:app --host 0.0.0.0 --port $PORT`
- Gere domínio público: **Settings** → **Networking** → **Generate Domain**  
  Ex.: `https://diffai-api-production.up.railway.app`

### 3.3 Volume (SQLite)

- **Add Volume** montado em `/data`
- Envs de caminho (ajuste se o código usar outro dir): dados em `/data`

### 3.4 Variáveis de ambiente no Railway

```text
PORT=                    # Railway preenche
STRIPE_SECRET_KEY=sk_live_...   # ou sk_test_... no sandbox
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_PRO=price_...
STRIPE_PRICE_TEAM=price_...
MAIL_BACKEND=resend
RESEND_API_KEY=re_...
PORTAL_ALLOWED_ORIGINS=https://comparedocs-landing.vercel.app,https://diffai.app
COMPAREDOCS_SIGNING_KEY=/data/signing_key.pem
```

- Gere chave de produção com `scripts/rotate_license_keys.py` — **não** use a chave de dev do repo.
- No Stripe Dashboard → Webhooks → endpoint  
  `https://SUA-API.up.railway.app/v1/stripe/webhook`  
  eventos de checkout/subscription conforme o código.

### 3.5 Ligar landing ↔ API

1. Copie a URL HTTPS do Railway  
2. Cole em `NEXT_PUBLIC_LICENSE_API` na Vercel  
3. Redeploy da landing  
4. Confirme `PORTAL_ALLOWED_ORIGINS` com a URL exata da landing (com `https://`, sem path)

### Render (alternativa parecida)

Mesma ideia: Web Service Python, disco persistente, start com uvicorn, envs iguais. Também **sem** plugin no Cursor.

### Azure (com plugin no Cursor)

Dá para provisionar Container Apps / App Service + storage. Mais passos; use se já estiver no Azure. O plugin Azure ajuda a criar recursos; o código da API continua o mesmo.

---

## 4. Conectar o executável (Mac e, depois, Windows)

1. Em `app/licensing/server_url.py`:

```python
DEFAULT_SERVER_URL = "https://diffai-api-production.up.railway.app"
```

2. Rebuild Mac: `./scripts/build_desktop.sh`  
3. Windows: ainda não há script de build Windows no repo — próximo passo de produto. Até lá a landing mostra Windows como “em breve” / avise-me.  
4. Publique os arquivos e preencha `NEXT_PUBLIC_DOWNLOAD_URL_MAC` / `_WINDOWS`.

Login no app = mesmo modelo da `/conta`: **e-mail + chave** (sem senha).

---

## 5. Ordem certa de trabalho (diffAI)

| Ordem | O quê | Quem / onde |
|------|--------|-------------|
| 1 | Landing no ar com marca **diffAI** + Mac/Windows | Vercel (feito / redeploy) |
| 2 | API de licenças pública + Stripe + Resend | Railway (você no dashboard; Cursor ajuda no código) |
| 3 | Envs Vercel apontando para a API | Dashboard Vercel ou pedir redeploy aqui |
| 4 | `DEFAULT_SERVER_URL` no app + rebuild Mac | Cursor + script local |
| 5 | Build Windows + URLs de download | Próximo marco |
| 6 | Domínio `diffai.app` → Vercel; `api.diffai.app` → Railway | DNS |

Não inverta 2 e 3: sem API pública, checkout/conta não fecham o ciclo.

---

## 6. Endpoints (já no código)

- `POST /v1/portal/login` `{email, key}` → token + licença  
- `GET /v1/portal/me` Bearer  
- `POST /v1/portal/deactivate` `{device}` Bearer  
- Checkout: `/v1/checkout/pro` e `/v1/checkout/team`  
- App: `/v1/activate`, `/v1/validate`, …

---

## 7. Smoke curto (quando API + envs existirem)

1. Abrir landing → Baixar → seção `#baixar` ok  
2. Checkout test Stripe → e-mail com chave  
3. Ativar no app  
4. `/conta` com e-mail+chave → ver dispositivo → desativar  

Sem testes pesados até a API estar no ar.
