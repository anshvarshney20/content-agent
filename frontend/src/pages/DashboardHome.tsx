import { useEffect, useRef, useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { Play, Clock3, RefreshCw } from 'lucide-react'
import type { Session } from '@supabase/supabase-js'
import { absUrl, loadDrafts, type Draft } from '../lib/drafts'
import { api } from '../lib/api'
import GenerationProgress from '../components/GenerationProgress'

type RunData = { date: string; topic: string; status: string; platforms: string }

type PipelineStatus = {
  status: string
  run_id?: string | null
  percent?: number
  elapsed_s?: number
  eta_s?: number | null
  elapsed_label?: string
  eta_label?: string
  current_stage?: string | null
  stages?: {
    id?: string
    name: string
    status: string
    time: string
    expected_s?: number
    elapsed_s?: number | null
  }[]
  error?: string | null
}

type OutletCtx = { session: Session; onSignOut: () => void }

export default function DashboardHome() {
  const { session } = useOutletContext<OutletCtx>()
  const navigate = useNavigate()
  const token = session.access_token
  const [stats, setStats] = useState({ totalRuns: 0, linkedinPosts: 0, instagramPosts: 0, nextRun: '--' })
  const [runs, setRuns] = useState<RunData[]>([])
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [nicheLabel, setNicheLabel] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null)
  const [runsLoading, setRunsLoading] = useState(true)
  const nicheLoaded = useRef(false)

  async function load(opts?: { soft?: boolean }) {
    if (!opts?.soft) setRunsLoading(true)
    try {
      const tasks: Promise<unknown>[] = [
        api.get('/api/stats').then((r) => setStats(r.data)),
        api.get('/api/pipeline/runs').then((r) => setRuns((r.data || []).slice(0, 8))),
      ]
      if (!opts?.soft || !nicheLoaded.current) {
        tasks.push(
          api.get('/api/profile').then((r) => {
            setNicheLabel(r.data.niche_label || '')
            nicheLoaded.current = true
          }),
        )
      }
      if (!opts?.soft) {
        tasks.push(loadDrafts(token).then(setDrafts))
      }
      await Promise.allSettled(tasks)
    } finally {
      setRunsLoading(false)
    }
  }

  async function pollStatus(runId?: string | null) {
    const q = runId ? `?run_id=${encodeURIComponent(runId)}` : ''
    try {
      const { data } = await api.get(`/api/pipeline/status${q}`)
      setPipeline(data)
      return data as PipelineStatus
    } catch {
      return null
    }
  }

  useEffect(() => {
    load().catch(() => {})
    pollStatus(activeRunId).catch(() => {})

    const running = Boolean(activeRunId) || busy
    // Idle: light poll every 12s. Generating: status every 2s, skip heavy lists.
    const intervalMs = running ? 2000 : 12000
    const t = setInterval(() => {
      if (running) {
        pollStatus(activeRunId).catch(() => {})
      } else {
        load({ soft: true }).catch(() => {})
        pollStatus(null).catch(() => {})
      }
    }, intervalMs)
    return () => clearInterval(t)
  }, [token, activeRunId, busy])

  async function generate() {
    setBusy(true)
    setMsg('')
    try {
      const { data } = await api.post('/api/pipeline/run', {
        dry_run: false,
        no_image: false,
        no_publish: true,
      })
      const runId = data.run_id as string
      setActiveRunId(runId)
      await pollStatus(runId)

      for (let i = 0; i < 180; i++) {
        await new Promise((r) => setTimeout(r, 2000))
        const st = await pollStatus(runId)
        if (!st) continue
        if (st.status === 'completed' || st.status === 'success') {
          setMsg('Generation complete.')
          await load()
          break
        }
        if (st.status === 'failed' || st.status === 'cancelled') {
          setMsg(st.error || `Generation ${st.status}`)
          break
        }
      }
      await load()
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
      setActiveRunId(null)
    }
  }

  const showProgress =
    pipeline != null &&
    (busy ||
      pipeline.status === 'running' ||
      pipeline.status === 'failed' ||
      pipeline.status === 'cancelled' ||
      ((pipeline.status === 'completed' || pipeline.status === 'success') && Boolean(activeRunId)))

  return (
    <>
      <header className="border-b border-white/5 px-6 py-4 flex flex-wrap items-center justify-between gap-4 sticky top-0 bg-navy-900/90 backdrop-blur z-10">
        <div>
          <h1 className="text-lg font-semibold">Dashboard</h1>
          <p className="text-xs text-gray-500">
            Posts & generate
            {nicheLabel ? (
              <>
                {' '}
                · category <span className="text-electric-blue">{nicheLabel}</span>
              </>
            ) : null}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className="secondary-button flex items-center text-sm" onClick={() => load()}>
            <RefreshCw className="w-4 h-4 mr-2" /> Refresh
          </button>
          <button
            type="button"
            className="primary-button flex items-center text-sm disabled:opacity-50"
            disabled={busy}
            onClick={generate}
          >
            {busy ? <Clock3 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
            Generate
          </button>
        </div>
      </header>

      <main className="w-full p-6 space-y-8">
        {msg && <p className="text-sm text-subtle-cyan break-all">{msg}</p>}

        {showProgress && pipeline && (
          <GenerationProgress
            status={pipeline.status}
            percent={pipeline.percent ?? 0}
            elapsedLabel={pipeline.elapsed_label || '0s'}
            etaLabel={pipeline.eta_label || '--'}
            currentStage={pipeline.current_stage}
            stages={pipeline.stages || []}
            error={pipeline.error}
          />
        )}

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full">
          {[
            ['Total Runs', stats.totalRuns],
            ['LinkedIn', stats.linkedinPosts],
            ['Instagram', stats.instagramPosts],
            ['Next', stats.nextRun],
          ].map(([label, value]) => (
            <div key={String(label)} className="glass-card p-4">
              <p className="text-xs text-gray-500">{label}</p>
              <p className="text-2xl font-semibold mt-1">{value}</p>
            </div>
          ))}
        </div>

        <section className="glass-card p-5 w-full">
          <h2 className="text-lg font-semibold mb-3">Recent runs</h2>
          <div className="overflow-x-auto w-full">
            <table className="w-full min-w-[640px] text-sm text-left table-fixed">
              <thead className="text-xs uppercase text-gray-500 border-b border-white/5">
                <tr>
                  <th className="py-2 pr-4 w-[22%]">Time</th>
                  <th className="py-2 pr-4 w-[40%]">Topic</th>
                  <th className="py-2 pr-4 w-[20%]">Status</th>
                  <th className="py-2 w-[18%]">Platforms</th>
                </tr>
              </thead>
              <tbody>
                {runsLoading &&
                  Array.from({ length: 5 }).map((_, i) => (
                    <tr key={`shimmer-${i}`} className="border-b border-white/5">
                      <td className="py-3 pr-4">
                        <div className="shimmer h-3.5 w-36" />
                      </td>
                      <td className="py-3 pr-4">
                        <div className="shimmer h-3.5 w-full max-w-md" />
                      </td>
                      <td className="py-3 pr-4">
                        <div className="shimmer h-3.5 w-24" />
                      </td>
                      <td className="py-3">
                        <div className="shimmer h-3.5 w-28" />
                      </td>
                    </tr>
                  ))}
                {!runsLoading &&
                  runs.map((r, i) => (
                    <tr key={i} className="border-b border-white/5">
                      <td className="py-2 pr-4 text-gray-400 whitespace-nowrap">{r.date}</td>
                      <td className="py-2 pr-4 truncate" title={r.topic}>
                        {r.topic}
                      </td>
                      <td className="py-2 pr-4">{r.status}</td>
                      <td className="py-2 text-gray-400">{r.platforms}</td>
                    </tr>
                  ))}
                {!runsLoading && runs.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-6 text-gray-500">
                      No runs yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="glass-card p-5 w-full">
          <h2 className="text-lg font-semibold mb-4">Latest posts</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {drafts.length === 0 && (
              <p className="text-gray-500 text-sm col-span-full">No posts yet — click Generate.</p>
            )}
            {drafts.map((d) => {
              const thumb = absUrl(d.image_urls?.[0] || d.image_url)
              return (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => navigate(`/posts/${encodeURIComponent(d.id)}`)}
                  className="text-left rounded-xl overflow-hidden border border-white/10 hover:border-electric-blue/40 transition-colors bg-navy-900"
                >
                  <div className="h-36 relative bg-navy-800">
                    {thumb ? (
                      <img src={thumb} alt="" className="absolute inset-0 w-full h-full object-cover opacity-70" />
                    ) : null}
                    <div className="absolute inset-0 bg-gradient-to-t from-navy-900/90 to-transparent" />
                    <h3 className="absolute bottom-3 left-3 right-3 text-sm font-semibold line-clamp-2">{d.title}</h3>
                  </div>
                  <div className="p-3 flex justify-between text-xs text-gray-500">
                    <span>{d.status || d.state}</span>
                    <span>{d.date}</span>
                  </div>
                </button>
              )
            })}
          </div>
        </section>
      </main>
    </>
  )
}
