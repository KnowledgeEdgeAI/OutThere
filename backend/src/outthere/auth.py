import hashlib
import secrets
from uuid import UUID

from sqlalchemy import Engine
from sqlmodel import Session, select

from outthere.contracts import Exchange
from outthere.db import transaction
from outthere.errors import AppError
from outthere.models import AuthSession, LoginInvite, User, now
from outthere.settings import Settings


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def create_invite(engine: Engine, user_id: UUID | None = None) -> str:
    token = secrets.token_urlsafe(32)
    with transaction(engine, write=True) as db:
        if user_id is not None and db.get(User, user_id) is None:
            raise AppError("not_found", "Account not found", 404)
        db.add(LoginInvite(token_hash=digest(token), user_id=user_id, expires_at=now() + 86400))
    return token


def rotate_tokens(record: AuthSession, settings: Settings) -> dict:
    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    record.access_hash = digest(access)
    record.refresh_hash = digest(refresh)
    record.access_expires_at = now() + settings.access_token_seconds
    # Refresh rotation never extends the session's absolute lifetime.
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "access_expires_at": record.access_expires_at,
        "refresh_expires_at": record.refresh_expires_at,
        "user_id": str(record.user_id),
    }


def exchange(engine: Engine, settings: Settings, payload: Exchange) -> dict:
    with transaction(engine, write=True) as db:
        invite = db.exec(
            select(LoginInvite)
            .where(LoginInvite.token_hash == digest(payload.invite_token))
            .with_for_update()
        ).first()
        if invite is None or invite.used_at is not None or invite.expires_at <= now():
            raise AppError("invalid_invite", "Invitation is invalid or expired", 401)
        if invite.user_id is None:
            if not payload.display_name:
                raise AppError("display_name_required", "A display name is required")
            user = User(display_name=payload.display_name)
            db.add(user)
            db.flush()
        else:
            user = db.get(User, invite.user_id)
            if user is None:
                raise AppError("invalid_invite", "Invitation is invalid", 401)
        invite.used_at = now()
        record = AuthSession(
            user_id=user.id,
            access_hash="",
            refresh_hash="",
            access_expires_at=0,
            refresh_expires_at=now() + settings.refresh_token_seconds,
        )
        result = rotate_tokens(record, settings)
        db.add(record)
        return result


def refresh(engine: Engine, settings: Settings, token: str) -> dict:
    with transaction(engine, write=True) as db:
        record = db.exec(
            select(AuthSession).where(AuthSession.refresh_hash == digest(token)).with_for_update()
        ).first()
        if (
            record is None
            or record.device_id is not None
            or record.revoked_at
            or record.refresh_expires_at <= now()
        ):
            raise AppError("unauthorized", "Session is invalid or expired", 401)
        return rotate_tokens(record, settings)


def authenticate(db: Session, token: str) -> AuthSession:
    record = db.exec(select(AuthSession).where(AuthSession.access_hash == digest(token))).first()
    if (
        record is None
        or record.device_id is not None
        or record.revoked_at
        or record.access_expires_at <= now()
    ):
        raise AppError("unauthorized", "Sign in or refresh your session", 401)
    return record


def logout(engine: Engine, token: str):
    with transaction(engine, write=True) as db:
        record = authenticate(db, token)
        record.revoked_at = now()
