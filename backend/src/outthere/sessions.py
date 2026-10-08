"""Phone identity boundary and device-bound sessions; no transport dependencies."""

import json
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import update
from sqlmodel import Session, select

from outthere.auth import digest, rotate_tokens
from outthere.errors import AppError
from outthere.models import AuthOperation, AuthSession, Device, User, now
from outthere.settings import Settings
from outthere.v2_contracts import Login, Renewal


def retry_cipher(settings: Settings) -> Fernet:
    try:
        return Fernet(settings.auth_retry_key.get_secret_value().encode())
    except (ValueError, TypeError) as exc:
        raise AppError("provider_unavailable", "Session renewal is not configured", 503) from exc


def profile(user: User) -> dict:
    return {
        "id": str(user.id),
        "name": user.display_name,
        "phone": user.phone,
        "version": user.version,
        "phone_verified_at": None,
        "paused": user.paused_at is not None,
        "dp_media_id": str(user.dp_media_id) if user.dp_media_id else None,
    }


def login(db: Session, settings: Settings, data: Login) -> dict:
    if settings.auth_mode != "unverified_phone":
        raise AppError("provider_unavailable", "Phone sign-in is disabled", 503)
    retry_cipher(settings)  # Fail before creating an account if renewal cannot work.
    user = db.exec(select(User).where(User.phone == data.phone).with_for_update()).first()
    if user is None:
        if data.name is None:
            raise AppError("invalid_input", "Enter a name to create your account")
        user = User(display_name=data.name, phone=data.phone)
        db.add(user)
        db.flush()
    device = db.exec(
        select(Device)
        .where(Device.user_id == user.id, Device.installation_id == data.installation_id)
        .with_for_update()
    ).first()
    if device is None:
        device = Device(
            user_id=user.id, installation_id=data.installation_id, platform=data.platform
        )
        db.add(device)
        db.flush()
    else:
        # Re-login replaces this installation's sessions, never another device's.
        db.exec(
            update(AuthSession).where(AuthSession.device_id == device.id).values(revoked_at=now())
        )
        device.revoked_at = None
        device.platform = data.platform
        device.last_seen_at = now()
    record = AuthSession(
        user_id=user.id,
        device_id=device.id,
        access_hash="",
        refresh_hash="",
        access_expires_at=0,
        refresh_expires_at=now() + settings.refresh_token_seconds,
    )
    result = rotate_tokens(record, settings)
    db.add(record)
    return result | {"device_id": str(device.id), "profile": profile(user)}


def active_device(db: Session, record: AuthSession, device_id: UUID) -> Device:
    device = db.get(Device, device_id)
    if (
        record.device_id != device_id
        or device is None
        or device.user_id != record.user_id
        or device.revoked_at is not None
        or record.revoked_at is not None
        or record.refresh_expires_at <= now()
        or db.get(User, record.user_id).deleted_at is not None
    ):
        raise AppError("unauthenticated", "This device session is no longer active", 401)
    return device


def authenticate(db: Session, token: str, device_id: UUID) -> AuthSession:
    record = db.exec(select(AuthSession).where(AuthSession.access_hash == digest(token))).first()
    if record is None:
        raise AppError("unauthenticated", "Sign in again", 401)
    active_device(db, record, device_id)
    if record.access_expires_at <= now():
        raise AppError("unauthenticated", "Renew your session", 401)
    return record


def renew(db: Session, settings: Settings, data: Renewal) -> dict:
    # Lock device before sessions: revoke, login and renew share this lock order.
    device = db.exec(select(Device).where(Device.id == data.device_id).with_for_update()).first()
    if device is None or device.revoked_at is not None:
        raise AppError("unauthenticated", "Sign in again", 401)
    request_hash = digest(f"{data.device_id}:{data.refresh_token}")
    records = db.exec(
        select(AuthSession)
        .where(AuthSession.device_id == device.id, AuthSession.revoked_at.is_(None))
        .with_for_update()
    ).all()
    for record in records:
        active_device(db, record, device.id)
        operation = db.get(AuthOperation, (record.id, data.renewal_id))
        if operation is not None:
            if operation.request_hash != request_hash:
                raise AppError("action_conflict", "Renewal ID belongs to another request", 409)
            if operation.expires_at <= now():
                raise AppError("unauthenticated", "Renewal retry expired; sign in again", 401)
            try:
                result = json.loads(retry_cipher(settings).decrypt(operation.encrypted_result))
            except InvalidToken as exc:
                raise AppError(
                    "unauthenticated", "Renewal unavailable; sign in again", 401
                ) from exc
            if digest(result["access_token"]) != record.access_hash:
                raise AppError("unauthenticated", "This renewal was superseded", 401)
            return result
        if record.refresh_hash == digest(data.refresh_token):
            result = rotate_tokens(record, settings) | {"device_id": str(device.id)}
            db.add(
                AuthOperation(
                    session_id=record.id,
                    renewal_id=data.renewal_id,
                    request_hash=request_hash,
                    encrypted_result=retry_cipher(settings)
                    .encrypt(json.dumps(result).encode())
                    .decode(),
                    expires_at=min(now() + settings.auth_retry_seconds, record.refresh_expires_at),
                )
            )
            device.last_seen_at = now()
            return result
    raise AppError("unauthenticated", "Sign in again", 401)


def revoke(db: Session, user_id: UUID, device_id: UUID):
    device = db.exec(select(Device).where(Device.id == device_id).with_for_update()).first()
    if device is None or device.user_id != user_id:
        raise AppError("not_found", "Device not found", 404)
    device.revoked_at = now()
    db.exec(update(AuthSession).where(AuthSession.device_id == device.id).values(revoked_at=now()))


def related_profile(db, viewer, target):
    from outthere.models import Membership, Participant
    from outthere.safety import blocked

    user = db.get(User, target)
    if user is None or user.deleted_at is not None or blocked(db, viewer, target):
        raise AppError("not_found", "Profile not found", 404)
    circles = select(Membership.circle_id).where(Membership.user_id == viewer)
    plans = select(Participant.plan_id).where(Participant.user_id == viewer)
    relationship = (
        db.exec(
            select(Membership).where(
                Membership.user_id == target, Membership.circle_id.in_(circles)
            )
        ).first()
        or db.exec(
            select(Participant).where(Participant.user_id == target, Participant.plan_id.in_(plans))
        ).first()
    )
    if not relationship:
        raise AppError("not_found", "Profile not found", 404)
    return profile(user)
