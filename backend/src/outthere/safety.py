"""Symmetric blocking checks, explicit reports, profile pause and account erasure."""

from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import CheckConstraint, update
from sqlmodel import Field as DBField
from sqlmodel import SQLModel, select

from outthere.contracts import Input
from outthere.errors import AppError
from outthere.events import emit
from outthere.models import AuthSession, Circle, Device, Membership, Participant, Plan, User, now
from outthere.product import invalidate, missing


class Block(SQLModel, table=True):
    __table_args__ = (CheckConstraint("blocker_id <> blocked_id", name="ck_block_not_self"),)
    blocker_id: UUID = DBField(foreign_key="user.id", primary_key=True)
    blocked_id: UUID = DBField(foreign_key="user.id", primary_key=True)
    created_at: int = DBField(default_factory=now)


class Report(SQLModel, table=True):
    id: UUID = DBField(default_factory=uuid4, primary_key=True)
    reporter_id: UUID = DBField(foreign_key="user.id", index=True)
    resource_type: str
    resource_id: UUID
    reason: str
    status: str = "new"


class Empty(Input):
    pass


class Person(Input):
    user_id: UUID


class ReportCreate(Input):
    resource_type: str = Field(pattern=r"^(plan|artifact|message|user)$")
    resource_id: UUID
    reason: str = Field(min_length=1, max_length=1000)


class Delete(Input):
    expected_version: int = Field(ge=1)


CONTRACTS = {
    "block.create": ("command", Person),
    "block.delete": ("command", Person),
    "block.list": ("query", Empty),
    "report.create": ("command", ReportCreate),
    "profile.pause": ("command", Delete),
    "profile.resume": ("command", Delete),
    "account.delete": ("command", Delete),
}


def blocked(db, first, second):
    return db.get(Block, (first, second)) is not None or db.get(Block, (second, first)) is not None


def handle(db, user, name, data):
    if name == "block.list":
        return {
            "items": [
                {"user_id": str(b.blocked_id), "created_at": b.created_at}
                for b in db.exec(
                    select(Block).where(Block.blocker_id == user.id).order_by(Block.blocked_id)
                ).all()
            ]
        }
    if name in {"block.create", "block.delete"}:
        if data.user_id == user.id:
            raise AppError("invalid_input", "Cannot block yourself")
        if db.get(User, data.user_id) is None:
            missing("User")
        row = db.get(Block, (user.id, data.user_id))
        if name.endswith("create") and row is None:
            db.add(Block(blocker_id=user.id, blocked_id=data.user_id))
        if name.endswith("delete") and row is not None:
            db.delete(row)
        db.flush()
        for target in sorted({user.id, data.user_id}, key=str):
            invalidate(db, target, "v2.block", data.user_id if target == user.id else user.id)
        from outthere.delivery import cleanup

        cleanup(db)
        return {"user_id": str(data.user_id), "blocked": name.endswith("create")}
    if name == "report.create":
        if data.resource_type == "plan":
            from outthere.product import plan_access

            plan_access(db, user.id, data.resource_id)
        elif data.resource_type == "artifact":
            from outthere.coordination import Artifact, access

            row = db.get(Artifact, data.resource_id)
            if row is None:
                missing("Artifact")
            access(db, user.id, row.plan_id, row.id)
        elif data.resource_type == "message":
            from outthere.delivery import DeliveryEvent

            row = db.exec(
                select(DeliveryEvent).where(DeliveryEvent.message_id == data.resource_id)
            ).first()
            if row is None:
                missing("Message")
            from outthere.delivery import room_access

            room_access(db, user.id, row.room_id)
        elif db.get(User, data.resource_id) is None:
            missing("User")
        row = Report(
            reporter_id=user.id,
            resource_type=data.resource_type,
            resource_id=data.resource_id,
            reason=data.reason,
        )
        db.add(row)
        return {"report_id": str(row.id), "status": "new"}
    if user.version != data.expected_version:
        raise AppError("version_conflict", "Refresh your profile", 409)
    if name in {"profile.pause", "profile.resume"}:
        user.paused_at = now() if name.endswith("pause") else None
        user.version += 1
        emit(db, {user.id}, "v2.profile", user.id)
        return {"paused": user.paused_at is not None, "version": user.version}
    user.phone, user.display_name, user.deleted_at = None, "Deleted account", now()
    user.version += 1
    user.dp_media_id = None
    db.exec(update(Device).where(Device.user_id == user.id).values(revoked_at=now()))
    db.exec(update(AuthSession).where(AuthSession.user_id == user.id).values(revoked_at=now()))
    from outthere.media import AlbumGrant, Media

    for grant in db.exec(select(AlbumGrant).where(AlbumGrant.user_id == user.id)).all():
        db.delete(grant)

    for participant in db.exec(select(Participant).where(Participant.user_id == user.id)).all():
        plan = db.get(Plan, participant.plan_id)
        users = set(
            db.exec(select(Participant.user_id).where(Participant.plan_id == plan.id)).all()
        )
        if plan.host_id == user.id:
            plan.status = "cancelled"
            plan.version += 1
        db.delete(participant)
        for target in users:
            invalidate(db, target, "v2.plan", plan.id)
    for membership in db.exec(select(Membership).where(Membership.user_id == user.id)).all():
        circle = db.get(Circle, membership.circle_id)
        users = set(
            db.exec(select(Membership.user_id).where(Membership.circle_id == circle.id)).all()
        )
        others = sorted(users - {user.id}, key=str)
        if circle.owner_id == user.id and others:
            circle.owner_id = others[0]
        db.delete(membership)
        for target in users:
            invalidate(db, target, "v2.circle", circle.id)
    from outthere.delivery import DeliveryEvent, DeliveryTarget, finish

    for event in db.exec(select(DeliveryEvent).where(DeliveryEvent.sender_id == user.id)).all():
        for target in db.exec(
            select(DeliveryTarget).where(DeliveryTarget.event_id == event.id)
        ).all():
            target.cancelled_at = now()
        db.flush()
        finish(db, event)
    # Shared financial rows keep only the redacted UUID identity.
    from outthere.media import AlbumMedia

    for media in db.exec(select(Media).where(Media.uploader_id == user.id)).all():
        for link in db.exec(select(AlbumMedia).where(AlbumMedia.media_id == media.id)).all():
            db.delete(link)
        media.state, media.expires_at = "aborted", now()
    return {"deleted": True}
