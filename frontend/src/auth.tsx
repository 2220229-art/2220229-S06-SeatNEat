import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import { Navigate } from "react-router-dom"
import { api, setUnauthorizedHandler } from "./api"
import type { LoginResult, Role, User } from "./types"

const TOKEN_KEY = "sitneat_token"
const USER_KEY = "sitneat_user"

type AuthValue = {
  user: User | null
  token: string | null
  ready: boolean
  login: (email: string, password: string) => Promise<User>
  logout: () => void
}

const AuthContext = createContext<AuthValue | null>(null)

function loadSaved() {
  const token = sessionStorage.getItem(TOKEN_KEY)
  const raw = sessionStorage.getItem(USER_KEY)
  if (!token || !raw) return null
  try {
    return { token, user: JSON.parse(raw) as User }
  } catch {
    return null
  }
}

function clearSaved() {
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(USER_KEY)
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const saved = loadSaved()
  const [token, setToken] = useState<string | null>(saved?.token ?? null)
  const [user, setUser] = useState<User | null>(saved?.user ?? null)
  const [ready, setReady] = useState(saved === null)

  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearSaved()
      setToken(null)
      setUser(null)
    })
  }, [])

  useEffect(() => {
    if (!token) {
      setReady(true)
      return
    }
    let cancelled = false
    api<User>("/auth/me", {}, token)
      .then((fresh) => {
        if (cancelled) return
        setUser(fresh)
        sessionStorage.setItem(USER_KEY, JSON.stringify(fresh))
      })
      .catch(() => {
        if (cancelled) return
        clearSaved()
        setToken(null)
        setUser(null)
      })
      .finally(() => {
        if (!cancelled) setReady(true)
      })
    return () => {
      cancelled = true
    }
  }, [token])

  async function login(email: string, password: string) {
    const result = await api<LoginResult>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    })
    sessionStorage.setItem(TOKEN_KEY, result.access_token)
    sessionStorage.setItem(USER_KEY, JSON.stringify(result.user))
    setUser(result.user)
    setToken(result.access_token)
    setReady(true)
    return result.user
  }

  function logout() {
    clearSaved()
    setToken(null)
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, token, ready, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error("useAuth must be used inside AuthProvider")
  return value
}

export function RequireAuth({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { user, ready } = useAuth()
  if (!ready) return <p className="muted">Loading…</p>
  if (!user) return <Navigate to="/login" replace />
  if (roles && !roles.includes(user.role)) return <Navigate to="/unauthorized" replace />
  return children
}

export function homePath(role: Role) {
  if (role === "staff") return "/today"
  if (role === "manager") return "/manage"
  return "/book"
}
