export type Role = "customer" | "staff" | "manager"
export type Status = "confirmed" | "seated" | "completed" | "cancelled"
export type FoodPreference = "vegetarian" | "non_vegetarian"
export type AllergyDeclaration = "none" | "specified"

export type User = {
  id: number
  full_name: string
  email: string
  role: Role
  is_active: boolean
}

export type Seat = {
  id: number
  seat_number: string
  capacity: number
  description: string | null
  is_active: boolean
}

export type AvailableSeat = {
  id: number
  seat_number: string
  capacity: number
  description: string | null
  available: boolean
}

export type Reservation = {
  id: number
  customer_id: number
  customer_name: string
  seat_id: number
  seat_number: string
  start_at: string
  end_at: string
  party_size: number
  food_preference: FoodPreference
  allergy_declaration: AllergyDeclaration
  allergy_details: string | null
  status: Status
}

export type RestaurantSettings = {
  open_time: string
  close_time: string
  duration_minutes: number
  slot_interval_minutes: number
  min_lead_minutes: number
  advance_days: number
  change_cutoff_minutes: number
  timezone: string
}

export type Summary = {
  date_from: string
  date_to: string
  total: number
  by_status: Record<Status, number>
}

export type LoginResult = {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}
