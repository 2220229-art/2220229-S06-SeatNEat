"""One place for account and group permission checks.

Restaurant job (customer, staff, manager) still decides the booking screens.
account_role is the security role the final brief asks for: user or admin.
"""

from sqlmodel import Session, select

from app.errors import AppError
from app.models import AccountRole, DiningGroup, GroupMember, User


def account_role_of(user: User) -> str:
    if user.account_role in {AccountRole.user.value, AccountRole.admin.value}:
        return user.account_role
    return AccountRole.user.value


def is_admin(user: User) -> bool:
    return account_role_of(user) == AccountRole.admin.value


def require_admin(user: User) -> None:
    if not is_admin(user):
        raise AppError(403, "FORBIDDEN", "You do not have permission for this action.")


def _group_or_404(session: Session, group_id: int) -> DiningGroup:
    group = session.get(DiningGroup, group_id)
    if group is None:
        raise AppError(404, "NOT_FOUND", "That group was not found.")
    return group


def membership(session: Session, group_id: int, user_id: int) -> GroupMember | None:
    return session.exec(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
    ).first()


def require_owner(session: Session, user: User, group_id: int) -> DiningGroup:
    group = _group_or_404(session, group_id)
    if group.owner_id != user.id:
        raise AppError(403, "FORBIDDEN", "Only the group owner can do that.")
    return group


def require_group_permission(session: Session, user: User, group_id: int, action: str) -> DiningGroup:
    group = _group_or_404(session, group_id)
    if group.owner_id == user.id:
        return group
    member = membership(session, group.id or 0, user.id or 0)
    if member is None:
        raise AppError(403, "FORBIDDEN", "You are not a member of this group.")
    allowed = {
        "create": member.can_create,
        "update": member.can_update,
        "assign": member.can_assign,
    }.get(action, False)
    if not allowed:
        raise AppError(403, "FORBIDDEN", "You do not have permission for this action.")
    return group
