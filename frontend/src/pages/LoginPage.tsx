import { type FormEvent, useState } from "react"
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom"
import { errorText } from "../api"
import { homePath, useAuth } from "../auth"

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const created = (location.state as { message?: string } | null)?.message ?? ""
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to={homePath(user.role)} replace />

  async function submit(nextEmail: string, nextPassword: string) {
    setBusy(true)
    setError("")
    try {
      const loggedIn = await login(nextEmail, nextPassword)
      navigate(homePath(loggedIn.role), { replace: true })
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    void submit(email, password)
  }

  return (
    <section className="card narrow">
      <h1>Log in</h1>
      {created && <p className="ok">{created}</p>}
      <form className="stack" onSubmit={onSubmit}>
        <label>
          Email
          <input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Logging in…" : "Log in"}
        </button>
      </form>
      <p>
        New here? <Link to="/register">Create a customer account</Link>
      </p>
    </section>
  )
}
