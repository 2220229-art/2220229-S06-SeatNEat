import { type FormEvent, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { api, errorText } from "../api"
import { useAuth } from "../auth"
import { ALLERGY_NOTICE, calendarDate, foodLabel, formatWhen, shiftDate, timeSlots } from "../format"
import type { AllergyDeclaration, AvailableSeat, FoodPreference, Reservation, RestaurantSettings } from "../types"

export function BookPage() {
  const { token } = useAuth()
  const [settings, setSettings] = useState<RestaurantSettings | null>(null)
  const [date, setDate] = useState("")
  const [startTime, setStartTime] = useState("18:00")
  const [partySize, setPartySize] = useState(2)
  const [seats, setSeats] = useState<AvailableSeat[]>([])
  const [searched, setSearched] = useState(false)
  const [seatId, setSeatId] = useState<number | null>(null)
  const [food, setFood] = useState<FoodPreference>("vegetarian")
  const [allergy, setAllergy] = useState<AllergyDeclaration>("none")
  const [allergyDetails, setAllergyDetails] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [confirmation, setConfirmation] = useState<Reservation | null>(null)

  useEffect(() => {
    if (!token) return
    api<RestaurantSettings>("/settings", {}, token)
      .then((loaded) => {
        setSettings(loaded)
        const tomorrow = calendarDate(loaded.timezone, 1)
        setDate(tomorrow)
        const slots = timeSlots(loaded)
        setStartTime(slots.includes("18:00") ? "18:00" : slots[0] ?? "18:00")
      })
      .catch((err) => setError(errorText(err)))
  }, [token])

  function clearResults() {
    setSeats([])
    setSearched(false)
    setSeatId(null)
    setConfirmation(null)
  }

  async function search(event?: FormEvent) {
    event?.preventDefault()
    if (!token || !settings) return
    setBusy(true)
    setError("")
    setConfirmation(null)
    try {
      const params = new URLSearchParams({
        date,
        start_time: startTime,
        party_size: String(partySize),
      })
      const found = await api<AvailableSeat[]>(`/seats/availability?${params}`, {}, token)
      setSeats(found)
      setSearched(true)
      setSeatId(found[0]?.id ?? null)
    } catch (err) {
      setSeats([])
      setSearched(false)
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  async function reserve(event: FormEvent) {
    event.preventDefault()
    if (!token || seatId === null) return
    setBusy(true)
    setError("")
    try {
      const saved = await api<Reservation>(
        "/reservations",
        {
          method: "POST",
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
      setConfirmation(saved)
      setSeats([])
      setSearched(false)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  if (!settings) return <p className="muted">{error || "Loading restaurant hours…"}</p>

  const slots = timeSlots(settings)
  const selected = seats.find((seat) => seat.id === seatId)
  const maxDate = shiftDate(calendarDate(settings.timezone), settings.advance_days)

  return (
    <section className="stack-page">
      <div className="card">
        <h1>Book a seat</h1>
        <p className="help">
          Open {settings.open_time}–{settings.close_time}. A booking lasts {settings.duration_minutes} minutes. Book at
          least {settings.min_lead_minutes} minutes ahead, and change or cancel up to {settings.change_cutoff_minutes}{" "}
          minutes before the start.
        </p>
        <form className="filters" onSubmit={search}>
          <label>
            Date
            <input
              type="date"
              value={date}
              min={calendarDate(settings.timezone)}
              max={maxDate}
              onChange={(e) => {
                setDate(e.target.value)
                clearResults()
              }}
              required
            />
          </label>
          <label>
            Start time
            <select
              value={startTime}
              onChange={(e) => {
                setStartTime(e.target.value)
                clearResults()
              }}
            >
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
              onChange={(e) => {
                setPartySize(Number(e.target.value))
                clearResults()
              }}
              required
            />
          </label>
          <button type="submit" disabled={busy}>
            {busy ? "Checking…" : "Check seats"}
          </button>
        </form>
      </div>

      {searched && seats.length === 0 && <p className="empty">No seats are free for that time. Try another slot.</p>}

      {seats.length > 0 && (
        <form className="card stack" onSubmit={reserve}>
          <h2>Choose a seat</h2>
          <div className="seat-grid">
            {seats.map((seat) => (
              <button
                key={seat.id}
                type="button"
                className={seat.id === seatId ? "seat selected" : "seat"}
                onClick={() => setSeatId(seat.id)}
              >
                <strong>Seat {seat.seat_number}</strong>
                <span>Up to {seat.capacity} guests</span>
                {seat.description && <span>{seat.description}</span>}
              </button>
            ))}
          </div>
          <fieldset>
            <legend>Food preference</legend>
            <label className="choice">
              <input type="radio" name="food" checked={food === "vegetarian"} onChange={() => setFood("vegetarian")} />
              Vegetarian
            </label>
            <label className="choice">
              <input
                type="radio"
                name="food"
                checked={food === "non_vegetarian"}
                onChange={() => setFood("non_vegetarian")}
              />
              Non-vegetarian
            </label>
          </fieldset>
          <fieldset>
            <legend>Allergies</legend>
            <label className="choice">
              <input type="radio" name="allergy" checked={allergy === "none"} onChange={() => setAllergy("none")} />
              No known allergies
            </label>
            <label className="choice">
              <input
                type="radio"
                name="allergy"
                checked={allergy === "specified"}
                onChange={() => setAllergy("specified")}
              />
              Allergies specified
            </label>
            {allergy === "specified" && (
              <label>
                Allergy details
                <textarea
                  value={allergyDetails}
                  onChange={(e) => setAllergyDetails(e.target.value)}
                  maxLength={300}
                  required
                />
              </label>
            )}
            <p className="help">{ALLERGY_NOTICE}</p>
          </fieldset>
          {selected && (
            <p>
              You are booking seat {selected.seat_number} for {partySize} on {date} at {startTime}. Food:{" "}
              {foodLabel(food)}.
            </p>
          )}
          {error && <p className="error">{error}</p>}
          <button type="submit" disabled={busy || seatId === null}>
            {busy ? "Booking…" : "Confirm reservation"}
          </button>
        </form>
      )}

      {!seats.length && error && <p className="error">{error}</p>}

      {confirmation && settings && (
        <div className="card ok-panel">
          <h2>Reservation confirmed</h2>
          <p>
            Seat {confirmation.seat_number} is booked for {confirmation.party_size} from{" "}
            {formatWhen(confirmation.start_at, settings.timezone)} until {formatWhen(confirmation.end_at, settings.timezone)}.
          </p>
          <p>
            <Link to="/reservations">View my reservations</Link>
          </p>
        </div>
      )}
    </section>
  )
}
