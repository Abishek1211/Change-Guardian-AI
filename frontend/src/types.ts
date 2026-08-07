export type ImpactLevel = 'low' | 'medium' | 'high' | 'critical'

export interface Incident {
  id: string
  title: string
  severity: string
  financial_impact: number
}

export interface MemoryLesson {
  deployment: string
  outcome: 'success' | 'failed' | string
  lessons: string[]
}

export interface Report {
  change_request: string
  service: string
  scenario: string
  affected_services: string[]
  similar_incidents: Incident[]
  rule_violations: string[]
  memory_lessons: MemoryLesson[]
  risk_score: number
  impact_level: ImpactLevel
  sla_impact: string
  financial_impact: number
  risk_reasons: string[]
  rollout_plan: string
  llm_explanation: string
  llm_remediation: string[]
  /** "llm" when the model answered, "rule-based" when it fell back. */
  llm_source: 'llm' | 'rule-based'
  elapsed_ms: number
}

export interface AgentMeta {
  key: string
  label: string
  description: string
  index: number
}

export type AgentStatus = 'pending' | 'running' | 'complete' | 'error'

export interface AgentRun extends AgentMeta {
  status: AgentStatus
  output?: Record<string, unknown>
  elapsedMs?: number
  error?: string
}

export interface GraphNode {
  id: string
  type: 'service' | 'database' | 'api' | 'kafka_event' | 'library' | string
  criticality: string | null
  team: string | null
}

export interface GraphEdge {
  source: string
  target: string
  rel: string
}

export interface ServiceGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
  service_count: number
}

export interface Example {
  scenario: string
  label: string
  request: string
}
