import { useState } from 'react'
import type { Example, KnownVocabulary } from '../types'

/** A clickable name that drops itself into the input. Shared by the estate
 *  browser and the "we don't recognise that" panel. */
export function VocabularyList({
  title,
  items,
  onPick,
  critical,
}: {
  title: string
  items: string[]
  onPick: (name: string) => void
  critical?: Set<string>
}) {
  if (items.length === 0) return null
  return (
    <div>
      <p className="mb-1.5 text-[10px] tracking-widest text-fg-faint uppercase">{title}</p>
      <ul className="space-y-1">
        {items.map((name) => (
          <li key={name}>
            <button
              type="button"
              onClick={() => onPick(name)}
              className="text-left font-mono text-[11px] text-fg-muted transition hover:text-accent"
            >
              {name}
              {critical?.has(name) && (
                <span className="ml-1.5 text-[9px] text-risk-critical/80">critical</span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

/**
 * What the visitor can actually ask about.
 *
 * The input takes free text but resolves against a closed set. Leaving that
 * invisible meant the natural first experiment - typing your own service name -
 * failed. Collapsed by default so it does not crowd the tool, but one click away
 * and summarised in the header so the counts are always visible.
 */
export function EstatePanel({
  known,
  criticalServices,
  onPick,
}: {
  known: KnownVocabulary | null
  criticalServices: Set<string>
  onPick: (name: string) => void
}) {
  const [open, setOpen] = useState(false)
  if (!known) return null

  const counts = [
    `${known.services.length} services`,
    `${known.libraries.length} libraries`,
    `${known.apis.length} APIs`,
    `${known.events.length} Kafka events`,
  ].join(' · ')

  return (
    <section className="mb-6 rounded border border-ink-800 bg-ink-900">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-4 py-2.5 text-left transition hover:bg-ink-850"
      >
        <span className="text-xs text-fg-muted">
          <span className="tracking-widest uppercase">What you can ask about</span>
          <span className="ml-2 font-mono text-[11px] text-fg-faint">{counts}</span>
        </span>
        <span className="font-mono text-fg-faint">{open ? '−' : '+'}</span>
      </button>

      {open && (
        <div className="border-t border-ink-800 px-4 py-4">
          <p className="mb-3 text-xs leading-relaxed text-fg-muted">
            This is a synthetic estate, so these are the only things that exist. Click any
            name to drop it into the box, then describe what you want to change — an
            upgrade, a memory limit, a schema constraint, a renamed field.
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <VocabularyList
              title="Services"
              items={known.services}
              onPick={onPick}
              critical={criticalServices}
            />
            <VocabularyList title="Shared libraries" items={known.libraries} onPick={onPick} />
            <VocabularyList title="APIs" items={known.apis} onPick={onPick} />
            <VocabularyList title="Kafka events" items={known.events} onPick={onPick} />
          </div>
        </div>
      )}
    </section>
  )
}

/** The "what am I looking at" panel. A visitor arriving cold sees an input box
 *  and a graph; this is what tells them why either matters. */
export function AboutPanel({
  examples,
  onPick,
  onClose,
}: {
  examples: Example[]
  onPick: (request: string) => void
  onClose: () => void
}) {
  return (
    <section className="mb-6 rounded border border-accent/30 bg-ink-900">
      <div className="flex items-start justify-between gap-4 border-b border-ink-800 px-5 py-3">
        <h2 className="text-xs tracking-widest text-fg-muted uppercase">
          About this project
        </h2>
        <button
          onClick={onClose}
          className="font-mono text-xs text-fg-faint transition hover:text-fg"
          aria-label="Close about panel"
        >
          close ×
        </button>
      </div>

      <div className="grid gap-6 px-5 py-5 lg:grid-cols-2">
        <div className="space-y-3 text-sm leading-relaxed text-fg-muted">
          <p>
            <span className="text-fg">ChangeGuardian predicts deployment risk before
            rollout.</span>{' '}
            Describe a change to a service in plain English and it returns a 0–100 risk
            score, every service that change can break, the rules it violates, what
            happened the last time someone tried it, and a rollout strategy.
          </p>
          <p>
            It runs seven agents in a pipeline, but{' '}
            <span className="text-accent">six of them never touch a language model.</span>{' '}
            The score is arithmetic. Every point it adds writes a matching line to an audit
            trail, so the number can be taken apart and argued with — which is the whole
            point, because a risk score nobody can interrogate is one nobody acts on.
          </p>
          <p>
            The model only writes the closing explanation. If it is unavailable, the wording
            changes and the findings do not.
          </p>
          <p className="text-xs text-fg-faint">
            The estate below is <span className="text-fg-muted">synthetic</span> — seven
            services modelled on a mid-size e-commerce system, not real production data. The
            financial figures are illustrative.
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <p className="mb-2 text-[10px] tracking-widest text-fg-faint uppercase">
              How to use it
            </p>
            <ol className="space-y-2 text-sm text-fg-muted">
              {[
                'Pick a scenario below, or describe your own change in the box.',
                'Watch the seven agents run — each shows what it actually found.',
                'Open “How this score was reached” to see the score taken apart.',
                'Hover a node in the graph to trace why a service is affected.',
              ].map((step, i) => (
                <li key={step} className="flex gap-2.5">
                  <span className="font-mono text-xs text-accent">{i + 1}</span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </div>

          <div>
            <p className="mb-2 text-[10px] tracking-widest text-fg-faint uppercase">
              Try one
            </p>
            <div className="flex flex-wrap gap-1.5">
              {examples.slice(0, 3).map((example) => (
                <button
                  key={example.scenario}
                  onClick={() => onPick(example.request)}
                  className="rounded border border-ink-700 bg-ink-850 px-2.5 py-1 font-mono text-[11px] text-fg-muted transition hover:border-accent/50 hover:text-accent"
                >
                  {example.request}
                </button>
              ))}
            </div>
          </div>

          <p className="font-mono text-[11px] text-fg-faint">
            <a
              href="https://github.com/Abishek1211/Change-Guardian-AI"
              target="_blank"
              rel="noreferrer"
              className="transition hover:text-accent"
            >
              source on github
            </a>
            {' · '}
            <a href="/docs" className="transition hover:text-accent">
              api docs
            </a>
          </p>
        </div>
      </div>
    </section>
  )
}
