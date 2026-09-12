/** Reusable shimmer placeholders matching `.shimmer` in index.css */

export function ShimmerBlock({ className = '' }: { className?: string }) {
  return <div className={`shimmer ${className}`} />
}

export function AdminOverviewShimmer() {
  return (
    <>
      <header className="border-b border-white/5 px-6 py-4 space-y-2">
        <ShimmerBlock className="h-6 w-36" />
        <ShimmerBlock className="h-3.5 w-56" />
      </header>
      <main className="p-6 space-y-8">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-xl border border-white/10 bg-navy-800/60 p-4 space-y-3">
              <ShimmerBlock className="h-3 w-20" />
              <ShimmerBlock className="h-8 w-16" />
            </div>
          ))}
        </div>
        <div className="rounded-xl border border-white/10 bg-navy-800/40 p-5 space-y-3">
          <ShimmerBlock className="h-4 w-48" />
          <div className="flex flex-wrap gap-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <ShimmerBlock key={i} className="h-7 w-24 rounded-md" />
            ))}
          </div>
        </div>
        <div className="rounded-xl border border-white/10 overflow-hidden">
          <div className="bg-white/5 px-4 py-2.5 flex gap-8">
            <ShimmerBlock className="h-3 w-16" />
            <ShimmerBlock className="h-3 w-20" />
            <ShimmerBlock className="h-3 w-14" />
            <ShimmerBlock className="h-3 w-28" />
          </div>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="border-t border-white/5 px-4 py-3 flex gap-8">
              <ShimmerBlock className="h-3.5 w-32" />
              <ShimmerBlock className="h-3.5 w-40" />
              <ShimmerBlock className="h-3.5 w-20" />
              <ShimmerBlock className="h-3.5 w-48 flex-1 max-w-md" />
            </div>
          ))}
        </div>
      </main>
    </>
  )
}

export function AdminAccountsShimmer() {
  return (
    <div className="rounded-xl border border-white/10 overflow-hidden">
      <div className="bg-white/5 px-4 py-2.5 flex gap-6">
        {['w-24', 'w-28', 'w-16', 'w-20', 'w-14', 'w-12', 'w-16'].map((w, i) => (
          <ShimmerBlock key={i} className={`h-3 ${w}`} />
        ))}
      </div>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="border-t border-white/5 px-4 py-3 flex gap-6 items-center">
          <ShimmerBlock className="h-3.5 w-36" />
          <ShimmerBlock className="h-3.5 w-44" />
          <ShimmerBlock className="h-3.5 w-24" />
          <ShimmerBlock className="h-3.5 w-28" />
          <ShimmerBlock className="h-3.5 w-10" />
          <ShimmerBlock className="h-3.5 w-10" />
          <ShimmerBlock className="h-3.5 w-16" />
        </div>
      ))}
    </div>
  )
}

export function AdminBrandShimmer() {
  return (
    <>
      <header className="border-b border-white/5 px-6 py-4 space-y-3">
        <ShimmerBlock className="h-3 w-20" />
        <ShimmerBlock className="h-6 w-48" />
        <ShimmerBlock className="h-3.5 w-64" />
        <div className="flex gap-2 pt-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <ShimmerBlock key={i} className="h-8 w-24 rounded-lg" />
          ))}
        </div>
      </header>
      <main className="p-6">
        <div className="grid sm:grid-cols-2 gap-4 max-w-3xl">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="rounded-lg border border-white/10 p-3 space-y-2">
              <ShimmerBlock className="h-3 w-16" />
              <ShimmerBlock className="h-4 w-full" />
            </div>
          ))}
        </div>
      </main>
    </>
  )
}

export function TableRowsShimmer({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, r) => (
        <tr key={r} className="border-b border-white/5">
          {Array.from({ length: cols }).map((_, c) => (
            <td key={c} className="px-4 py-3">
              <ShimmerBlock className={`h-3.5 ${c === 1 ? 'w-full max-w-md' : 'w-28'}`} />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}
