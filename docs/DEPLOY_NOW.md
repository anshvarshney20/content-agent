# Deploy NOW — Render + Puter

You need a **GitHub repo**. This folder is not pushed yet.

## Step 0 — Push to GitHub (once)

In a terminal (from `initials-content-agent`):

```bash
cd e:\Personal_Repos\initials-content-agent
git init
git add .
git commit -m "Deploy Daily Content Agent to Render"
```

Create an empty repo on GitHub (e.g. `daily-content-agent`), then:

```bash
git remote add origin https://github.com/YOUR_USER/daily-content-agent.git
git branch -M main
git push -u origin main
```

(Do **not** commit `.env` — secrets stay in Render.)

## Step 1 — Render Blueprint

1. Go to [https://dashboard.render.com](https://dashboard.render.com)
2. **New** → **Blueprint**
3. Connect the GitHub repo
4. Render reads `render.yaml` → creates:
   - `daily-content-api` (Docker = Python + Node + Puter)
   - `daily-content-web` (React static)

## Step 2 — Secrets to paste (API)

| Key | Value |
|-----|--------|
| `SUPABASE__URL` | your project URL |
| `SUPABASE__ANON_KEY` | anon key |
| `SUPABASE__SERVICE_ROLE_KEY` | service role |
| `SAAS__CRON_SECRET` | any long random string |
| `SAAS__ADMIN_EMAILS` | `admin@dailycontent.demo` or your email |
| `SAAS__CORS_ORIGINS` | leave placeholder; update after web URL exists |
| `AI__API_KEY` | OpenRouter key (for **text**) |
| `IMAGE__API_KEY` | your **Puter** auth token |
| `IMAGE__PROVIDER` | already `puter` in blueprint |

## Step 3 — Secrets to paste (Web / static)

| Key | Value |
|-----|--------|
| `VITE_SUPABASE_URL` | same Supabase URL |
| `VITE_SUPABASE_ANON_KEY` | anon only |
| `VITE_API_BASE_URL` | `https://daily-content-api.onrender.com` (use your real API URL after it exists) |

## Step 4 — After first deploy (cross-link)

1. Copy **API URL** → set Web env `VITE_API_BASE_URL` → **Manual Deploy** web  
2. Copy **Web URL** → set API env `SAAS__CORS_ORIGINS` to that URL → restart API  
3. Supabase → Authentication → URL config → add Web URL as Site URL + Redirect  

## Step 5 — Test

1. Open Web URL (first load may be slow — free sleep)  
2. Login  
3. Generate a post (Puter image)  
4. `/admin` if your email is allowlisted  

## If build fails

- API Docker logs: Node/Puter `npm ci` or pip errors  
- Web: missing `VITE_*` at build time  

Full detail: [RENDER_DEPLOY.md](./RENDER_DEPLOY.md)
