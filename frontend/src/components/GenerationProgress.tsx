type Stage = {
  id?: string
  name: string
  status: string
  time: string
  expected_s?: number
  elapsed_s?: number | null
}

export default function GenerationProgress({
  status,
  percent,
  elapsedLabel,
  etaLabel,
  currentStage,
  stages,
  error,
}: {
  status: string
  percent: number
  elapsedLabel: string
  etaLabel: string
  currentStage?: string | null
  stages: Stage[]
  error?: string | null
}) {
  const running = status === 'running'
  const failed = status === 'failed' || status === 'cancelled'
  const done = status === 'completed' || status === 'success'
  const pct = Math.max(0, Math.min(100, percent))

  return (
    <section className="glass-card p-5 space-y-4 border border-electric-blue/20">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">
            {failed ? 'Generation stopped' : done ? 'Generation complete' : 'Generating post'}
          </h2>
          <p className="text-xs text-gray-500 mt-1">
            {currentStage ? (
              <>
                Now: <span className="text-electric-blue">{currentStage}</span>
              </>
            ) : done ? (
              'All stages finished'
            ) : (
              'Starting…'
            )}
          </p>
        </div>
        <div className="text-right text-xs font-mono text-gray-400 space-y-0.5">
          <p>
            Elapsed <span className="text-white">{elapsedLabel}</span>
          </p>
          {running && (
            <p>
              ETA <span className="text-subtle-cyan">~{etaLabel}</span>
            </p>
          )}
          {done && !running && <p className="text-green-400/80">Finished in {elapsedLabel}</p>}
        </div>
      </div>

      <div>
        <div className="flex justify-between text-xs mb-1.5">
          <span className="text-gray-500">Overall</span>
          <span className="font-mono text-electric-blue">{pct}%</span>
        </div>
        <div className="h-2.5 rounded-full bg-navy-800 overflow-hidden border border-white/5">
          <div
            className={`h-full rounded-full transition-all duration-500 ease-out ${
              failed ? 'bg-red-500' : done ? 'bg-green-500' : 'bg-gradient-to-r from-electric-blue to-subtle-cyan'
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {stages.length > 0 && (
        <ul className="space-y-2.5">
          {stages.map((s) => {
            const st = (s.status || 'pending').toLowerCase()
            const expected = s.expected_s || 30
            let fill = 0
            if (st === 'completed' || st === 'skipped') fill = 100
            else if (st === 'failed') fill = 100
            else if (st === 'running') {
              const elapsed = typeof s.elapsed_s === 'number' ? s.elapsed_s : 0
              fill = Math.min(92, Math.max(6, Math.round((elapsed / expected) * 100)))
            }

            return (
              <li key={s.id || s.name} className="space-y-1">
                <div className="flex justify-between gap-3 text-xs">
                  <span
                    className={
                      st === 'running'
                        ? 'text-electric-blue'
                        : st === 'completed'
                          ? 'text-gray-300'
                          : st === 'failed'
                            ? 'text-red-300'
                            : 'text-gray-500'
                    }
                  >
                    {s.name}
                    {st === 'running' ? '…' : ''}
                  </span>
                  <span className="font-mono text-gray-500 shrink-0">{s.time}</span>
                </div>
                <div className="h-1 rounded-full bg-navy-800 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${
                      st === 'failed'
                        ? 'bg-red-500/80'
                        : st === 'skipped'
                          ? 'bg-gray-600'
                          : st === 'completed'
                            ? 'bg-green-500/70'
                            : st === 'running'
                              ? 'bg-electric-blue'
                              : 'bg-transparent'
                    }`}
                    style={{ width: `${fill}%` }}
                  />
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {error && <p className="text-xs text-red-300 break-all">{error}</p>}
    </section>
  )
}
