import { Link } from "react-router-dom"

export function LandingPage() {
  return (
    <section className="stack-page">
      <div className="hero card">
        <h1>Reserve a seat without calling the restaurant.</h1>
        <p>
          SitNeat is a seat reservation system for one restaurant. Customers check which seats are free, book a time,
          and tell the kitchen their food preference and any allergies. Staff run the service from today’s list, and
          the manager looks after seats and staff accounts.
        </p>
        <div className="row">
          <Link className="button" to="/register">
            Create a customer account
          </Link>
          <Link className="button secondary" to="/login">
            Log in
          </Link>
        </div>
      </div>
      <div className="role-grid">
        <article className="card">
          <h2>Customer</h2>
          <p>Register, search open seats, book, and change or cancel your own reservation before the cutoff.</p>
        </article>
        <article className="card">
          <h2>Restaurant staff</h2>
          <p>See who is coming today, read food and allergy notes, and mark guests seated or completed.</p>
        </article>
        <article className="card">
          <h2>Restaurant manager</h2>
          <p>Manage seats, create staff accounts, set opening hours and booking rules, and review reservations.</p>
        </article>
      </div>
    </section>
  )
}
