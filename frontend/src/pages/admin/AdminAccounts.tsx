import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { AdminAccountsShimmer } from '../../components/Shimmer'

type Account = {
  brand_id: string
  business_name: string
  owner_email?: string | null
  owner_id: string
  active_niche_id?: string
  setup_complete: boolean
  schedule_enabled: boolean
  schedule_time?: string
  timezone?: string
  publish_mode?: string
  created_at?: string
  draft_count: number
  job_count: number
}

export default function AdminAccounts() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [q, setQ] = useState('')
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setErr('')
    api
      .get('/api/admin/accounts')
      .then((r) => {
        if (!cancelled) setAccounts(r.data.accounts || [])
      })
      .catch((e) => {
        if (!cancelled) {
          const detail = e?.response?.data?.detail
          setErr(
            typeof detail === 'string'
              ? detail
              : e?.code === 'ECONNABORTED'
                ? 'Request timed out — is the API running?'
                : e.message || String(e),
          )
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase()
    if (!s) return accounts
    return accounts.filter(
      (a) =>
        (a.business_name || '').toLowerCase().includes(s) ||
        (a.owner_email || '').toLowerCase().includes(s) ||
        (a.active_niche_id || '').toLowerCase().includes(s) ||
        a.brand_id.toLowerCase().includes(s),
    )
  }, [accounts, q])

  return (
    <>
      <header className="border-b border-white/5 px-6 py-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Accounts</h1>
          <p className="text-sm text-gray-500 mt-0.5">All brands on the platform</p>
        </div>
        <input
          className="rounded-lg bg-navy-800 border border-white/10 px-3 py-2 text-sm w-64 max-w-full"
          placeholder="Search email, brand, niche…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </header>

      <main className="p-6">
        {loading && <AdminAccountsShimmer />}
        {err && <p className="text-red-400">{err}</p>}
        {!loading && !err && (
          <div className="rounded-xl border border-white/10 overflow-x-auto">
            <table className="w-full text-sm min-w-[720px]">
              <thead className="bg-white/5 text-left text-xs text-gray-500 uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-2.5">Brand</th>
                  <th className="px-4 py-2.5">Owner</th>
                  <th className="px-4 py-2.5">Niche</th>
                  <th className="px-4 py-2.5">Schedule</th>
                  <th className="px-4 py-2.5">Drafts</th>
                  <th className="px-4 py-2.5">Jobs</th>
                  <th className="px-4 py-2.5">Setup</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-10 text-center text-gray-500">
                      No accounts match
                    </td>
                  </tr>
                )}
                {filtered.map((a) => (
                  <tr key={a.brand_id} className="border-t border-white/5 hover:bg-white/[0.02]">
                    <td className="px-4 py-2.5">
                      <Link
                        to={`/admin/brands/${a.brand_id}`}
                        className="text-electric-blue hover:underline font-medium"
                      >
                        {a.business_name || 'Untitled'}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5 text-gray-300">{a.owner_email || a.owner_id.slice(0, 8)}</td>
                    <td className="px-4 py-2.5 text-gray-400">{a.active_niche_id || '—'}</td>
                    <td className="px-4 py-2.5 text-gray-400">
                      {a.schedule_enabled
                        ? `${a.schedule_time || ''} ${a.timezone || ''}`.trim()
                        : 'off'}
                    </td>
                    <td className="px-4 py-2.5 tabular-nums">{a.draft_count}</td>
                    <td className="px-4 py-2.5 tabular-nums">{a.job_count}</td>
                    <td className="px-4 py-2.5">
                      <span
                        className={
                          a.setup_complete ? 'text-emerald-400 text-xs' : 'text-amber-400 text-xs'
                        }
                      >
                        {a.setup_complete ? 'ready' : 'incomplete'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </>
  )
}
