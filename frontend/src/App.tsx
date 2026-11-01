import { Navigate, Route, Routes } from "react-router-dom"
import { homePath, RequireAuth, useAuth } from "./auth"
import { Layout } from "./components/Layout"
import { BookPage } from "./pages/BookPage"
import { LandingPage } from "./pages/LandingPage"
import { LoginPage } from "./pages/LoginPage"
import { ManagerPage } from "./pages/ManagerPage"
import { ProfilePage } from "./pages/ProfilePage"
import { RegisterPage } from "./pages/RegisterPage"
import { ReservationsPage } from "./pages/ReservationsPage"
import { StaffPage } from "./pages/StaffPage"

function Home() {
  const { user, ready } = useAuth()
  if (!ready) return <p className="muted">Loading…</p>
  if (!user) return <LandingPage />
  return <Navigate to={homePath(user.role)} replace />
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/book"
          element={
            <RequireAuth roles={["customer"]}>
              <BookPage />
            </RequireAuth>
          }
        />
        <Route
          path="/reservations"
          element={
            <RequireAuth roles={["customer"]}>
              <ReservationsPage />
            </RequireAuth>
          }
        />
        <Route
          path="/today"
          element={
            <RequireAuth roles={["staff"]}>
              <StaffPage />
            </RequireAuth>
          }
        />
        <Route
          path="/manage"
          element={
            <RequireAuth roles={["manager"]}>
              <ManagerPage />
            </RequireAuth>
          }
        />
        <Route
          path="/profile"
          element={
            <RequireAuth>
              <ProfilePage />
            </RequireAuth>
          }
        />
        <Route
          path="/unauthorized"
          element={
            <section className="card">
              <h1>You cannot open this page</h1>
              <p>Your account does not have access to this area.</p>
            </section>
          }
        />
        <Route
          path="*"
          element={
            <section className="card">
              <h1>Page not found</h1>
              <p>That page is not part of SitNeat.</p>
            </section>
          }
        />
      </Route>
    </Routes>
  )
}
