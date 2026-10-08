"""Minimal device delivery policy and generic APNs/FCM notifications, without chat bodies."""

import base64
import hashlib
import json
from typing import Literal
from uuid import UUID

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from pydantic import Field, model_validator
from sqlmodel import select

from outthere.contracts import Input
from outthere.errors import AppError
from outthere.models import Device, Job, now


class Register(Input):
    token: str = Field(min_length=16, max_length=4096)
    provider: Literal["apns", "fcm"]
    platform: Literal["ios", "android"]
    enabled_categories: list[Literal["messages", "plans", "ripples", "splits"]] = Field(
        max_length=4
    )

    @model_validator(mode="after")
    def valid(self):
        if len(set(self.enabled_categories)) != len(self.enabled_categories):
            raise ValueError("Duplicate categories")
        if self.provider == "apns" and (
            self.platform != "ios"
            or len(self.token) != 64
            or any(c not in "0123456789abcdefABCDEF" for c in self.token)
        ):
            raise ValueError("APNs requires an iOS device token")
        return self


class Empty(Input):
    pass


CONTRACTS = {
    "device.push.register": ("command", Register),
    "device.push.unregister": ("command", Empty),
}


def handle(db, device, name, data):
    if name.endswith("unregister"):
        device.push_token, device.push_provider, device.push_categories = None, None, []
    else:
        if device.platform != data.platform:
            raise AppError("invalid_input", "Push platform must match this installation")
        # A provider token is bound to one active installation at a time.
        for other in db.exec(
            select(Device).where(Device.push_token == data.token, Device.id != device.id)
        ).all():
            other.push_token, other.push_provider, other.push_categories = None, None, []
        device.push_token, device.push_provider = data.token, data.provider
        device.push_categories = data.enabled_categories
    return {
        "registered": device.push_token is not None,
        "enabled_categories": device.push_categories,
    }


def enqueue(db, device, category, resource_id, unique_key):
    if not device.push_token or category not in device.push_categories:
        return
    if db.exec(select(Job).where(Job.unique_key == unique_key)).first():
        return
    db.add(
        Job(
            kind="push.notify",
            entity_id=resource_id,
            unique_key=unique_key,
            safe_payload={"device_id": str(device.id), "category": category},
            run_at=now() + 30,
        )
    )


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def jwt(header, payload, key, algorithm):
    value = (
        b64(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + b64(json.dumps(payload, separators=(",", ":")).encode())
    )
    private = serialization.load_pem_private_key(key.encode(), password=None)
    if algorithm == "RS256":
        signature = private.sign(value.encode(), padding.PKCS1v15(), hashes.SHA256())
    else:
        der = private.sign(value.encode(), ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return value + "." + b64(signature)


_cache = {}


def notify(settings, device, category, resource_id, transport=None):
    try:
        if device.push_provider == "fcm":
            credentials = json.loads(settings.fcm_service_account.get_secret_value())
            project = credentials["project_id"]
            if not project or any(
                c not in "abcdefghijklmnopqrstuvwxyz0123456789-:" for c in project
            ):
                raise ValueError("Invalid project ID")
            key_hash = hashlib.sha256(credentials["private_key"].encode()).hexdigest()
            cached = _cache.get(key_hash)
            with httpx.Client(timeout=8, transport=transport) as client:
                if not cached or cached[1] <= now():
                    assertion = jwt(
                        {"alg": "RS256", "typ": "JWT"},
                        {
                            "iss": credentials["client_email"],
                            "scope": "https://www.googleapis.com/auth/firebase.messaging",
                            "aud": "https://oauth2.googleapis.com/token",
                            "iat": now(),
                            "exp": now() + 3600,
                        },
                        credentials["private_key"],
                        "RS256",
                    )
                    response = client.post(
                        "https://oauth2.googleapis.com/token",
                        data={
                            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                            "assertion": assertion,
                        },
                    )
                    response.raise_for_status()
                    result = response.json()
                    cached = (result["access_token"], now() + min(int(result["expires_in"]), 3300))
                    _cache[key_hash] = cached
                response = client.post(
                    f"https://fcm.googleapis.com/v1/projects/{project}/messages:send",
                    headers={"Authorization": f"Bearer {cached[0]}"},
                    json={
                        "message": {
                            "token": device.push_token,
                            "notification": {"title": "OutThere", "body": "You have an update"},
                            "data": {"category": category, "resource_id": str(resource_id)},
                            "android": {"collapse_key": category},
                        }
                    },
                )
                if response.status_code == 404 and any(
                    d.get("errorCode") == "UNREGISTERED"
                    for d in response.json().get("error", {}).get("details", [])
                ):
                    return False
                response.raise_for_status()
        elif device.push_provider == "apns":
            key = settings.apns_private_key.get_secret_value()
            if (
                not key
                or not settings.apns_key_id
                or not settings.apns_team_id
                or not settings.apns_topic
            ):
                raise ValueError("APNs is not configured")
            key_hash = hashlib.sha256(key.encode()).hexdigest()
            cached = _cache.get(key_hash)
            if not cached or cached[1] <= now():
                cached = (
                    jwt(
                        {"alg": "ES256", "kid": settings.apns_key_id},
                        {"iss": settings.apns_team_id, "iat": now()},
                        key,
                        "ES256",
                    ),
                    now() + 3300,
                )
                _cache[key_hash] = cached
            host = "api.sandbox.push.apple.com" if settings.apns_sandbox else "api.push.apple.com"
            with httpx.Client(http2=True, timeout=8, transport=transport) as client:
                response = client.post(
                    f"https://{host}/3/device/{device.push_token}",
                    headers={
                        "authorization": f"bearer {cached[0]}",
                        "apns-topic": settings.apns_topic,
                        "apns-push-type": "alert",
                        "apns-collapse-id": category,
                        "apns-expiration": str(now() + 3600),
                    },
                    json={
                        "aps": {"alert": {"title": "OutThere", "body": "You have an update"}},
                        "category": category,
                        "resource_id": str(resource_id),
                    },
                )
                if response.status_code == 410 or (
                    response.status_code == 400
                    and response.json().get("reason")
                    in {"BadDeviceToken", "DeviceTokenNotForTopic"}
                ):
                    return False
                response.raise_for_status()
        else:
            raise ValueError("Unknown provider")
        return True
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise AppError("provider_unavailable", "Push delivery unavailable", 503) from None


def execute(db, settings, job):
    device = db.get(Device, UUID(job.safe_payload["device_id"]))
    category = job.safe_payload["category"]
    if (
        not device
        or device.revoked_at is not None
        or not device.push_token
        or category not in device.push_categories
    ):
        return
    if category == "messages":
        from outthere.delivery import DeliveryEvent, DeliveryTarget, permitted
        from outthere.safety import blocked

        event = db.get(DeliveryEvent, job.entity_id)
        target = db.get(DeliveryTarget, (job.entity_id, device.id))
        if (
            not event
            or event.expires_at <= now()
            or not target
            or target.acknowledged_at is not None
            or target.cancelled_at is not None
            or not permitted(db, device.user_id, event.room_id)
            or blocked(db, event.sender_id, device.user_id)
        ):
            return
    if not notify(settings, device, category, job.entity_id):
        device.push_token, device.push_provider, device.push_categories = None, None, []
