# SaaS setup — required things

You need these accounts and values before the web product can run end-to-end.

## 1. Supabase (required — free tier OK)

1. Create a project at [https://supabase.com](https://supabase.com)
2. Copy from **Project Settings → API**:
   - `SUPABASE__URL` — Project URL  
   - `SUPABASE__ANON_KEY` — `anon` `public` key (React)  
   - `SUPABASE__SERVICE_ROLE_KEY` — `service_role` key (**server only, never in React**)
3. Copy from **Project Settings → Database**:
   - `DB__CONNECTION_STRING` — URI mode connection string  
     Example: `postgresql://postgres.[ref]:[PASSWORD]@aws-0-….pooler.supabase.com:6543/postgres`  
     Prefer the **Transaction pooler** URI for Render/FastAPI.
4. In **SQL Editor**, run the full file:  
   `supabase/migrations/001_saas_schema.sql`
5. Confirm **Storage** bucket `post-images` exists and is **public**.
6. Auth → enable **Email** (magic link or password).

## 2. FastAPI env (server)

Copy from `.env.example` into `.env` (or Render env vars):

| Variable | Required | Purpose |
|----------|----------|---------|
| `SUPABASE__URL` | Yes | Supabase project |
| `SUPABASE__ANON_KEY` | Yes | JWT validation / client |
| `SUPABASE__SERVICE_ROLE_KEY` | Yes | Jobs, tokens, Storage upload |
| `DB__CONNECTION_STRING` | Yes | Postgres (Supabase) |
| `SAAS__CRON_SECRET` | Yes | Protects `/api/internal/cron/daily` |
| `SAAS__ADMIN_EMAILS` | Yes for admin | Comma-separated emails allowed at `/admin` |
| `SAAS__CORS_ORIGINS` | Yes | Your React URL(s), comma-separated |
| `AI__API_KEY` | Yes | OpenRouter / writing |
| `AI__PROVIDER` | Yes | `openrouter` |
| `IMAGE__API_KEY` | Yes for images | Puter / image provider |
| `IMAGE__PROVIDER` | Optional | default `puter` |
| `INSTAGRAM__*` | Per brand later | Can stay in DB `social_connections` |
| `APP__PUBLIC_BASE_URL` | Optional | Fallback; prefer Supabase Storage URLs |

Desktop Instagram keys in `.env` can remain for local publishing tests.

## 3. React env (`frontend/.env`)

```env
VITE_SUPABASE_URL=https://xxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
VITE_API_BASE_URL=http://127.0.0.1:8000
```

On production, set `VITE_API_BASE_URL` to your Render FastAPI URL.

## 4. Run locally (dev)

```bash
# API (from repo root, venv on)
pip install -e ".[saas]"
python -m initials_agent serve --reload --port 8000

# React
cd frontend
npm install
npm run dev
```

Open the Vite URL → Sign up → you get a `brands` row automatically.

Sidebar: **Dashboard** · **Topics** · **Settings** (brand + niche category). Allowlisted emails also see **Admin** (`/admin`) for platform overview, accounts, and failures.

## 5. Cron / schedule (later on Render)

- Create a **Cron Job** (or [cron-job.org](https://cron-job.org) free) daily at your time.
- `POST https://YOUR-API/api/internal/cron/daily`
- Header: `X-Cron-Secret: <same as SAAS__CRON_SECRET>`

Free Render web services **sleep** — scheduler is reliable only on always-on or external cron that can wake + wait.

## 6. Instagram / LinkedIn (per brand)

Still needed to publish:

- Instagram Graph account id + access token (`IGAA…`)
- Optional location id  
- LinkedIn token + author URN  

In SaaS these will live in `social_connections` (filled via Settings API), not only `.env`.

## 7. Deploy (Render)

Step-by-step: **[docs/RENDER_DEPLOY.md](RENDER_DEPLOY.md)** (`render.yaml` Blueprint).

| Service | Host |
|---------|------|
| React | Render Static Site |
| FastAPI | Render Web Service |
| DB / Auth / Storage | Supabase |

## What you should send / create now

Checklist — create these and paste into `.env` / `frontend/.env` (do not commit secrets):

- [ ] Supabase project URL  
- [ ] anon key  
- [ ] service_role key  
- [ ] Database connection string  
- [ ] Ran `001_saas_schema.sql`  
- [ ] Storage bucket `post-images` public  
- [ ] `SAAS__CRON_SECRET` (any long random string)  
- [ ] Existing `AI__API_KEY` (you likely have this)  
- [ ] Image provider key  

Tell the agent when Supabase keys are in `.env` and the SQL has been run — next step is wiring generate/publish jobs to Supabase rows.
