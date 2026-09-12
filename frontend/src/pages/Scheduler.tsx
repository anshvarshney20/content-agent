import { useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { CalendarClock, Play, RefreshCw } from 'lucide-react'
import type { Session } from '@supabase/supabase-js'
import { api } from '../lib/api'

type Niche = { id: string; label: string }
type RunRow = { id: string; date: string; status: string; retries?: number }

type OutletCtx = { session: Session }

const fieldClass = 'mt-1 w-full rounded-lg bg-navy-900 border border-white/10 px-3 py-2 text-sm'
const labelClass = 'text-xs text-gray-500 uppercase tracking-wider'

export default function Scheduler() {
  useOutletContext<OutletCtx>()
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  const [enabled, setEnabled] = useState(false)
  const [time, setTime] = useState('09:00')
  const [timezone, setTimezone] = useState('Asia/Kolkata')
  const [publishMode, setPublishMode] = useState('review')
  const [activeNiche, setActiveNiche] = useState('ai_automation')
  const [customNiche, setCustomNiche] = useState('')
  const [enabledNiches, setEnabledNiches] = useState<string[]>([])
  const [niches, setNiches] = useState<Niche[]>([])
  const [nicheLabel, setNicheLabel] = useState('')
  const [researchQuery, setResearchQuery] = useState('')
  const [nextRun, setNextRun] = useState('')
  const [runs, setRuns] = useState<RunRow[]>([])

  async function load(soft = false) {
    if (!soft) setLoading(true)
    try {
      const { data } = await api.get('/api/scheduler')
      setEnabled(Boolean(data.schedule_enabled))
      setTime(data.schedule_time || '09:00')
      setTimezone(data.timezone || 'Asia/Kolkata')
      setPublishMode(data.publish_mode || 'review')
      setActiveNiche(data.active_niche_id || 'ai_automation')
      setCustomNiche(data.custom_niche_text || '')
      setEnabledNiches(data.enabled_niche_ids || [])
      setNiches(data.niches || [])
      setNicheLabel(data.niche_label || '')
      setResearchQuery(data.research_query || '')
      setNextRun(data.next_run || '')
      setRuns(data.recent_runs || [])
      setMsg('')
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load().catch(() => {})
    const t = setInterval(() => load(true).catch(() => {}), 5000)
    return () => clearInterval(t)
  }, [])

  function toggleNiche(id: string) {
    setEnabledNiches((prev) => {
      if (prev.includes(id)) {
        if (id === activeNiche) return prev
        return prev.filter((x) => x !== id)
      }
      return [...prev, id]
    })
  }

  async function save() {
    setBusy(true)
    setMsg('')
    try {
      const { data } = await api.put('/api/scheduler', {
        schedule_enabled: enabled,
        schedule_time: time,
        timezone,
        publish_mode: publishMode,
        active_niche_id: activeNiche,
        custom_niche_text: customNiche,
        enabled_niche_ids: enabledNiches,
      })
      setMsg(`Saved. Next: ${data.next_run}`)
      setNicheLabel(data.niche_label || '')
      setResearchQuery(data.research_query || '')
      setNextRun(data.next_run || '')
      await load(true)
    } catch (e) {
      setMsg((e as any)?.response?.data?.detail || (e instanceof Error ? e.message : String(e)))
    } finally {
      setBusy(false)
    }
  }

  async function runNow() {
    setBusy(true)
    setMsg('Starting scheduled generate…')
    try {
      // Persist niche selection first so the run uses it
      await api.put('/api/scheduler', {
        schedule_enabled: enabled,
        schedule_time: time,
        timezone,
        publish_mode: publishMode,
        active_niche_id: activeNiche,
        custom_niche_text: customNiche,
        enabled_niche_ids: enabledNiches,
      })
      const { data } = await api.post('/api/scheduler/run-now')
      setMsg(`Run started (${data.status}). Open Dashboard for progress.`)
      await load(true)
    } catch (e) {
      setMsg((e as any)?.response?.data?.detail || (e instanceof Error ? e.message : String(e)))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <header className="border-b border-white/5 px-6 py-4 flex flex-wrap items-center justify-between gap-4 sticky top-0 bg-navy-900/90 backdrop-blur z-10">
        <div>
          <h1 className="text-lg font-semibold flex items-center gap-2">
            <CalendarClock className="w-5 h-5 text-electric-blue" /> Scheduler
          </h1>
          <p className="text-xs text-gray-500">
            Daily run · niche topics · {nextRun || '—'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="secondary-button text-sm flex items-center" onClick={() => load()}>
            <RefreshCw className="w-4 h-4 mr-2" /> Refresh
          </button>
          <button
            type="button"
            className="primary-button text-sm flex items-center disabled:opacity-50"
            disabled={busy}
            onClick={runNow}
          >
            <Play className="w-4 h-4 mr-2" /> Run now
          </button>
        </div>
      </header>

      <main className="w-full p-6 space-y-8">
        {msg && <p className="text-sm text-subtle-cyan break-all">{msg}</p>}

        <section className="glass-card p-5 space-y-4 w-full">
          <h2 className="text-base font-medium">Daily schedule</h2>
          <label className="flex items-center gap-2 text-sm text-gray-300">
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
            Enable automatic daily generate
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className={labelClass}>Time</label>
              <input className={fieldClass} value={time} onChange={(e) => setTime(e.target.value)} placeholder="09:00" />
            </div>
            <div>
              <label className={labelClass}>Timezone</label>
              <input className={fieldClass} value={timezone} onChange={(e) => setTimezone(e.target.value)} />
            </div>
            <div>
              <label className={labelClass}>Publish mode</label>
              <select className={fieldClass} value={publishMode} onChange={(e) => setPublishMode(e.target.value)}>
                <option value="review">Review first (no auto-publish)</option>
                <option value="auto_linkedin">Auto LinkedIn</option>
                <option value="auto_instagram">Auto Instagram</option>
                <option value="auto_both">Auto both</option>
              </select>
            </div>
          </div>
          <p className="text-xs text-gray-500">
            Keep the scheduler daemon running on your server for automatic daily posts. Use <span className="text-gray-400">Run now</span> below for a one-off generation.
          </p>
        </section>

        <section className="glass-card p-5 space-y-4 w-full">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <h2 className="text-base font-medium">Topic niche</h2>
              <p className="text-xs text-gray-500 mt-1">
                Active: <span className="text-electric-blue">{nicheLabel || '—'}</span>
              </p>
            </div>
            <Link to="/topics" className="text-xs text-electric-blue">
              View recent topics →
            </Link>
          </div>

          <div>
            <label className={labelClass}>Active category for Generate / schedule</label>
            <select
              className={fieldClass}
              value={activeNiche}
              onChange={(e) => {
                const id = e.target.value
                setActiveNiche(id)
                if (!enabledNiches.includes(id)) setEnabledNiches((p) => [...p, id])
              }}
            >
              {niches.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.label}
                </option>
              ))}
            </select>
          </div>

          {activeNiche === 'custom' && (
            <div>
              <label className={labelClass}>Custom topic keywords</label>
              <input
                className={fieldClass}
                value={customNiche}
                onChange={(e) => setCustomNiche(e.target.value)}
                placeholder="e.g. AI agents healthcare compliance"
              />
            </div>
          )}

          <div>
            <label className={labelClass}>Enabled niches (select topics to rotate / keep available)</label>
            <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {loading
                ? Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="shimmer h-10 rounded-lg" />
                  ))
                : niches.map((n) => {
                    const on = enabledNiches.includes(n.id)
                    const active = n.id === activeNiche
                    return (
                      <label
                        key={n.id}
                        className={`flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm cursor-pointer transition-colors ${
                          on
                            ? 'border-electric-blue/30 bg-electric-blue/5 text-white'
                            : 'border-white/10 text-gray-400 hover:border-white/20'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={on}
                          disabled={active}
                          onChange={() => toggleNiche(n.id)}
                        />
                        <span className="min-w-0 truncate">
                          {n.label}
                          {active ? ' · active' : ''}
                        </span>
                      </label>
                    )
                  })}
            </div>
          </div>

          <div className="rounded-lg border border-white/5 bg-navy-900/50 p-3">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Research query</p>
            <p className="text-sm text-subtle-cyan break-words">{researchQuery || '—'}</p>
          </div>
        </section>

        <button
          type="button"
          className="primary-button text-sm disabled:opacity-50"
          disabled={busy}
          onClick={save}
        >
          {busy ? 'Saving…' : 'Save scheduler'}
        </button>

        <section className="glass-card p-5 w-full">
          <h2 className="text-lg font-semibold mb-3">Recent schedule / pipeline runs</h2>
          <div className="overflow-x-auto w-full">
            <table className="w-full min-w-[520px] text-sm text-left">
              <thead className="text-xs uppercase text-gray-500 border-b border-white/5">
                <tr>
                  <th className="py-2 pr-4">Time</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2">Retries</th>
                </tr>
              </thead>
              <tbody>
                {loading &&
                  Array.from({ length: 4 }).map((_, i) => (
                    <tr key={i} className="border-b border-white/5">
                      <td className="py-3 pr-4">
                        <div className="shimmer h-3.5 w-40" />
                      </td>
                      <td className="py-3 pr-4">
                        <div className="shimmer h-3.5 w-24" />
                      </td>
                      <td className="py-3">
                        <div className="shimmer h-3.5 w-10" />
                      </td>
                    </tr>
                  ))}
                {!loading &&
                  runs.map((r) => (
                    <tr key={r.id} className="border-b border-white/5">
                      <td className="py-2 pr-4 text-gray-400 whitespace-nowrap">{r.date}</td>
                      <td className="py-2 pr-4">{r.status}</td>
                      <td className="py-2 text-gray-400">{r.retries ?? 0}</td>
                    </tr>
                  ))}
                {!loading && runs.length === 0 && (
                  <tr>
                    <td colSpan={3} className="py-6 text-gray-500">
                      No runs yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </>
  )
}
