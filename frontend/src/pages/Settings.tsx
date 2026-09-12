import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import type { Session } from '@supabase/supabase-js'
import { api } from '../lib/api'
import { apiFetch } from '../lib/supabase'

type Niche = { id: string; label: string }

type Profile = {
  business_name?: string
  positioning?: string
  audience?: string
  offer?: string
  cta_text?: string
  website_url?: string
  active_niche_id?: string
  custom_niche_text?: string
  niche_label?: string
  schedule_enabled?: boolean
  schedule_time?: string
  timezone?: string
  niches?: Niche[]
  ai_ready?: boolean
  ai_provider?: string
  ai_model?: string
  ai_key_masked?: string
  image_ready?: boolean
  image_provider?: string
  image_model?: string
  image_key_masked?: string
  linkedin_connected?: boolean
  linkedin_author_urn?: string
  linkedin_access_token_masked?: string
  instagram_connected?: boolean
  instagram_account_id?: string
  instagram_access_token_masked?: string
  public_base_url?: string
  instagram_location_id?: string
  instagram_location_name?: string
}

type OutletCtx = { session: Session }

const fieldClass = 'mt-1 w-full rounded-lg bg-navy-900 border border-white/10 px-3 py-2 text-sm'
const labelClass = 'text-xs text-gray-500 uppercase tracking-wider'

export default function Settings() {
  const { session } = useOutletContext<OutletCtx>()
  const accessToken = session.access_token
  const [profile, setProfile] = useState<Profile | null>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [confirm, setConfirm] = useState('')

  const [businessName, setBusinessName] = useState('')
  const [positioning, setPositioning] = useState('')
  const [audience, setAudience] = useState('')
  const [offer, setOffer] = useState('')
  const [cta, setCta] = useState('')
  const [website, setWebsite] = useState('')
  const [nicheId, setNicheId] = useState('ai_automation')
  const [customNiche, setCustomNiche] = useState('')
  const [scheduleEnabled, setScheduleEnabled] = useState(false)
  const [scheduleTime, setScheduleTime] = useState('09:00')
  const [timezone, setTimezone] = useState('Asia/Kolkata')

  const [aiProvider, setAiProvider] = useState('openrouter')
  const [aiModel, setAiModel] = useState('')
  const [aiKey, setAiKey] = useState('')
  const [imageProvider, setImageProvider] = useState('puter')
  const [imageModel, setImageModel] = useState('')
  const [imageKey, setImageKey] = useState('')
  const [liToken, setLiToken] = useState('')
  const [liUrn, setLiUrn] = useState('')
  const [igToken, setIgToken] = useState('')
  const [igAccount, setIgAccount] = useState('')
  const [publicBase, setPublicBase] = useState('')
  const [igLocationId, setIgLocationId] = useState('')
  const [igLocationName, setIgLocationName] = useState('')

  async function load() {
    const { data } = await api.get('/api/profile')
    setProfile(data)
    setBusinessName(data.business_name || '')
    setPositioning(data.positioning || '')
    setAudience(data.audience || '')
    setOffer(data.offer || '')
    setCta(data.cta_text || '')
    setWebsite(data.website_url || '')
    setNicheId(data.active_niche_id || 'ai_automation')
    setCustomNiche(data.custom_niche_text || '')
    setScheduleEnabled(Boolean(data.schedule_enabled))
    setScheduleTime(data.schedule_time || '09:00')
    setTimezone(data.timezone || 'Asia/Kolkata')
    setAiProvider(data.ai_provider || 'openrouter')
    setAiModel(data.ai_model || '')
    setAiKey('')
    setImageProvider(data.image_provider || 'puter')
    setImageModel(data.image_model || '')
    setImageKey('')
    setLiToken('')
    setLiUrn(data.linkedin_author_urn || '')
    setIgToken('')
    setIgAccount(data.instagram_account_id || '')
    setPublicBase(data.public_base_url || '')
    setIgLocationId(data.instagram_location_id || '')
    setIgLocationName(data.instagram_location_name || '')
  }

  useEffect(() => {
    load().catch((e) => setMsg(e instanceof Error ? e.message : String(e)))
  }, [])

  async function saveProfile() {
    setBusy(true)
    setMsg('')
    try {
      await api.put('/api/profile', {
        business_name: businessName,
        positioning,
        audience,
        offer,
        cta_text: cta,
        website_url: website,
        active_niche_id: nicheId,
        custom_niche_text: customNiche,
        schedule_enabled: scheduleEnabled,
        schedule_time: scheduleTime,
        timezone,
      })
      setMsg('Brand / category / schedule saved.')
      await load()
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function saveAi() {
    setBusy(true)
    setMsg('')
    try {
      await api.post('/api/settings/ai', {
        provider: aiProvider,
        model_name: aiModel,
        api_key: aiKey,
      })
      setMsg('AI settings saved.')
      setAiKey('')
      await load()
    } catch (e) {
      setMsg((e as any)?.response?.data?.detail || (e instanceof Error ? e.message : String(e)))
    } finally {
      setBusy(false)
    }
  }

  async function saveImage() {
    setBusy(true)
    setMsg('')
    try {
      await api.post('/api/settings/image', {
        provider: imageProvider,
        model_name: imageModel,
        api_key: imageKey,
      })
      setMsg('Image settings saved.')
      setImageKey('')
      await load()
    } catch (e) {
      setMsg((e as any)?.response?.data?.detail || (e instanceof Error ? e.message : String(e)))
    } finally {
      setBusy(false)
    }
  }

  async function saveLinkedIn() {
    setBusy(true)
    setMsg('')
    try {
      await api.post('/api/settings/linkedin', {
        access_token: liToken,
        author_urn: liUrn,
      })
      setMsg('LinkedIn connected.')
      setLiToken('')
      await load()
    } catch (e) {
      setMsg((e as any)?.response?.data?.detail || (e instanceof Error ? e.message : String(e)))
    } finally {
      setBusy(false)
    }
  }

  async function saveInstagram() {
    setBusy(true)
    setMsg('')
    try {
      await api.post('/api/settings/instagram', {
        access_token: igToken,
        account_id: igAccount,
        public_base_url: publicBase || 'https://example.com',
        location_id: igLocationId || null,
        location_name: igLocationName || null,
      })
      setMsg('Instagram connected.')
      setIgToken('')
      await load()
    } catch (e) {
      setMsg((e as any)?.response?.data?.detail || (e instanceof Error ? e.message : String(e)))
    } finally {
      setBusy(false)
    }
  }

  async function resetStorage() {
    if (confirm.trim().toUpperCase() !== 'RESET') {
      setMsg('Type RESET in the box to confirm.')
      return
    }
    if (
      !window.confirm(
        'This clears Supabase Storage images, cloud drafts/assets, and local pipeline runs / drafts.',
      )
    ) {
      return
    }
    setBusy(true)
    setMsg('')
    try {
      const res = await apiFetch('/api/saas/reset-storage', accessToken, {
        method: 'POST',
        body: JSON.stringify({ confirm: 'RESET', all_brands: false }),
      })
      setMsg(
        `Reset done. Runs: ${res.local?.local_counts?.pipeline_runs ?? '?'}. Files: ${res.cloud?.files_deleted ?? 0}.`,
      )
      setConfirm('')
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const niches = profile?.niches || []
  const isCustom = nicheId === 'custom'

  return (
    <>
      <header className="border-b border-white/5 px-6 py-4 sticky top-0 bg-navy-900/90 backdrop-blur z-10">
        <h1 className="text-lg font-semibold">Settings</h1>
        <p className="text-xs text-gray-500">Brand, category, schedule, and connections</p>
      </header>

      <main className="w-full p-6 space-y-8">
        {msg && <p className="text-sm text-subtle-cyan break-all">{msg}</p>}

        <section className="glass-card p-5 space-y-4">
          <h2 className="text-base font-medium">Brand</h2>
          {[
            ['Business name', businessName, setBusinessName],
            ['Positioning', positioning, setPositioning],
            ['Audience', audience, setAudience],
            ['Offer', offer, setOffer],
            ['CTA', cta, setCta],
            ['Website', website, setWebsite],
          ].map(([label, value, setter]) => (
            <div key={String(label)}>
              <label className={labelClass}>{label as string}</label>
              <input
                className={fieldClass}
                value={value as string}
                onChange={(e) => (setter as (v: string) => void)(e.target.value)}
              />
            </div>
          ))}
        </section>

        <section className="glass-card p-5 space-y-4">
          <h2 className="text-base font-medium">Category (niche)</h2>
          <p className="text-xs text-gray-500">Every Generate uses only this category.</p>
          <select className={fieldClass} value={nicheId} onChange={(e) => setNicheId(e.target.value)}>
            {niches.map((n) => (
              <option key={n.id} value={n.id}>
                {n.label}
              </option>
            ))}
          </select>
          {isCustom && (
            <input
              className={fieldClass}
              value={customNiche}
              onChange={(e) => setCustomNiche(e.target.value)}
              placeholder="Custom keywords / niche"
            />
          )}
        </section>

        <section className="glass-card p-5 space-y-4">
          <h2 className="text-base font-medium">Schedule</h2>
          <label className="flex items-center gap-2 text-sm text-gray-300">
            <input
              type="checkbox"
              checked={scheduleEnabled}
              onChange={(e) => setScheduleEnabled(e.target.checked)}
            />
            Enable daily schedule
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className={labelClass}>Time</label>
              <input
                className={fieldClass}
                value={scheduleTime}
                onChange={(e) => setScheduleTime(e.target.value)}
                placeholder="09:00"
              />
            </div>
            <div>
              <label className={labelClass}>Timezone</label>
              <input className={fieldClass} value={timezone} onChange={(e) => setTimezone(e.target.value)} />
            </div>
          </div>
        </section>

        <button
          type="button"
          className="primary-button text-sm disabled:opacity-50"
          disabled={busy}
          onClick={saveProfile}
        >
          {busy ? 'Saving…' : 'Save brand & schedule'}
        </button>

        <section className="glass-card p-5 space-y-6">
          <div>
            <h2 className="text-base font-medium text-white">Connections</h2>
            <p className="text-xs text-gray-500 mt-1">
              Leave API key blank to keep the current key. Saved into server <code className="text-subtle-cyan">.env</code>.
            </p>
          </div>

          <div className="space-y-3 border-t border-white/5 pt-4">
            <h3 className="text-sm font-medium text-gray-200">AI writing</h3>
            <p className="text-xs text-gray-500 font-mono">{profile?.ai_key_masked || 'no key'}</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className={labelClass}>Provider</label>
                <select className={fieldClass} value={aiProvider} onChange={(e) => setAiProvider(e.target.value)}>
                  <option value="openrouter">openrouter</option>
                  <option value="openai">openai</option>
                </select>
              </div>
              <div>
                <label className={labelClass}>Model</label>
                <input className={fieldClass} value={aiModel} onChange={(e) => setAiModel(e.target.value)} />
              </div>
            </div>
            <div>
              <label className={labelClass}>API key (new)</label>
              <input
                className={fieldClass}
                type="password"
                autoComplete="off"
                value={aiKey}
                onChange={(e) => setAiKey(e.target.value)}
                placeholder="Leave blank to keep current"
              />
            </div>
            <button type="button" className="secondary-button text-sm disabled:opacity-50" disabled={busy} onClick={saveAi}>
              Save AI
            </button>
          </div>

          <div className="space-y-3 border-t border-white/5 pt-4">
            <h3 className="text-sm font-medium text-gray-200">Image generation</h3>
            <p className="text-xs text-gray-500 font-mono">{profile?.image_key_masked || 'no key'}</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className={labelClass}>Provider</label>
                <select
                  className={fieldClass}
                  value={imageProvider}
                  onChange={(e) => setImageProvider(e.target.value)}
                >
                  <option value="puter">puter</option>
                  <option value="openrouter">openrouter</option>
                  <option value="dalle">dalle</option>
                  <option value="gemini">gemini</option>
                  <option value="mock">mock</option>
                </select>
              </div>
              <div>
                <label className={labelClass}>Model</label>
                <input className={fieldClass} value={imageModel} onChange={(e) => setImageModel(e.target.value)} />
              </div>
            </div>
            <div>
              <label className={labelClass}>API key / Puter token (new)</label>
              <input
                className={fieldClass}
                type="password"
                autoComplete="off"
                value={imageKey}
                onChange={(e) => setImageKey(e.target.value)}
                placeholder="Leave blank to keep current"
              />
            </div>
            <button
              type="button"
              className="secondary-button text-sm disabled:opacity-50"
              disabled={busy}
              onClick={saveImage}
            >
              Save image
            </button>
          </div>

          <div className="space-y-3 border-t border-white/5 pt-4">
            <h3 className="text-sm font-medium text-gray-200">
              LinkedIn{' '}
              <span className="text-xs font-normal text-gray-500">
                ({profile?.linkedin_connected ? 'connected' : 'not connected'})
              </span>
            </h3>
            <div>
              <label className={labelClass}>Author URN</label>
              <input
                className={fieldClass}
                value={liUrn}
                onChange={(e) => setLiUrn(e.target.value)}
                placeholder="urn:li:person:… or urn:li:organization:…"
              />
            </div>
            <div>
              <label className={labelClass}>Access token (new)</label>
              <input
                className={fieldClass}
                type="password"
                autoComplete="off"
                value={liToken}
                onChange={(e) => setLiToken(e.target.value)}
                placeholder={profile?.linkedin_access_token_masked || 'Leave blank to keep current'}
              />
            </div>
            <button
              type="button"
              className="secondary-button text-sm disabled:opacity-50"
              disabled={busy}
              onClick={saveLinkedIn}
            >
              Save LinkedIn
            </button>
          </div>

          <div className="space-y-3 border-t border-white/5 pt-4">
            <h3 className="text-sm font-medium text-gray-200">
              Instagram{' '}
              <span className="text-xs font-normal text-gray-500">
                ({profile?.instagram_connected ? 'connected' : 'not connected'})
              </span>
            </h3>
            <div>
              <label className={labelClass}>Account ID</label>
              <input className={fieldClass} value={igAccount} onChange={(e) => setIgAccount(e.target.value)} />
            </div>
            <div>
              <label className={labelClass}>Access token (new)</label>
              <input
                className={fieldClass}
                type="password"
                autoComplete="off"
                value={igToken}
                onChange={(e) => setIgToken(e.target.value)}
                placeholder={profile?.instagram_access_token_masked || 'Leave blank to keep current'}
              />
            </div>
            <div>
              <label className={labelClass}>Public base URL (for Graph fetch)</label>
              <input
                className={fieldClass}
                value={publicBase}
                onChange={(e) => setPublicBase(e.target.value)}
                placeholder="https://…"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className={labelClass}>Location ID (optional)</label>
                <input className={fieldClass} value={igLocationId} onChange={(e) => setIgLocationId(e.target.value)} />
              </div>
              <div>
                <label className={labelClass}>Location name (optional)</label>
                <input
                  className={fieldClass}
                  value={igLocationName}
                  onChange={(e) => setIgLocationName(e.target.value)}
                />
              </div>
            </div>
            <button
              type="button"
              className="secondary-button text-sm disabled:opacity-50"
              disabled={busy}
              onClick={saveInstagram}
            >
              Save Instagram
            </button>
          </div>
        </section>

        <section className="rounded-xl border border-red-500/30 bg-red-500/5 p-5 space-y-4">
          <h2 className="text-lg font-medium text-red-200">Reset platform</h2>
          <p className="text-sm text-gray-400">
            Clears Supabase Storage images, cloud drafts/assets, and local pipeline runs / drafts.
          </p>
          <input
            className="w-full max-w-xs rounded-lg bg-navy-900 border border-white/10 px-3 py-2 text-sm"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="Type RESET"
          />
          <button
            type="button"
            disabled={busy}
            onClick={resetStorage}
            className="rounded-lg bg-red-600/90 hover:bg-red-600 px-4 py-2 text-sm font-semibold disabled:opacity-50"
          >
            {busy ? 'Clearing…' : 'Reset platform'}
          </button>
        </section>
      </main>
    </>
  )
}
