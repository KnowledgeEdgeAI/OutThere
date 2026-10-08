from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Exchange(Input):
    invite_token: str = Field(min_length=32, max_length=256)
    display_name: str | None = Field(default=None, min_length=1, max_length=80)


class Refresh(Input):
    refresh_token: str = Field(min_length=32, max_length=256)


class Authenticate(Input):
    type: Literal["auth"]
    access_token: str = Field(min_length=32, max_length=256)
    cursor: int = Field(default=0, ge=0)


class Envelope(Input):
    id: UUID
    type: Literal["command", "query", "ping"]
    name: str = Field(default="", max_length=80)
    action_id: UUID | None = None
    payload: dict = Field(default_factory=dict)


class CircleCreate(Input):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["social", "work"] = "social"


class CircleJoin(Input):
    circle_id: UUID


class CircleInviteCreate(CircleJoin):
    user_id: UUID


class PlanCreate(Input):
    title: str = Field(min_length=1, max_length=160)
    circle_id: UUID | None = None
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    venue_timezone: str = "Asia/Kolkata"
    place_label: str = Field(default="", max_length=240)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("venue_timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Use an IANA timezone, such as Asia/Kolkata") from exc
        return value

    @model_validator(mode="after")
    def valid_interval(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("Plan end must follow its start")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Supply both latitude and longitude")
        return self


class RSVP(Input):
    plan_id: UUID
    rsvp: Literal["in", "maybe", "out"]
    version: int = Field(ge=1)


class MessageSend(Input):
    plan_id: UUID
    body: str = Field(min_length=1, max_length=2000)


class Page(Input):
    offset: int = Field(default=0, ge=0, le=100_000)
    limit: int = Field(default=50, ge=1, le=100)


class PlanGet(Input):
    plan_id: UUID


class History(PlanGet):
    before_seq: int | None = Field(default=None, ge=1)
    limit: int = Field(default=50, ge=1, le=100)


class PlacesSearch(Input):
    query: str = Field(min_length=2, max_length=160)
