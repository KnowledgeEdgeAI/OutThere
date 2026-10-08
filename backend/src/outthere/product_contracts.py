"""Strict v2 planning and sync inputs; shared scheduling values stay in wire units."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from outthere.contracts import Input
from outthere.contracts import PlanCreate as Scheduling


class Page(Input):
    after: UUID | None = None
    limit: int = Field(default=50, ge=1, le=100)


class CircleId(Input):
    circle_id: UUID


class CircleCreate(Input):
    circle_id: UUID
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["social", "work"] = "social"


class CircleEdit(CircleId):
    expected_version: int = Field(ge=1)


class CircleUpdate(CircleEdit):
    name: str = Field(min_length=1, max_length=100)


class CirclePerson(CircleId):
    user_id: UUID


class CircleRole(CirclePerson):
    expected_version: int = Field(ge=1)
    role: Literal["admin", "member"]


class CircleTransfer(CircleEdit):
    user_id: UUID


class Stop(Input):
    stop_id: UUID
    order: int = Field(ge=0, le=49)
    label: str = Field(min_length=1, max_length=240)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    place_id: str | None = Field(default=None, min_length=1, max_length=240)
    arrival_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Supply both coordinates")
        if self.place_id is not None and self.latitude is not None:
            raise ValueError("Provider places use a reference, not stored coordinates")
        return self


class PlanId(Input):
    plan_id: UUID


class PlanCreate(Scheduling):
    plan_id: UUID
    visibility: Literal["private", "public", "link"] = "private"
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    capacity: int = Field(default=15, ge=1, le=100)
    tags: list[str] = Field(default_factory=list, max_length=10)
    circle_ids: list[UUID] = Field(default_factory=list, max_length=15)
    invitee_ids: list[UUID] = Field(default_factory=list, max_length=100)
    stops: list[Stop] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def unique_values(self):
        if len({s.stop_id for s in self.stops}) != len(self.stops):
            raise ValueError("Duplicate stop IDs")
        if sorted(s.order for s in self.stops) != list(range(len(self.stops))):
            raise ValueError("Stop orders must be contiguous from zero")
        scheduled = [
            stop.arrival_at
            for stop in sorted(self.stops, key=lambda stop: stop.order)
            if stop.arrival_at is not None
        ]
        if any(not self.starts_at <= arrival <= self.ends_at for arrival in scheduled):
            raise ValueError("Stop arrivals must be within the plan interval")
        if scheduled != sorted(scheduled):
            raise ValueError("Stop arrivals must be chronological")
        if len(set(self.circle_ids)) != len(self.circle_ids):
            raise ValueError("Duplicate circle IDs")
        if len(set(self.invitee_ids)) != len(self.invitee_ids):
            raise ValueError("Duplicate invitees")
        if len(set(self.tags)) != len(self.tags) or any(not t or len(t) > 40 for t in self.tags):
            raise ValueError("Use unique tags of 1–40 characters")
        return self


class PlanEdit(PlanId):
    expected_version: int = Field(ge=1)


class PlanUpdate(PlanCreate):
    expected_version: int = Field(ge=1)


class PlanPerson(PlanId):
    user_id: UUID


class Rsvp(PlanId):
    expected_version: int = Field(ge=1)
    rsvp: Literal["in", "maybe", "out"]


class ArrivalUpdate(PlanId):
    expected_version: int = Field(ge=0)
    state: Literal["not_started", "on_way", "arrived"]


class SyncPage(Input):
    snapshot_id: UUID
    after: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)


class SyncResume(Input):
    cursor: int = Field(ge=0)
    epoch: int = Field(ge=1)


CONTRACTS = {
    "circle.list": ("query", Page),
    "circle.get": ("query", CircleId),
    "circle.create": ("command", CircleCreate),
    "circle.update": ("command", CircleUpdate),
    "circle.invite": ("command", CirclePerson),
    "circle.invitation.accept": ("command", CircleId),
    "circle.invitation.decline": ("command", CircleId),
    "circle.leave": ("command", CircleId),
    "circle.member.remove": ("command", CirclePerson),
    "circle.member.role": ("command", CircleRole),
    "circle.owner.transfer": ("command", CircleTransfer),
    "circle.sleep": ("command", CircleEdit),
    "circle.wake": ("command", CircleEdit),
    "plan.list": ("query", Page),
    "plan.get": ("query", PlanId),
    "plan.create": ("command", PlanCreate),
    "plan.update": ("command", PlanUpdate),
    "plan.cancel": ("command", PlanEdit),
    "plan.invite": ("command", PlanPerson),
    "plan.join.request": ("command", PlanId),
    "plan.join.approve": ("command", PlanPerson),
    "plan.join.decline": ("command", PlanPerson),
    "plan.leave": ("command", PlanId),
    "plan.member.remove": ("command", PlanPerson),
    "plan.rsvp": ("command", Rsvp),
    "plan.arrival.update": ("command", ArrivalUpdate),
    "sync.start": ("query", Page),
    "sync.page": ("query", SyncPage),
    "sync.resume": ("query", SyncResume),
    "sync.ack": ("command", SyncResume),
}
