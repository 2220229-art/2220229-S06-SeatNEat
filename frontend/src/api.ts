import type { User } from "./types"

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
let onToken: ((token: string, user: User) => void) | null = null

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

export function setTokenHandler(handler: (token: string, user: User) => void) {
  onToken = handler
}

async function refreshSession(): Promise<{ access_token: string; user: User } | null> {
  const response = await fetch(`${API_BASE}/auth/refresh`, { method: "POST", credentials: "include" })
  if (!response.ok) return null
  return (await response.json()) as { access_token: string; user: User }
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
  allowRefresh = true,
): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json")
  if (token) headers.set("Authorization", `Bearer ${token}`)

  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: "include" })
  } catch {
    throw new ApiError(0, "NETWORK", "Could not reach the server. Start the backend and try again.")
  }

  if (
    response.status === 401 &&
    allowRefresh &&
    token &&
    !path.startsWith("/auth/login") &&
    !path.startsWith("/auth/refresh") &&
    path !== "/auth/logout"
  ) {
    const renewed = await refreshSession()
    if (renewed) {
      onToken?.(renewed.access_token, renewed.user)
      return api<T>(path, options, renewed.access_token, false)
    }
    onUnauthorized?.()
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
