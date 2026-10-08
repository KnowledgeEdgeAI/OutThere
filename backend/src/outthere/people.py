from uuid import UUID

from sqlmodel import Session, select

from outthere.contracts import CircleCreate, CircleInviteCreate, CircleJoin
from outthere.errors import AppError
from outthere.events import emit
from outthere.models import Circle, CircleInvite, Membership, User, now


def member_ids(db: Session, circle_id: UUID) -> set[UUID]:
    return set(db.exec(select(Membership.user_id).where(Membership.circle_id == circle_id)).all())


def circle_view(db: Session, circle: Circle) -> dict:
    return {
        "id": str(circle.id),
        "name": circle.name,
        "kind": circle.kind,
        "owner_id": str(circle.owner_id),
        "member_count": len(member_ids(db, circle.id)),
    }


def create_circle(db: Session, user_id: UUID, data: CircleCreate, action_id: UUID) -> dict:
    circle = Circle(owner_id=user_id, name=data.name, kind=data.kind)
    db.add(circle)
    db.flush()
    db.add(Membership(circle_id=circle.id, user_id=user_id))
    db.flush()
    emit(db, {user_id}, "circle.changed", circle.id)
    return circle_view(db, circle)


def invite_member(db: Session, user_id: UUID, data: CircleInviteCreate, action_id: UUID) -> dict:
    circle = db.get(Circle, data.circle_id)
    if circle is None or circle.owner_id != user_id:
        raise AppError("not_found", "Circle not found", 404)
    if db.get(User, data.user_id) is None:
        raise AppError("not_found", "Invitee not found", 404)
    if db.get(Membership, (circle.id, data.user_id)):
        raise AppError("already_member", "This person is already in the circle", 409)
    invite = db.get(CircleInvite, (circle.id, data.user_id))
    if invite is None:
        invite = CircleInvite(circle_id=circle.id, user_id=data.user_id, expires_at=0)
        db.add(invite)
    invite.expires_at = now() + 7 * 86400
    invite.accepted_at = None
    emit(db, {data.user_id}, "circle.invited", circle.id)
    return {"circle_id": str(circle.id), "user_id": str(data.user_id)}


def join_circle(db: Session, user_id: UUID, data: CircleJoin, action_id: UUID) -> dict:
    circle = db.exec(select(Circle).where(Circle.id == data.circle_id).with_for_update()).first()
    invite = db.get(CircleInvite, (data.circle_id, user_id))
    if circle is None or invite is None or invite.expires_at <= now():
        raise AppError("not_found", "Active invitation not found", 404)
    users = member_ids(db, circle.id)
    if user_id not in users:
        if len(users) >= 15:
            raise AppError("circle_full", "Circles can have at most 15 members", 409)
        db.add(Membership(circle_id=circle.id, user_id=user_id))
        invite.accepted_at = now()
        users.add(user_id)
        db.flush()
        emit(db, users, "circle.changed", circle.id)
    return circle_view(db, circle)
