import { useEffect, useState } from "react"
import { api, errorText } from "../api"
import { useAuth } from "../auth"
import { ReservationDetail } from "../components/ReservationDetail"
import { ReservationTable } from "../components/ReservationTable"
import { StatusActions } from "../components/StatusActions"
import type { Reservation, RestaurantSettings } from "../types"

export function StaffPage() {
  const { token } = useAuth()
  const [settings, setSettings] = useState<RestaurantSettings | null>(null)
  const [rows, setRows] = useState<Reservation[]>([])
  const [error, setError] = useState("")
  const [viewId, setViewId] = useState<number | null>(null)

  async function load() {
    if (!token) return
    const [loadedSettings, today] = await Promise.all([
      api<RestaurantSettings>("/settings", {}, token),
      api<Reservation[]>("/reservations/today", {}, token),
    ])
    setSettings(loadedSettings)
    setRows(today)
  }

  useEffect(() => {
    if (!token) return
    load().catch((err) => setError(errorText(err)))
  }, [token])

  return (
    <section className="stack-page">
      <div className="card">
        <h1>Today’s reservations</h1>
        <p className="help">Confirmed and seated bookings for the current restaurant day.</p>
        {error && <p className="error">{error}</p>}
        {settings && token && (
          <ReservationTable
            rows={rows}
            timeZone={settings.timezone}
            showGuest
            emptyText="No confirmed or seated bookings for today."
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
        <ReservationDetail id={viewId} timeZone={settings.timezone} onClose={() => setViewId(null)} onDeleted={() => setViewId(null)} />
      )}
    </section>
  )
}
