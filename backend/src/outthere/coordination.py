"""Shared decision cards, relational votes/claims and immutable closed poll results."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field as DBField
from sqlmodel import SQLModel, select

from outthere.contracts import Input
from outthere.errors import AppError
from outthere.events import emit
from outthere.models import Job, Participant, now
from outthere.product import editable, missing, plan_access, version


class Artifact(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("plan_id", "source_message_id"),)
    id: UUID = DBField(primary_key=True)
    plan_id: UUID = DBField(foreign_key="plan.id", index=True)
    creator_id: UUID = DBField(foreign_key="user.id")
    kind: str
    data: dict = DBField(sa_column=Column(JSON, nullable=False))
    source_message_id: UUID | None = None
    pinned: bool = False
    state: str = "active"
    closes_at: int | None = DBField(default=None, index=True)
    version: int = 1


class PersonalPoint(SQLModel, table=True):
    artifact_id: UUID = DBField(foreign_key="artifact.id", primary_key=True)
    latitude: float
    longitude: float
    captured_at: int
    expires_at: int = DBField(index=True)


class ArtifactResponse(SQLModel, table=True):
    artifact_id: UUID = DBField(foreign_key="artifact.id", primary_key=True)
    user_id: UUID = DBField(foreign_key="user.id", primary_key=True)
    value: str
    version: int = 1


class BringClaim(SQLModel, table=True):
    artifact_id: UUID = DBField(foreign_key="artifact.id", primary_key=True)
    item_id: UUID = DBField(primary_key=True)
    user_id: UUID | None = DBField(default=None, foreign_key="user.id")
    version: int = 1


class Note(Input):
    kind: Literal["note"]
    text: str = Field(min_length=1, max_length=4000)


class Option(Input):
    option_id: UUID
    label: str = Field(min_length=1, max_length=100)


class Poll(Input):
    kind: Literal["poll"]
    question: str = Field(min_length=1, max_length=240)
    options: list[Option] = Field(min_length=2, max_length=6)
    closes_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def unique(self):
        if len({o.option_id for o in self.options}) != len(self.options):
            raise ValueError("Duplicate options")
        return self


class Location(Input):
    kind: Literal["location"]
    label: str = Field(min_length=1, max_length=240)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class PersonalLocation(Input):
    kind: Literal["personal_location"]
    label: str = Field(min_length=1, max_length=240)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    captured_at: AwareDatetime
    expires_in_seconds: int = Field(default=900, ge=60, le=3600)


class BringItem(Input):
    item_id: UUID
    label: str = Field(min_length=1, max_length=100)


class Bring(Input):
    kind: Literal["bring"]
    items: list[BringItem] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique(self):
        if len({o.item_id for o in self.items}) != len(self.items):
            raise ValueError("Duplicate items")
        return self


Data = Annotated[Note | Poll | Location | PersonalLocation | Bring, Field(discriminator="kind")]


class PlanId(Input):
    plan_id: UUID


class Create(PlanId):
    artifact_id: UUID
    data: Data


class Edit(PlanId):
    artifact_id: UUID
    expected_version: int = Field(ge=1)


class Update(Edit):
    data: Data


class Respond(PlanId):
    artifact_id: UUID
    expected_version: int = Field(ge=0)
    option_id: UUID | None = None
    item_id: UUID | None = None
    release: bool = False
    artifact_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def one_response(self):
        if sum(v is not None for v in [self.option_id, self.item_id, self.artifact_version]) != 1:
            raise ValueError("Supply exactly one response type")
        if self.release and self.item_id is None:
            raise ValueError("Only bring claims can be released")
        return self


class Pin(PlanId):
    artifact_id: UUID
    expected_version: int | None = Field(default=None, ge=1)
    source_message_id: UUID | None = None


class MeetingSet(Edit):
    confirm_personal: bool = False
    expected_plan_version: int = Field(ge=1)


CONTRACTS = {
    "artifact.point.get": ("query", Edit),
    "artifact.list": ("query", PlanId),
    "artifact.create": ("command", Create),
    "artifact.update": ("command", Update),
    "artifact.delete": ("command", Edit),
    "artifact.respond": ("command", Respond),
    "artifact.pin": ("command", Pin),
    "artifact.unpin": ("command", Edit),
    "poll.close": ("command", Edit),
    "plan.meeting.set": ("command", MeetingSet),
    "wrap.get": ("query", PlanId),
}


def change(db, row):
    users = set(
        db.exec(select(Participant.user_id).where(Participant.plan_id == row.plan_id)).all()
    )
    emit(db, users, "v2.artifact", row.id)
    key = f"artifact.notify:{row.id}:{row.version}"
    if db.exec(select(Job).where(Job.unique_key == key)).first() is None:
        db.add(
            Job(
                kind="artifact.notify",
                entity_id=row.id,
                unique_key=key,
                safe_payload={"version": row.version},
                run_at=now(),
            )
        )


def access(db, user_id, plan_id, artifact_id):
    plan = plan_access(db, user_id, plan_id)
    row = db.get(Artifact, artifact_id)
    from outthere.safety import blocked

    if (
        row is None
        or row.plan_id != plan.id
        or row.state in {"deleted", "expired"}
        or blocked(db, user_id, row.creator_id)
    ):
        missing("Artifact")
    return plan, row


def tally(db, row):
    counts = {o["option_id"]: 0 for o in row.data["options"]}
    for response in db.exec(
        select(ArtifactResponse).where(ArtifactResponse.artifact_id == row.id)
    ).all():
        if response.value in counts:
            counts[response.value] += 1
    return counts


def close(db, row, cancelled=False):
    if row.kind != "poll" or row.state != "active":
        return
    counts = tally(db, row)
    top = max(counts.values())
    winners = [key for key, value in counts.items() if value == top] if top else []
    result = (
        "cancelled"
        if cancelled
        else "no_votes"
        if not top
        else "winner"
        if len(winners) == 1
        else "tied"
    )
    row.data = row.data | {"counts": counts, "result": result, "winners": winners}
    row.state, row.pinned, row.version = "closed", True, row.version + 1
    change(db, row)


def projection(db, row, user_id):
    response = db.get(ArtifactResponse, (row.id, user_id))
    data = dict(row.data)
    if row.kind == "poll" and row.state == "active":
        data["counts"] = tally(db, row)
    claims = []
    if row.kind == "bring":
        claims = [
            {
                "item_id": str(c.item_id),
                "user_id": str(c.user_id) if c.user_id else None,
                "version": c.version,
            }
            for c in db.exec(
                select(BringClaim)
                .where(BringClaim.artifact_id == row.id)
                .order_by(BringClaim.item_id)
            ).all()
        ]
    return {
        "id": str(row.id),
        "plan_id": str(row.plan_id),
        "kind": row.kind,
        "creator_id": str(row.creator_id),
        "data": data,
        "pinned": row.pinned,
        "state": row.state,
        "version": row.version,
        "closes_at": row.closes_at,
        "own_response": {"value": response.value, "version": response.version}
        if response
        else None,
        "claims": claims,
    }


def listing(db, user_id, plan_id):
    from outthere.safety import blocked

    plan_access(db, user_id, plan_id)
    return {
        "items": [
            projection(db, row, user_id)
            for row in db.exec(
                select(Artifact)
                .where(Artifact.plan_id == plan_id, Artifact.state.notin_(["deleted", "expired"]))
                .order_by(Artifact.id)
            ).all()
            if not blocked(db, user_id, row.creator_id)
        ]
    }


def handle(db, user, name, data):
    plan = plan_access(db, user.id, data.plan_id)
    if name == "artifact.point.get":
        _, artifact = access(db, user.id, data.plan_id, data.artifact_id)
        version(artifact, data.expected_version)
        point = db.get(PersonalPoint, artifact.id)
        if point is None or point.expires_at <= now():
            raise AppError("expired", "Personal location expired", 409)
        return {
            "artifact_id": str(artifact.id),
            "latitude": point.latitude,
            "longitude": point.longitude,
            "captured_at": point.captured_at,
            "expires_at": point.expires_at,
        }
    if name in {"artifact.list", "wrap.get"}:
        items = listing(db, user.id, plan.id)
        if name == "wrap.get":
            from outthere.media import Album, AlbumGrant
            from outthere.product import plan_projection
            from outthere.safety import blocked

            albums = db.exec(
                select(Album)
                .join(AlbumGrant)
                .where(
                    Album.plan_id == plan.id,
                    AlbumGrant.user_id == user.id,
                    Album.state == "active",
                )
                .order_by(Album.id)
                .limit(100)
            ).all()
            return {
                "plan": plan_projection(db, plan),
                "decisions": items["items"],
                "albums": [
                    {"id": str(album.id), "title": album.title, "version": album.version}
                    for album in albums
                    if not blocked(db, user.id, album.creator_id)
                ],
            }
        return items
    editable(db, plan)
    if name == "artifact.create":
        if db.get(Artifact, data.artifact_id):
            raise AppError("action_conflict", "Artifact ID already exists", 409)
        deadline = None
        if data.data.kind == "poll":
            deadline = (
                int(data.data.closes_at.timestamp()) if data.data.closes_at else plan.starts_at
            )
            if deadline <= now() or deadline > plan.ends_at + 86400:
                raise AppError(
                    "invalid_input", "Poll deadline must be within the plan room lifetime"
                )
        row = Artifact(
            id=data.artifact_id,
            plan_id=plan.id,
            creator_id=user.id,
            kind=data.data.kind,
            data=data.data.model_dump(mode="json"),
            closes_at=deadline,
        )
        if data.data.kind == "personal_location":
            captured = int(data.data.captured_at.timestamp())
            if not now() - 300 <= captured <= now() + 60:
                raise AppError("expired", "Capture a current location", 409)
            row.kind = "location"
            row.data = {"kind": "location", "personal": True, "label": data.data.label}
            row.closes_at = min(now() + data.data.expires_in_seconds, plan.ends_at + 86400)
            db.add(row)
            db.flush()
            db.add(
                PersonalPoint(
                    artifact_id=row.id,
                    latitude=data.data.latitude,
                    longitude=data.data.longitude,
                    captured_at=captured,
                    expires_at=row.closes_at,
                )
            )
        else:
            db.add(row)
    elif name == "artifact.pin" and data.source_message_id:
        from outthere.delivery import DeliveryEvent

        existing = db.exec(
            select(Artifact).where(
                Artifact.plan_id == plan.id, Artifact.source_message_id == data.source_message_id
            )
        ).first()
        if existing:
            return projection(db, existing, user.id)
        source = db.exec(
            select(DeliveryEvent)
            .where(
                DeliveryEvent.message_id == data.source_message_id, DeliveryEvent.room_id == plan.id
            )
            .with_for_update()
        ).first()
        if source is None or source.expires_at <= now():
            raise AppError("expired", "Source message expired; create a standalone note", 409)
        if source.payload["kind"] not in {"text", "link"}:
            raise AppError("invalid_input", "Only text and links can become notes")
        if db.get(Artifact, data.artifact_id):
            raise AppError("action_conflict", "Artifact ID already exists", 409)
        text = source.payload.get("text") or source.payload.get("url")
        row = Artifact(
            id=data.artifact_id,
            plan_id=plan.id,
            creator_id=user.id,
            kind="note",
            data={"kind": "note", "text": text},
            source_message_id=data.source_message_id,
            pinned=True,
        )
        db.add(row)
    else:
        _, row = access(db, user.id, plan.id, data.artifact_id)
        if name == "artifact.respond":
            if row.state != "active" or (row.closes_at is not None and row.closes_at <= now()):
                raise AppError("expired", "This decision is closed", 409)
            if row.kind == "bring" and data.item_id is not None:
                if str(data.item_id) not in {i["item_id"] for i in row.data["items"]}:
                    raise AppError("invalid_input", "Unknown item")
                claim = db.get(BringClaim, (row.id, data.item_id))
                if (claim.version if claim else 0) != data.expected_version:
                    raise AppError("version_conflict", "Refresh claim", 409)
                if claim is None:
                    claim = BringClaim(artifact_id=row.id, item_id=data.item_id, user_id=user.id)
                    db.add(claim)
                else:
                    if claim.user_id is not None and (
                        not data.release or user.id not in {claim.user_id, plan.host_id}
                    ):
                        raise AppError("version_conflict", "Item already claimed", 409)
                    claim.user_id, claim.version = (
                        None if data.release else user.id,
                        claim.version + 1,
                    )
            else:
                if row.kind == "poll" and data.option_id is not None:
                    if str(data.option_id) not in {o["option_id"] for o in row.data["options"]}:
                        raise AppError("invalid_input", "Unknown poll option")
                    value = str(data.option_id)
                elif row.kind == "location" and data.artifact_version == row.version:
                    value = str(data.artifact_version)
                else:
                    raise AppError("invalid_input", "Response does not match current artifact")
                response = db.get(ArtifactResponse, (row.id, user.id))
                if (response.version if response else 0) != data.expected_version:
                    raise AppError("version_conflict", "Refresh your response", 409)
                if response is None:
                    db.add(ArtifactResponse(artifact_id=row.id, user_id=user.id, value=value))
                else:
                    response.value, response.version = value, response.version + 1
        else:
            if user.id not in {row.creator_id, plan.host_id}:
                raise AppError("forbidden", "Only creator or host can edit decisions", 403)
            if data.expected_version is None:
                raise AppError("invalid_input", "Expected version required")
            version(row, data.expected_version)
            if name == "poll.close":
                if row.kind != "poll":
                    raise AppError("invalid_input", "This artifact is not a poll")
                close(db, row)
                return projection(db, row, user.id)
            if name == "plan.meeting.set":
                if user.id != plan.host_id or row.kind != "location":
                    raise AppError("forbidden", "Host must select a shared location", 403)
                if row.data.get("personal"):
                    point = db.get(PersonalPoint, row.id)
                    if not data.confirm_personal or point is None or point.expires_at <= now():
                        raise AppError("invalid_input", "Confirm an unexpired personal point")
                    row.data = {
                        "kind": "location",
                        "label": row.data["label"],
                        "latitude": point.latitude,
                        "longitude": point.longitude,
                    }
                    row.closes_at = None
                    db.delete(point)
                version(plan, data.expected_plan_version)
                plan.meeting_artifact_id = row.id
                plan.version += 1
                emit(
                    db,
                    set(
                        db.exec(
                            select(Participant.user_id).where(Participant.plan_id == plan.id)
                        ).all()
                    ),
                    "v2.plan",
                    plan.id,
                )
            elif name == "artifact.update":
                if (
                    row.data.get("personal")
                    or row.kind != data.data.kind
                    or row.kind in {"poll", "bring"}
                ):
                    raise AppError("invalid_input", "Poll options and bring lists are immutable")
                row.data = data.data.model_dump(mode="json")
                if plan.meeting_artifact_id == row.id:
                    plan.version += 1
                    emit(
                        db,
                        set(
                            db.exec(
                                select(Participant.user_id).where(Participant.plan_id == plan.id)
                            ).all()
                        ),
                        "v2.plan",
                        plan.id,
                    )
            elif name == "artifact.delete":
                if plan.meeting_artifact_id == row.id:
                    plan.meeting_artifact_id = None
                    plan.version += 1
                    emit(
                        db,
                        set(
                            db.exec(
                                select(Participant.user_id).where(Participant.plan_id == plan.id)
                            ).all()
                        ),
                        "v2.plan",
                        plan.id,
                    )
                point = db.get(PersonalPoint, row.id)
                if point:
                    db.delete(point)
                row.state = "deleted"
            else:
                row.pinned = name == "artifact.pin"
            row.version += 1
    db.flush()
    change(db, row)
    return projection(db, row, user.id)


def cleanup(db):
    for point in db.exec(
        select(PersonalPoint).where(PersonalPoint.expires_at <= now()).with_for_update()
    ).all():
        row = db.get(Artifact, point.artifact_id)
        row.state, row.version = "expired", row.version + 1
        db.delete(point)
        change(db, row)
    for row in db.exec(
        select(Artifact)
        .where(Artifact.kind == "poll", Artifact.state == "active", Artifact.closes_at <= now())
        .with_for_update()
    ).all():
        close(db, row)


def notify(db, job):
    from outthere.delivery import DeliveryEvent, DeliveryTarget
    from outthere.models import Device, Plan
    from outthere.safety import blocked

    row = db.get(Artifact, job.entity_id)
    if row is None:
        return
    plan = db.get(Plan, row.plan_id)
    expires = min(now() + 7 * 86400, plan.ends_at + 86400)
    if expires <= now():
        return
    plan.message_seq += 1
    event = DeliveryEvent(
        room_id=plan.id,
        seq=plan.message_seq,
        message_id=row.id,
        sender_id=row.creator_id,
        kind="artifact.changed",
        payload={
            "plan_id": str(plan.id),
            "artifact_id": str(row.id),
            "version": row.version,
            "change": row.state,
        },
        expires_at=expires,
    )
    db.add(event)
    db.flush()
    users = select(Participant.user_id).where(Participant.plan_id == plan.id)
    for device in db.exec(
        select(Device).where(Device.user_id.in_(users), Device.revoked_at.is_(None))
    ).all():
        if not blocked(db, row.creator_id, device.user_id):
            db.add(DeliveryTarget(event_id=event.id, device_id=device.id))
