import { useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { RefreshCw, Tags } from 'lucide-react'
import type { Session } from '@supabase/supabase-js'
import { api } from '../lib/api'
import { ShimmerBlock } from '../components/Shimmer'

type Topic = {
  id: string
  title: string
  description?: string | null
  angle?: string | null
  score?: number | null
  date?: string
  draft_id?: string | null
  draft_title?: string | null
  draft_state?: string | null
}

type OutletCtx = { session: Session }

export default function Topics() {
  useOutletContext<OutletCtx>()
  const [topics, setTopics] = useState<Topic[]>([])
  const [niche, setNiche] = useState('')
  const [query, setQuery] = useState('')
  const [msg, setMsg] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    try {
      const { data } = await api.get('/api/topics')
      setTopics(data.topics || [])
      setNiche(data.niche_label || '')
      setQuery(data.research_query || '')
      setMsg('')
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load().catch(() => {})
  }, [])

  return (
    <>
      <header className="border-b border-white/5 px-6 py-4 flex flex-wrap items-center justify-between gap-4 sticky top-0 bg-navy-900/90 backdrop-blur z-10">
        <div>
          <h1 className="text-lg font-semibold flex items-center gap-2">
            <Tags className="w-5 h-5 text-electric-blue" /> Topics
          </h1>
          <p className="text-xs text-gray-500">
            Active category: <span className="text-gray-300">{niche || '—'}</span>
          </p>
        </div>
        <button type="button" className="secondary-button flex items-center text-sm" onClick={() => load()}>
          <RefreshCw className="w-4 h-4 mr-2" /> Refresh
        </button>
      </header>

      <main className="w-full p-6 space-y-6">
        {msg && <p className="text-sm text-red-300 break-all">{msg}</p>}

        <section className="glass-card p-5 space-y-2">
          <h2 className="text-sm font-medium text-gray-300">Research focus</h2>
          <p className="text-xs text-gray-500">
            Change category in Settings. Every Generate uses only this niche.
          </p>
          <p className="text-sm text-subtle-cyan break-words">{query || '—'}</p>
          <Link to="/settings" className="text-xs text-electric-blue inline-block mt-1">
            Edit category in Settings →
          </Link>
        </section>

        <section className="glass-card p-5">
          <h2 className="text-lg font-semibold mb-4">Recent topics</h2>
          {loading && (
            <ul className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <li key={i} className="rounded-xl border border-white/10 bg-navy-900/60 p-4 space-y-3">
                  <div className="flex justify-between gap-2">
                    <ShimmerBlock className="h-4 w-2/3 max-w-md" />
                    <ShimmerBlock className="h-3 w-20" />
                  </div>
                  <ShimmerBlock className="h-3 w-full max-w-lg" />
                  <ShimmerBlock className="h-3 w-40" />
                </li>
              ))}
            </ul>
          )}
          {!loading && topics.length === 0 && (
            <p className="text-sm text-gray-500">No topics yet — run Generate on the Dashboard.</p>
          )}
          {!loading && (
          <ul className="space-y-3">
            {topics.map((t) => (
              <li
                key={t.id}
                className="rounded-xl border border-white/10 bg-navy-900/60 p-4 space-y-2"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <h3 className="font-medium text-sm sm:text-base">{t.title}</h3>
                  <span className="text-[11px] text-gray-500 font-mono shrink-0">{t.date}</span>
                </div>
                {t.angle && <p className="text-xs text-gray-400">Angle: {t.angle}</p>}
                {typeof t.score === 'number' && (
                  <p className="text-[11px] text-gray-500">Score {t.score.toFixed(1)}</p>
                )}
                {t.draft_id ? (
                  <Link
                    to={`/posts/${encodeURIComponent(t.draft_id)}`}
                    className="text-xs text-electric-blue"
                  >
                    Open draft: {t.draft_title || t.draft_id} ({t.draft_state})
                  </Link>
                ) : (
                  <p className="text-xs text-gray-600">No draft linked</p>
                )}
              </li>
            ))}
          </ul>
          )}
        </section>
      </main>
    </>
  )
}
