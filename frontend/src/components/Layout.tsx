import { Link, NavLink, Outlet } from "react-router-dom"
import { useAuth } from "../auth"
import { roleLabel } from "../format"

export function Layout() {
  const { user, logout } = useAuth()

  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">
          SitNeat <span>Reservations</span>
        </Link>
        <nav>
          {!user && (
            <>
              <NavLink to="/login">Log in</NavLink>
              <NavLink to="/register">Register</NavLink>
            </>
          )}
          {user?.role === "customer" && (
            <>
              <NavLink to="/book">Book a seat</NavLink>
              <NavLink to="/reservations">My reservations</NavLink>
            </>
          )}
          {user?.role === "staff" && <NavLink to="/today">Today</NavLink>}
          {user?.role === "manager" && <NavLink to="/manage">Dashboard</NavLink>}
          {user && <NavLink to="/profile">Profile</NavLink>}
          {user && (
            <button type="button" className="secondary" onClick={logout}>
              Log out
            </button>
          )}
        </nav>
      </header>
      <main className="wrap">
        {user && (
          <p className="who">
            {user.full_name} · {roleLabel(user.role)}
          </p>
        )}
        <Outlet />
      </main>
    </>
  )
}
