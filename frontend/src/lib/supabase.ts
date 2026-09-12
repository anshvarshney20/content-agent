import { createClient, type SupabaseClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined
const anon = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

export const supabaseConfigured = Boolean(url && anon && !url.includes('YOUR_PROJECT'))

export const supabase: SupabaseClient | null = supabaseConfigured
  ? createClient(url!, anon!)
  : null

export const apiBase = (import.meta.env.VITE_API_BASE_URL as string) || 'http://127.0.0.1:8000'

export async function apiFetch(path: string, accessToken: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers || {})
  headers.set('Authorization', `Bearer ${accessToken}`)
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const res = await fetch(`${apiBase}${path}`, { ...init, headers })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  return res.json()
}
