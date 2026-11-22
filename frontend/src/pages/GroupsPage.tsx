import { type FormEvent, useEffect, useState } from "react"
import { api, errorText } from "../api"
import { useAuth } from "../auth"

type Member = {
  user_id: number
  full_name: string
  email: string
  can_create: boolean
  can_update: boolean
  can_assign: boolean
}

type DiningGroup = {
  id: number
  name: string
  owner_id: number
  owner_name: string
  is_owner: boolean
  members: Member[]
}

export function GroupsPage() {
  const { token } = useAuth()
  const [groups, setGroups] = useState<DiningGroup[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [canCreate, setCanCreate] = useState(false)
  const [canUpdate, setCanUpdate] = useState(false)
  const [canAssign, setCanAssign] = useState(false)
  const [error, setError] = useState("")

  const group = groups.find((item) => item.id === selected) ?? null

  function load() {
    if (!token) return
    api<DiningGroup[]>("/groups", {}, token)
      .then((rows) => {
        setGroups(rows)
        setSelected((current) => current ?? rows[0]?.id ?? null)
      })
      .catch((err) => setError(errorText(err)))
  }

  useEffect(() => {
    load()
    // Reload when the signed-in account changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function createGroup(event: FormEvent) {
    event.preventDefault()
    setError("")
    try {
      const created = await api<DiningGroup>("/groups", { method: "POST", body: JSON.stringify({ name }) }, token)
      setName("")
      setGroups((rows) => [created, ...rows])
      setSelected(created.id)
    } catch (err) {
      setError(errorText(err))
    }
  }

  async function rename(event: FormEvent) {
    event.preventDefault()
    if (!group) return
    setError("")
    try {
      const updated = await api<DiningGroup>(
        `/groups/${group.id}`,
        { method: "PATCH", body: JSON.stringify({ name: group.name }) },
        token,
      )
      setGroups((rows) => rows.map((item) => (item.id === updated.id ? updated : item)))
    } catch (err) {
      setError(errorText(err))
    }
  }

  async function removeGroup() {
    if (!group) return
    setError("")
    try {
      await api(`/groups/${group.id}`, { method: "DELETE" }, token)
      setGroups((rows) => rows.filter((item) => item.id !== group.id))
      setSelected(null)
    } catch (err) {
      setError(errorText(err))
    }
  }

  async function addMember(event: FormEvent) {
    event.preventDefault()
    if (!group) return
    setError("")
    try {
      const updated = await api<DiningGroup>(
        `/groups/${group.id}/members`,
        {
          method: "POST",
          body: JSON.stringify({
            email,
            can_create: canCreate,
            can_update: canUpdate,
            can_assign: canAssign,
          }),
        },
        token,
      )
      setEmail("")
      setGroups((rows) => rows.map((item) => (item.id === updated.id ? updated : item)))
    } catch (err) {
      setError(errorText(err))
    }
  }

  async function removeMember(userId: number) {
    if (!group) return
    setError("")
    try {
      await api(`/groups/${group.id}/members/${userId}`, { method: "DELETE" }, token)
      load()
    } catch (err) {
      setError(errorText(err))
    }
  }

  return (
    <section className="stack-page">
      <article className="card">
        <h1>Dining groups</h1>
        <p className="muted">The owner can rename the group, delete it, and choose what each member may do.</p>
        {error && <p className="error">{error}</p>}
        <form className="row" onSubmit={createGroup}>
          <label>
            New group
            <input value={name} onChange={(event) => setName(event.target.value)} required minLength={2} />
          </label>
          <button type="submit">Create group</button>
        </form>
      </article>
      <article className="card">
        {groups.length === 0 && <p className="empty">You are not in a group yet.</p>}
        <div className="tabs">
          {groups.map((item) => (
            <button
              key={item.id}
              type="button"
              className={item.id === selected ? "" : "secondary"}
              onClick={() => setSelected(item.id)}
            >
              {item.name}
            </button>
          ))}
        </div>
        {group && (
          <>
            <p>
              Owner: {group.owner_name}
              {group.is_owner ? " (you)" : ""}
            </p>
            {group.is_owner && (
              <form className="row" onSubmit={rename}>
                <label>
                  Group name
                  <input
                    value={group.name}
                    onChange={(event) =>
                      setGroups((rows) =>
                        rows.map((item) => (item.id === group.id ? { ...item, name: event.target.value } : item)),
                      )
                    }
                  />
                </label>
                <button type="submit">Rename</button>
                <button type="button" className="danger" onClick={() => void removeGroup()}>
                  Delete group
                </button>
              </form>
            )}
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Member</th>
                    <th>Create</th>
                    <th>Update</th>
                    <th>Assign seat</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {group.members.map((member) => (
                    <tr key={member.user_id}>
                      <td>
                        {member.full_name}
                        <div className="muted">{member.email}</div>
                      </td>
                      <td>{member.can_create ? "Yes" : "No"}</td>
                      <td>{member.can_update ? "Yes" : "No"}</td>
                      <td>{member.can_assign ? "Yes" : "No"}</td>
                      <td>
                        {group.is_owner && (
                          <button type="button" className="secondary" onClick={() => void removeMember(member.user_id)}>
                            Remove
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {group.is_owner && (
              <form className="stack" onSubmit={addMember}>
                <h2>Add a member</h2>
                <label>
                  Email
                  <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
                </label>
                <label className="choice">
                  <input type="checkbox" checked={canCreate} onChange={(event) => setCanCreate(event.target.checked)} />
                  Can create a booking
                </label>
                <label className="choice">
                  <input type="checkbox" checked={canUpdate} onChange={(event) => setCanUpdate(event.target.checked)} />
                  Can update a booking
                </label>
                <label className="choice">
                  <input type="checkbox" checked={canAssign} onChange={(event) => setCanAssign(event.target.checked)} />
                  Can assign a seat
                </label>
                <button type="submit">Add member</button>
              </form>
            )}
          </>
        )}
      </article>
    </section>
  )
}
