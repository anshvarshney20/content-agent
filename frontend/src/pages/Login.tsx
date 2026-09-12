import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { apiBase, supabase, supabaseConfigured } from '../lib/supabase'

type Props = {
  onAuthed: () => void
}

type Niche = { id: string; label: string }

const NICHES_FALLBACK: Niche[] = [
  { id: 'ai_automation', label: 'AI & Automation' },
  { id: 'saas_product', label: 'SaaS & Product' },
  { id: 'cybersecurity', label: 'Cybersecurity' },
  { id: 'founders_startups', label: 'Founders & Startups' },
  { id: 'enterprise_dx', label: 'Enterprise / Digital Transformation' },
  { id: 'marketing_growth', label: 'Marketing & Growth' },
  { id: 'fintech', label: 'Fintech' },
  { id: 'ecommerce', label: 'E-commerce & Retail tech' },
  { id: 'healthtech', label: 'Healthtech' },
  { id: 'custom', label: 'Custom…' },
]

const fieldClass = 'mt-1 w-full rounded-lg bg-navy-900 border border-white/10 px-3 py-2 text-sm'
const labelClass = 'text-xs text-gray-400 uppercase tracking-wider'

export default function Login({ onAuthed }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [step, setStep] = useState<1 | 2>(1)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [niches, setNiches] = useState<Niche[]>(NICHES_FALLBACK)

  const [businessName, setBusinessName] = useState('')
  const [positioning, setPositioning] = useState('')
  const [audience, setAudience] = useState('')
  const [offer, setOffer] = useState('')
  const [cta, setCta] = useState('Book a demo')
  const [website, setWebsite] = useState('')
  const [nicheId, setNicheId] = useState('ai_automation')
  const [customNiche, setCustomNiche] = useState('')

  useEffect(() => {
    loadNiches().catch(() => {})
  }, [])

  async function loadNiches() {
    try {
      const res = await fetch(`${apiBase}/api/niches`)
      if (!res.ok) return
      const data = await res.json()
      if (Array.isArray(data.niches) && data.niches.length) setNiches(data.niches)
    } catch {
      /* fallback list */
    }
  }

  if (!supabaseConfigured || !supabase) {
    return (
      <div className="h-dvh overflow-hidden flex items-center justify-center p-4">
        <div className="w-full max-w-md p-8 rounded-2xl bg-navy-800 border border-white/10 text-white">
          <h1 className="text-xl font-semibold mb-3">Supabase not configured</h1>
          <p className="text-sm text-gray-400">
            Set <code className="text-subtle-cyan">VITE_SUPABASE_URL</code> and{' '}
            <code className="text-subtle-cyan">VITE_SUPABASE_ANON_KEY</code> in{' '}
            <code className="text-subtle-cyan">frontend/.env</code>.
          </p>
        </div>
      </div>
    )
  }

  async function finishOnboard(accessToken: string) {
    const res = await fetch(`${apiBase}/api/saas/onboard`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        business_name: businessName,
        positioning,
        audience,
        offer,
        cta_text: cta,
        website_url: website,
        active_niche_id: nicheId,
        custom_niche_text: customNiche,
      }),
    })
    if (!res.ok) {
      const text = await res.text()
      throw new Error(text || 'Could not save brand profile')
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setMessage('')
    try {
      if (mode === 'signup') {
        if (step === 1) {
          if (!email || password.length < 6) {
            setMessage('Enter email and a password (min 6 characters).')
            return
          }
          setStep(2)
          return
        }

        if (!businessName.trim() || !positioning.trim()) {
          setMessage('Business name and positioning are required.')
          return
        }

        const { data, error } = await supabase!.auth.signUp({
          email,
          password,
          options: {
            data: {
              business_name: businessName.trim(),
              positioning: positioning.trim(),
              audience: audience.trim(),
              offer: offer.trim(),
              cta_text: cta.trim() || 'Book a demo',
              website_url: website.trim(),
              active_niche_id: nicheId,
              custom_niche_text: customNiche.trim(),
              setup_complete: true,
            },
          },
        })
        if (error) throw error

        const session = data.session
        if (session?.access_token) {
          await finishOnboard(session.access_token)
          onAuthed()
          return
        }

        // Email confirmation required — sign in after confirm, or try password sign-in
        const signed = await supabase!.auth.signInWithPassword({ email, password })
        if (signed.data.session?.access_token) {
          await finishOnboard(signed.data.session.access_token)
          onAuthed()
          return
        }

        setMessage('Account created. Confirm email if required, then sign in — your brand details are saved.')
        setMode('signin')
        setStep(1)
      } else {
        const { error } = await supabase!.auth.signInWithPassword({ email, password })
        if (error) throw error
        onAuthed()
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  function switchMode(next: 'signin' | 'signup') {
    setMode(next)
    setStep(1)
    setMessage('')
  }

  return (
    <div className="h-dvh overflow-hidden flex items-center justify-center p-4 bg-navy-900">
      <div className="w-full max-w-md max-h-[90dvh] overflow-y-auto rounded-2xl bg-navy-800 border border-white/10 text-white shadow-xl">
        <div className="px-8 pt-7 pb-2">
          <h1 className="text-2xl font-semibold tracking-tight">
            Daily Content <span className="text-electric-blue">Agent</span>
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            {mode === 'signin'
              ? 'Sign in to your content workspace'
              : step === 1
                ? 'Create your account — step 1 of 2'
                : 'Tell us about your brand — step 2 of 2'}
          </p>
        </div>

        <form onSubmit={submit} className="px-8 pb-7 pt-3 space-y-3.5">
          {mode === 'signin' || step === 1 ? (
            <>
              <div>
                <label className={labelClass}>Email</label>
                <input
                  className={fieldClass}
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                />
              </div>
              <div>
                <label className={labelClass}>Password</label>
                <input
                  className={fieldClass}
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                />
              </div>
            </>
          ) : (
            <>
              <div>
                <label className={labelClass}>Business name *</label>
                <input
                  className={fieldClass}
                  value={businessName}
                  onChange={(e) => setBusinessName(e.target.value)}
                  required
                  placeholder="Acme Studio"
                />
              </div>
              <div>
                <label className={labelClass}>Positioning *</label>
                <input
                  className={fieldClass}
                  value={positioning}
                  onChange={(e) => setPositioning(e.target.value)}
                  required
                  placeholder="What you do in one line"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={labelClass}>Audience</label>
                  <input
                    className={fieldClass}
                    value={audience}
                    onChange={(e) => setAudience(e.target.value)}
                    placeholder="Who you serve"
                  />
                </div>
                <div>
                  <label className={labelClass}>CTA</label>
                  <input className={fieldClass} value={cta} onChange={(e) => setCta(e.target.value)} />
                </div>
              </div>
              <div>
                <label className={labelClass}>Offer</label>
                <input
                  className={fieldClass}
                  value={offer}
                  onChange={(e) => setOffer(e.target.value)}
                  placeholder="What you sell / promote"
                />
              </div>
              <div>
                <label className={labelClass}>Website</label>
                <input
                  className={fieldClass}
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                  placeholder="https://"
                />
              </div>
              <div>
                <label className={labelClass}>Content category</label>
                <select className={fieldClass} value={nicheId} onChange={(e) => setNicheId(e.target.value)}>
                  {niches.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.label}
                    </option>
                  ))}
                </select>
              </div>
              {nicheId === 'custom' && (
                <div>
                  <label className={labelClass}>Custom keywords</label>
                  <input
                    className={fieldClass}
                    value={customNiche}
                    onChange={(e) => setCustomNiche(e.target.value)}
                    placeholder="Topic keywords"
                  />
                </div>
              )}
            </>
          )}

          <div className="flex gap-2 pt-1">
            {mode === 'signup' && step === 2 && (
              <button
                type="button"
                className="secondary-button flex-1 text-sm"
                onClick={() => setStep(1)}
                disabled={busy}
              >
                Back
              </button>
            )}
            <button
              type="submit"
              disabled={busy}
              className="flex-1 rounded-lg bg-electric-blue/90 hover:bg-electric-blue py-2.5 text-sm font-semibold disabled:opacity-50"
            >
              {busy
                ? 'Please wait…'
                : mode === 'signin'
                  ? 'Sign in'
                  : step === 1
                    ? 'Continue'
                    : 'Create account'}
            </button>
          </div>
        </form>

        <div className="px-8 pb-6">
          <button
            type="button"
            className="text-xs text-subtle-cyan hover:underline"
            onClick={() => switchMode(mode === 'signin' ? 'signup' : 'signin')}
          >
            {mode === 'signin' ? 'Need an account? Sign up' : 'Have an account? Sign in'}
          </button>
          {message && <p className="mt-3 text-sm text-amber-300 break-words">{message}</p>}
        </div>
      </div>
    </div>
  )
}
