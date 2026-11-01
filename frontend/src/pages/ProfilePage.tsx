import { useAuth } from "../auth"
import { roleLabel } from "../format"

export function ProfilePage() {
  const { user } = useAuth()
  if (!user) return null
  return (
    <section className="card narrow">
      <h1>Your profile</h1>
      <dl className="profile">
        <div>
          <dt>Name</dt>
          <dd>{user.full_name}</dd>
        </div>
        <div>
          <dt>Email</dt>
          <dd>{user.email}</dd>
        </div>
        <div>
          <dt>Role</dt>
          <dd>{roleLabel(user.role)}</dd>
        </div>
      </dl>
    </section>
  )
}
