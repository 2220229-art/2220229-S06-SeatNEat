import { useEffect, useState } from "react"
import { api, errorText } from "../api"
import { useAuth } from "../auth"
import { ALLERGY_NOTICE, foodLabel, formatWhen, statusLabel } from "../format"
import type { Reservation } from "../types"

export function ReservationDetail({
  id,
  timeZone,
  onClose,
  onDeleted,
}: {
  id: number
  timeZone: string
  onClose: () => void
  onDeleted: () => void
}) {
  const { token, user } = useAuth()
  const [row, setRow] = useState<Reservation | null>(null)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const allowDelete = user?.role === "customer" || user?.role === "manager"

  useEffect(() => {
    if (!token) return
    setRow(null)
    setError("")
    setConfirming(false)
    api<Reservation>(`/reservations/${id}`, {}, token)
      .then(setRow)
      .catch((err) => setError(errorText(err)))
  }, [id, token])

  async function remove() {
    if (!token) return
    setBusy(true)
    setError("")
    try {
      await api(`/reservations/${id}`, { method: "DELETE" }, token)
      onDeleted()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card stack">
      <h2>Reservation details</h2>
      {error && <p className="error">{error}</p>}
      {!row && !error && <p className="muted">Loading reservation…</p>}
      {row && (
        <dl className="profile">
          <div>
            <dt>When</dt>
            <dd>
              {formatWhen(row.start_at, timeZone)} until {formatWhen(row.end_at, timeZone)}
            </dd>
          </div>
          <div>
            <dt>Guest</dt>
            <dd>{row.customer_name}</dd>
          </div>
          <div>
            <dt>Seat</dt>
            <dd>{row.seat_number}</dd>
          </div>
          <div>
            <dt>Party</dt>
            <dd>{row.party_size}</dd>
          </div>
          <div>
            <dt>Food</dt>
            <dd>{foodLabel(row.food_preference)}</dd>
          </div>
          <div>
            <dt>Allergies</dt>
            <dd>{row.allergy_declaration === "none" ? "No known allergies" : row.allergy_details}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>
              <span className={`badge ${row.status}`}>{statusLabel(row.status)}</span>
            </dd>
          </div>
        </dl>
      )}
      <p className="help">{ALLERGY_NOTICE}</p>
      {allowDelete && (
        <p className="help">Delete removes this booking permanently. Cancel keeps it in the list as cancelled.</p>
      )}
      <div className="row">
        {allowDelete && !confirming && (
          <button type="button" className="danger" disabled={busy || !row} onClick={() => setConfirming(true)}>
            Delete
          </button>
        )}
        {allowDelete && confirming && (
          <>
            <button type="button" className="danger" disabled={busy} onClick={() => void remove()}>
              Confirm delete
            </button>
            <button type="button" className="secondary" disabled={busy} onClick={() => setConfirming(false)}>
              Keep
            </button>
          </>
        )}
        <button type="button" className="secondary" onClick={onClose}>
          Close
        </button>
      </div>
    </section>
  )
}
