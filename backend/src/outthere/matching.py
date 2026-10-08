"""Deterministic discovery with anonymous density-gated overlaps and mutual Hello."""

import secrets
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import JSON, CheckConstraint, Column, UniqueConstraint
from sqlmodel import Field as DBField
from sqlmodel import SQLModel, select

from outthere.contracts import Input
from outthere.contracts import PlanCreate as Scheduling
from outthere.discovery import Availability, distance_m
from outthere.errors import AppError
from outthere.events import emit
from outthere.models import Participant, Plan, User, now
from outthere.product import missing, plan_create, safe_plan, version
from outthere.product_contracts import PlanCreate
from outthere.safety import blocked


class Open(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("radius_m > 0 AND ends_at > starts_at", name="ck_open_interval"),
        CheckConstraint(
            "latitude >= -90 AND latitude <= 90 AND longitude >= -180 AND longitude <= 180",
            name="ck_open_coordinates",
        ),
    )
    id: UUID = DBField(primary_key=True)
    user_id: UUID = DBField(foreign_key="user.id", index=True)
    latitude: float
    longitude: float
    radius_m: int
    starts_at: int = DBField(index=True)
    ends_at: int
    expires_at: int = DBField(index=True)
    tags: list = DBField(sa_column=Column(JSON, nullable=False))
    state: str = "active"
    version: int = 1


class Overlap(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("open_a_id", "open_b_id"),)
    id: UUID = DBField(default_factory=uuid4, primary_key=True)
    open_a_id: UUID = DBField(foreign_key="open.id")
    open_b_id: UUID = DBField(foreign_key="open.id")
    decision_a: str | None = None
    decision_b: str | None = None
    state: str = "candidate"
    deliver_after: int
    hello_expires_at: int | None = None
    extended: bool = False
    message_seq: int = 0
    converted_plan_id: UUID | None = DBField(default=None, foreign_key="plan.id", unique=True)
    version: int = 1


class Area(Input):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: int = Field(gt=0, le=100000)


class Create(Area):
    open_id: UUID
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    tags: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def interval(self):
        Scheduling(title="Open", starts_at=self.starts_at, ends_at=self.ends_at)
        if len(set(self.tags)) != len(self.tags) or any(not t or len(t) > 40 for t in self.tags):
            raise ValueError("Use unique bounded activity tags")
        return self


class Edit(Create):
    expected_version: int = Field(ge=1)


class Close(Input):
    open_id: UUID
    expected_version: int = Field(ge=1)


class List(Input):
    after: UUID | None = None
    limit: int = Field(default=50, ge=1, le=100)


class Search(Area):
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    tags: list[str] = Field(default_factory=list, max_length=10)
    limit: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def interval(self):
        if (self.starts_at is None) != (self.ends_at is None):
            raise ValueError("Supply both interval endpoints")
        if self.starts_at and self.ends_at <= self.starts_at:
            raise ValueError("End must follow start")
        return self


class Overlaps(Input):
    open_id: UUID
    limit: int = Field(default=20, ge=1, le=100)


class Respond(Input):
    overlap_id: UUID
    choice: str = Field(pattern=r"^(hi|pass)$")
    expected_version: int = Field(ge=1)


class Hello(Input):
    overlap_id: UUID
    expected_version: int = Field(ge=1)


class HelloPlan(Hello):
    plan: PlanCreate


CONTRACTS = {
    "open.list": ("query", List),
    "open.create": ("command", Create),
    "open.update": ("command", Edit),
    "open.close": ("command", Close),
    "discovery.plans": ("query", Search),
    "overlap.list": ("query", Overlaps),
    "overlap.respond": ("command", Respond),
    "hello.extend": ("command", Hello),
    "hello.plan.create": ("command", HelloPlan),
}


def active(db, row):
    if row is None or row.state != "active" or row.expires_at <= now() or row.ends_at <= now():
        return False
    user = db.get(User, row.user_id)
    return user.deleted_at is None and user.paused_at is None


def availability(row):
    return Availability(
        str(row.user_id),
        row.latitude,
        row.longitude,
        row.radius_m,
        row.starts_at,
        row.ends_at,
        frozenset(row.tags),
    )


def eligible(db, a, b):
    if (
        not active(db, a)
        or not active(db, b)
        or a.user_id == b.user_id
        or blocked(db, a.user_id, b.user_id)
    ):
        return False
    return (
        max(a.starts_at, b.starts_at) < min(a.ends_at, b.ends_at)
        and distance_m(availability(a), availability(b)) <= min(a.radius_m, b.radius_m)
        and (not a.tags or not b.tags or bool(set(a.tags) & set(b.tags)))
    )


def pair(db, row):
    return db.get(Open, row.open_a_id), db.get(Open, row.open_b_id)


def members(db, row):
    a, b = pair(db, row)
    return {a.user_id, b.user_id}


def card(db, row, viewer):
    a, b = pair(db, row)
    if viewer not in {a.user_id, b.user_id}:
        missing("Overlap")
    data = {
        "id": str(row.id),
        "version": row.version,
        "state": row.state,
        "own_decision": row.decision_a if viewer == a.user_id else row.decision_b,
    }
    if row.state == "hello":
        if row.hello_expires_at <= now():
            return None
        other = db.get(User, b.user_id if viewer == a.user_id else a.user_id)
        data.update(
            room_id=str(row.id),
            expires_at=row.hello_expires_at,
            extended=row.extended,
            other={"id": str(other.id), "name": other.display_name},
        )
    elif (
        row.state != "passed"
        and row.deliver_after <= now()
        and eligible(db, a, b)
        and density(db, a if viewer == a.user_id else b)
    ):
        metres = distance_m(availability(a), availability(b))
        data.update(
            starts_at=max(a.starts_at, b.starts_at),
            ends_at=min(a.ends_at, b.ends_at),
            distance_band="nearby" if metres <= 1000 else "in_your_area",
            tags=sorted(set(a.tags) & set(b.tags)),
        )
    else:
        return None
    return data


def change(db, row):
    emit(db, members(db, row), "v2.overlap", row.id)


def handle(db, settings, user, name, data):
    if name == "discovery.plans":
        probe = Availability(
            str(user.id), data.latitude, data.longitude, data.radius_m, 0, 1, frozenset()
        )
        candidates = []
        for plan in db.exec(
            select(Plan).where(
                Plan.visibility == "public",
                Plan.status == "active",
                Plan.archived.is_(False),
                Plan.starts_at > now(),
            )
        ).all():
            state = plan
            host = db.get(User, plan.host_id)
            if (
                host.deleted_at is not None
                or host.paused_at is not None
                or blocked(db, user.id, host.id)
            ):
                continue
            if plan.latitude is None or plan.longitude is None:
                continue
            count = len(db.exec(select(Participant).where(Participant.plan_id == plan.id)).all())
            if count >= state.capacity or (data.tags and not set(data.tags) & set(state.tags)):
                continue
            area = Availability(
                str(plan.host_id),
                plan.latitude,
                plan.longitude,
                1,
                plan.starts_at,
                plan.ends_at,
                frozenset(),
            )
            distance = distance_m(probe, area)
            if distance > data.radius_m:
                continue
            overlap = 0
            if data.starts_at:
                overlap = min(plan.ends_at, int(data.ends_at.timestamp())) - max(
                    plan.starts_at, int(data.starts_at.timestamp())
                )
                if overlap <= 0:
                    continue
            candidates.append((-overlap, distance, plan.starts_at, str(plan.id), plan))
        candidates.sort(key=lambda c: c[:4])
        return {
            "items": [
                safe_plan(db, p)
                | {
                    "distance_m": round(distance),
                    "reasons": ["within_your_area"]
                    + (["fits_your_time"] if data.starts_at else []),
                }
                for _, distance, _, _, p in candidates[: data.limit]
            ]
        }
    if name == "open.list":
        statement = select(Open).where(Open.user_id == user.id)
        if data.after:
            statement = statement.where(Open.id > data.after)
        rows = db.exec(statement.order_by(Open.id).limit(data.limit + 1)).all()
        return {
            "items": [own_view(o) for o in rows[: data.limit]],
            "next_after": str(rows[data.limit - 1].id) if len(rows) > data.limit else None,
        }
    if name == "overlap.list":
        own = db.get(Open, data.open_id)
        if own is None or own.user_id != user.id:
            missing("Open")
        candidates = [
            o
            for o in db.exec(select(Open).where(Open.user_id != user.id)).all()
            if eligible(db, own, o)
        ]
        if len({o.user_id for o in candidates}) < 3:
            return {"items": [], "state": "insufficient_density"}
        candidates.sort(
            key=lambda o: (
                -(min(own.ends_at, o.ends_at) - max(own.starts_at, o.starts_at)),
                distance_m(availability(own), availability(o)),
                str(o.id),
            )
        )
        cards = []
        for other in candidates:
            a, b = sorted([own.id, other.id], key=str)
            row = db.exec(
                select(Overlap).where(Overlap.open_a_id == a, Overlap.open_b_id == b)
            ).first()
            if row is None:
                row = Overlap(
                    open_a_id=a,
                    open_b_id=b,
                    deliver_after=now() + secrets.randbelow(settings.match_jitter_seconds + 1),
                )
                db.add(row)
                db.flush()
            if row.state != "passed" and row.deliver_after <= now():
                cards.append(card(db, row, user.id))
        return {"items": cards[: data.limit], "state": "ready"}
    if name.startswith("open."):
        if name == "open.create":
            if user.paused_at is not None:
                raise AppError("forbidden", "Resume your profile before opening", 403)
            existing = db.exec(
                select(Open).where(
                    Open.user_id == user.id, Open.state == "active", Open.expires_at > now()
                )
            ).first()
            if existing:
                raise AppError("capacity_reached", "Close your active Open first", 409)
            if db.get(Open, data.open_id):
                raise AppError("action_conflict", "Open ID already exists", 409)
            row = Open(
                id=data.open_id,
                user_id=user.id,
                latitude=data.latitude,
                longitude=data.longitude,
                radius_m=data.radius_m,
                starts_at=int(data.starts_at.timestamp()),
                ends_at=int(data.ends_at.timestamp()),
                expires_at=min(int(data.ends_at.timestamp()), now() + 86400),
                tags=data.tags,
            )
            if row.ends_at <= now() or row.starts_at > now() + 86400:
                raise AppError("invalid_input", "Open must begin within the next day")
            db.add(row)
        else:
            row = db.get(Open, data.open_id)
            if row is None or row.user_id != user.id:
                missing("Open")
            version(row, data.expected_version)
            if name == "open.close":
                row.state = "closed"
            else:
                if not active(db, row) or data.ends_at.timestamp() <= now():
                    raise AppError("expired", "Open expired", 409)
                row.latitude, row.longitude, row.radius_m = (
                    data.latitude,
                    data.longitude,
                    data.radius_m,
                )
                row.starts_at, row.ends_at = (
                    int(data.starts_at.timestamp()),
                    int(data.ends_at.timestamp()),
                )
                row.tags = data.tags
                row.expires_at = min(row.expires_at, row.ends_at)
            row.version += 1
        db.flush()
        emit(db, {user.id}, "v2.open", row.id)
        for overlap in db.exec(
            select(Overlap).where((Overlap.open_a_id == row.id) | (Overlap.open_b_id == row.id))
        ).all():
            change(db, overlap)
        return own_view(row)
    row = db.get(Overlap, data.overlap_id)
    if row is None or user.id not in members(db, row):
        missing("Overlap")
    a, b = pair(db, row)
    if blocked(db, a.user_id, b.user_id):
        missing("Overlap")
    if name == "overlap.respond":
        if row.deliver_after > now() or not eligible(db, a, b) or row.state == "passed":
            raise AppError("expired", "Overlap is no longer eligible", 409)
        version(row, data.expected_version)
        if row.state == "hello":
            return card(db, row, user.id)
        if user.id == a.user_id:
            row.decision_a = data.choice
        else:
            row.decision_b = data.choice
        if data.choice == "pass":
            row.state = "passed"
        elif row.decision_a == row.decision_b == "hi":
            row.state, row.hello_expires_at = "hello", now() + 86400
        row.version += 1
    else:
        if row.state != "hello" or row.hello_expires_at <= now():
            raise AppError("expired", "Hello expired", 409)
        if name == "hello.plan.create" and row.converted_plan_id:
            return {"plan_id": str(row.converted_plan_id)}
        version(row, data.expected_version)
        if name == "hello.extend":
            if row.extended:
                raise AppError("version_conflict", "Hello already extended", 409)
            row.extended, row.hello_expires_at = True, row.hello_expires_at + 48 * 3600
        else:
            if (
                data.plan.circle_id
                or data.plan.circle_ids
                or not set(data.plan.invitee_ids) <= members(db, row)
            ):
                raise AppError("invalid_input", "Hello conversion uses only the mutual pair")
            result = plan_create(db, user.id, data.plan)
            row.converted_plan_id = UUID(result["id"])
        row.version += 1
    db.flush()
    change(db, row)
    return (
        card(db, row, user.id)
        if name != "hello.plan.create"
        else {"plan_id": str(row.converted_plan_id)}
    )


def own_view(row):
    return {
        "id": str(row.id),
        "latitude": row.latitude,
        "longitude": row.longitude,
        "radius_m": row.radius_m,
        "starts_at": row.starts_at,
        "ends_at": row.ends_at,
        "expires_at": row.expires_at,
        "tags": row.tags,
        "state": row.state,
        "version": row.version,
    }


def density(db, own):
    return (
        len(
            {
                other.user_id
                for other in db.exec(select(Open).where(Open.user_id != own.user_id)).all()
                if eligible(db, own, other)
            }
        )
        >= 3
    )
