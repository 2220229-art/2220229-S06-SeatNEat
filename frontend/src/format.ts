import type { FoodPreference, RestaurantSettings, Status } from "./types"

export const ALLERGY_NOTICE =
  "Allergy information is customer-declared and does not guarantee allergen-free food."

export function foodLabel(value: FoodPreference) {
  return value === "vegetarian" ? "Vegetarian" : "Non-vegetarian"
}

export function statusLabel(value: Status) {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

export function roleLabel(value: string) {
  if (value === "customer") return "Customer"
  if (value === "staff") return "Restaurant staff"
  return "Restaurant manager"
}

export function formatWhen(iso: string, timeZone: string) {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone,
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso))
}

export function zonedParts(iso: string, timeZone: string) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso))
  const read = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? ""
  return {
    date: `${read("year")}-${read("month")}-${read("day")}`,
    time: `${read("hour")}:${read("minute")}`,
  }
}

export function calendarDate(timeZone: string, offsetDays = 0) {
  const now = new Date()
  const shifted = new Date(now.getTime() + offsetDays * 24 * 60 * 60 * 1000)
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(shifted)
}

export function shiftDate(isoDate: string, days: number) {
  const [year, month, day] = isoDate.split("-").map(Number)
  const next = new Date(Date.UTC(year, month - 1, day + days))
  return next.toISOString().slice(0, 10)
}

export function timeSlots(settings: RestaurantSettings) {
  const [openHour, openMinute] = settings.open_time.split(":").map(Number)
  const [closeHour, closeMinute] = settings.close_time.split(":").map(Number)
  const open = openHour * 60 + openMinute
  const close = closeHour * 60 + closeMinute
  const slots: string[] = []
  for (let minute = open; minute + settings.duration_minutes <= close; minute += settings.slot_interval_minutes) {
    const hour = Math.floor(minute / 60)
    const mins = minute % 60
    slots.push(`${String(hour).padStart(2, "0")}:${String(mins).padStart(2, "0")}`)
  }
  return slots
}

export function canCustomerChange(startAt: string, settings: RestaurantSettings, status: Status) {
  if (status !== "confirmed") return false
  const cutoff = new Date(startAt).getTime() - settings.change_cutoff_minutes * 60 * 1000
  return Date.now() <= cutoff
}
