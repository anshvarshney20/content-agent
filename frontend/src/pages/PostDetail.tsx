import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { ArrowLeft, Clock3, RefreshCw } from 'lucide-react'
import type { Session } from '@supabase/supabase-js'
import { absUrl, loadDrafts, type Draft } from '../lib/drafts'
import { api } from '../lib/api'
import { ShimmerBlock } from '../components/Shimmer'

type OutletCtx = { session: Session; onSignOut: () => void }

export default function PostDetail() {
  const { session } = useOutletContext<OutletCtx>()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const token = session.access_token
  const [draft, setDraft] = useState<Draft | null>(null)
  const [slide, setSlide] = useState(0)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [loading, setLoading] = useState(true)

  const imageUrls = useMemo(() => {
    if (!draft) return []
    if (draft.image_urls?.length) return draft.image_urls
    if (draft.image_url) return [draft.image_url]
    return []
  }, [draft])

  async function load() {
    setLoading(true)
    try {
      const drafts = await loadDrafts(token)
      const match = drafts.find((d) => String(d.id) === String(id))
      setDraft(match || null)
      setSlide(0)
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load().catch(() => {})
  }, [token, id])

  async function approve() {
    if (!draft?.id) return
    setBusy(true)
    setMsg('')
    try {
      const { data } = await api.post(`/api/content/${draft.id}/approve`)
      setMsg(`Approved. ${JSON.stringify(data.publish || data)}`)
      await load()
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <header className="border-b border-white/5 px-6 py-4 flex flex-wrap items-center justify-between gap-4 sticky top-0 bg-navy-900/90 backdrop-blur z-10">
        <div>
          <h1 className="text-lg font-semibold">Post</h1>
          <p className="text-xs text-gray-500 truncate max-w-md">{draft?.title || 'Loading…'}</p>
        </div>
        <button type="button" className="secondary-button flex items-center text-sm" onClick={() => load()}>
          <RefreshCw className="w-4 h-4 mr-2" /> Refresh
        </button>
      </header>

      <main className="w-full max-w-none px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        <button
          type="button"
          className="secondary-button text-sm inline-flex items-center"
          onClick={() => navigate('/')}
        >
          <ArrowLeft className="w-4 h-4 mr-2" /> Back to posts
        </button>

        {msg && <p className="text-sm text-subtle-cyan break-all">{msg}</p>}

        {loading && (
          <div className="glass-card p-6 lg:p-8 space-y-6 w-full">
            <div className="flex justify-between gap-4">
              <div className="space-y-3 flex-1">
                <ShimmerBlock className="h-7 w-2/3 max-w-xl" />
                <ShimmerBlock className="h-3 w-40" />
              </div>
              <ShimmerBlock className="h-10 w-36 rounded-lg" />
            </div>
            <div className="grid xl:grid-cols-2 gap-6">
              <div className="space-y-3">
                <ShimmerBlock className="h-4 w-24" />
                <ShimmerBlock className="h-40 w-full" />
              </div>
              <ShimmerBlock className="h-64 w-full rounded-xl" />
            </div>
          </div>
        )}

        {!loading && !draft && (
          <div className="glass-card p-6 space-y-3">
            <p className="text-gray-400">Post not found.</p>
            <p className="text-xs text-gray-500 font-mono">{id}</p>
            <Link to="/" className="text-electric-blue text-sm">
              Return to dashboard
            </Link>
          </div>
        )}

        {draft && (
          <section className="glass-card p-5 sm:p-6 lg:p-8 space-y-6 w-full">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <h1 className="text-xl sm:text-2xl font-semibold">{draft.title}</h1>
                <p className="text-xs text-gray-500 mt-1">
                  {draft.status || draft.state} · {draft.date}
                </p>
                <p className="text-[10px] text-gray-600 mt-1 font-mono break-all">{draft.id}</p>
              </div>
              <button
                type="button"
                className="primary-button text-sm disabled:opacity-50 inline-flex items-center shrink-0"
                disabled={busy}
                onClick={approve}
              >
                {busy ? <Clock3 className="w-4 h-4 mr-2 animate-spin" /> : null}
                Approve & Post
              </button>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 w-full">
              {imageUrls.length > 0 && (
                <div className="space-y-2 min-w-0">
                  {imageUrls.length > 1 && (
                    <div className="flex gap-2 text-xs">
                      <button
                        type="button"
                        className="text-electric-blue"
                        onClick={() => setSlide((s) => (s - 1 + imageUrls.length) % imageUrls.length)}
                      >
                        ← Prev
                      </button>
                      <span className="text-gray-500">
                        {slide + 1}/{imageUrls.length}
                      </span>
                      <button
                        type="button"
                        className="text-electric-blue"
                        onClick={() => setSlide((s) => (s + 1) % imageUrls.length)}
                      >
                        Next →
                      </button>
                    </div>
                  )}
                  <img
                    src={absUrl(imageUrls[slide])}
                    alt=""
                    className="w-full h-auto max-h-[min(80vh,56rem)] rounded-lg border border-white/10 object-contain bg-navy-900"
                  />
                </div>
              )}

              <div className={`space-y-4 min-w-0 ${imageUrls.length === 0 ? 'xl:col-span-2' : ''}`}>
                <div>
                  <h2 className="text-xs uppercase text-gray-500 mb-1">LinkedIn</h2>
                  <pre className="whitespace-pre-wrap text-sm bg-navy-900/80 rounded-lg p-3 border border-white/5 max-h-[40vh] overflow-y-auto">
                    {draft.linkedin_post || '—'}
                  </pre>
                </div>
                <div>
                  <h2 className="text-xs uppercase text-gray-500 mb-1">Instagram</h2>
                  <pre className="whitespace-pre-wrap text-sm bg-navy-900/80 rounded-lg p-3 border border-white/5 max-h-[40vh] overflow-y-auto">
                    {draft.instagram_caption || '—'}
                  </pre>
                </div>
              </div>
            </div>
          </section>
        )}
      </main>
    </>
  )
}
