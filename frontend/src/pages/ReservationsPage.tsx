import { type FormEvent, useEffect, useState } from "react"
import { api, errorText } from "../api"
import { useAuth } from "../auth"
import { ReservationDetail } from "../components/ReservationDetail"
import { ReservationTable } from "../components/ReservationTable"
import { ALLERGY_NOTICE, canCustomerChange, timeSlots, zonedParts } from "../format"
import type { AllergyDeclaration, AvailableSeat, FoodPreference, Reservation, RestaurantSettings } from "../types"

export function ReservationsPage() {
  const { token } = useAuth()
  const [settings, setSettings] = useState<RestaurantSettings | null>(null)
  const [rows, setRows] = useState<Reservation[]>([])
  const [editing, setEditing] = useState<Reservation | null>(null)
  const [date, setDate] = useState("")
  const [startTime, setStartTime] = useState("18:00")
  const [partySize, setPartySize] = useState(2)
  const [seatId, setSeatId] = useState<number | null>(null)
  const [seats, setSeats] = useState<AvailableSeat[]>([])
  const [food, setFood] = useState<FoodPreference>("vegetarian")
  const [allergy, setAllergy] = useState<AllergyDeclaration>("none")
  const [allergyDetails, setAllergyDetails] = useState("")
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [busy, setBusy] = useState(false)
  const [confirmId, setConfirmId] = useState<number | null>(null)
  const [viewId, setViewId] = useState<number | null>(null)

  async function load() {
    if (!token) return
    const [loadedSettings, mine] = await Promise.all([
      api<RestaurantSettings>("/settings", {}, token),
      api<Reservation[]>("/reservations/mine", {}, token),
    ])
    setSettings(loadedSettings)
    setRows(mine)
  }

  useEffect(() => {
    if (!token) return
    load().catch((err) => setError(errorText(err)))
  }, [token])

  function beginEdit(row: Reservation) {
    if (!settings || !token) return
    setEditing(row)
    setError("")
    setNotice("")
    const when = zonedParts(row.start_at, settings.timezone)
    setDate(when.date)
    setStartTime(when.time)
    setPartySize(row.party_size)
    setSeatId(row.seat_id)
    setFood(row.food_preference)
    setAllergy(row.allergy_declaration)
    setAllergyDetails(row.allergy_details ?? "")
    const params = new URLSearchParams({
      date: when.date,
      start_time: when.time,
      party_size: String(row.party_size),
      exclude_reservation_id: String(row.id),
    })
    api<AvailableSeat[]>(`/seats/availability?${params}`, {}, token)
      .then(setSeats)
      .catch((err) => setError(errorText(err)))
  }

  async function refreshSeats() {
    if (!token || !editing) return
    setBusy(true)
    setError("")
    try {
      const params = new URLSearchParams({
        date,
        start_time: startTime,
        party_size: String(partySize),
        exclude_reservation_id: String(editing.id),
      })
      const found = await api<AvailableSeat[]>(`/seats/availability?${params}`, {}, token)
      setSeats(found)
      setSeatId(found.some((seat) => seat.id === seatId) ? seatId : (found[0]?.id ?? null))
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  async function saveEdit(event: FormEvent) {
    event.preventDefault()
    if (!token || !editing || seatId === null) return
    setBusy(true)
    setError("")
    try {
      await api(
        `/reservations/${editing.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            seat_id: seatId,
            date,
            start_time: startTime,
            party_size: partySize,
            food_preference: food,
            allergy_declaration: allergy,
            allergy_details: allergy === "specified" ? allergyDetails : null,
          }),
        },
        token,
      )
      setEditing(null)
      setNotice("Reservation updated.")
      await load()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  async function cancel(id: number) {
    if (!token) return
    setBusy(true)
    setError("")
    try {
      await api(`/reservations/${id}/cancel`, { method: "POST" }, token)
      setConfirmId(null)
      setNotice("Reservation cancelled.")
      await load()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const slots = settings ? timeSlots(settings) : []

  return (
    <section className="stack-page">
      <div className="card">
        <h1>My reservations</h1>
        {notice && <p className="ok">{notice}</p>}
        {error && !editing && <p className="error">{error}</p>}
        {settings && (
          <ReservationTable
            rows={rows}
            timeZone={settings.timezone}
            emptyText="You have no reservations yet."
            actions={(row) =>
              <div className="action-stack">
                <button type="button" className="secondary" onClick={() => setViewId(row.id)}>
                  View
                </button>
                {settings && canCustomerChange(row.start_at, settings, row.status) ? (
                  <>
                  <button type="button" className="secondary" onClick={() => beginEdit(row)}>
                    Change
                  </button>
                  {confirmId === row.id ? (
                    <>
                      <button type="button" className="danger" disabled={busy} onClick={() => void cancel(row.id)}>
                        Confirm cancel
                      </button>
                      <button type="button" className="secondary" onClick={() => setConfirmId(null)}>
                        Keep
                      </button>
                    </>
                  ) : (
                    <button type="button" className="danger" onClick={() => setConfirmId(row.id)}>
                      Cancel
                    </button>
                  )}
                  </>
                ) : null}
              </div>
            }
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
            setEditing(null)
            setNotice("Reservation deleted.")
            void load()
          }}
        />
      )}

      {editing && settings && (
        <form className="card stack" onSubmit={saveEdit}>
          <h2>Change reservation</h2>
          <div className="filters">
            <label>
              Date
              <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
            </label>
            <label>
              Start time
              <select value={startTime} onChange={(e) => setStartTime(e.target.value)}>
                {slots.map((slot) => (
                  <option key={slot} value={slot}>
                    {slot}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Party size
              <input
                type="number"
                min={1}
                max={20}
                value={partySize}
                onChange={(e) => setPartySize(Number(e.target.value))}
                required
              />
            </label>
            <button type="button" className="secondary" disabled={busy} onClick={() => void refreshSeats()}>
              Find seats
            </button>
          </div>
          <label>
            Seat
            <select value={seatId ?? ""} onChange={(e) => setSeatId(Number(e.target.value))} required>
              {seats.length === 0 && <option value="">No free seats for this time</option>}
              {seats.map((seat) => (
                <option key={seat.id} value={seat.id}>
                  {seat.seat_number} · up to {seat.capacity}
                </option>
              ))}
            </select>
          </label>
          <label>
            Food preference
            <select value={food} onChange={(e) => setFood(e.target.value as FoodPreference)}>
              <option value="vegetarian">Vegetarian</option>
              <option value="non_vegetarian">Non-vegetarian</option>
            </select>
          </label>
          <label>
            Allergies
            <select value={allergy} onChange={(e) => setAllergy(e.target.value as AllergyDeclaration)}>
              <option value="none">No known allergies</option>
              <option value="specified">Allergies specified</option>
            </select>
          </label>
          {allergy === "specified" && (
            <label>
              Allergy details
              <textarea value={allergyDetails} onChange={(e) => setAllergyDetails(e.target.value)} maxLength={300} required />
            </label>
          )}
          <p className="help">{ALLERGY_NOTICE}</p>
          {error && <p className="error">{error}</p>}
          <div className="row">
            <button type="submit" disabled={busy || seatId === null}>
              Save changes
            </button>
            <button type="button" className="secondary" onClick={() => setEditing(null)}>
              Close
            </button>
          </div>
        </form>
      )}
    </section>
  )
}
