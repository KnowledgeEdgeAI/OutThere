"""Frozen Ripple audiences, bounded slots and one transactional plan conversion."""

from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import JSON, Column
from sqlmodel import Field as DBField
from sqlmodel import SQLModel, select

from outthere.contracts import Input
from outthere.contracts import PlanCreate as Scheduling
from outthere.errors import AppError
from outthere.events import emit
from outthere.models import User, now
from outthere.people import member_ids
from outthere.product import circle_access, missing, plan_create, version
from outthere.product_contracts import PlanCreate


class Ripple(SQLModel, table=True):
    id: UUID = DBField(primary_key=True)
    sender_id: UUID = DBField(foreign_key="user.id", index=True)
    idea: str
    slots: list = DBField(sa_column=Column(JSON, nullable=False))
    place_hint: str | None = None
    closes_at: int = DBField(index=True)
    state: str = "open"
    converted_plan_id: UUID | None = DBField(default=None, foreign_key="plan.id", unique=True)
    version: int = 1


class RippleRecipient(SQLModel, table=True):
    ripple_id: UUID = DBField(foreign_key="ripple.id", primary_key=True)
    user_id: UUID = DBField(foreign_key="user.id", primary_key=True, index=True)
    response: str | None = None
    selected_slot_ids: list = DBField(default_factory=list, sa_column=Column(JSON, nullable=False))
    note: str | None = None
    version: int = 0


class Slot(Input):
    slot_id: UUID
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    venue_timezone: str
    note: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def interval(self):
        Scheduling(
            title="slot",
            starts_at=self.starts_at,
            ends_at=self.ends_at,
            venue_timezone=self.venue_timezone,
        )
        return self


class Id(Input):
    ripple_id: UUID


class Create(Id):
    idea: str = Field(min_length=1, max_length=240)
    user_ids: list[UUID] = Field(default_factory=list, max_length=100)
    circle_ids: list[UUID] = Field(default_factory=list, max_length=15)
    slots: list[Slot] = Field(default_factory=list, max_length=2)
    place_hint: str | None = Field(default=None, max_length=240)
    reply_window_seconds: int = Field(default=86400, ge=60, le=7 * 86400)

    @model_validator(mode="after")
    def unique(self):
        if len({s.slot_id for s in self.slots}) != len(self.slots):
            raise ValueError("Duplicate slots")
        return self


class Respond(Id):
    expected_version: int = Field(ge=0)
    choice: str = Field(pattern=r"^(up_for_it|another_time|cannot)$")
    selected_slot_ids: list[UUID] = Field(default_factory=list, max_length=2)
    note: str | None = Field(default=None, max_length=140)

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.selected_slot_ids)) != len(self.selected_slot_ids):
            raise ValueError("Duplicate slots")
        if self.choice != "up_for_it" and self.selected_slot_ids:
            raise ValueError("Non-interested responses cannot select slots")
        return self


class Edit(Id):
    expected_version: int = Field(ge=1)


class Convert(Edit):
    plan: PlanCreate


class List(Input):
    after: UUID | None = None
    limit: int = Field(default=50, ge=1, le=100)


CONTRACTS = {
    "ripple.list": ("query", List),
    "ripple.create": ("command", Create),
    "ripple.respond": ("command", Respond),
    "ripple.convert": ("command", Convert),
    "ripple.close": ("command", Edit),
}


def audience(db, row):
    return {row.sender_id} | set(
        db.exec(select(RippleRecipient.user_id).where(RippleRecipient.ripple_id == row.id)).all()
    )


def projection(db, row, viewer):
    recipients = db.exec(
        select(RippleRecipient)
        .where(RippleRecipient.ripple_id == row.id)
        .order_by(RippleRecipient.user_id)
    ).all()
    if viewer not in {row.sender_id} | {r.user_id for r in recipients}:
        missing("Ripple")
    counts = {
        choice: sum(r.response == choice for r in recipients)
        for choice in ["up_for_it", "another_time", "cannot"]
    }
    visible = (
        recipients if viewer == row.sender_id else [r for r in recipients if r.user_id == viewer]
    )
    return {
        "id": str(row.id),
        "sender_id": str(row.sender_id),
        "idea": row.idea,
        "slots": row.slots,
        "place_hint": row.place_hint,
        "closes_at": row.closes_at,
        "state": row.state,
        "version": row.version,
        "counts": counts,
        "converted_plan_id": str(row.converted_plan_id) if row.converted_plan_id else None,
        "responses": [
            {
                "user_id": str(r.user_id),
                "choice": r.response,
                "selected_slot_ids": r.selected_slot_ids,
                "note": r.note,
                "version": r.version,
            }
            for r in visible
        ],
    }


def change(db, row):
    emit(db, audience(db, row), "v2.ripple", row.id)


def handle(db, user, name, data):
    if name == "ripple.list":
        own = select(RippleRecipient.ripple_id).where(RippleRecipient.user_id == user.id)
        statement = select(Ripple).where((Ripple.sender_id == user.id) | Ripple.id.in_(own))
        if data.after:
            statement = statement.where(Ripple.id > data.after)
        rows = db.exec(statement.order_by(Ripple.id).limit(data.limit + 1)).all()
        return {
            "items": [projection(db, r, user.id) for r in rows[: data.limit]],
            "next_after": str(rows[data.limit - 1].id) if len(rows) > data.limit else None,
        }
    if name == "ripple.create":
        if db.get(Ripple, data.ripple_id):
            raise AppError("action_conflict", "Ripple ID already exists", 409)
        users = set(data.user_ids)
        for circle_id in set(data.circle_ids):
            circle_access(db, user.id, circle_id)
            users.update(member_ids(db, circle_id))
        users.discard(user.id)
        if not users or len(users) > 100:
            raise AppError("invalid_input", "Choose 1–100 recipients")
        for person in users:
            if db.get(User, person) is None:
                missing("Recipient")
        deadline = now() + data.reply_window_seconds
        if data.slots:
            deadline = min(deadline, min(int(s.starts_at.timestamp()) for s in data.slots))
        if deadline <= now():
            raise AppError("invalid_input", "Choose future slots")
        row = Ripple(
            id=data.ripple_id,
            sender_id=user.id,
            idea=data.idea,
            slots=[s.model_dump(mode="json") for s in data.slots],
            place_hint=data.place_hint,
            closes_at=deadline,
        )
        db.add(row)
        db.flush()
        for person in sorted(users, key=str):
            db.add(RippleRecipient(ripple_id=row.id, user_id=person))
        db.flush()
    else:
        row = db.exec(select(Ripple).where(Ripple.id == data.ripple_id).with_for_update()).first()
        if row is None or user.id not in audience(db, row):
            missing("Ripple")
        if name == "ripple.convert":
            if user.id != row.sender_id:
                raise AppError("forbidden", "Only sender can convert a Ripple", 403)
            if row.converted_plan_id:
                return {"plan_id": str(row.converted_plan_id), "ripple_id": str(row.id)}
        if row.state != "open" or row.closes_at <= now():
            raise AppError("expired", "Ripple is closed", 409)
        if name == "ripple.respond":
            recipient = db.get(RippleRecipient, (row.id, user.id))
            if recipient is None:
                missing("Recipient")
            version(recipient, data.expected_version)
            slots = {s["slot_id"] for s in row.slots}
            if not {str(i) for i in data.selected_slot_ids} <= slots:
                raise AppError("invalid_input", "Unknown slot")
            recipient.response, recipient.note = data.choice, data.note
            recipient.selected_slot_ids = [str(i) for i in data.selected_slot_ids]
            recipient.version += 1
        else:
            if row.sender_id != user.id:
                raise AppError("forbidden", "Only sender can change a Ripple", 403)
            version(row, data.expected_version)
            if name == "ripple.convert":
                if not set(data.plan.invitee_ids) <= audience(db, row):
                    raise AppError("invalid_input", "Invitees must belong to the Ripple audience")
                if data.plan.circle_ids or data.plan.circle_id:
                    raise AppError("invalid_input", "Conversion must use reviewed direct invitees")
                result = plan_create(db, user.id, data.plan)
                row.converted_plan_id, row.state = UUID(result["id"]), "converted"
            else:
                row.state = "closed"
            row.version += 1
    db.flush()
    change(db, row)
    if name in {"ripple.create", "ripple.convert"}:
        from outthere.models import Device
        from outthere.push import enqueue

        for device in db.exec(
            select(Device).where(
                Device.user_id.in_(audience(db, row) - {user.id}), Device.revoked_at.is_(None)
            )
        ).all():
            enqueue(
                db, device, "ripples", row.id, f"push.ripple:{row.id}:{device.id}:{row.version}"
            )
    if name == "ripple.convert":
        return {"plan_id": str(row.converted_plan_id), "ripple_id": str(row.id)}
    return projection(db, row, user.id)


def cleanup(db):
    for row in db.exec(
        select(Ripple).where(Ripple.state == "open", Ripple.closes_at <= now()).with_for_update()
    ).all():
        row.state, row.version = "closed", row.version + 1
        change(db, row)
