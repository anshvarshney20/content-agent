import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { AdminOverviewShimmer } from '../../components/Shimmer'

type Overview = {
  brands_total: number
  brands_setup_complete: number
  jobs_total: number
  jobs_by_status: Record<string, number>
  jobs_today: number
  jobs_today_by_status: Record<string, number>
  recent_failures: {
    id: string
    brand_id: string
    brand_name: string
    job_type?: string
    error?: string
    created_at?: string
    status?: string
  }[]
}

export default function AdminHome() {
  const [data, setData] = useState<Overview | null>(null)
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api
      .get('/api/admin/overview')
      .then((r) => setData(r.data))
      .catch((e) => setErr(e?.response?.data?.detail || e.message || String(e)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <AdminOverviewShimmer />
  }
  if (err) {
    return <div className="p-8 text-red-400">{err}</div>
  }
  if (!data) return null

  const cards = [
    { label: 'Brands', value: data.brands_total },
    { label: 'Setup complete', value: data.brands_setup_complete },
    { label: 'Jobs today', value: data.jobs_today },
    { label: 'Failed (recent pool)', value: data.jobs_by_status.failed || 0 },
  ]

  return (
    <>
      <header className="border-b border-white/5 px-6 py-4">
        <h1 className="text-xl font-semibold">Overview</h1>
        <p className="text-sm text-gray-500 mt-0.5">Platform pulse across all customers</p>
      </header>

      <main className="p-6 space-y-8">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {cards.map((c) => (
            <div key={c.label} className="rounded-xl border border-white/10 bg-navy-800/60 p-4">
              <p className="text-xs uppercase tracking-wider text-gray-500">{c.label}</p>
              <p className="text-3xl font-semibold mt-2 tabular-nums">{c.value}</p>
            </div>
          ))}
        </div>

        <section className="rounded-xl border border-white/10 bg-navy-800/40 p-5">
          <h2 className="text-sm font-medium text-gray-300 mb-3">Jobs by status (latest 500)</h2>
          <div className="flex flex-wrap gap-3">
            {Object.entries(data.jobs_by_status).length === 0 && (
              <p className="text-sm text-gray-500">No jobs yet</p>
            )}
            {Object.entries(data.jobs_by_status).map(([k, v]) => (
              <span
                key={k}
                className="text-xs px-2.5 py-1 rounded-md border border-white/10 text-gray-300"
              >
                {k}: <span className="text-white font-medium">{v}</span>
              </span>
            ))}
          </div>
        </section>

        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-gray-300">Recent failures</h2>
            <Link to="/admin/accounts" className="text-xs text-electric-blue">
              View accounts →
            </Link>
          </div>
          <div className="rounded-xl border border-white/10 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-white/5 text-left text-xs text-gray-500 uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-2.5">When</th>
                  <th className="px-4 py-2.5">Brand</th>
                  <th className="px-4 py-2.5">Type</th>
                  <th className="px-4 py-2.5">Error</th>
                </tr>
              </thead>
              <tbody>
                {(data.recent_failures || []).length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-gray-500">
                      No recent failures
                    </td>
                  </tr>
                )}
                {(data.recent_failures || []).map((f) => (
                  <tr key={String(f.id)} className="border-t border-white/5">
                    <td className="px-4 py-2.5 text-gray-400 whitespace-nowrap">
                      {f.created_at ? String(f.created_at).slice(0, 19).replace('T', ' ') : '—'}
                    </td>
                    <td className="px-4 py-2.5">
                      <Link
                        to={`/admin/brands/${f.brand_id}`}
                        className="text-electric-blue hover:underline"
                      >
                        {f.brand_name || '—'}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5 text-gray-400">{f.job_type || '—'}</td>
                    <td className="px-4 py-2.5 text-red-300/90 max-w-md truncate" title={f.error || ''}>
                      {f.error || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </>
  )
}
