# Deploy to Render

**Do this now:** follow **[DEPLOY_NOW.md](./DEPLOY_NOW.md)** (GitHub → Blueprint → secrets).

Two services: **API** (Docker = FastAPI + Node/Puter) + **Web** (Vite static). Supabase = DB/Auth/Storage.

## Images

Production uses **Puter** (`IMAGE__PROVIDER=puter`). The API Docker image installs Node and `scripts/puter`.

Text generation still uses **OpenRouter** (`AI__API_KEY`) — free/cheap text models exist; image gen stays on Puter.

## 2. Create services

### Option A — Blueprint (recommended)

1. Render Dashboard → **New** → **Blueprint**
2. Connect the repo → select `render.yaml`
3. Fill **sync: false** secrets when prompted (see table below)
4. Deploy

### Option B — Manual

**Web Service (API)**

| Field | Value |
|-------|--------|
| Runtime | Python 3 |
| Build | `pip install -r requirements-render.txt` |
| Start | `python -m initials_agent serve --host 0.0.0.0 --port $PORT` |
| Health | `/api/health` |

**Static Site (frontend)**

| Field | Value |
|-------|--------|
| Root directory | `frontend` |
| Build | `npm ci && npm run build` |
| Publish | `dist` |
| Rewrite | `/*` → `/index.html` (SPA) |

## 3. Environment variables

### API (`daily-content-api`)

| Key | Notes |
|-----|--------|
| `SUPABASE__URL` | Project URL |
| `SUPABASE__ANON_KEY` | anon public |
| `SUPABASE__SERVICE_ROLE_KEY` | **secret** — server only |
| `SUPABASE__STORAGE_BUCKET` | `post-images` |
| `SAAS__ENABLED` | `true` |
| `SAAS__CRON_SECRET` | long random string |
| `SAAS__ADMIN_EMAILS` | your admin email(s), comma-separated |
| `SAAS__CORS_ORIGINS` | **your Static Site URL**, e.g. `https://daily-content-web.onrender.com` |
| `AI__PROVIDER` | `openrouter` |
| `AI__API_KEY` | OpenRouter key |
| `AI__MODEL_NAME` | e.g. `deepseek/deepseek-v4-flash-0731` |
| `IMAGE__PROVIDER` | `openrouter` (recommended on Render) |
| `IMAGE__API_KEY` | same OpenRouter key OK |
| `IMAGE__MODEL_NAME` | e.g. `openai/gpt-image-2` |
| `APP__ENVIRONMENT` | `production` |
| `DB__CONNECTION_STRING` | `sqlite:///tmp/daily_content_agent.db` (ephemeral — see note) |

### Web (`daily-content-web`)

| Key | Notes |
|-----|--------|
| `VITE_SUPABASE_URL` | same as API |
| `VITE_SUPABASE_ANON_KEY` | anon key only (**never** service role) |
| `VITE_API_BASE_URL` | API URL, e.g. `https://daily-content-api.onrender.com` |

Vite bakes `VITE_*` at **build** time — change them → **clear build cache / redeploy** the static site.

## 4. After first deploy

1. Copy API URL → set `VITE_API_BASE_URL` on the static site → redeploy web  
2. Copy Web URL → set `SAAS__CORS_ORIGINS` on the API → restart API  
3. Supabase Auth → **URL configuration** → add Web URL to Redirect URLs / Site URL  
4. Sign in at the Web URL; open `/admin` with an allowlisted email  

## 5. Cron / scheduler

Free web services **sleep**. For daily generate:

- External cron ([cron-job.org](https://cron-job.org)):  
  `POST https://YOUR-API.onrender.com/api/internal/cron/daily`  
  Header: `X-Cron-Secret: <SAAS__CRON_SECRET>`  
- Or Render Cron (paid) hitting the same endpoint  

## 6. Important limits

- **Free API sleeps** after idle (~15 min) — first request can take 30–60s  
- **Disk is ephemeral** — tenant SQLite under `/tmp` resets on redeploy. Cloud drafts/jobs/images live in **Supabase**; treat local SQLite as a scratch cache  
- **Puter** image provider may fail on Render; use OpenRouter images  
- Never put `SERVICE_ROLE` in the frontend  

## 7. Smoke test

```bash
curl https://YOUR-API.onrender.com/api/health
# → {"ok":true,...}
```

Open the Static Site → login → Generate → Admin → Accounts.
