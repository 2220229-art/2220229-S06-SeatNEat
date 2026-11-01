import { type FormEvent, useEffect, useState } from "react"
import { api, errorText } from "../api"
import { useAuth } from "../auth"
import { ReservationDetail } from "../components/ReservationDetail"
import { ReservationTable } from "../components/ReservationTable"
import { StatusActions } from "../components/StatusActions"
import { calendarDate, shiftDate } from "../format"
import type { Reservation, RestaurantSettings, Seat, Status, Summary, User } from "../types"

type Tab = "bookings" | "seats" | "staff" | "settings" | "summary"

export function ManagerPage() {
  const [tab, setTab] = useState<Tab>("bookings")
  return (
    <section className="stack-page">
      <div className="tabs" role="tablist">
        {(
          [
            ["bookings", "Bookings"],
            ["seats", "Seats"],
            ["staff", "Staff"],
            ["settings", "Hours and rules"],
            ["summary", "Summary"],
          ] as const
        ).map(([id, label]) => (
          <button key={id} type="button" className={tab === id ? "" : "secondary"} onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </div>
      {tab === "bookings" && <BookingsPanel />}
      {tab === "seats" && <SeatsPanel />}
      {tab === "staff" && <StaffPanel />}
      {tab === "settings" && <SettingsPanel />}
      {tab === "summary" && <SummaryPanel />}
    </section>
  )
}

function BookingsPanel() {
  const { token } = useAuth()
  const [settings, setSettings] = useState<RestaurantSettings | null>(null)
  const [rows, setRows] = useState<Reservation[]>([])
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [status, setStatus] = useState("")
  const [error, setError] = useState("")
  const [viewId, setViewId] = useState<number | null>(null)

  async function load(from = dateFrom, to = dateTo, nextStatus = status) {
    if (!token) return
    const params = new URLSearchParams()
    if (from) params.set("date_from", from)
    if (to) params.set("date_to", to)
    if (nextStatus) params.set("status", nextStatus)
    const [loadedSettings, bookings] = await Promise.all([
      api<RestaurantSettings>("/settings", {}, token),
      api<Reservation[]>(`/reservations?${params}`, {}, token),
    ])
    setSettings(loadedSettings)
    setRows(bookings)
  }

  useEffect(() => {
    if (!token) return
    const from = calendarDate("Asia/Dhaka")
    const to = shiftDate(from, 7)
    setDateFrom(from)
    setDateTo(to)
    load(from, to, "").catch((err) => setError(errorText(err)))
  }, [token])

  return (
    <div className="stack">
    <div className="card">
      <h1>All reservations</h1>
      <form
        className="filters"
        onSubmit={(event) => {
          event.preventDefault()
          load().catch((err) => setError(errorText(err)))
        }}
      >
        <label>
          From
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </label>
        <label>
          To
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </label>
        <label>
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>
            <option value="confirmed">Confirmed</option>
            <option value="seated">Seated</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </label>
        <button type="submit">Filter</button>
      </form>
      {error && <p className="error">{error}</p>}
      {settings && token && (
        <ReservationTable
          rows={rows}
          timeZone={settings.timezone}
          showGuest
          emptyText="No reservations match this filter."
          actions={(row) => (
            <div className="action-stack">
              <button type="button" className="secondary" onClick={() => setViewId(row.id)}>
                View
              </button>
              <StatusActions row={row} token={token} onDone={() => void load().catch((err) => setError(errorText(err)))} />
            </div>
          )}
        />
      )}
    </div>
    {viewId !== null && settings && (
      <ReservationDetail
        id={viewId}
        timeZone={settings.timezone}
        onClose={() => setViewId(null)}
        onDeleted={() => {
          setViewId(null)
          void load().catch((err) => setError(errorText(err)))
        }}
      />
    )}
    </div>
  )
}

function SeatsPanel() {
  const { token } = useAuth()
  const [seats, setSeats] = useState<Seat[]>([])
  const [editing, setEditing] = useState<Seat | null>(null)
  const [seatNumber, setSeatNumber] = useState("")
  const [capacity, setCapacity] = useState(2)
  const [description, setDescription] = useState("")
  const [isActive, setIsActive] = useState(true)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [viewing, setViewing] = useState<Seat | null>(null)
  const [deleteId, setDeleteId] = useState<number | null>(null)

  async function load() {
    if (!token) return
    setSeats(await api<Seat[]>("/seats?include_inactive=true", {}, token))
  }

  async function view(id: number) {
    if (!token) return
    setError("")
    setNotice("")
    try {
      setViewing(await api<Seat>(`/seats/${id}`, {}, token))
    } catch (err) {
      setError(errorText(err))
    }
  }

  async function remove(id: number) {
    if (!token) return
    setError("")
    try {
      await api(`/seats/${id}`, { method: "DELETE" }, token)
      if (editing?.id === id) reset()
      if (viewing?.id === id) setViewing(null)
      setDeleteId(null)
      setNotice("Seat deleted.")
      await load()
    } catch (err) {
      setError(errorText(err))
    }
  }

  useEffect(() => {
    load().catch((err) => setError(errorText(err)))
  }, [token])

  function edit(seat: Seat) {
    setEditing(seat)
    setSeatNumber(seat.seat_number)
    setCapacity(seat.capacity)
    setDescription(seat.description ?? "")
    setIsActive(seat.is_active)
    setError("")
    setNotice("")
  }

  function reset() {
    setEditing(null)
    setSeatNumber("")
    setCapacity(2)
    setDescription("")
    setIsActive(true)
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!token) return
    setError("")
    try {
      const payload = { seat_number: seatNumber, capacity, description, is_active: isActive }
      if (editing) {
        await api(`/seats/${editing.id}`, { method: "PATCH", body: JSON.stringify(payload) }, token)
        setNotice("Seat updated.")
      } else {
        await api("/seats", { method: "POST", body: JSON.stringify(payload) }, token)
        setNotice("Seat added.")
      }
      reset()
      await load()
    } catch (err) {
      setError(errorText(err))
    }
  }

  return (
    <div className="card stack">
      <h1>Seats</h1>
      {notice && <p className="ok">{notice}</p>}
      {error && <p className="error">{error}</p>}
      <form className="stack" onSubmit={onSubmit}>
        <div className="filters">
          <label>
            Seat number
            <input value={seatNumber} onChange={(e) => setSeatNumber(e.target.value)} required maxLength={20} />
          </label>
          <label>
            Capacity
            <input type="number" min={1} max={20} value={capacity} onChange={(e) => setCapacity(Number(e.target.value))} required />
          </label>
          <label>
            Description
            <input value={description} onChange={(e) => setDescription(e.target.value)} maxLength={200} />
          </label>
        </div>
        <label className="choice">
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
          Active for new bookings
        </label>
        <div className="row">
          <button type="submit">{editing ? "Save seat" : "Add seat"}</button>
          {editing && (
            <button type="button" className="secondary" onClick={reset}>
              Cancel edit
            </button>
          )}
        </div>
      </form>
      {viewing && (
        <dl className="profile">
          <div>
            <dt>Seat</dt>
            <dd>{viewing.seat_number}</dd>
          </div>
          <div>
            <dt>Capacity</dt>
            <dd>{viewing.capacity}</dd>
          </div>
          <div>
            <dt>Description</dt>
            <dd>{viewing.description || "None"}</dd>
          </div>
          <div>
            <dt>Active</dt>
            <dd>{viewing.is_active ? "Yes" : "No"}</dd>
          </div>
        </dl>
      )}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Seat</th>
              <th>Capacity</th>
              <th>Description</th>
              <th>Active</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {seats.map((seat) => (
              <tr key={seat.id}>
                <td>{seat.seat_number}</td>
                <td>{seat.capacity}</td>
                <td>{seat.description}</td>
                <td>{seat.is_active ? "Yes" : "No"}</td>
                <td>
                  <div className="action-stack">
                    <button type="button" className="secondary" onClick={() => void view(seat.id)}>
                      View
                    </button>
                    <button type="button" className="secondary" onClick={() => edit(seat)}>
                      Edit
                    </button>
                    {deleteId === seat.id ? (
                      <>
                        <button type="button" className="danger" onClick={() => void remove(seat.id)}>
                          Confirm delete
                        </button>
                        <button type="button" className="secondary" onClick={() => setDeleteId(null)}>
                          Keep
                        </button>
                      </>
                    ) : (
                      <button type="button" className="danger" onClick={() => setDeleteId(seat.id)}>
                        Delete
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function StaffPanel() {
  const { token } = useAuth()
  const [staff, setStaff] = useState<User[]>([])
  const [editing, setEditing] = useState<User | null>(null)
  const [fullName, setFullName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [isActive, setIsActive] = useState(true)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [viewing, setViewing] = useState<User | null>(null)
  const [deleteId, setDeleteId] = useState<number | null>(null)

  async function load() {
    if (!token) return
    setStaff(await api<User[]>("/staff", {}, token))
  }

  async function view(id: number) {
    if (!token) return
    setError("")
    setNotice("")
    try {
      setViewing(await api<User>(`/staff/${id}`, {}, token))
    } catch (err) {
      setError(errorText(err))
    }
  }

  async function remove(id: number) {
    if (!token) return
    setError("")
    try {
      await api(`/staff/${id}`, { method: "DELETE" }, token)
      if (editing?.id === id) reset()
      if (viewing?.id === id) setViewing(null)
      setDeleteId(null)
      setNotice("Staff account deleted.")
      await load()
    } catch (err) {
      setError(errorText(err))
    }
  }

  useEffect(() => {
    load().catch((err) => setError(errorText(err)))
  }, [token])

  function reset() {
    setEditing(null)
    setFullName("")
    setEmail("")
    setPassword("")
    setIsActive(true)
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!token) return
    setError("")
    try {
      if (editing) {
        const payload: { full_name: string; is_active: boolean; password?: string } = {
          full_name: fullName,
          is_active: isActive,
        }
        if (password) payload.password = password
        await api(`/staff/${editing.id}`, { method: "PATCH", body: JSON.stringify(payload) }, token)
        setNotice("Staff account updated.")
      } else {
        await api(
          "/staff",
          { method: "POST", body: JSON.stringify({ full_name: fullName, email, password }) },
          token,
        )
        setNotice("Staff account created.")
      }
      reset()
      await load()
    } catch (err) {
      setError(errorText(err))
    }
  }

  return (
    <div className="card stack">
      <h1>Staff accounts</h1>
      <p className="help">Managers can create staff accounts. Manager accounts cannot be created here.</p>
      {notice && <p className="ok">{notice}</p>}
      {error && <p className="error">{error}</p>}
      <form className="stack" onSubmit={onSubmit}>
        <div className="filters">
          <label>
            Full name
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} required minLength={2} />
          </label>
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required disabled={editing !== null} />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required={!editing}
              minLength={editing && !password ? undefined : 8}
              placeholder={editing ? "Leave blank to keep the current password" : ""}
            />
          </label>
        </div>
        {editing && (
          <label className="choice">
            <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
            Active
          </label>
        )}
        <div className="row">
          <button type="submit">{editing ? "Save staff account" : "Create staff account"}</button>
          {editing && (
            <button type="button" className="secondary" onClick={reset}>
              Cancel edit
            </button>
          )}
        </div>
      </form>
      {viewing && (
        <dl className="profile">
          <div>
            <dt>Name</dt>
            <dd>{viewing.full_name}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{viewing.email}</dd>
          </div>
          <div>
            <dt>Role</dt>
            <dd>{viewing.role}</dd>
          </div>
          <div>
            <dt>Active</dt>
            <dd>{viewing.is_active ? "Yes" : "No"}</dd>
          </div>
        </dl>
      )}
      {staff.length === 0 && <p className="empty">No staff accounts yet.</p>}
      {staff.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Active</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {staff.map((member) => (
                <tr key={member.id}>
                  <td>{member.full_name}</td>
                  <td>{member.email}</td>
                  <td>{member.is_active ? "Yes" : "No"}</td>
                  <td>
                    <div className="action-stack">
                      <button type="button" className="secondary" onClick={() => void view(member.id)}>
                        View
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => {
                          setEditing(member)
                          setFullName(member.full_name)
                          setEmail(member.email)
                          setPassword("")
                          setIsActive(member.is_active)
                        }}
                      >
                        Edit
                      </button>
                      {deleteId === member.id ? (
                        <>
                          <button type="button" className="danger" onClick={() => void remove(member.id)}>
                            Confirm delete
                          </button>
                          <button type="button" className="secondary" onClick={() => setDeleteId(null)}>
                            Keep
                          </button>
                        </>
                      ) : (
                        <button type="button" className="danger" onClick={() => setDeleteId(member.id)}>
                          Delete
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function SettingsPanel() {
  const { token } = useAuth()
  const [form, setForm] = useState<RestaurantSettings | null>(null)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")

  useEffect(() => {
    if (!token) return
    api<RestaurantSettings>("/settings", {}, token)
      .then(setForm)
      .catch((err) => setError(errorText(err)))
  }, [token])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!token || !form) return
    setError("")
    setNotice("")
    try {
      const saved = await api<RestaurantSettings>("/settings", { method: "PUT", body: JSON.stringify(form) }, token)
      setForm(saved)
      setNotice("Booking rules saved. They apply to new reservations.")
    } catch (err) {
      setError(errorText(err))
    }
  }

  if (!form) return <p className="muted">{error || "Loading settings…"}</p>

  function set<K extends keyof RestaurantSettings>(key: K, value: RestaurantSettings[K]) {
    setForm((current) => (current ? { ...current, [key]: value } : current))
  }

  return (
    <form className="card stack" onSubmit={onSubmit}>
      <h1>Hours and booking rules</h1>
      <div className="filters">
        <label>
          Opens
          <input type="time" value={form.open_time} onChange={(e) => set("open_time", e.target.value)} required />
        </label>
        <label>
          Closes
          <input type="time" value={form.close_time} onChange={(e) => set("close_time", e.target.value)} required />
        </label>
        <label>
          Duration (minutes)
          <input
            type="number"
            min={30}
            max={300}
            value={form.duration_minutes}
            onChange={(e) => set("duration_minutes", Number(e.target.value))}
            required
          />
        </label>
        <label>
          Slot interval
          <select
            value={form.slot_interval_minutes}
            onChange={(e) => set("slot_interval_minutes", Number(e.target.value))}
          >
            <option value={15}>15 minutes</option>
            <option value={30}>30 minutes</option>
            <option value={60}>60 minutes</option>
          </select>
        </label>
        <label>
          Lead time (minutes)
          <input
            type="number"
            min={0}
            value={form.min_lead_minutes}
            onChange={(e) => set("min_lead_minutes", Number(e.target.value))}
            required
          />
        </label>
        <label>
          Advance window (days)
          <input
            type="number"
            min={1}
            max={365}
            value={form.advance_days}
            onChange={(e) => set("advance_days", Number(e.target.value))}
            required
          />
        </label>
        <label>
          Change cutoff (minutes)
          <input
            type="number"
            min={0}
            value={form.change_cutoff_minutes}
            onChange={(e) => set("change_cutoff_minutes", Number(e.target.value))}
            required
          />
        </label>
        <label>
          Time zone
          <input value={form.timezone} onChange={(e) => set("timezone", e.target.value)} required />
        </label>
      </div>
      <p className="help">Example time zone: Asia/Dhaka. New rules apply to later bookings and do not change old ones.</p>
      {notice && <p className="ok">{notice}</p>}
      {error && <p className="error">{error}</p>}
      <button type="submit">Save rules</button>
    </form>
  )
}

function SummaryPanel() {
  const { token } = useAuth()
  const [dateFrom, setDateFrom] = useState(calendarDate("Asia/Dhaka"))
  const [dateTo, setDateTo] = useState(shiftDate(calendarDate("Asia/Dhaka"), 7))
  const [summary, setSummary] = useState<Summary | null>(null)
  const [error, setError] = useState("")

  async function load(event?: FormEvent) {
    event?.preventDefault()
    if (!token) return
    setError("")
    try {
      const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo })
      setSummary(await api<Summary>(`/reports/summary?${params}`, {}, token))
    } catch (err) {
      setError(errorText(err))
    }
  }

  useEffect(() => {
    load().catch((err) => setError(errorText(err)))
  }, [token])

  const counts: Status[] = ["confirmed", "seated", "completed", "cancelled"]

  return (
    <div className="card stack">
      <h1>Booking summary</h1>
      <form className="filters" onSubmit={load}>
        <label>
          From
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} required />
        </label>
        <label>
          To
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} required />
        </label>
        <button type="submit">Show summary</button>
      </form>
      {error && <p className="error">{error}</p>}
      {summary && (
        <div className="stat-grid">
          <article>
            <strong>{summary.total}</strong>
            <span>Total</span>
          </article>
          {counts.map((status) => (
            <article key={status}>
              <strong>{summary.by_status[status] ?? 0}</strong>
              <span>{status}</span>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
