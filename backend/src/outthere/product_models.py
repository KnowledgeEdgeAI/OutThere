"""V2 shared planning and bounded sync records."""

from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


class PlanCircle(SQLModel, table=True):
    plan_id: UUID = Field(foreign_key="plan.id", primary_key=True)
    circle_id: UUID = Field(foreign_key="circle.id", primary_key=True)


class PlanInvitation(SQLModel, table=True):
    plan_id: UUID = Field(foreign_key="plan.id", primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", primary_key=True, index=True)
    status: str = "invited"
    expires_at: int


class PlanStop(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("plan_id", "position"),)
    id: UUID = Field(primary_key=True)
    plan_id: UUID = Field(foreign_key="plan.id", index=True)
    position: int
    label: str
    latitude: float | None = None
    longitude: float | None = None
    place_id: str | None = None
    arrival_at: int | None = None


class Arrival(SQLModel, table=True):
    plan_id: UUID = Field(foreign_key="plan.id", primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", primary_key=True)
    state: str
    version: int = 1


class SyncState(SQLModel, table=True):
    user_id: UUID = Field(foreign_key="user.id", primary_key=True)
    epoch: int = 1
    low_water: int = 0


class Snapshot(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    device_id: UUID = Field(foreign_key="device.id", index=True)
    cursor: int
    epoch: int
    expires_at: int = Field(index=True)
    items: list = Field(sa_column=Column(JSON, nullable=False))
