import { type FormEvent, useEffect, useState } from "react"
import { api, errorText } from "../api"
import { useAuth } from "../auth"
import { roleLabel } from "../format"

type SessionRow = {
  id: number
  ip_address: string | null
  user_agent: string | null
  created_at: string
  expires_at: string
  revoked: boolean
  current: boolean
}

export function ProfilePage() {
  const { user, token } = useAuth()
  const [name, setName] = useState(user?.full_name ?? "")
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [sessions, setSessions] = useState<SessionRow[]>([])

  useEffect(() => {
    if (!token) return
    api<SessionRow[]>("/auth/sessions", {}, token)
      .then(setSessions)
      .catch(() => setSessions([]))
  }, [token])

  if (!user) return null

  async function saveName(event: FormEvent) {
    event.preventDefault()
    setError("")
    setMessage("")
    try {
      await api("/auth/profile", { method: "PATCH", body: JSON.stringify({ full_name: name }) }, token)
      setMessage("Name saved.")
    } catch (err) {
      setError(errorText(err))
    }
  }

  async function savePassword(event: FormEvent) {
    event.preventDefault()
    setError("")
    setMessage("")
    try {
      await api(
        "/auth/password",
        { method: "POST", body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }) },
        token,
      )
      setCurrentPassword("")
      setNewPassword("")
      setMessage("Password changed.")
    } catch (err) {
      setError(errorText(err))
    }
  }

  async function revoke(id: number) {
    setError("")
    try {
      await api(`/auth/sessions/${id}`, { method: "DELETE" }, token)
      setSessions((rows) => rows.map((row) => (row.id === id ? { ...row, revoked: true, current: false } : row)))
    } catch (err) {
      setError(errorText(err))
    }
  }

  return (
    <section className="stack-page">
      <article className="card narrow">
        <h1>Your profile</h1>
        {message && <p className="ok">{message}</p>}
        {error && <p className="error">{error}</p>}
        <dl className="profile">
          <div>
            <dt>Email</dt>
            <dd>{user.email}</dd>
          </div>
          <div>
            <dt>Restaurant job</dt>
            <dd>{roleLabel(user.role)}</dd>
          </div>
          <div>
            <dt>Account role</dt>
            <dd>{user.account_role === "admin" ? "Admin" : "User"}</dd>
          </div>
        </dl>
        <form className="stack" onSubmit={saveName}>
          <label>
            Name
            <input value={name} onChange={(event) => setName(event.target.value)} required minLength={2} />
          </label>
          <button type="submit">Save name</button>
        </form>
      </article>
      <article className="card narrow">
        <h2>Change password</h2>
        <form className="stack" onSubmit={savePassword}>
          <label>
            Current password
            <input
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              required
            />
          </label>
          <label>
            New password
            <input
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              required
              minLength={8}
            />
          </label>
          <button type="submit">Change password</button>
        </form>
      </article>
      <article className="card">
        <h2>Sessions</h2>
        {sessions.length === 0 && <p className="empty">No sessions yet.</p>}
        {sessions.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>When</th>
                  <th>IP</th>
                  <th>Browser</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((row) => (
                  <tr key={row.id}>
                    <td>
                      {new Date(row.created_at).toLocaleString()}
                      {row.current ? " · this device" : ""}
                      {row.revoked ? " · revoked" : ""}
                    </td>
                    <td>{row.ip_address || "Unknown"}</td>
                    <td>{row.user_agent || "Unknown"}</td>
                    <td>
                      {!row.revoked && (
                        <button type="button" className="secondary" onClick={() => void revoke(row.id)}>
                          Revoke
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </article>
    </section>
  )
}
