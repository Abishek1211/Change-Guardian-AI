import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchExamples, fetchGraph, streamAnalysis } from './api'
import { AgentTimeline } from './components/AgentTimeline'
import { BlastRadiusGraph } from './components/BlastRadiusGraph'
import { Explanation, History, Incidents, Violations } from './components/Findings'
import { AboutPanel, EstatePanel, VocabularyList } from './components/Guide'
import { RiskScore } from './components/RiskScore'
import type {
  AgentRun,
  Example,
  KnownVocabulary,
  Report,
  ServiceGraph,
  Unrecognised,
} from './types'

export default function App() {
  const [changeRequest, setChangeRequest] = useState('')
  const [examples, setExamples] = useState<Example[]>([])
  const [known, setKnown] = useState<KnownVocabulary | null>(null)
  const [graph, setGraph] = useState<ServiceGraph | null>(null)

  const [agents, setAgents] = useState<AgentRun[]>([])
  const [report, setReport] = useState<Report | null>(null)
  const [unrecognised, setUnrecognised] = useState<Unrecognised | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  // Open on a visitor's first arrival - someone landing cold needs to know what
  // this is before an input box is useful. Dismissing it is remembered.
  const [showAbout, setShowAbout] = useState(
    () => localStorage.getItem('cg.about.dismissed') !== '1',
  )

  const dismissAbout = useCallback(() => {
    localStorage.setItem('cg.about.dismissed', '1')
    setShowAbout(false)
  }, [])

  const criticalServices = useMemo(
    () =>
      new Set(
        (graph?.nodes ?? [])
          .filter((n) => n.criticality === 'critical')
          .map((n) => n.id),
      ),
    [graph],
  )

  const abortRef = useRef<AbortController | null>(null)
  const autoRunRef = useRef(false)

  useEffect(() => {
    fetchGraph().then(setGraph).catch(() => setGraph(null))
    fetchExamples()
      .then((data) => {
        setExamples(data.examples)
        setKnown(data.known)
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
      setUnrecognised(null)
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
          onUnrecognised: (payload) => {
            setUnrecognised(payload)
            setAgents([])
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
          <h1 className="text-lg font-semibold tracking-tight text-fg">
            ChangeGuardian <span className="text-accent">AI</span>
          </h1>
          <p className="mt-0.5 text-xs text-fg-muted">
            Deployment risk analysis · 7-agent pipeline · six of seven agents are deterministic
          </p>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => (showAbout ? dismissAbout() : setShowAbout(true))}
            aria-expanded={showAbout}
            className="rounded border border-ink-700 px-2.5 py-1 font-mono text-xs text-fg-muted transition hover:border-accent/50 hover:text-accent"
          >
            {showAbout ? 'hide about' : 'about'}
          </button>
          <a
            href="/docs"
            className="font-mono text-xs text-fg-faint transition hover:text-accent"
          >
            API docs →
          </a>
        </div>
      </header>

      {showAbout && (
        <AboutPanel
          examples={examples}
          onPick={(request) => {
            setChangeRequest(request)
            analyse(request)
          }}
          onClose={dismissAbout}
        />
      )}

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
            list="known-targets"
            spellCheck={false}
            autoComplete="off"
            className="flex-1 rounded border border-ink-700 bg-ink-900 px-3.5 py-2.5 font-mono text-sm text-fg placeholder:text-fg-faint focus:border-accent/60 focus:outline-none"
          />
          {/* The dataset is a closed set. Offering it as suggestions means
              typing your own request is guided rather than a guess. */}
          <datalist id="known-targets">
            {known &&
              [...known.services, ...known.libraries, ...known.apis, ...known.events].map(
                (name) => <option key={name} value={name} />,
              )}
          </datalist>
          <button
            type="submit"
            disabled={running || !changeRequest.trim()}
            className="rounded border border-accent/50 bg-accent/10 px-6 py-2.5 text-sm font-medium text-accent transition hover:bg-accent/20 disabled:cursor-not-allowed disabled:border-ink-700 disabled:bg-ink-900 disabled:text-fg-faint"
          >
            {running ? 'Analysing…' : 'Analyse'}
          </button>
        </div>
      </form>

      <div className="mb-3 flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-[11px] text-fg-faint">Try:</span>
        {examples.map((example) => (
          <button
            key={example.scenario}
            onClick={() => {
              setChangeRequest(example.request)
              analyse(example.request)
            }}
            disabled={running}
            title={example.request}
            className="rounded border border-ink-800 bg-ink-900 px-2.5 py-1 font-mono text-[11px] text-fg-muted transition hover:border-ink-600 hover:text-fg disabled:opacity-40"
          >
            {example.label}
          </button>
        ))}
      </div>

      <EstatePanel
        known={known}
        criticalServices={criticalServices}
        onPick={(name) => setChangeRequest(name)}
      />

      {error && (
        <div className="mb-6 rounded border border-risk-critical/40 bg-risk-critical/5 px-4 py-3 text-sm text-risk-critical">
          {error}
        </div>
      )}

      {unrecognised && (
        <section
          data-shot="unrecognised"
          className="mb-6 rounded border border-risk-medium/40 bg-risk-medium/5 px-4 py-4"
        >
          <p className="text-sm text-risk-medium">
            No match for{' '}
            <span className="font-mono">“{unrecognised.change_request}”</span>
          </p>
          <p className="mt-1.5 text-xs leading-relaxed text-fg-muted">
            {unrecognised.detail} Rather than score a service it cannot find, the pipeline
            stops here — a number built from defaults would look authoritative and mean
            nothing.
          </p>

          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <VocabularyList title="Services" items={unrecognised.known.services} onPick={setChangeRequest} />
            <VocabularyList title="Libraries" items={unrecognised.known.libraries} onPick={setChangeRequest} />
            <VocabularyList title="APIs" items={unrecognised.known.apis} onPick={setChangeRequest} />
            <VocabularyList title="Kafka events" items={unrecognised.known.events} onPick={setChangeRequest} />
          </div>

          <p className="mt-3 text-xs text-fg-muted">
            Or try one of the scenarios above.
          </p>
        </section>
      )}

      <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          {agents.length > 0 ? (
            <AgentTimeline agents={agents} />
          ) : (
            <section className="rounded border border-dashed border-ink-800 px-4 py-8 text-center text-xs text-fg-faint">
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

      <footer className="mt-8 border-t border-ink-800 pt-4 text-[11px] text-fg-faint">
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
