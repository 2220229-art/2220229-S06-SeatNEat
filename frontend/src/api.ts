export class ApiError extends Error {
  status: number
  code: string
  details?: { field: string; message: string }[]

  constructor(status: number, code: string, message: string, details?: { field: string; message: string }[]) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

type ErrorBody = {
  code?: string
  message?: string
  details?: { field: string; message: string }[]
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1"

let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

export async function api<T>(path: string, options: RequestInit = {}, token?: string | null): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json")
  if (token) headers.set("Authorization", `Bearer ${token}`)

  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers })
  } catch {
    throw new ApiError(0, "NETWORK", "Could not reach the server. Start the backend and try again.")
  }

  const text = await response.text()
  let payload: ErrorBody | null = null
  if (text) {
    try {
      payload = JSON.parse(text) as ErrorBody
    } catch {
      payload = null
    }
  }

  if (!response.ok) {
    if (response.status === 401 && token) onUnauthorized?.()
    throw new ApiError(
      response.status,
      payload?.code ?? "REQUEST_FAILED",
      payload?.message ?? `Request failed (${response.status}).`,
      payload?.details,
    )
  }
  return payload as T
}

export function errorText(error: unknown) {
  if (error instanceof ApiError) {
    if (error.details && error.details.length > 0) return error.details.map((item) => item.message).join(" ")
    return error.message
  }
  return "Something went wrong. Please try again."
}
