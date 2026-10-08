import time
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


def now() -> int:
    return int(time.time())


class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    display_name: str
    created_at: int = Field(default_factory=now)
    feed_seq: int = 0
    phone: str | None = Field(default=None, unique=True, index=True)
    paused_at: int | None = None
    deleted_at: int | None = None
    dp_media_id: UUID | None = None
    version: int = 1


class LoginInvite(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    token_hash: str = Field(unique=True, index=True)
    user_id: UUID | None = Field(default=None, foreign_key="user.id")
    expires_at: int
    used_at: int | None = None


class AuthSession(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    access_hash: str = Field(unique=True, index=True)
    refresh_hash: str = Field(unique=True, index=True)
    access_expires_at: int
    refresh_expires_at: int
    revoked_at: int | None = None
    device_id: UUID | None = Field(default=None, foreign_key="device.id", index=True)


class Circle(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(foreign_key="user.id")
    name: str
    kind: str = "social"
    version: int = 1
    sleeping: bool = False
    created_at: int = Field(default_factory=now)


class Membership(SQLModel, table=True):
    role: str = "member"
    circle_id: UUID = Field(foreign_key="circle.id", primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", primary_key=True, index=True)


class CircleInvite(SQLModel, table=True):
    circle_id: UUID = Field(foreign_key="circle.id", primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", primary_key=True, index=True)
    expires_at: int
    accepted_at: int | None = None


class Plan(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    host_id: UUID = Field(foreign_key="user.id")
    circle_id: UUID | None = Field(default=None, foreign_key="circle.id", index=True)
    title: str
    starts_at: int = Field(index=True)
    ends_at: int
    venue_timezone: str
    place_label: str = ""
    latitude: float | None = None
    longitude: float | None = None
    version: int = 1
    message_seq: int = 0
    archived: bool = False
    visibility: str = "private"
    status: str = "active"
    currency: str = "INR"
    capacity: int = 15
    tags: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    meeting_artifact_id: UUID | None = None


class Participant(SQLModel, table=True):
    plan_id: UUID = Field(foreign_key="plan.id", primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", primary_key=True, index=True)
    rsvp: str = "maybe"
    version: int = 1


class Message(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("plan_id", "seq"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    plan_id: UUID = Field(foreign_key="plan.id", index=True)
    sender_id: UUID = Field(foreign_key="user.id")
    action_id: UUID = Field(unique=True)
    seq: int
    body: str
    created_at: int = Field(default_factory=now)


class Receipt(SQLModel, table=True):
    user_id: UUID = Field(foreign_key="user.id", primary_key=True)
    action_id: UUID = Field(primary_key=True)
    request_hash: str
    result: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class Change(SQLModel, table=True):
    user_id: UUID = Field(foreign_key="user.id", primary_key=True)
    seq: int = Field(primary_key=True)
    kind: str
    entity_id: UUID
    created_at: int = Field(default_factory=now)


class Job(SQLModel, table=True):
    __table_args__ = (Index("ix_job_due", "state", "run_at"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    unique_key: str = Field(unique=True)
    kind: str
    entity_id: UUID
    run_at: int
    state: str = "pending"
    attempts: int = 0
    lease_until: int = 0
    lease_token: UUID | None = None
    safe_payload: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class Device(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "installation_id"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    installation_id: UUID
    platform: str
    created_at: int = Field(default_factory=now)
    last_seen_at: int = Field(default_factory=now)
    revoked_at: int | None = None
    acknowledged_cursor: int = 0
    sync_epoch: int = 0
    push_provider: str | None = None
    push_token: str | None = None
    push_categories: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class AuthOperation(SQLModel, table=True):
    session_id: UUID = Field(foreign_key="authsession.id", primary_key=True)
    renewal_id: UUID = Field(primary_key=True)
    request_hash: str
    encrypted_result: str
    expires_at: int = Field(index=True)


class ActionReceipt(SQLModel, table=True):
    user_id: UUID = Field(foreign_key="user.id", primary_key=True)
    action_id: UUID = Field(primary_key=True)
    request_hash: str
    result: dict = Field(sa_column=Column(JSON, nullable=False))
    expires_at: int = Field(index=True)
