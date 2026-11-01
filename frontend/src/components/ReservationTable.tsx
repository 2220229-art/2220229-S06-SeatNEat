import type { ReactNode } from "react"
import { ALLERGY_NOTICE, foodLabel, formatWhen, statusLabel } from "../format"
import type { Reservation } from "../types"

export function ReservationTable({
  rows,
  timeZone,
  showGuest = false,
  emptyText,
  actions,
}: {
  rows: Reservation[]
  timeZone: string
  showGuest?: boolean
  emptyText: string
  actions?: (row: Reservation) => ReactNode
}) {
  if (rows.length === 0) return <p className="empty">{emptyText}</p>
  return (
    <>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>When</th>
              {showGuest && <th>Guest</th>}
              <th>Seat</th>
              <th>Party</th>
              <th>Food</th>
              <th>Allergies</th>
              <th>Status</th>
              {actions && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  {formatWhen(row.start_at, timeZone)}
                  <div className="muted">until {formatWhen(row.end_at, timeZone)}</div>
                </td>
                {showGuest && <td>{row.customer_name}</td>}
                <td>{row.seat_number}</td>
                <td>{row.party_size}</td>
                <td>{foodLabel(row.food_preference)}</td>
                <td>{row.allergy_declaration === "none" ? "No known allergies" : row.allergy_details}</td>
                <td>
                  <span className={`badge ${row.status}`}>{statusLabel(row.status)}</span>
                </td>
                {actions && <td className="actions">{actions(row)}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="help">{ALLERGY_NOTICE}</p>
    </>
  )
}
