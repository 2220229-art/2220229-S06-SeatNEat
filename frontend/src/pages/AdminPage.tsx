import { useEffect, useState } from "react"
import { api, errorText } from "../api"
import { useAuth } from "../auth"

type Overview = {
  users: number
  banned: number
  records: number
  groups: number
  new_users_7_days: number
  new_records_7_days: number
}

type UserRow = {
  id: number
  full_name: string
  email: string
  role: string
  account_role: string
  is_active: boolean
  ban_reason: string | null
}

type UserPage = { items: UserRow[]; total: number }

type Detail = {
  user: UserRow
  reservations: number
  groups: number
  sessions: { id: number; ip_address: string | null; user_agent: string | null; revoked: boolean }[]
  activity: { id: number; action: string; created_at: string; detail: string | null }[]
}

type RecordRow = {
  id: number
  customer_name: string
  status: string
  start_at: string
  party_size: number
}

type GroupRow = { id: number; name: string; owner_name: string; members: number }
type ActivityRow = {
  id: number
  action: string
  ip_address: string | null
  user_agent: string | null
  detail: string | null
  created_at: string
}
type SecurityView = {
  failed_by_ip: { ip_address: string; count: number }[]
  failed_by_account: { account: string; count: number }[]
}

type Tab = "overview" | "users" | "records" | "activity" | "security"

export function AdminPage() {
  const { token } = useAuth()
  const [tab, setTab] = useState<Tab>("overview")
  const [error, setError] = useState("")
  const [overview, setOverview] = useState<Overview | null>(null)
  const [query, setQuery] = useState("")
  const [roleFilter, setRoleFilter] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [users, setUsers] = useState<UserPage>({ items: [], total: 0 })
  const [detail, setDetail] = useState<Detail | null>(null)
  const [reason, setReason] = useState("Repeated no-shows")
  const [records, setRecords] = useState<RecordRow[]>([])
  const [groups, setGroups] = useState<GroupRow[]>([])
  const [activity, setActivity] = useState<ActivityRow[]>([])
  const [actionFilter, setActionFilter] = useState("")
  const [security, setSecurity] = useState<SecurityView | null>(null)
  const [selected, setSelected] = useState<number[]>([])

  useEffect(() => {
    if (!token) return
    if (tab === "overview") {
      api<Overview>("/admin/overview", {}, token).then(setOverview).catch((err) => setError(errorText(err)))
    }
    if (tab === "users") void loadUsers().catch((err) => setError(errorText(err)))
    if (tab === "records") {
      api<{ items: RecordRow[] }>("/admin/records", {}, token)
        .then((page) => setRecords(page.items))
        .catch((err) => setError(errorText(err)))
      api<{ items: GroupRow[] }>("/admin/groups", {}, token)
        .then((page) => setGroups(page.items))
        .catch((err) => setError(errorText(err)))
    }
    if (tab === "activity") void loadActivity()
    if (tab === "security") {
      api<SecurityView>("/admin/security", {}, token).then(setSecurity).catch((err) => setError(errorText(err)))
    }
  }, [tab, token])

  async function loadUsers() {
    const params = new URLSearchParams()
    if (query) params.set("q", query)
    if (roleFilter) params.set("account_role", roleFilter)
    if (statusFilter) params.set("status", statusFilter)
    const page = await api<UserPage>(`/admin/users?${params.toString()}`, {}, token)
    setUsers(page)
  }

  async function loadActivity() {
    const params = new URLSearchParams()
    if (actionFilter) params.set("action", actionFilter)
    if (query) params.set("q", query)
    const page = await api<{ items: ActivityRow[] }>(`/admin/activity?${params.toString()}`, {}, token)
    setActivity(page.items)
  }

  async function openUser(id: number) {
    setError("")
    try {
      setDetail(await api<Detail>(`/admin/users/${id}`, {}, token))
    } catch (err) {
      setError(errorText(err))
    }
  }

  async function ban(id: number) {
    setError("")
    try {
      await api(`/admin/users/${id}/ban`, { method: "POST", body: JSON.stringify({ reason }) }, token)
      await openUser(id)
      await loadUsers()
    } catch (err) {
      setError(errorText(err))
    }
  }

  async function unban(id: number) {
    setError("")
    try {
      await api(`/admin/users/${id}/unban`, { method: "POST" }, token)
      await openUser(id)
      await loadUsers()
    } catch (err) {
      setError(errorText(err))
    }
  }

  async function changeRole(id: number, accountRole: string) {
    setError("")
    try {
      await api(`/admin/users/${id}/role`, { method: "POST", body: JSON.stringify({ account_role: accountRole }) }, token)
      await openUser(id)
      await loadUsers()
    } catch (err) {
      setError(errorText(err))
    }
  }

  async function revokeSessions(id: number) {
    setError("")
    try {
      await api(`/admin/users/${id}/sessions/revoke`, { method: "POST" }, token)
      await openUser(id)
    } catch (err) {
      setError(errorText(err))
    }
  }

  async function bulk(path: string) {
    setError("")
    try {
      await api(`/admin/users/${path}`, { method: "POST", body: JSON.stringify({ ids: selected, reason }) }, token)
      setSelected([])
      await loadUsers()
    } catch (err) {
      setError(errorText(err))
    }
  }

  async function removeRecord(id: number) {
    await api(`/admin/records/${id}`, { method: "DELETE" }, token)
    setRecords((rows) => rows.filter((row) => row.id !== id))
  }

  async function removeGroup(id: number) {
    await api(`/admin/groups/${id}`, { method: "DELETE" }, token)
    setGroups((rows) => rows.filter((row) => row.id !== id))
  }

  async function download(path: string, filename: string) {
    const response = await fetch(`/api/v1${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: "include",
    })
    if (!response.ok) {
      setError("The export could not be downloaded.")
      return
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <section className="stack-page">
      <article className="card">
        <h1>Admin</h1>
        {error && <p className="error">{error}</p>}
        <div className="tabs">
          {(
            [
              ["overview", "Overview"],
              ["users", "Users"],
              ["records", "Records"],
              ["activity", "Activity"],
              ["security", "Security"],
            ] as const
          ).map(([id, label]) => (
            <button key={id} type="button" className={tab === id ? "" : "secondary"} onClick={() => setTab(id)}>
              {label}
            </button>
          ))}
        </div>
      </article>

      {tab === "overview" && overview && (
        <article className="card">
          <div className="stat-grid">
            <article>
              <strong>{overview.users}</strong>
              <span>Users</span>
            </article>
            <article>
              <strong>{overview.banned}</strong>
              <span>Banned</span>
            </article>
            <article>
              <strong>{overview.records}</strong>
              <span>Reservations</span>
            </article>
            <article>
              <strong>{overview.groups}</strong>
              <span>Groups</span>
            </article>
            <article>
              <strong>{overview.new_users_7_days}</strong>
              <span>New users in 7 days</span>
            </article>
            <article>
              <strong>{overview.new_records_7_days}</strong>
              <span>New bookings in 7 days</span>
            </article>
          </div>
        </article>
      )}

      {tab === "users" && (
        <article className="card">
          <form
            className="filters"
            onSubmit={(event) => {
              event.preventDefault()
              void loadUsers().catch((err) => setError(errorText(err)))
            }}
          >
            <label>
              Search
              <input value={query} onChange={(event) => setQuery(event.target.value)} />
            </label>
            <label>
              Role
              <select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}>
                <option value="">Any</option>
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </select>
            </label>
            <label>
              Status
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="">Any</option>
                <option value="active">Active</option>
                <option value="banned">Banned</option>
              </select>
            </label>
            <button type="submit">Apply</button>
          </form>
          <p className="muted">{users.total} accounts</p>
          <div className="actions">
            <button type="button" className="secondary" onClick={() => void bulk("bulk-ban")}>
              Ban selected
            </button>
            <button type="button" className="secondary" onClick={() => void bulk("bulk-unban")}>
              Unban selected
            </button>
            <button type="button" className="secondary" onClick={() => void download("/admin/export/users.csv", "users.csv")}>
              Export users
            </button>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th></th>
                  <th>Name</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {users.items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selected.includes(row.id)}
                        onChange={(event) =>
                          setSelected((ids) =>
                            event.target.checked ? [...ids, row.id] : ids.filter((id) => id !== row.id),
                          )
                        }
                      />
                    </td>
                    <td>
                      {row.full_name}
                      <div className="muted">{row.email}</div>
                    </td>
                    <td>{row.account_role}</td>
                    <td>{row.is_active ? "Active" : "Banned"}</td>
                    <td>
                      <button type="button" className="secondary" onClick={() => void openUser(row.id)}>
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {detail && (
            <div className="stack">
              <h2>{detail.user.full_name}</h2>
              <p>
                {detail.reservations} reservations · {detail.groups} groups · {detail.sessions.length} sessions
              </p>
              <label>
                Ban reason
                <input value={reason} onChange={(event) => setReason(event.target.value)} />
              </label>
              <div className="actions">
                <button type="button" className="danger" onClick={() => void ban(detail.user.id)}>
                  Ban
                </button>
                <button type="button" className="secondary" onClick={() => void unban(detail.user.id)}>
                  Unban
                </button>
                <button type="button" className="secondary" onClick={() => void revokeSessions(detail.user.id)}>
                  Revoke sessions
                </button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => void changeRole(detail.user.id, detail.user.account_role === "admin" ? "user" : "admin")}
                >
                  {detail.user.account_role === "admin" ? "Make user" : "Make admin"}
                </button>
              </div>
              <ul>
                {detail.activity.map((row) => (
                  <li key={row.id}>
                    {row.action} · {new Date(row.created_at).toLocaleString()} {row.detail ? `· ${row.detail}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </article>
      )}

      {tab === "records" && (
        <article className="card">
          <div className="actions">
            <button type="button" className="secondary" onClick={() => void download("/admin/export/records.csv", "records.csv")}>
              Export reservations
            </button>
          </div>
          <h2>Reservations</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Guest</th>
                  <th>When</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {records.map((row) => (
                  <tr key={row.id}>
                    <td>
                      {row.customer_name}
                      <div className="muted">Party of {row.party_size}</div>
                    </td>
                    <td>{new Date(row.start_at).toLocaleString()}</td>
                    <td>{row.status}</td>
                    <td>
                      <button type="button" className="danger" onClick={() => void removeRecord(row.id)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h2>Groups</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Owner</th>
                  <th>Members</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {groups.map((row) => (
                  <tr key={row.id}>
                    <td>{row.name}</td>
                    <td>{row.owner_name}</td>
                    <td>{row.members}</td>
                    <td>
                      <button type="button" className="danger" onClick={() => void removeGroup(row.id)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      )}

      {tab === "activity" && (
        <article className="card">
          <form
            className="filters"
            onSubmit={(event) => {
              event.preventDefault()
              void loadActivity().catch((err) => setError(errorText(err)))
            }}
          >
            <label>
              Action
              <input value={actionFilter} onChange={(event) => setActionFilter(event.target.value)} placeholder="login" />
            </label>
            <label>
              Search
              <input value={query} onChange={(event) => setQuery(event.target.value)} />
            </label>
            <button type="submit">Apply</button>
            <button type="button" className="secondary" onClick={() => void download("/admin/export/activity.csv", "activity.csv")}>
              Export activity
            </button>
          </form>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>When</th>
                  <th>Action</th>
                  <th>IP</th>
                  <th>Browser</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {activity.map((row) => (
                  <tr key={row.id}>
                    <td>{new Date(row.created_at).toLocaleString()}</td>
                    <td>{row.action}</td>
                    <td>{row.ip_address || ""}</td>
                    <td>{row.user_agent || ""}</td>
                    <td>{row.detail || ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      )}

      {tab === "security" && security && (
        <article className="card">
          <h2>Failed logins by IP</h2>
          {security.failed_by_ip.length === 0 && <p className="empty">No failed logins yet.</p>}
          <ul>
            {security.failed_by_ip.map((row) => (
              <li key={row.ip_address}>
                {row.ip_address}: {row.count}
              </li>
            ))}
          </ul>
          <h2>Failed logins by account</h2>
          <ul>
            {security.failed_by_account.map((row) => (
              <li key={row.account}>
                {row.account}: {row.count}
              </li>
            ))}
          </ul>
        </article>
      )}
    </section>
  )
}
