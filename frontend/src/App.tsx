import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import type { Session } from '@supabase/supabase-js'
import Login from './pages/Login'
import AppLayout from './components/AppLayout'
import DashboardHome from './pages/DashboardHome'
import PostDetail from './pages/PostDetail'
import Settings from './pages/Settings'
import Topics from './pages/Topics'
import Scheduler from './pages/Scheduler'
import AdminLayout from './pages/admin/AdminLayout'
import AdminHome from './pages/admin/AdminHome'
import AdminAccounts from './pages/admin/AdminAccounts'
import AdminBrand from './pages/admin/AdminBrand'
import { supabase } from './lib/supabase'
import { api } from './lib/api'
import { ShimmerBlock } from './components/Shimmer'

function AdminGate({ children }: { children: React.ReactNode }) {
  const [ok, setOk] = useState<boolean | null>(null)

  useEffect(() => {
    api
      .get('/api/admin/me')
      .then(() => setOk(true))
      .catch(() => setOk(false))
  }, [])

  if (ok === null) {
    return (
      <div className="min-h-screen bg-navy-900 flex items-center justify-center p-6">
        <div className="w-full max-w-sm space-y-4">
          <ShimmerBlock className="h-6 w-32 mx-auto" />
          <ShimmerBlock className="h-3.5 w-48 mx-auto" />
          <div className="grid grid-cols-2 gap-3 pt-2">
            <ShimmerBlock className="h-16 rounded-xl" />
            <ShimmerBlock className="h-16 rounded-xl" />
          </div>
        </div>
      </div>
    )
  }
  if (!ok) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [ready, setReady] = useState(false)
  const [isAdmin, setIsAdmin] = useState(false)

  useEffect(() => {
    if (!supabase) {
      setReady(true)
      return
    }
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setReady(true)
    })
    const { data: sub } = supabase.auth.onAuthStateChange((_e, next) => setSession(next))
    return () => sub.subscription.unsubscribe()
  }, [])

  useEffect(() => {
    if (!session) {
      setIsAdmin(false)
      return
    }
    api
      .get('/api/admin/me')
      .then(() => setIsAdmin(true))
      .catch(() => setIsAdmin(false))
  }, [session])

  async function signOut() {
    await supabase?.auth.signOut()
    setSession(null)
    setIsAdmin(false)
  }

  if (!ready) {
    return (
      <div className="min-h-screen bg-navy-900 flex items-center justify-center text-gray-400">
        Loading…
      </div>
    )
  }

  if (!session) {
    return <Login onAuthed={() => supabase?.auth.getSession().then(({ data }) => setSession(data.session))} />
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/admin"
          element={
            <AdminGate>
              <AdminLayout session={session} onSignOut={signOut} />
            </AdminGate>
          }
        >
          <Route index element={<AdminHome />} />
          <Route path="accounts" element={<AdminAccounts />} />
          <Route path="brands/:id" element={<AdminBrand />} />
        </Route>

        <Route element={<AppLayout session={session} onSignOut={signOut} isAdmin={isAdmin} />}>
          <Route path="/" element={<DashboardHome />} />
          <Route path="/topics" element={<Topics />} />
          <Route path="/scheduler" element={<Scheduler />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/posts/:id" element={<PostDetail />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
