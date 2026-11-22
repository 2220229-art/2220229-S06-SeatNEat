import csv
import io
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, Security
from pydantic import BaseModel, Field
from sqlmodel import select

from app.access import is_admin, require_admin
from app.deps import SessionDep, get_current_user
from app.errors import AppError
from app.models import AccountRole, AuditLog, DiningGroup, GroupMember, RefreshSession, Reservation, Role, User
from app.request_meta import client_agent, client_ip
from app.schemas import UserPublic
from app.services import audit, user_public
from app.timeutil import to_utc, utc_now

router = APIRouter(prefix="/admin", tags=["admin"])


class Page(BaseModel):
    items: list
    total: int
    offset: int
    limit: int


class RoleChange(BaseModel):
    account_role: str


class BanBody(BaseModel):
    reason: str = Field(min_length=3, max_length=200)


class BulkBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=100)
    reason: str | None = Field(default=None, max_length=200)


def _admin(
    request: Request,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user)],
) -> User:
    require_admin(user)
    return user


AdminUser = Annotated[User, Security(_admin)]


def _page(items: list, total: int, offset: int, limit: int) -> dict:
    return {"items": items, "total": total, "offset": offset, "limit": limit}


def _user_row(user: User) -> dict:
    public = user_public(user).model_dump()
    public["banned_at"] = to_utc(user.banned_at).isoformat() if user.banned_at else None
    public["ban_reason"] = user.ban_reason
    public["failed_attempts"] = user.failed_attempts
    return public


def _filtered_users(session: SessionDep, q: str | None, account_role: str | None, status: str | None) -> list[User]:
    rows = list(session.exec(select(User).order_by(User.id)).all())
    if q:
        needle = q.strip().lower()
        rows = [row for row in rows if needle in row.full_name.lower() or needle in row.email.lower()]
    if account_role in {AccountRole.user.value, AccountRole.admin.value}:
        rows = [row for row in rows if row.account_role == account_role]
    if status == "banned":
        rows = [row for row in rows if row.banned_at is not None or not row.is_active]
    elif status == "active":
        rows = [row for row in rows if row.banned_at is None and row.is_active]
    return rows


def _ban(session: SessionDep, actor: User, target: User, reason: str, request: Request) -> None:
    if target.id == actor.id:
        raise AppError(403, "FORBIDDEN", "You cannot ban your own account.")
    if is_admin(target):
        raise AppError(403, "FORBIDDEN", "An admin cannot ban another admin.")
    target.is_active = False
    target.banned_at = utc_now()
    target.ban_reason = reason.strip()
    target.updated_at = utc_now()
    _revoke_user_sessions(session, target.id or 0)
    ip_address, user_agent = client_ip(request), client_agent(request)
    audit(session, actor.id, "ban", "user", target.id, ip_address, user_agent, target.ban_reason)
    session.add(target)


def _unban(session: SessionDep, actor: User, target: User, request: Request) -> None:
    if is_admin(target) and target.id != actor.id and target.banned_at is None and target.is_active:
        return
    target.is_active = True
    target.banned_at = None
    target.ban_reason = None
    target.failed_attempts = 0
    target.locked_until = None
    target.updated_at = utc_now()
    ip_address, user_agent = client_ip(request), client_agent(request)
    audit(session, actor.id, "unban", "user", target.id, ip_address, user_agent)
    session.add(target)


def _revoke_user_sessions(session: SessionDep, user_id: int) -> None:
    now = utc_now()
    rows = session.exec(select(RefreshSession).where(RefreshSession.user_id == user_id)).all()
    for row in rows:
        if row.revoked_at is None:
            row.revoked_at = now
            session.add(row)


@router.get("/overview")
def overview(session: SessionDep, actor: AdminUser) -> dict:
    del actor
    now = utc_now()
    since = now - timedelta(days=7)
    users = list(session.exec(select(User)).all())
    reservations = list(session.exec(select(Reservation)).all())
    groups = list(session.exec(select(DiningGroup)).all())
    return {
        "users": len(users),
        "banned": sum(1 for row in users if row.banned_at is not None or not row.is_active),
        "records": len(reservations),
        "groups": len(groups),
        "new_users_7_days": sum(1 for row in users if to_utc(row.created_at) >= since),
        "new_records_7_days": sum(1 for row in reservations if to_utc(row.created_at) >= since),
    }


@router.get("/users")
def list_users(
    session: SessionDep,
    actor: AdminUser,
    q: str | None = None,
    account_role: str | None = None,
    status: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    del actor
    rows = _filtered_users(session, q, account_role, status)
    page = rows[offset : offset + limit]
    return _page([_user_row(row) for row in page], len(rows), offset, limit)


@router.get("/users/{user_id}")
def user_detail(user_id: int, session: SessionDep, actor: AdminUser) -> dict:
    del actor
    target = session.get(User, user_id)
    if target is None:
        raise AppError(404, "NOT_FOUND", "That user was not found.")
    reservations = session.exec(select(Reservation).where(Reservation.customer_id == target.id)).all()
    owned = session.exec(select(DiningGroup).where(DiningGroup.owner_id == target.id)).all()
    joined = session.exec(select(GroupMember).where(GroupMember.user_id == target.id)).all()
    sessions = session.exec(select(RefreshSession).where(RefreshSession.user_id == target.id)).all()
    activity = session.exec(
        select(AuditLog).where(AuditLog.actor_id == target.id).order_by(AuditLog.id.desc())
    ).all()[:20]
    return {
        "user": _user_row(target),
        "reservations": len(list(reservations)),
        "groups": len(list(owned)) + len(list(joined)),
        "sessions": [
            {
                "id": row.id,
                "ip_address": row.ip_address,
                "user_agent": row.user_agent,
                "created_at": to_utc(row.created_at).isoformat(),
                "revoked": row.revoked_at is not None,
            }
            for row in sessions
        ],
        "activity": [_activity_row(row) for row in activity],
    }


@router.post("/users/{user_id}/ban")
def ban_user(
    user_id: int,
    data: BanBody,
    request: Request,
    session: SessionDep,
    actor: AdminUser,
) -> UserPublic:
    target = session.get(User, user_id)
    if target is None:
        raise AppError(404, "NOT_FOUND", "That user was not found.")
    _ban(session, actor, target, data.reason, request)
    session.commit()
    session.refresh(target)
    return user_public(target)


@router.post("/users/{user_id}/unban")
def unban_user(user_id: int, request: Request, session: SessionDep, actor: AdminUser) -> UserPublic:
    target = session.get(User, user_id)
    if target is None:
        raise AppError(404, "NOT_FOUND", "That user was not found.")
    _unban(session, actor, target, request)
    session.commit()
    session.refresh(target)
    return user_public(target)


@router.post("/users/{user_id}/role")
def change_role(
    user_id: int,
    data: RoleChange,
    request: Request,
    session: SessionDep,
    actor: AdminUser,
) -> UserPublic:
    if data.account_role not in {AccountRole.user.value, AccountRole.admin.value}:
        raise AppError(422, "VALIDATION_ERROR", "Role must be user or admin.")
    target = session.get(User, user_id)
    if target is None:
        raise AppError(404, "NOT_FOUND", "That user was not found.")
    if target.id == actor.id:
        raise AppError(403, "FORBIDDEN", "You cannot change your own role.")
    target.account_role = data.account_role
    if data.account_role == AccountRole.admin.value:
        target.role = Role.manager.value
    elif target.role == Role.manager.value:
        target.role = Role.customer.value
    target.updated_at = utc_now()
    ip_address, user_agent = client_ip(request), client_agent(request)
    audit(session, actor.id, "role_change", "user", target.id, ip_address, user_agent, data.account_role)
    session.add(target)
    session.commit()
    session.refresh(target)
    return user_public(target)


@router.post("/users/{user_id}/sessions/revoke", status_code=204)
def revoke_sessions(user_id: int, session: SessionDep, actor: AdminUser) -> Response:
    del actor
    target = session.get(User, user_id)
    if target is None:
        raise AppError(404, "NOT_FOUND", "That user was not found.")
    _revoke_user_sessions(session, target.id or 0)
    session.commit()
    return Response(status_code=204)


@router.post("/users/bulk-ban")
def bulk_ban(data: BulkBody, request: Request, session: SessionDep, actor: AdminUser) -> dict:
    reason = (data.reason or "Banned by an administrator.").strip()
    changed = 0
    skipped = 0
    for user_id in data.ids:
        target = session.get(User, user_id)
        if target is None or target.id == actor.id or is_admin(target):
            skipped += 1
            continue
        _ban(session, actor, target, reason, request)
        changed += 1
    session.commit()
    return {"changed": changed, "skipped": skipped}


@router.post("/users/bulk-unban")
def bulk_unban(data: BulkBody, request: Request, session: SessionDep, actor: AdminUser) -> dict:
    changed = 0
    skipped = 0
    for user_id in data.ids:
        target = session.get(User, user_id)
        if target is None:
            skipped += 1
            continue
        _unban(session, actor, target, request)
        changed += 1
    session.commit()
    return {"changed": changed, "skipped": skipped}


@router.get("/records")
def list_records(
    session: SessionDep,
    actor: AdminUser,
    status: str | None = None,
    q: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    del actor
    rows = list(session.exec(select(Reservation).order_by(Reservation.id.desc())).all())
    if status:
        rows = [row for row in rows if row.status == status]
    if q:
        needle = q.strip().lower()
        kept = []
        for row in rows:
            customer = session.get(User, row.customer_id)
            name = customer.full_name.lower() if customer else ""
            email = customer.email.lower() if customer else ""
            if needle in name or needle in email or needle in str(row.id):
                kept.append(row)
        rows = kept
    page = rows[offset : offset + limit]
    items = []
    for row in page:
        customer = session.get(User, row.customer_id)
        items.append(
            {
                "id": row.id,
                "customer_name": customer.full_name if customer else "Unknown",
                "customer_email": customer.email if customer else "",
                "status": row.status,
                "start_at": to_utc(row.start_at).isoformat(),
                "party_size": row.party_size,
                "group_id": row.group_id,
            }
        )
    return _page(items, len(rows), offset, limit)


@router.delete("/records/{record_id}", status_code=204)
def delete_record(record_id: int, request: Request, session: SessionDep, actor: AdminUser) -> Response:
    row = session.get(Reservation, record_id)
    if row is None:
        raise AppError(404, "NOT_FOUND", "That reservation was not found.")
    ip_address, user_agent = client_ip(request), client_agent(request)
    audit(session, actor.id, "delete", "reservation", row.id, ip_address, user_agent)
    session.delete(row)
    session.commit()
    return Response(status_code=204)


@router.post("/records/bulk-delete")
def delete_records(data: BulkBody, request: Request, session: SessionDep, actor: AdminUser) -> dict:
    changed = 0
    ip_address, user_agent = client_ip(request), client_agent(request)
    for record_id in data.ids:
        row = session.get(Reservation, record_id)
        if row is None:
            continue
        audit(session, actor.id, "delete", "reservation", row.id, ip_address, user_agent)
        session.delete(row)
        changed += 1
    session.commit()
    return {"changed": changed}


@router.get("/groups")
def list_groups(
    session: SessionDep,
    actor: AdminUser,
    q: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    del actor
    rows = list(session.exec(select(DiningGroup).order_by(DiningGroup.id)).all())
    if q:
        needle = q.strip().lower()
        rows = [row for row in rows if needle in row.name.lower()]
    page = rows[offset : offset + limit]
    items = []
    for row in page:
        owner = session.get(User, row.owner_id)
        members = session.exec(select(GroupMember).where(GroupMember.group_id == row.id)).all()
        items.append(
            {
                "id": row.id,
                "name": row.name,
                "owner_name": owner.full_name if owner else "Unknown",
                "members": len(list(members)),
            }
        )
    return _page(items, len(rows), offset, limit)


@router.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: int, request: Request, session: SessionDep, actor: AdminUser) -> Response:
    group = session.get(DiningGroup, group_id)
    if group is None:
        raise AppError(404, "NOT_FOUND", "That group was not found.")
    for row in session.exec(select(GroupMember).where(GroupMember.group_id == group.id)).all():
        session.delete(row)
    for reservation in session.exec(select(Reservation).where(Reservation.group_id == group.id)).all():
        reservation.group_id = None
        session.add(reservation)
    ip_address, user_agent = client_ip(request), client_agent(request)
    audit(session, actor.id, "delete", "group", group.id, ip_address, user_agent, group.name)
    session.delete(group)
    session.commit()
    return Response(status_code=204)


def _activity_row(row: AuditLog) -> dict:
    return {
        "id": row.id,
        "actor_id": row.actor_id,
        "action": row.action,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "ip_address": row.ip_address,
        "user_agent": row.user_agent,
        "detail": row.detail,
        "created_at": to_utc(row.created_at).isoformat(),
    }


def _filtered_activity(session: SessionDep, action: str | None, q: str | None) -> list[AuditLog]:
    rows = list(session.exec(select(AuditLog).order_by(AuditLog.id.desc())).all())
    if action:
        rows = [row for row in rows if row.action == action]
    if q:
        needle = q.strip().lower()
        kept = []
        for row in rows:
            actor = session.get(User, row.actor_id) if row.actor_id else None
            haystack = " ".join(
                part
                for part in (
                    row.action,
                    row.detail or "",
                    row.ip_address or "",
                    actor.email if actor else "",
                    actor.full_name if actor else "",
                )
            ).lower()
            if needle in haystack:
                kept.append(row)
        rows = kept
    return rows


@router.get("/activity")
def activity(
    session: SessionDep,
    actor: AdminUser,
    action: str | None = None,
    q: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    del actor
    rows = _filtered_activity(session, action, q)
    page = rows[offset : offset + limit]
    return _page([_activity_row(row) for row in page], len(rows), offset, limit)


@router.get("/security")
def security_view(session: SessionDep, actor: AdminUser) -> dict:
    del actor
    rows = session.exec(select(AuditLog).where(AuditLog.action == "login_failed")).all()
    by_ip: dict[str, int] = {}
    by_account: dict[str, int] = {}
    for row in rows:
        ip_key = row.ip_address or "unknown"
        by_ip[ip_key] = by_ip.get(ip_key, 0) + 1
        account = row.detail or ""
        if row.actor_id:
            actor_row = session.get(User, row.actor_id)
            account = actor_row.email if actor_row else str(row.actor_id)
        account = account or "unknown"
        by_account[account] = by_account.get(account, 0) + 1
    return {
        "failed_by_ip": [{"ip_address": key, "count": value} for key, value in sorted(by_ip.items())],
        "failed_by_account": [{"account": key, "count": value} for key, value in sorted(by_account.items())],
    }


def _csv(filename: str, header: list[str], records: list[list[str]]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(records)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/users.csv")
def export_users(
    request: Request,
    session: SessionDep,
    actor: AdminUser,
    q: str | None = None,
    account_role: str | None = None,
    status: str | None = None,
) -> Response:
    rows = _filtered_users(session, q, account_role, status)
    ip_address, user_agent = client_ip(request), client_agent(request)
    audit(session, actor.id, "export", "user", None, ip_address, user_agent, "users")
    session.commit()
    return _csv(
        "users.csv",
        ["id", "full_name", "email", "job", "account_role", "is_active", "ban_reason"],
        [
            [
                str(row.id),
                row.full_name,
                row.email,
                row.role,
                row.account_role,
                str(row.is_active).lower(),
                row.ban_reason or "",
            ]
            for row in rows
        ],
    )


@router.get("/export/records.csv")
def export_records(
    request: Request,
    session: SessionDep,
    actor: AdminUser,
    status: str | None = None,
) -> Response:
    rows = list(session.exec(select(Reservation).order_by(Reservation.id)).all())
    if status:
        rows = [row for row in rows if row.status == status]
    ip_address, user_agent = client_ip(request), client_agent(request)
    audit(session, actor.id, "export", "reservation", None, ip_address, user_agent, "records")
    session.commit()
    return _csv(
        "records.csv",
        ["id", "customer_id", "seat_id", "status", "party_size", "group_id", "start_at"],
        [
            [
                str(row.id),
                str(row.customer_id),
                str(row.seat_id),
                row.status,
                str(row.party_size),
                "" if row.group_id is None else str(row.group_id),
                to_utc(row.start_at).isoformat(),
            ]
            for row in rows
        ],
    )


@router.get("/export/activity.csv")
def export_activity(
    request: Request,
    session: SessionDep,
    actor: AdminUser,
    action: str | None = None,
    q: str | None = None,
) -> Response:
    rows = _filtered_activity(session, action, q)
    ip_address, user_agent = client_ip(request), client_agent(request)
    audit(session, actor.id, "export", "activity", None, ip_address, user_agent, "activity")
    session.commit()
    return _csv(
        "activity.csv",
        ["id", "actor_id", "action", "target_type", "target_id", "ip_address", "detail", "created_at"],
        [
            [
                str(row.id or ""),
                "" if row.actor_id is None else str(row.actor_id),
                row.action,
                row.target_type,
                "" if row.target_id is None else str(row.target_id),
                row.ip_address or "",
                row.detail or "",
                to_utc(row.created_at).isoformat(),
            ]
            for row in rows
        ],
    )
