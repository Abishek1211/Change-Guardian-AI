import { useMemo } from 'react'
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
  quiet: 'border-ink-700 bg-ink-850 text-slate-500',
  infra: 'border-ink-700 bg-ink-900 text-slate-600',
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
        <span className="mr-1.5 text-[9px] text-slate-700">{KIND_GLYPH[data.kind] ?? ''}</span>
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
      }
    })

    const edges: Edge[] = graph.edges.map((edge, i) => {
      const hot = impacted.has(edge.source) && impacted.has(edge.target)
      const touchesOrigin = edge.source === origin || edge.target === origin
      return {
        id: `${edge.source}-${edge.rel}-${edge.target}-${i}`,
        source: edge.source,
        target: edge.target,
        animated: hot && touchesOrigin,
        style: {
          stroke: hot ? '#f87171' : '#1e293b',
          strokeWidth: hot ? 1.6 : 1,
          opacity: hot ? 0.85 : 0.35,
        },
      }
    })

    return { nodes, edges }
  }, [graph, origin, affected])

  return (
    <section className="flex h-[460px] flex-col rounded border border-ink-800 bg-ink-900">
      <div className="flex items-center justify-between border-b border-ink-800 px-4 py-2.5">
        <h2 className="text-xs tracking-widest text-slate-500 uppercase">Blast radius</h2>
        <div className="flex items-center gap-3 font-mono text-[10px] text-slate-600">
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
          <div className="flex h-full items-center justify-center text-xs text-slate-600">
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
