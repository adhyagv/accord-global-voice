const API_BASE_URL = (import.meta.env.VITE_ACCORD_API_URL ?? 'http://127.0.0.1:8000').replace(/\/+$/, '')

type RequestOptions = { memberId?: string }

async function request<T>(path: string, init: RequestInit = {}, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (options.memberId) headers.set('X-Member-Id', options.memberId)

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers })
  } catch (error) {
    const detail = error instanceof Error ? error.message : 'Network request failed.'
    throw new Error(`Cannot reach the Accord API at ${API_BASE_URL}. Start the backend and keep its terminal open. (${detail})`, { cause: error })
  }
  const raw = await response.text()
  let payload: unknown = undefined
  if (raw) {
    try { payload = JSON.parse(raw) as unknown } catch { payload = raw }
  }
  if (!response.ok) {
    const apiMessage = typeof payload === 'object' && payload !== null && 'error' in payload
      ? String((payload as { error?: { message?: string } }).error?.message ?? '')
      : ''
    throw new Error(apiMessage || `API request failed (${response.status}): ${response.statusText}`)
  }
  return payload as T
}

export function apiGet<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return request<T>(path, {}, options)
}

export function apiPost<T>(path: string, body: unknown, options: RequestOptions = {}): Promise<T> {
  return request<T>(path, { method: 'POST', body: JSON.stringify(body) }, options)
}

export function apiPatch<T>(path: string, body: unknown, options: RequestOptions = {}): Promise<T> {
  return request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }, options)
}
