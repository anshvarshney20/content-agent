import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../lib/api'
import { AdminBrandShimmer } from '../../components/Shimmer'

type Tab = 'profile' | 'runs' | 'drafts' | 'connections'

type BrandDetail = {
  profile: Record<string, unknown>
  owner_email?: string | null
  connections: { platform: string; connected: boolean; account_hint?: string; updated_at?: string }[]
  jobs: Record<string, unknown>[]
  pipeline_runs: Record<string, unknown>[]
  drafts: Record<string, unknown>[]
}

export default function AdminBrand() {
  const { id } = useParams<{ id: string }>()
  const [tab, setTab] = useState<Tab>('profile')
  const [data, setData] = useState<BrandDetail | null>(null)
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    api
      .get(`/api/admin/brands/${id}`)
      .then((r) => setData(r.data))
      .catch((e) => setErr(e?.response?.data?.detail || e.message || String(e)))
      .finally(() => setLoading(false))
  }, [id])

  const tabs: { id: Tab; label: string }[] = [
    { id: 'profile', label: 'Profile' },
    { id: 'runs', label: 'Runs' },
    { id: 'drafts', label: 'Drafts' },
    { id: 'connections', label: 'Connections' },
  ]

  if (loading) return <AdminBrandShimmer />
  if (err) return <div className="p-8 text-red-400">{err}</div>
  if (!data) return null

  const p = data.profile
  const name = String(p.business_name || 'Brand')

  return (
    <>
      <header className="border-b border-white/5 px-6 py-4">
        <Link to="/admin/accounts" className="text-xs text-electric-blue">
          ← Accounts
        </Link>
        <h1 className="text-xl font-semibold mt-1">{name}</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          {data.owner_email || String(p.owner_id || '')} · {String(p.active_niche_id || '')}
        </p>
        <div className="flex gap-2 mt-4">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={
                tab === t.id
                  ? 'text-sm px-3 py-1.5 rounded-lg bg-amber-500/15 text-amber-200 border border-amber-500/25'
                  : 'text-sm px-3 py-1.5 rounded-lg text-gray-400 border border-transparent hover:bg-white/5'
              }
            >
              {t.label}
            </button>
          ))}
        </div>
      </header>

      <main className="p-6">
        {tab === 'profile' && (
          <dl className="grid sm:grid-cols-2 gap-4 max-w-3xl">
            {[
              ['Business', p.business_name],
              ['Positioning', p.positioning],
              ['Audience', p.audience],
              ['Offer', p.offer],
              ['CTA', p.cta_text],
              ['Website', p.website_url],
              ['Niche', p.active_niche_id],
              ['Custom niche', p.custom_niche_text],
              ['Schedule', p.schedule_enabled ? `${p.schedule_time} ${p.timezone}` : 'off'],
              ['Publish mode', p.publish_mode],
              ['Setup', p.setup_complete ? 'complete' : 'incomplete'],
              ['Created', p.created_at],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded-lg border border-white/10 p-3">
                <dt className="text-[11px] uppercase tracking-wider text-gray-500">{String(label)}</dt>
                <dd className="text-sm mt-1 text-gray-200 break-words">{String(value ?? '—')}</dd>
              </div>
            ))}
          </dl>
        )}

        {tab === 'runs' && (
          <div className="space-y-6">
            <section>
              <h2 className="text-sm text-gray-400 mb-2">Jobs</h2>
              <RunsTable
                rows={data.jobs}
                columns={['created_at', 'job_type', 'status', 'error']}
              />
            </section>
            <section>
              <h2 className="text-sm text-gray-400 mb-2">Pipeline runs</h2>
              <RunsTable
                rows={data.pipeline_runs}
                columns={['created_at', 'run_date', 'status', 'retry_count']}
              />
            </section>
          </div>
        )}

        {tab === 'drafts' && (
          <RunsTable rows={data.drafts} columns={['created_at', 'title', 'state']} />
        )}

        {tab === 'connections' && (
          <div className="space-y-3 max-w-lg">
            {data.connections.length === 0 && (
              <p className="text-gray-500 text-sm">No social_connections rows for this brand</p>
            )}
            {data.connections.map((c) => (
              <div
                key={c.platform}
                className="flex items-center justify-between rounded-lg border border-white/10 px-4 py-3"
              >
                <div>
                  <p className="font-medium capitalize">{c.platform}</p>
                  <p className="text-xs text-gray-500 truncate max-w-xs">{c.account_hint || '—'}</p>
                </div>
                <span className={c.connected ? 'text-emerald-400 text-xs' : 'text-gray-500 text-xs'}>
                  {c.connected ? 'connected' : 'not connected'}
                </span>
              </div>
            ))}
            <p className="text-xs text-gray-600 pt-2">
              Tokens are never shown. Status is derived from encrypted token presence + account ids.
            </p>
          </div>
        )}
      </main>
    </>
  )
}

function RunsTable({
  rows,
  columns,
}: {
  rows: Record<string, unknown>[]
  columns: string[]
}) {
  if (!rows.length) {
    return <p className="text-sm text-gray-500">None</p>
  }
  return (
    <div className="rounded-xl border border-white/10 overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-white/5 text-left text-xs text-gray-500 uppercase tracking-wider">
          <tr>
            {columns.map((c) => (
              <th key={c} className="px-4 py-2.5">
                {c.replace(/_/g, ' ')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={String(r.id || i)} className="border-t border-white/5">
              {columns.map((c) => (
                <td key={c} className="px-4 py-2.5 text-gray-300 max-w-xs truncate">
                  {fmt(r[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function fmt(v: unknown) {
  if (v == null || v === '') return '—'
  if (typeof v === 'string' && v.includes('T') && v.length > 16) {
    return v.slice(0, 19).replace('T', ' ')
  }
  return String(v)
}
