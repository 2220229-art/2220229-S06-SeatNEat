import { useState } from "react"
import { api, errorText } from "../api"
import type { Reservation } from "../types"

export function StatusActions({
  row,
  token,
  onDone,
}: {
  row: Reservation
  token: string
  onDone: () => void
}) {
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [confirming, setConfirming] = useState(false)

  async function update(status: "seated" | "completed") {
    setBusy(true)
    setError("")
    try {
      await api(`/reservations/${row.id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }, token)
      onDone()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  async function cancel() {
    setBusy(true)
    setError("")
    try {
      await api(`/reservations/${row.id}/cancel`, { method: "POST" }, token)
      setConfirming(false)
      onDone()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  if (row.status !== "confirmed" && row.status !== "seated") return null

  return (
    <div className="action-stack">
      {row.status === "confirmed" && (
        <button type="button" disabled={busy} onClick={() => update("seated")}>
          Mark seated
        </button>
      )}
      {row.status === "seated" && (
        <button type="button" disabled={busy} onClick={() => update("completed")}>
          Mark completed
        </button>
      )}
      {row.status === "confirmed" && !confirming && (
        <button type="button" className="danger" disabled={busy} onClick={() => setConfirming(true)}>
          Cancel
        </button>
      )}
      {confirming && (
        <>
          <button type="button" className="danger" disabled={busy} onClick={cancel}>
            Confirm cancel
          </button>
          <button type="button" className="secondary" disabled={busy} onClick={() => setConfirming(false)}>
            Keep
          </button>
        </>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  )
}
