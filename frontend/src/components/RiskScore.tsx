import { useState } from 'react'
import type { ImpactLevel, Report } from '../types'

const IMPACT_STYLE: Record<ImpactLevel, { text: string; ring: string; bar: string }> = {
  low: { text: 'text-risk-low', ring: 'border-risk-low/40', bar: 'bg-risk-low' },
  medium: { text: 'text-risk-medium', ring: 'border-risk-medium/40', bar: 'bg-risk-medium' },
  high: { text: 'text-risk-high', ring: 'border-risk-high/40', bar: 'bg-risk-high' },
  critical: { text: 'text-risk-critical', ring: 'border-risk-critical/40', bar: 'bg-risk-critical' },
}

const usd = (value: number) =>
  value >= 1000 ? `$${(value / 1000).toFixed(0)}K` : `$${value}`

/** Pull the "(+N)" a reason carries so the breakdown can show it as a bar. */
function pointsOf(reason: string): number {
  const match = reason.match(/\(\+(\d+)\)\s*$/)
  return match ? Number(match[1]) : 0
}

export function RiskScore({ report }: { report: Report }) {
  const [showBreakdown, setShowBreakdown] = useState(true)
  const style = IMPACT_STYLE[report.impact_level] ?? IMPACT_STYLE.medium
  const maxPoints = Math.max(...report.risk_reasons.map(pointsOf), 1)

  return (
    <section data-shot="risk-score" className={`rounded border ${style.ring} bg-ink-900`}>
      <div className="flex flex-wrap items-center gap-x-8 gap-y-4 p-5">
        <div className="flex items-baseline gap-2">
          <span className={`font-mono text-6xl leading-none font-semibold ${style.text}`}>
            {report.risk_score}
          </span>
          <span className="font-mono text-lg text-fg-faint">/100</span>
        </div>

        <div className="flex flex-col gap-1">
          <span className={`text-sm font-semibold tracking-widest uppercase ${style.text}`}>
            {report.impact_level}
          </span>
          <span className="font-mono text-xs text-fg-muted">{report.scenario}</span>
        </div>

        <div className="ml-auto grid grid-cols-2 gap-x-8 gap-y-2 sm:grid-cols-3">
          <Stat label="Blast radius" value={`${report.affected_services.length} services`} />
          <Stat label="SLA" value={report.sla_impact} />
          <Stat
            label="Comparable cost"
            value={report.financial_impact ? usd(report.financial_impact) : '—'}
          />
        </div>
      </div>

      <div className="border-t border-ink-800 px-5 py-3">
        <p className="font-mono text-sm text-fg">{report.rollout_plan}</p>
      </div>

      <div className="border-t border-ink-800">
        <button
          onClick={() => setShowBreakdown((open) => !open)}
          className="flex w-full items-center justify-between px-5 py-2.5 text-left text-xs tracking-wide text-fg-muted uppercase transition hover:bg-ink-850 hover:text-fg"
          aria-expanded={showBreakdown}
        >
          <span>How this score was reached · {report.risk_reasons.length} factors</span>
          <span className="font-mono text-fg-faint">{showBreakdown ? '−' : '+'}</span>
        </button>

        {showBreakdown && (
          <ul className="space-y-1 px-5 pt-1 pb-4">
            {report.risk_reasons.map((reason) => {
              const points = pointsOf(reason)
              return (
                <li key={reason} className="flex items-center gap-3 font-mono text-xs">
                  <span className="w-8 shrink-0 text-right text-fg-muted">+{points}</span>
                  <span
                    className={`h-1.5 shrink-0 rounded-sm ${style.bar} opacity-70`}
                    style={{ width: `${Math.max((points / maxPoints) * 88, 4)}px` }}
                    aria-hidden
                  />
                  <span className="text-fg-muted">
                    {reason.replace(/\s*\(\+\d+\)\s*$/, '')}
                  </span>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </section>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] tracking-widest text-fg-faint uppercase">{label}</span>
      <span className="font-mono text-xs text-fg">{value}</span>
    </div>
  )
}
