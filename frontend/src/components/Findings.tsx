import type { Report } from '../types'

const usd = (value: number) => `$${value.toLocaleString('en-US')}`

function Panel({ title, count, children }: { title: string; count?: number; children: React.ReactNode }) {
  return (
    <section className="rounded border border-ink-800 bg-ink-900">
      <h2 className="flex items-baseline justify-between border-b border-ink-800 px-4 py-2.5 text-xs tracking-widest text-slate-500 uppercase">
        {title}
        {count !== undefined && <span className="font-mono text-slate-600">{count}</span>}
      </h2>
      <div className="p-4">{children}</div>
    </section>
  )
}

export function Explanation({ report }: { report: Report }) {
  return (
    <Panel title="Assessment">
      {report.llm_source === 'rule-based' && (
        <p className="mb-3 rounded border border-ink-700 bg-ink-850 px-3 py-2 text-xs text-slate-500">
          Model unavailable — this explanation is the deterministic fallback. The score, blast
          radius, and violations above are unaffected; they never depend on a model.
        </p>
      )}

      <p className="text-sm leading-relaxed text-slate-300">{report.llm_explanation}</p>

      {report.llm_remediation.length > 0 && (
        <ol className="mt-4 space-y-2">
          {report.llm_remediation.map((step, index) => (
            <li key={step} className="flex gap-3 text-sm text-slate-400">
              <span className="mt-px font-mono text-xs text-accent">{index + 1}</span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  )
}

export function Violations({ report }: { report: Report }) {
  if (report.rule_violations.length === 0) {
    return (
      <Panel title="Rule violations" count={0}>
        <p className="text-xs text-slate-600">
          No deterministic constraints violated by this change.
        </p>
      </Panel>
    )
  }

  return (
    <Panel title="Rule violations" count={report.rule_violations.length}>
      <ul className="space-y-2">
        {report.rule_violations.map((violation) => {
          const [code, ...rest] = violation.split(': ')
          const detail = rest.join(': ')
          return (
            <li key={violation} className="font-mono text-xs leading-relaxed">
              <span className="text-risk-critical">{detail ? code : 'RULE'}</span>
              <span className="text-slate-400"> {detail || violation}</span>
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}

export function Incidents({ report }: { report: Report }) {
  return (
    <Panel title="Comparable incidents" count={report.similar_incidents.length}>
      <ul className="space-y-3">
        {report.similar_incidents.map((incident) => (
          <li key={incident.id} className="flex items-baseline gap-3">
            <span
              className={`font-mono text-[10px] ${
                incident.severity === 'P1' ? 'text-risk-critical' : 'text-risk-medium'
              }`}
            >
              {incident.severity}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-xs text-slate-300">{incident.title}</p>
              <p className="font-mono text-[11px] text-slate-600">
                {incident.id}
                {incident.financial_impact > 0 && ` · ${usd(incident.financial_impact)}`}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  )
}

export function History({ report }: { report: Report }) {
  if (report.memory_lessons.length === 0) {
    return (
      <Panel title="Deployment history" count={0}>
        <p className="text-xs text-slate-600">No comparable past deployment on record.</p>
      </Panel>
    )
  }

  return (
    <Panel title="Deployment history" count={report.memory_lessons.length}>
      <ul className="space-y-3">
        {report.memory_lessons.map((entry) => (
          <li key={entry.deployment} className="flex items-baseline gap-3">
            <span
              className={`font-mono text-[10px] uppercase ${
                entry.outcome === 'failed' ? 'text-risk-critical' : 'text-risk-low'
              }`}
            >
              {entry.outcome}
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-mono text-[11px] text-slate-500">{entry.deployment}</p>
              <ul className="mt-0.5 space-y-0.5">
                {entry.lessons.map((lesson) => (
                  <li key={lesson} className="text-xs text-slate-400">
                    {lesson}
                  </li>
                ))}
              </ul>
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  )
}
