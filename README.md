# Daily Content Agent

Sellable content product: niche news → brand LinkedIn/Instagram drafts (React + FastAPI + Supabase).

## Web app

See **[docs/SAAS_SETUP.md](docs/SAAS_SETUP.md)** for Supabase keys, SQL, and Storage.

## Deploy (Render)

See **[docs/RENDER_DEPLOY.md](docs/RENDER_DEPLOY.md)**. Blueprint: `render.yaml` (API + static web).

```bash
# API
python -m initials_agent serve --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

Sidebar: **Dashboard** (generate/posts) · **Topics** (research history + category) · **Settings** (brand, niche, schedule, reset).

## Setup

```bash
python -m venv venv
# Windows: .\venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env   # AI__, IMAGE__, SUPABASE__*
alembic upgrade head
```

## CLI

- `python -m initials_agent serve` — FastAPI for the React app
- `python -m initials_agent run` — one pipeline run (`--dry-run`, `--no-image`, `--no-publish`)
- `python -m initials_agent scheduler start` — daily daemon
- `python -m initials_agent approval list|approve|reject`
- `python -m initials_agent analytics report`

## Security

- Never commit `.env` or service-role keys
- Browser only gets the Supabase **anon** key; API keys stay on the server
- CORS defaults to local Vite origins (`CORS_ORIGINS` to override)

```bash
pytest tests/
```
