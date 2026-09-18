import { api } from './api'
import { apiBase, apiFetch } from './supabase'

export type Draft = {
  id: string
  title: string
  status?: string
  state?: string
  linkedin_post?: string
  instagram_caption?: string
  date?: string
  image_url?: string
  image_urls?: string[]
  text?: string
  hook?: string
}

export function absUrl(url?: string) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  return `${apiBase}${url.startsWith('/') ? '' : '/'}${url}`
}

export async function loadDrafts(token: string, opts?: { localOnly?: boolean }): Promise<Draft[]> {
  // Local drafts for THIS account only (API scopes by JWT → tenant DB)
  const latestRes = await api.get('/api/content/latest').catch(() => null)
  let local: Draft[] = []
  if (latestRes?.data) {
    local = (latestRes.data || []).map((d: Draft & { status?: string }) => ({
      ...d,
      state: d.status || d.state,
    }))
  }

  if (opts?.localOnly) {
    local.sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')))
    return local
  }

  try {
    const me = await apiFetch('/api/saas/me', token)
    const brandId = me.brands?.[0]?.id
    if (brandId) {
      const cloud = await apiFetch(
        `/api/saas/drafts?brand_id=${encodeURIComponent(brandId)}`,
        token,
      )
      const byId = new Map<string, Draft>()
      for (const d of local) byId.set(String(d.id), d)
      for (const raw of cloud.drafts || []) {
        const assets = (raw.generated_assets || []) as { url?: string; asset_type?: string }[]
        const urls = assets.map((a) => a.url).filter(Boolean) as string[]
        byId.set(String(raw.id), {
          id: String(raw.id),
          title: raw.title,
          state: raw.state,
          status: raw.state,
          linkedin_post: raw.linkedin_post,
          instagram_caption: raw.instagram_caption,
          date: raw.created_at ? String(raw.created_at).slice(0, 16).replace('T', ' ') : '',
          image_url: urls[0],
          image_urls: urls,
        })
      }
      local = Array.from(byId.values())
    }
  } catch {
    /* local only */
  }

  local.sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')))
  return local
}
