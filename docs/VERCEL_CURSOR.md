# diffAI — Guia completo: landing (Vercel) + API de licenças + downloads

Landing: https://comparedocs-landing.vercel.app  
Código da landing: `landing/`  
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

## Fix 404 após conectar GitHub (Root Directory)

Se o build log mostrar só **`Route (pages) ─ /404`** ou o site der 404:

1. Vercel → projeto **comparedocs-landing** → **Settings** → **General**
2. **Root Directory** → **Edit** → digite: **`landing`**
3. **Save**
4. **Deployments** → ⋮ no último → **Redeploy** → marque **Clear build cache** (importante)

Build correto deve listar:

```text
Route (app)
┌ ○ /
├ ○ /_not-found
└ ○ /conta
```

---

O repo **jprl123/DiffAI** está **privado** e a landing **não está na raiz** do repo.
Por isso a Vercel muitas vezes não lista o projeto ou importa o app Python errado.

### Por que não aparece

| Motivo | O que fazer |
|--------|-------------|
| Repo **privado** | Dar permissão ao app **Vercel** no GitHub |
| Conta GitHub errada na Vercel | Conectar a conta **jprl123** (mesma do push) |
| Nome diferente | Procurar **`DiffAI`**, não `Compare-docs` |
| Monorepo | A landing é Next.js numa **subpasta** (ver abaixo) |

### Passo 1 — Liberar o repo privado no GitHub

1. Abra: https://github.com/settings/installations  
2. Clique em **Vercel** → **Configure**  
3. Em **Repository access**, escolha:
   - **All repositories**, ou  
   - **Only select repositories** → marque **`jprl123/DiffAI`**  
4. Salve (**Save**)

Se **Vercel** não aparecer na lista, instale primeiro:  
https://github.com/apps/vercel → **Install** → conta **jprl123**

### Passo 2 — Conectar na Vercel (projeto existente)

Landing já no ar: **comparedocs-landing**

1. Abra: https://vercel.com/jprl123s-projects/comparedocs-landing/settings/git  
2. **Connect Git Repository** → GitHub → **jprl123/DiffAI**  
3. **Root Directory** (obrigatório):

   ```
   landing
   ```

4. Framework: **Next.js** (auto)  
5. Salve e faça **Redeploy**

### Passo 2 (alternativa) — Importar projeto novo

1. https://vercel.com/new  
2. **Import** → **DiffAI**  
3. **Root Directory** → **Edit** → mesma pasta acima  
4. Nome sugerido: `diffai-landing`  
5. Adicione as envs da seção 2 → **Deploy**

> O deploy anterior (via Cursor, sem Git) continua funcionando até você
> conectar o repo. Depois de conectar, cada `git push` na `main` redeploya.

### Checklist se ainda não listar

- [ ] GitHub logado na Vercel = **jprl123** (Settings → Authentication)  
- [ ] App Vercel com acesso a **DiffAI** (privado)  
- [ ] Root Directory = subpasta da landing (não a raiz do repo)  
- [ ] Branch = **main**

---

## 2. Variáveis na Vercel (passo a passo)

Guia Railway completo: **[docs/RAILWAY.md](RAILWAY.md)**

1. Abra https://vercel.com → projeto da landing (ex.: **comparedocs-landing** ou **diffai-landing**)
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

## 3. Subir a API de licenças no Railway

**Guia detalhado:** [docs/RAILWAY.md](RAILWAY.md) — Dockerfile, volume `/data`, envs, webhook Stripe.

Resumo:

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
