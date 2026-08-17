import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  Position,
  type Edge,
  type Node,
  type NodeProps,
} from 'reactflow'
import type { ServiceGraph } from '../types'

type Ring = 'origin' | 'affected' | 'quiet' | 'infra'

interface NodeData {
  label: string
  ring: Ring
  kind: string
  criticality: string | null
}

const RING_STYLE: Record<Ring, string> = {
  origin: 'border-accent bg-accent/15 text-accent shadow-[0_0_0_3px_rgb(52_211_153/0.12)]',
  affected: 'border-risk-critical/70 bg-risk-critical/10 text-risk-critical',
  quiet: 'border-ink-700 bg-ink-850 text-fg-muted',
  infra: 'border-ink-700 bg-ink-900 text-fg-faint',
}

const KIND_GLYPH: Record<string, string> = {
  database: 'DB',
  api: 'API',
  kafka_event: 'EVT',
  library: 'LIB',
}

function GraphNodeCard({ data }: NodeProps<NodeData>) {
  const isInfra = data.ring === 'infra'
  return (
    <div
      className={`rounded border px-2.5 py-1.5 font-mono transition-colors ${RING_STYLE[data.ring]} ${
        isInfra ? 'text-[10px]' : 'text-[11px]'
      }`}
    >
      <Handle type="target" position={Position.Top} className="!opacity-0" />
      {isInfra && (
        <span className="mr-1.5 text-[9px] text-fg-faint">{KIND_GLYPH[data.kind] ?? ''}</span>
      )}
      {data.label}
      {data.criticality === 'critical' && data.ring !== 'infra' && (
        <span className="ml-1.5 text-[9px] opacity-70">crit</span>
      )}
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
    </div>
  )
}

const nodeTypes = { card: GraphNodeCard }

/** Place `count` items evenly around a circle of the given radius. */
function ring(index: number, count: number, radius: number, offset = 0) {
  const angle = (index / Math.max(count, 1)) * Math.PI * 2 + offset
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius }
}

export function BlastRadiusGraph({
  graph,
  origin,
  affected,
}: {
  graph: ServiceGraph | null
  origin: string | null
  affected: string[]
}) {
  // Hovering a node isolates it. The graph shows *which* services are affected;
  // this is how you find out *why* a particular one is in the set.
  const [hovered, setHovered] = useState<string | null>(null)

  // Hysteresis. Without it, dragging the cursor across the pane clips a dozen
  // nodes on the way past and each one re-dims all 19 with a 140ms fade - the
  // whole graph pulses. ENTER_DELAY means a node has to be settled on rather
  // than merely passed over; LEAVE_DELAY keeps the isolation up long enough to
  // move between a node and its neighbours without flashing back to normal.
  const ENTER_DELAY = 160
  const LEAVE_DELAY = 220
  const enterTimer = useRef<number | undefined>(undefined)
  const leaveTimer = useRef<number | undefined>(undefined)

  const clearTimers = useCallback(() => {
    window.clearTimeout(enterTimer.current)
    window.clearTimeout(leaveTimer.current)
  }, [])

  const onNodeEnter = useCallback(
    (_: unknown, node: Node) => {
      clearTimers()
      enterTimer.current = window.setTimeout(() => setHovered(node.id), ENTER_DELAY)
    },
    [clearTimers],
  )

  const onNodeLeave = useCallback(() => {
    clearTimers()
    leaveTimer.current = window.setTimeout(() => setHovered(null), LEAVE_DELAY)
  }, [clearTimers])

  useEffect(() => clearTimers, [clearTimers])

  const neighbours = useMemo(() => {
    if (!graph || !hovered) return null
    const near = new Set<string>([hovered])
    for (const edge of graph.edges) {
      if (edge.source === hovered) near.add(edge.target)
      if (edge.target === hovered) near.add(edge.source)
    }
    return near
  }, [graph, hovered])

  const { nodes, edges } = useMemo(() => {
    if (!graph) return { nodes: [] as Node[], edges: [] as Edge[] }

    const affectedSet = new Set(affected)
    const impacted = new Set([...affected, ...(origin ? [origin] : [])])

    const ringOf = (id: string, kind: string): Ring => {
      if (id === origin) return 'origin'
      if (affectedSet.has(id)) return 'affected'
      return kind === 'service' ? 'quiet' : 'infra'
    }

    // Group first so each ring can be spaced evenly by its own population.
    const buckets: Record<Ring, string[]> = { origin: [], affected: [], quiet: [], infra: [] }
    for (const node of graph.nodes) buckets[ringOf(node.id, node.type)].push(node.id)

    const RADII: Record<Ring, number> = { origin: 0, affected: 210, quiet: 380, infra: 540 }

    const nodes: Node[] = graph.nodes.map((node) => {
      const r = ringOf(node.id, node.type)
      const indexInRing = buckets[r].indexOf(node.id)
      // Offset each ring slightly so nodes do not line up radially.
      const position =
        r === 'origin'
          ? { x: 0, y: 0 }
          : ring(indexInRing, buckets[r].length, RADII[r], r === 'quiet' ? 0.4 : 0)

      return {
        id: node.id,
        type: 'card',
        position,
        data: { label: node.id, ring: r, kind: node.type, criticality: node.criticality },
        draggable: true,
        selectable: false,
        style: {
          // 0.22 rather than 0.12: still unmistakably backgrounded, but a
          // smaller jump, so a transition that does happen reads as a fade
          // rather than a flash.
          opacity: neighbours && !neighbours.has(node.id) ? 0.22 : 1,
          transition: 'opacity 200ms ease',
        },
      }
    })

    const edges: Edge[] = graph.edges.map((edge, i) => {
      const hot = impacted.has(edge.source) && impacted.has(edge.target)
      const touchesOrigin = edge.source === origin || edge.target === origin
      const touchesHover = hovered === edge.source || hovered === edge.target

      // While hovering, only the hovered node's own edges stay visible - and
      // they carry their relationship label, which is the actual answer to
      // "why is this service affected?"
      const dimmed = hovered !== null && !touchesHover
      const stroke = touchesHover ? '#34d399' : hot ? '#f87171' : '#1e293b'

      return {
        id: `${edge.source}-${edge.rel}-${edge.target}-${i}`,
        source: edge.source,
        target: edge.target,
        animated: touchesHover || (hot && touchesOrigin && hovered === null),
        label: touchesHover ? edge.rel : undefined,
        labelShowBg: true,
        labelBgPadding: [5, 2] as [number, number],
        labelBgBorderRadius: 3,
        labelBgStyle: { fill: '#0d121b', fillOpacity: 0.95 },
        labelStyle: { fill: '#34d399', fontSize: 9, fontFamily: 'ui-monospace, monospace' },
        // React Flow draws an invisible 20px-wide interaction path over every
        // edge so they are easy to click. We never interact with edges, and
        // those fat hit-areas sit on top of the nodes - hovering a node landed
        // on an edge instead, which cleared the hover, which removed the edge
        // styling, which restored the hover: a ~15Hz flicker. Zero disables it.
        interactionWidth: 0,
        style: {
          stroke,
          strokeWidth: touchesHover ? 1.8 : hot ? 1.6 : 1,
          opacity: dimmed ? 0.1 : touchesHover ? 0.95 : hot ? 0.85 : 0.35,
          transition: 'opacity 200ms ease',
        },
      }
    })

    return { nodes, edges }
  }, [graph, origin, affected, hovered, neighbours])

  return (
    <section
      data-shot="blast-radius"
      className="flex h-[460px] flex-col rounded border border-ink-800 bg-ink-900"
    >
      <div className="flex items-center justify-between border-b border-ink-800 px-4 py-2.5">
        <h2 className="text-xs tracking-widest text-fg-muted uppercase">
          Blast radius
          <span className="ml-2 hidden normal-case tracking-normal text-fg-faint sm:inline">
            — hover a node to trace its dependencies
          </span>
        </h2>
        <div className="flex items-center gap-3 font-mono text-[10px] text-fg-faint">
          <Legend className="bg-accent" label="changed" />
          <Legend className="bg-risk-critical" label={`affected (${affected.length})`} />
          <Legend className="bg-ink-600" label="unaffected" />
        </div>
      </div>

      <div className="min-h-0 flex-1">
        {graph ? (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodeMouseEnter={onNodeEnter}
            onNodeMouseLeave={onNodeLeave}
            fitView
            fitViewOptions={{ padding: 0.15 }}
            minZoom={0.2}
            proOptions={{ hideAttribution: true }}
            nodesConnectable={false}
            edgesFocusable={false}
          >
            <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#1a2333" />
            <Controls showInteractive={false} className="!shadow-none" />
          </ReactFlow>
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-fg-faint">
            Loading dependency graph…
          </div>
        )}
      </div>
    </section>
  )
}

function Legend({ className, label }: { className: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`h-2 w-2 rounded-full ${className}`} aria-hidden />
      {label}
    </span>
  )
}
