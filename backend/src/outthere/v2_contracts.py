"""Strict contracts for the implemented v2 account slice."""

from typing import Literal
from uuid import UUID

import phonenumbers
from pydantic import AwareDatetime, Field, field_validator, model_validator

from outthere.contracts import Input


class Frame(Input):
    v: Literal[2]
    id: UUID
    type: Literal["command", "query"]
    name: str = Field(min_length=1, max_length=80)
    action_id: UUID | None = None
    issued_at: AwareDatetime | None = None
    payload: dict = Field(default_factory=dict)


class Empty(Input):
    pass


class Login(Input):
    phone: str = Field(min_length=8, max_length=40)
    installation_id: UUID
    platform: Literal["ios", "android", "web"]
    name: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("phone")
    @classmethod
    def canonical_phone(cls, value):
        if not value.startswith("+"):
            raise ValueError("Include an explicit country code")
        try:
            number = phonenumbers.parse(value, None)
        except phonenumbers.NumberParseException as exc:
            raise ValueError("Invalid phone format") from exc
        if not phonenumbers.is_possible_number(number):
            raise ValueError("Invalid phone format")
        return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


class Resume(Input):
    access_token: str = Field(min_length=32, max_length=256)
    device_id: UUID


class Renewal(Input):
    refresh_token: str = Field(min_length=32, max_length=256)
    device_id: UUID
    renewal_id: UUID


class DeviceRevoke(Input):
    device_id: UUID


class ProfileGet(Input):
    user_id: UUID | None = None


class ProfileUpdate(Input):
    dp_media_id: UUID | None = None
    name: str = Field(min_length=1, max_length=80)
    expected_version: int = Field(ge=1)


class Dispatch(Input):
    """Enforce mutation intent before handlers or receipt lookup."""

    action_id: UUID
    issued_at: AwareDatetime

    @model_validator(mode="after")
    def valid_action(self):
        if self.action_id.int == 0:
            raise ValueError("Use a unique action ID")
        return self
