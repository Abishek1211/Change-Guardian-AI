import type { AgentRun } from '../types'

/** Condense an agent's emitted state into one line of evidence it did work. */
function summarise(agent: AgentRun): string | null {
  const output = agent.output
  if (!output) return null

  switch (agent.key) {
    case 'intake': {
      const service = output.service_name as string
      const from = output.old_value as string
      const to = output.new_value as string
      return from && to ? `${service} · ${from} → ${to}` : service
    }
    case 'router':
      return output.change_type as string
    case 'graph_impact': {
      const affected = (output.affected_services as string[]) ?? []
      return affected.length ? affected.join(', ') : 'no downstream services'
    }
    case 'hybrid_rag': {
      const incidents = (output.similar_incidents as { id: string }[]) ?? []
      const violations = (output.rule_violations as string[]) ?? []
      return `${incidents.length} incidents · ${violations.length} violations`
    }
    case 'memory_graph': {
      const lessons = (output.memory_lessons as { outcome: string }[]) ?? []
      const failed = lessons.filter((l) => l.outcome === 'failed').length
      return lessons.length
        ? `${lessons.length} prior deployments · ${failed} failed`
        : 'no history'
    }
    case 'risk_rollout':
      return `score ${output.risk_score} · ${output.impact_level}`
    case 'llm_explain':
      return output.llm_source === 'llm'
        ? 'model explanation'
        : 'rule-based fallback (model unavailable)'
    default:
      return null
  }
}

const DOT: Record<AgentRun['status'], string> = {
  pending: 'border-ink-600 bg-ink-900',
  running: 'border-accent bg-accent/20 running',
  complete: 'border-accent bg-accent',
  error: 'border-risk-critical bg-risk-critical',
}

export function AgentTimeline({ agents }: { agents: AgentRun[] }) {
  return (
    <section className="rounded border border-ink-800 bg-ink-900">
      <h2 className="border-b border-ink-800 px-4 py-2.5 text-xs tracking-widest text-slate-500 uppercase">
        Pipeline
      </h2>

      <ol className="p-4">
        {agents.map((agent, index) => {
          const summary = summarise(agent)
          const isLast = index === agents.length - 1
          return (
            <li key={agent.key} className="relative flex gap-3 pb-4 last:pb-0">
              {!isLast && (
                <span
                  className={`absolute top-4 left-[5px] h-full w-px ${
                    agent.status === 'complete' ? 'bg-accent/30' : 'bg-ink-700'
                  }`}
                  aria-hidden
                />
              )}

              <span
                className={`mt-1 h-[11px] w-[11px] shrink-0 rounded-full border ${DOT[agent.status]}`}
                aria-hidden
              />

              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <span
                    className={`text-sm ${
                      agent.status === 'pending' ? 'text-slate-600' : 'text-slate-200'
                    }`}
                  >
                    <span className="font-mono text-xs text-slate-600">{agent.index}. </span>
                    {agent.label}
                  </span>
                  {agent.elapsedMs !== undefined && (
                    <span className="font-mono text-[11px] text-slate-600 tabular-nums">
                      {agent.elapsedMs}ms
                    </span>
                  )}
                </div>

                {agent.status === 'error' ? (
                  <p className="mt-0.5 font-mono text-xs break-words text-risk-critical">
                    {agent.error}
                  </p>
                ) : summary ? (
                  <p className="mt-0.5 font-mono text-xs break-words text-slate-500">{summary}</p>
                ) : (
                  <p className="mt-0.5 text-xs text-slate-700">{agent.description}</p>
                )}
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
