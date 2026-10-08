"""Temporary text/link chat with independently acknowledged device targets."""

from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import Field, HttpUrl, model_validator
from sqlalchemy import JSON, Column, UniqueConstraint, delete
from sqlmodel import Field as DBField
from sqlmodel import SQLModel, select

from outthere.contracts import Input
from outthere.errors import AppError
from outthere.models import Device, Participant, Plan, now
from outthere.product import editable, missing, plan_access, plan_state


class DeliveryEvent(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("room_id", "seq"),)
    id: UUID = DBField(default_factory=uuid4, primary_key=True)
    room_id: UUID = DBField(index=True)
    seq: int
    message_id: UUID = DBField(index=True)
    sender_id: UUID = DBField(foreign_key="user.id")
    kind: str
    payload: dict = DBField(sa_column=Column(JSON, nullable=False))
    created_at: int = DBField(default_factory=now)
    expires_at: int = DBField(index=True)


class DeliveryTarget(SQLModel, table=True):
    event_id: UUID = DBField(foreign_key="deliveryevent.id", primary_key=True)
    device_id: UUID = DBField(foreign_key="device.id", primary_key=True, index=True)
    acknowledged_at: int | None = None
    cancelled_at: int | None = None


class MessageAcceptance(SQLModel, table=True):
    user_id: UUID = DBField(foreign_key="user.id", primary_key=True)
    action_id: UUID = DBField(primary_key=True)
    message_id: UUID = DBField(unique=True, index=True)
    request_hash: str
    result: dict = DBField(sa_column=Column(JSON, nullable=False))
    reaction_state: dict = DBField(default_factory=dict, sa_column=Column(JSON, nullable=False))
    final_summary: dict | None = DBField(default=None, sa_column=Column(JSON))
    expires_at: int = DBField(index=True)


class AttachmentTarget(SQLModel, table=True):
    event_id: UUID = DBField(foreign_key="deliveryevent.id", primary_key=True)
    media_id: UUID = DBField(foreign_key="media.id", primary_key=True)
    device_id: UUID = DBField(foreign_key="device.id", primary_key=True, index=True)
    downloaded_at: int | None = None
    expires_at: int = DBField(index=True)


class Text(Input):
    kind: Literal["text"]
    text: str = Field(min_length=1, max_length=4000)


class Link(Input):
    kind: Literal["link"]
    url: HttpUrl
    text: str | None = Field(default=None, max_length=4000)


class Location(Input):
    kind: Literal["location"]
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    label: str = Field(min_length=1, max_length=240)


class Image(Input):
    kind: Literal["image", "video"]
    media_ids: list[UUID] = Field(min_length=1, max_length=10)
    caption: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.media_ids)) != len(self.media_ids):
            raise ValueError("Duplicate media IDs")
        if self.kind == "video" and len(self.media_ids) != 1:
            raise ValueError("Video messages require one file")
        return self


class Voice(Input):
    kind: Literal["voice"]
    media_id: UUID
    duration_seconds: int = Field(gt=0, le=600)


class Send(Input):
    room_id: UUID
    message_id: UUID
    content: Annotated[Text | Link | Location | Image | Voice, Field(discriminator="kind")]


class Room(Input):
    room_id: UUID


class Pull(Input):
    after: UUID | None = None
    limit: int = Field(default=50, ge=1, le=100)


class Ack(Input):
    event_ids: list[UUID] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.event_ids)) != len(self.event_ids):
            raise ValueError("Duplicate events")
        return self


class Typing(Room):
    active: bool


class MediaAck(Input):
    event_id: UUID
    media_id: UUID


class Reaction(Input):
    room_id: UUID
    message_id: UUID
    emoji: str = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def valid_emoji(self):
        if any(c.isalnum() or c.isspace() for c in self.emoji) or all(
            ord(c) < 128 for c in self.emoji
        ):
            raise ValueError("Use an emoji")
        return self


class Status(Input):
    message_ids: list[UUID] = Field(min_length=1, max_length=100)


CONTRACTS = {
    "room.get": ("query", Room),
    "message.send": ("command", Send),
    "delivery.pull": ("query", Pull),
    "delivery.ack": ("command", Ack),
    "delivery.status": ("query", Status),
    "typing.update": ("command", Typing),
    "delivery.media.ack": ("command", MediaAck),
    "message.reaction.add": ("command", Reaction),
    "message.reaction.remove": ("command", Reaction),
}


def view(event):
    return {
        "event_id": str(event.id),
        "room_id": str(event.room_id),
        "room_seq": event.seq,
        "kind": event.kind,
        "message_id": str(event.message_id),
        "sender_id": str(event.sender_id),
        "created_at": event.created_at,
        "expires_at": event.expires_at,
        "content": event.payload,
    }


def finish(db, event, expired=False):
    targets = db.exec(select(DeliveryTarget).where(DeliveryTarget.event_id == event.id)).all()
    if not expired and any(t.acknowledged_at is None and t.cancelled_at is None for t in targets):
        return
    receipt = db.exec(
        select(MessageAcceptance).where(MessageAcceptance.message_id == event.message_id)
    ).first()
    if receipt and event.kind == "message.created" and receipt.final_summary is None:
        receipt.reaction_state = {}
        receipt.final_summary = {
            "delivered": sum(t.acknowledged_at is not None for t in targets),
            "cancelled": sum(
                t.cancelled_at is not None and t.acknowledged_at is None for t in targets
            ),
            "expired": sum(t.acknowledged_at is None and t.cancelled_at is None for t in targets),
            "finished_at": now(),
        }
    attachments = db.exec(
        select(AttachmentTarget).where(AttachmentTarget.event_id == event.id)
    ).all()
    if not expired and any(a.downloaded_at is None and a.expires_at > now() for a in attachments):
        event.payload = {}
        return
    db.exec(delete(AttachmentTarget).where(AttachmentTarget.event_id == event.id))
    db.exec(delete(DeliveryTarget).where(DeliveryTarget.event_id == event.id))
    db.delete(event)
    db.flush()


def room_access(db, user_id, room_id, write=False):
    from outthere.matching import Overlap, members
    from outthere.safety import blocked

    plan = db.get(Plan, room_id)
    if plan:
        plan = plan_access(db, user_id, room_id)
        if write:
            editable(db, plan)
        return plan
    overlap = db.get(Overlap, room_id)
    if overlap is None or user_id not in members(db, overlap) or overlap.state != "hello":
        missing("Room")
    people = members(db, overlap)
    if blocked(db, *sorted(people, key=str)) or overlap.hello_expires_at <= now():
        missing("Room")
    return overlap


def room_members(db, row):
    if isinstance(row, Plan):
        return set(db.exec(select(Participant.user_id).where(Participant.plan_id == row.id)).all())
    from outthere.matching import members

    return members(db, row)


def room_deadline(row):
    return row.ends_at + 86400 if isinstance(row, Plan) else row.hello_expires_at


def cleanup(db):
    from outthere.safety import blocked

    events = db.exec(select(DeliveryEvent).order_by(DeliveryEvent.id).with_for_update()).all()
    for event in events:
        for target in db.exec(
            select(DeliveryTarget).where(DeliveryTarget.event_id == event.id)
        ).all():
            device = db.get(Device, target.device_id)
            if (
                device.revoked_at is not None
                or not permitted(db, device.user_id, event.room_id)
                or blocked(db, event.sender_id, device.user_id)
            ):
                if target.cancelled_at is None:
                    target.cancelled_at = now()
                for attachment in db.exec(
                    select(AttachmentTarget).where(
                        AttachmentTarget.event_id == event.id,
                        AttachmentTarget.device_id == device.id,
                    )
                ).all():
                    attachment.expires_at = now()
        db.flush()
        finish(db, event, expired=event.expires_at <= now())
    db.exec(delete(MessageAcceptance).where(MessageAcceptance.expires_at <= now()))


def send(db, user, device, data, action_id, request_hash):
    receipt = db.get(MessageAcceptance, (user.id, action_id))
    if receipt:
        if receipt.request_hash != request_hash:
            raise AppError("action_conflict", "Action ID belongs to another request", 409)
        return receipt.result
    plan = room_access(db, user.id, data.room_id, write=True)
    if db.exec(
        select(MessageAcceptance).where(MessageAcceptance.message_id == data.message_id)
    ).first():
        raise AppError("action_conflict", "Message ID already exists", 409)
    content = data.content.model_dump(mode="json")
    ids = content.get("media_ids", []) + ([content["media_id"]] if "media_id" in content else [])
    from outthere.media import Media

    for media_id in ids:
        media = db.get(Media, UUID(media_id))
        expected = {"image": "image/", "video": "video/", "voice": "audio/"}[content["kind"]]
        if (
            media is None
            or media.uploader_id != user.id
            or media.room_id != plan.id
            or media.state != "ready"
            or not media.mime.startswith(expected)
            or (media.expires_at is not None and media.expires_at <= now())
        ):
            missing("Attachment")
        media.accepted_at = now()
    if content["kind"] == "location" and isinstance(plan, Plan):
        raise AppError("invalid_input", "Plan locations use shared artifacts")
    plan.message_seq += 1
    expires = min(now() + 7 * 86400, room_deadline(plan))
    event = DeliveryEvent(
        room_id=plan.id,
        seq=plan.message_seq,
        message_id=data.message_id,
        sender_id=user.id,
        kind="message.created",
        payload=content,
        expires_at=expires,
    )
    db.add(event)
    result = {
        "message_id": str(data.message_id),
        "event_id": str(event.id),
        "room_seq": event.seq,
        "expires_at": expires,
    }
    receipt = MessageAcceptance(
        user_id=user.id,
        action_id=action_id,
        message_id=data.message_id,
        request_hash=request_hash,
        result=result,
        expires_at=now() + 30 * 86400,
    )
    db.add(receipt)
    db.flush()
    devices = db.exec(
        select(Device)
        .where(
            Device.user_id.in_(room_members(db, plan)),
            Device.revoked_at.is_(None),
            Device.last_seen_at > now() - 30 * 86400,
            Device.id != device.id,
        )
        .order_by(Device.id)
    ).all()
    from outthere.safety import blocked

    for recipient in devices:
        if blocked(db, user.id, recipient.user_id):
            continue
        db.add(DeliveryTarget(event_id=event.id, device_id=recipient.id))
        from outthere.push import enqueue

        enqueue(db, recipient, "messages", event.id, f"push.message:{event.id}:{recipient.id}")
        for media_id in ids:
            db.add(
                AttachmentTarget(
                    event_id=event.id,
                    media_id=UUID(media_id),
                    device_id=recipient.id,
                    expires_at=expires,
                )
            )
    db.flush()
    # The sending device has already stored its own outgoing message locally.
    finish(db, event)
    return result


def handle(db, user, device, name, data):
    cleanup(db)
    if name == "typing.update":
        room_access(db, user.id, data.room_id, write=True)
        return {
            "room_id": str(data.room_id),
            "sender_id": str(user.id),
            "active": data.active,
            "expires_at": now() + 5,
        }
    if name == "room.get":
        plan = room_access(db, user.id, data.room_id)
        return {
            "room_id": str(plan.id),
            "plan_id": str(plan.id) if isinstance(plan, Plan) else None,
            "overlap_id": None if isinstance(plan, Plan) else str(plan.id),
            "read_only": (
                plan.archived
                or room_deadline(plan) <= now()
                or plan_state(db, plan.id).status != "active"
            )
            if isinstance(plan, Plan)
            else False,
            "expires_at": room_deadline(plan),
            "members": [str(u) for u in room_members(db, plan)],
        }
    if name == "delivery.pull":
        statement = (
            select(DeliveryEvent)
            .join(DeliveryTarget)
            .where(
                DeliveryTarget.device_id == device.id,
                DeliveryTarget.acknowledged_at.is_(None),
                DeliveryTarget.cancelled_at.is_(None),
                DeliveryEvent.expires_at > now(),
            )
        )
        if data.after:
            statement = statement.where(DeliveryEvent.id > data.after)
        rows = db.exec(statement.order_by(DeliveryEvent.id).limit(data.limit + 1)).all()
        return {
            "items": [view(e) for e in rows[: data.limit]],
            "next_after": str(rows[data.limit - 1].id) if len(rows) > data.limit else None,
        }
    if name == "delivery.ack":
        # Validate all existing IDs before acknowledging any, including cross-device IDs.
        for event_id in data.event_ids:
            event = db.get(DeliveryEvent, event_id)
            target = db.get(DeliveryTarget, (event_id, device.id))
            if event and not target:
                missing("Delivery")
            if target and target.cancelled_at is None:
                target.acknowledged_at = now()
        db.flush()
        for event_id in data.event_ids:
            event = db.get(DeliveryEvent, event_id)
            if event:
                finish(db, event)
        return {"acknowledged": [str(i) for i in data.event_ids]}
    if name == "delivery.media.ack":
        attachment = db.get(AttachmentTarget, (data.event_id, data.media_id, device.id))
        if attachment is None:
            event = db.get(DeliveryEvent, data.event_id)
            if event:
                missing("Attachment")
        else:
            attachment.downloaded_at = now()
            db.flush()
            finish(db, db.get(DeliveryEvent, data.event_id))
        return {"downloaded": True}
    if name.startswith("message.reaction."):
        room = room_access(db, user.id, data.room_id, write=True)
        source = db.exec(
            select(DeliveryEvent).where(
                DeliveryEvent.room_id == room.id,
                DeliveryEvent.message_id == data.message_id,
                DeliveryEvent.kind == "message.created",
            )
        ).first()
        if source is None or source.expires_at <= now() or not source.payload:
            raise AppError("expired", "Message expired", 409)
        acceptance = db.exec(
            select(MessageAcceptance).where(MessageAcceptance.message_id == data.message_id)
        ).first()
        if acceptance is None:
            raise AppError("expired", "Message acceptance expired", 409)
        key = f"{user.id}:{data.emoji}"
        current = dict(acceptance.reaction_state)
        adding = name.endswith("add")
        if (key in current) == adding:
            return {"message_id": str(data.message_id), "changed": False}
        if adding:
            if sum(k.startswith(f"{user.id}:") for k in current) >= 6:
                raise AppError("invalid_input", "At most six active reactions per person")
            current[key] = True
        else:
            current.pop(key, None)
        acceptance.reaction_state = current
        kind = "reaction.added" if adding else "reaction.removed"
        room.message_seq += 1
        event = DeliveryEvent(
            room_id=room.id,
            seq=room.message_seq,
            message_id=data.message_id,
            sender_id=user.id,
            kind=kind,
            payload={"emoji": data.emoji},
            expires_at=source.expires_at,
        )
        db.add(event)
        db.flush()
        from outthere.safety import blocked

        for recipient in db.exec(
            select(Device).where(
                Device.user_id.in_(room_members(db, room)),
                Device.revoked_at.is_(None),
                Device.id != device.id,
            )
        ).all():
            if not blocked(db, user.id, recipient.user_id):
                db.add(DeliveryTarget(event_id=event.id, device_id=recipient.id))
        db.flush()
        # Reaction events must not overwrite the original message's terminal receipt.
        return {"message_id": str(data.message_id), "changed": True, "event_id": str(event.id)}
    if name == "delivery.status":
        items = []
        for message_id in data.message_ids:
            receipt = db.exec(
                select(MessageAcceptance).where(
                    MessageAcceptance.user_id == user.id, MessageAcceptance.message_id == message_id
                )
            ).first()
            state = {"state": "unknown"}
            if receipt:
                if receipt.final_summary is not None:
                    state = {"state": "finished", **receipt.final_summary}
                else:
                    event = db.exec(
                        select(DeliveryEvent).where(DeliveryEvent.message_id == message_id)
                    ).first()
                    targets = (
                        db.exec(
                            select(DeliveryTarget).where(DeliveryTarget.event_id == event.id)
                        ).all()
                        if event
                        else []
                    )
                    state = {
                        "state": "pending",
                        "delivered": sum(t.acknowledged_at is not None for t in targets),
                        "pending": sum(
                            t.acknowledged_at is None and t.cancelled_at is None for t in targets
                        ),
                    }
            items.append({"message_id": str(message_id), **state})
        return {"items": items}
    raise AppError("unsupported_version", "Unsupported delivery operation")


def permitted(db, user_id, room_id):
    try:
        room_access(db, user_id, room_id)
        return True
    except AppError as exc:
        if exc.code == "not_found":
            return False
        raise
