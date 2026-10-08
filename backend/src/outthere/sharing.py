"""Revocable, scoped share invitations; tokens never grant chat/media/finance access."""

import hashlib
import secrets
from uuid import UUID, uuid4

from pydantic import Field
from sqlmodel import Field as DBField
from sqlmodel import SQLModel

from outthere.contracts import Input
from outthere.errors import AppError
from outthere.models import Plan, now
from outthere.product import editable, missing, plan_access, safe_plan


class ShareLink(SQLModel, table=True):
    id: UUID = DBField(default_factory=uuid4, primary_key=True)
    owner_id: UUID = DBField(foreign_key="user.id")
    plan_id: UUID = DBField(foreign_key="plan.id", index=True)
    token_hash: str = DBField(unique=True, index=True)
    expires_at: int = DBField(index=True)
    revoked_at: int | None = None


class Create(Input):
    plan_id: UUID
    expires_in_seconds: int = Field(default=86400, ge=60, le=7 * 86400)


class Revoke(Input):
    share_id: UUID


class Resolve(Input):
    share_id: UUID
    token: str = Field(min_length=32, max_length=128)


CONTRACTS = {
    "plan.share.create": ("command", Create),
    "plan.share.revoke": ("command", Revoke),
    "plan.share.resolve": ("query", Resolve),
    "plan.share.join": ("command", Resolve),
}


def handle(db, user, name, data):
    if name == "plan.share.create":
        plan = plan_access(db, user.id, data.plan_id, host=True)
        editable(db, plan)
        if plan.starts_at <= now():
            raise AppError("expired", "Plan invitations are closed", 409)
        token = secrets.token_urlsafe(32)
        row = ShareLink(
            owner_id=user.id,
            plan_id=plan.id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=min(plan.starts_at, now() + data.expires_in_seconds),
        )
        db.add(row)
        return {"share_id": str(row.id), "token": token, "expires_at": row.expires_at}
    row = db.get(ShareLink, data.share_id)
    if row is None:
        missing("Share")
    if name == "plan.share.revoke":
        plan_access(db, user.id, row.plan_id, host=True)
        row.revoked_at = now()
        return {"revoked": True}
    if (
        row.revoked_at is not None
        or row.expires_at <= now()
        or row.token_hash != hashlib.sha256(data.token.encode()).hexdigest()
    ):
        missing("Share")
    plan = db.get(Plan, row.plan_id)
    from outthere.safety import blocked

    if blocked(db, user.id, plan.host_id):
        missing("Share")
    editable(db, plan)
    if name == "plan.share.join":
        from outthere.events import emit
        from outthere.product_models import PlanInvitation

        invitation = db.get(PlanInvitation, (plan.id, user.id))
        if invitation is None:
            invitation = PlanInvitation(plan_id=plan.id, user_id=user.id, expires_at=plan.starts_at)
            db.add(invitation)
        if invitation.status in {"removed", "declined"}:
            raise AppError("forbidden", "Ask the host for a new invitation", 403)
        invitation.status = "requested"
        emit(db, {user.id, plan.host_id}, "v2.plan", plan.id)
        return {"plan_id": str(plan.id), "approval_state": "requested"}
    return safe_plan(db, plan)
