import { NavLink, Outlet, Link } from 'react-router-dom'
import { LayoutDashboard, Users, ArrowLeft, LogOut } from 'lucide-react'
import type { Session } from '@supabase/supabase-js'
import clsx from 'clsx'

const nav = [
  { to: '/admin', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/admin/accounts', label: 'Accounts', icon: Users, end: false },
]

export default function AdminLayout({
  session,
  onSignOut,
}: {
  session: Session
  onSignOut: () => void
}) {
  return (
    <div className="min-h-screen bg-navy-900 text-white flex">
      <aside className="w-56 shrink-0 border-r border-white/5 bg-navy-900/95 flex flex-col sticky top-0 h-screen">
        <div className="px-5 py-5 border-b border-white/5">
          <p className="text-xs uppercase tracking-wider text-amber-400/90 mb-1">Platform</p>
          <p className="text-base font-semibold tracking-tight">Admin</p>
          <p className="text-[11px] text-gray-500 mt-1 truncate" title={session.user.email}>
            {session.user.email}
          </p>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors',
                  isActive
                    ? 'bg-amber-500/10 text-amber-300 border border-amber-500/20'
                    : 'text-gray-400 hover:text-white hover:bg-white/5 border border-transparent',
                )
              }
            >
              <item.icon className="w-4 h-4 shrink-0" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="p-3 border-t border-white/5 space-y-1">
          <Link
            to="/"
            className="w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to app
          </Link>
          <button
            type="button"
            onClick={onSignOut}
            className="w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Sign out
          </button>
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col min-h-screen">
        <Outlet context={{ session, onSignOut }} />
      </div>
    </div>
  )
}
