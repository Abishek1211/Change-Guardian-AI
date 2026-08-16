import type { Example, KnownVocabulary, Report, ServiceGraph, Unrecognised } from './types'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) throw new ApiError(`${path} failed`, response.status)
  return response.json() as Promise<T>
}

export const fetchGraph = () => getJson<ServiceGraph>('/api/services')
export const fetchExamples = () =>
  getJson<{ examples: Example[]; known: KnownVocabulary }>('/api/examples')

export interface StreamHandlers {
  onStart: (agents: { key: string; label: string; description: string; index: number }[]) => void
  onAgent: (event: {
    agent: string
    index: number
    status: 'complete' | 'error'
    output?: Record<string, unknown>
    elapsed_ms: number
    error?: string
  }) => void
  onComplete: (report: Report) => void
  /** The request named nothing in the dataset - the pipeline refused to score
   *  it and returned the vocabulary that would have worked. */
  onUnrecognised: (payload: Unrecognised) => void
  onError: (message: string) => void
}

/**
 * Consume the SSE stream via fetch rather than EventSource.
 *
 * EventSource cannot surface an HTTP status - a 429 arrives as an
 * indistinguishable `onerror`. Since the whole point of the rate limit is to
 * tell the visitor *why* they were turned away, we parse the stream by hand.
 */
export async function streamAnalysis(
  changeRequest: string,
  handlers: StreamHandlers,
  signal: AbortSignal,
): Promise<void> {
  let response: Response
  try {
    response = await fetch(
      `/api/analyze/stream?change_request=${encodeURIComponent(changeRequest)}`,
      { signal, headers: { Accept: 'text/event-stream' } },
    )
  } catch (error) {
    if ((error as Error).name === 'AbortError') return
    handlers.onError('Could not reach the API. Is the backend running?')
    return
  }

  if (!response.ok) {
    let detail = `Request failed (HTTP ${response.status})`
    try {
      const body = await response.json()
      if (body.detail) detail = typeof body.detail === 'string' ? body.detail : detail
    } catch {
      /* non-JSON error body; keep the generic message */
    }
    handlers.onError(detail)
    return
  }

  if (!response.body) {
    handlers.onError('The API returned an empty stream.')
    return
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  let sawComplete = false

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      // sse_starlette terminates lines with CRLF. Normalise before splitting,
      // otherwise the frame separator is "\r\n\r\n" and a plain "\n\n" split
      // never matches - the buffer grows forever and no event is ever parsed.
      buffer += value.replace(/\r\n/g, '\n')

      // SSE frames are separated by a blank line. Keep the trailing partial.
      const frames = buffer.split('\n\n')
      buffer = frames.pop() ?? ''

      for (const frame of frames) {
        const dataLine = frame
          .split('\n')
          .find((line) => line.startsWith('data:'))
        if (!dataLine) continue

        let payload: Record<string, unknown>
        try {
          payload = JSON.parse(dataLine.slice(5).trim())
        } catch {
          continue
        }

        switch (payload.event) {
          case 'start':
            handlers.onStart(payload.agents as never)
            break
          case 'agent':
            handlers.onAgent(payload as never)
            break
          case 'unrecognised':
            // A refusal is a terminal outcome, not an error - the stream ends
            // here on purpose and must not report "ended before finishing".
            sawComplete = true
            handlers.onUnrecognised(payload as never)
            break
          case 'complete':
            sawComplete = true
            handlers.onComplete(payload.report as Report)
            break
        }
      }
    }

    // A stream that ends without a `complete` event leaves the UI spinning
    // forever, which is worse than an error. Say so instead.
    if (!sawComplete && !signal.aborted) {
      handlers.onError('The analysis stream ended before finishing.')
    }
  } catch (error) {
    if ((error as Error).name !== 'AbortError') {
      handlers.onError('The stream ended unexpectedly.')
    }
  } finally {
    reader.releaseLock()
  }
}
