import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchExamples, fetchGraph, streamAnalysis } from './api'
import { AgentTimeline } from './components/AgentTimeline'
import { BlastRadiusGraph } from './components/BlastRadiusGraph'
import { Explanation, History, Incidents, Violations } from './components/Findings'
import { RiskScore } from './components/RiskScore'
import type { AgentRun, Example, Report, ServiceGraph } from './types'

export default function App() {
  const [changeRequest, setChangeRequest] = useState('')
  const [examples, setExamples] = useState<Example[]>([])
  const [graph, setGraph] = useState<ServiceGraph | null>(null)

  const [agents, setAgents] = useState<AgentRun[]>([])
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  const abortRef = useRef<AbortController | null>(null)
  const autoRunRef = useRef(false)

  useEffect(() => {
    fetchGraph().then(setGraph).catch(() => setGraph(null))
    fetchExamples()
      .then((data) => {
        setExamples(data.examples)
        setChangeRequest((current) => current || data.examples[0]?.request || '')
      })
      .catch(() => setExamples([]))
  }, [])

  // Abort an in-flight stream if the component unmounts mid-analysis.
  useEffect(() => () => abortRef.current?.abort(), [])

  // `?q=<change request>` runs on load, so an analysis is a shareable link.
  // The ref guards against StrictMode's double effect invocation in dev.
  useEffect(() => {
    if (autoRunRef.current) return
    const query = new URLSearchParams(window.location.search).get('q')?.trim()
    if (!query) return
    autoRunRef.current = true
    setChangeRequest(query)
    analyse(query)
    // analyse is intentionally omitted: this must fire once, on mount only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const analyse = useCallback(
    (request: string) => {
      const trimmed = request.trim()
      if (!trimmed || running) return

      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setRunning(true)
      setError(null)
      setReport(null)
      setAgents([])

      // Keep the address bar in sync so the current analysis can be copied and
      // shared. replaceState rather than pushState - re-running an analysis is
      // not a navigation and should not stack up back-button entries.
      window.history.replaceState(null, '', `?q=${encodeURIComponent(trimmed)}`)

      void streamAnalysis(
        trimmed,
        {
          onStart: (metas) =>
            setAgents(
              metas.map((meta, index) => ({
                ...meta,
                status: index === 0 ? 'running' : 'pending',
              })),
            ),
          onAgent: (event) =>
            setAgents((current) =>
              current.map((agent) => {
                if (agent.key === event.agent) {
                  return {
                    ...agent,
                    status: event.status,
                    output: event.output,
                    elapsedMs: event.elapsed_ms,
                    error: event.error,
                  }
                }
                // Light up the next agent so the timeline always shows where
                // the pipeline currently is, not just where it has been.
                if (agent.index === event.index + 1 && event.status === 'complete') {
                  return { ...agent, status: 'running' }
                }
                return agent
              }),
            ),
          onComplete: (finished) => {
            setReport(finished)
            setRunning(false)
          },
          onError: (message) => {
            setError(message)
            setRunning(false)
            setAgents((current) =>
              current.map((agent) =>
                agent.status === 'running' ? { ...agent, status: 'pending' } : agent,
              ),
            )
          },
        },
        controller.signal,
      )
    },
    [running],
  )

  return (
    <div className="mx-auto max-w-[1400px] px-5 py-6">
      <header className="mb-6 flex flex-wrap items-baseline justify-between gap-3 border-b border-ink-800 pb-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-100">
            ChangeGuardian <span className="text-accent">AI</span>
          </h1>
          <p className="mt-0.5 text-xs text-slate-500">
            Deployment risk analysis · 7-agent pipeline · six of seven agents are deterministic
          </p>
        </div>
        <a
          href="/docs"
          className="font-mono text-xs text-slate-600 transition hover:text-accent"
        >
          API docs →
        </a>
      </header>

      <form
        onSubmit={(event) => {
          event.preventDefault()
          analyse(changeRequest)
        }}
        className="mb-3"
      >
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            value={changeRequest}
            onChange={(event) => setChangeRequest(event.target.value)}
            placeholder="Upgrade payment-service from Spring Boot 2.7 to 3.2"
            maxLength={500}
            className="flex-1 rounded border border-ink-700 bg-ink-900 px-3.5 py-2.5 font-mono text-sm text-slate-200 placeholder:text-slate-700 focus:border-accent/60 focus:outline-none"
          />
          <button
            type="submit"
            disabled={running || !changeRequest.trim()}
            className="rounded border border-accent/50 bg-accent/10 px-6 py-2.5 text-sm font-medium text-accent transition hover:bg-accent/20 disabled:cursor-not-allowed disabled:border-ink-700 disabled:bg-ink-900 disabled:text-slate-600"
          >
            {running ? 'Analysing…' : 'Analyse'}
          </button>
        </div>
      </form>

      <div className="mb-6 flex flex-wrap gap-1.5">
        {examples.map((example) => (
          <button
            key={example.scenario}
            onClick={() => {
              setChangeRequest(example.request)
              analyse(example.request)
            }}
            disabled={running}
            title={example.request}
            className="rounded border border-ink-800 bg-ink-900 px-2.5 py-1 font-mono text-[11px] text-slate-500 transition hover:border-ink-600 hover:text-slate-300 disabled:opacity-40"
          >
            {example.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-6 rounded border border-risk-critical/40 bg-risk-critical/5 px-4 py-3 text-sm text-risk-critical">
          {error}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          {agents.length > 0 ? (
            <AgentTimeline agents={agents} />
          ) : (
            <section className="rounded border border-dashed border-ink-800 px-4 py-8 text-center text-xs text-slate-700">
              Describe a change, or pick a scenario above.
            </section>
          )}
        </div>

        <div className="flex min-w-0 flex-col gap-4">
          {report && <RiskScore report={report} />}

          <BlastRadiusGraph
            graph={graph}
            origin={report?.service ?? null}
            affected={report?.affected_services ?? []}
          />

          {report && (
            <>
              <Explanation report={report} />
              <div className="grid gap-4 md:grid-cols-2">
                <Violations report={report} />
                <Incidents report={report} />
              </div>
              <History report={report} />
            </>
          )}
        </div>
      </div>

      <footer className="mt-8 border-t border-ink-800 pt-4 text-[11px] text-slate-700">
        Demo dataset — the services, incidents, and deployment history are synthetic, modelled on a
        mid-size e-commerce estate rather than drawn from any real system.
        {report && (
          <span className="ml-2 font-mono">
            · analysed in {report.elapsed_ms}ms ({report.llm_source})
          </span>
        )}
      </footer>
    </div>
  )
}
