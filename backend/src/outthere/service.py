import hashlib
import json
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlmodel import select

from outthere.auth import authenticate
from outthere.contracts import (
    RSVP,
    CircleCreate,
    CircleInviteCreate,
    CircleJoin,
    Envelope,
    History,
    MessageSend,
    Page,
    PlanCreate,
    PlanGet,
)
from outthere.db import transaction
from outthere.errors import AppError
from outthere.models import (
    Change,
    Circle,
    CircleInvite,
    Membership,
    Message,
    Participant,
    Plan,
    Receipt,
    User,
    now,
)
from outthere.people import circle_view, create_circle, invite_member, join_circle
from outthere.plans import accessible_plan, create_plan, plan_view, set_rsvp
from outthere.rooms import message_view, send_message

COMMANDS = {
    "circle.create": (CircleCreate, create_circle),
    "circle.invite": (CircleInviteCreate, invite_member),
    "circle.join": (CircleJoin, join_circle),
    "plan.create": (PlanCreate, create_plan),
    "plan.rsvp": (RSVP, set_rsvp),
    "message.send": (MessageSend, send_message),
}


def validate(model, payload):
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        # Validation replies never echo submitted tokens or message text.
        fields = ", ".join(".".join(map(str, e["loc"])) or "payload" for e in exc.errors())
        raise AppError("invalid_payload", f"Check these fields: {fields}", 422) from exc


def replay(receipt: Receipt, request_hash: str):
    if receipt.request_hash != request_hash:
        raise AppError("action_conflict", "This action ID belongs to a different request", 409)
    return receipt.result


def command(engine: Engine, token: str, request: Envelope) -> dict:
    if request.name not in COMMANDS or request.action_id is None:
        raise AppError("invalid_command", "Known command name and action_id are required")
    model, handler = COMMANDS[request.name]
    payload = validate(model, request.payload)
    canonical = json.dumps([request.name, payload.model_dump(mode="json")], sort_keys=True)
    request_hash = hashlib.sha256(canonical.encode()).hexdigest()
    for attempt in range(3):
        try:
            with transaction(engine, write=True) as db:
                user_id = authenticate(db, token).user_id
                receipt = db.get(Receipt, (user_id, request.action_id))
                if receipt is not None:
                    return replay(receipt, request_hash)
                receipt = Receipt(
                    user_id=user_id,
                    action_id=request.action_id,
                    request_hash=request_hash,
                )
                db.add(receipt)
                db.flush()  # Concurrent requests with the same ID serialize here.
                receipt.result = handler(db, user_id, payload, request.action_id)
                result = receipt.result
            return result  # The acknowledgement can be sent only after commit.
        except IntegrityError as exc:
            with transaction(engine) as db:
                user_id = authenticate(db, token).user_id
                receipt = db.get(Receipt, (user_id, request.action_id))
                if receipt:
                    return replay(receipt, request_hash)
            raise AppError("conflict", "This action conflicts with existing data", 409) from exc
        except DBAPIError as exc:
            code = getattr(exc.orig, "sqlstate", None)
            if code in {"40P01", "40001"} and attempt < 2:
                continue  # Whole transaction rolled back; handlers have no external effects.
            raise
    raise AssertionError("unreachable")


def query(engine: Engine, token: str, request: Envelope) -> dict:
    with transaction(engine) as db:
        user_id = authenticate(db, token).user_id
        if request.name == "me":
            user = db.get(User, user_id)
            return {"id": str(user.id), "display_name": user.display_name}
        if request.name in {"circle.list", "plan.list", "invitation.list"}:
            page = validate(Page, request.payload)
            if request.name == "circle.list":
                statement = (
                    select(Circle)
                    .join(Membership)
                    .where(Membership.user_id == user_id)
                    .order_by(Circle.created_at, Circle.id)
                )

                def render(row):
                    return circle_view(db, row)
            elif request.name == "plan.list":
                statement = (
                    select(Plan)
                    .join(Participant)
                    .where(Participant.user_id == user_id)
                    .order_by(Plan.starts_at, Plan.id)
                )

                def render(row):
                    return plan_view(db, row)
            else:
                statement = (
                    select(Circle)
                    .join(CircleInvite)
                    .where(
                        CircleInvite.user_id == user_id,
                        CircleInvite.accepted_at.is_(None),
                        CircleInvite.expires_at > now(),
                    )
                    .order_by(Circle.id)
                )

                def render(row):
                    return {"circle_id": str(row.id), "name": row.name}

            rows = db.exec(statement.offset(page.offset).limit(page.limit + 1)).all()
            return {
                "items": [render(row) for row in rows[: page.limit]],
                "next_offset": page.offset + page.limit if len(rows) > page.limit else None,
            }
        if request.name == "plan.get":
            data = validate(PlanGet, request.payload)
            return plan_view(db, accessible_plan(db, user_id, data.plan_id))
        if request.name == "message.history":
            data = validate(History, request.payload)
            accessible_plan(db, user_id, data.plan_id)
            statement = select(Message).where(Message.plan_id == data.plan_id)
            if data.before_seq is not None:
                statement = statement.where(Message.seq < data.before_seq)
            rows = db.exec(statement.order_by(Message.seq.desc()).limit(data.limit + 1)).all()
            visible = rows[: data.limit]
            return {
                "items": [message_view(row) for row in reversed(visible)],
                "next_before_seq": visible[-1].seq if len(rows) > data.limit else None,
            }
    raise AppError("invalid_query", "Unknown query")


def project_change(db, user_id: UUID, change: Change) -> dict | None:
    """Hydrate current data after checking current access; never replay stored private payloads."""
    if change.kind == "circle.changed":
        circle = db.get(Circle, change.entity_id)
        if circle and db.get(Membership, (circle.id, user_id)):
            return circle_view(db, circle)
    elif change.kind == "circle.invited":
        invite = db.get(CircleInvite, (change.entity_id, user_id))
        circle = db.get(Circle, change.entity_id)
        if invite and circle and invite.accepted_at is None and invite.expires_at > now():
            return {"circle_id": str(circle.id), "name": circle.name}
    elif change.kind == "plan.changed":
        if db.get(Participant, (change.entity_id, user_id)):
            plan = db.get(Plan, change.entity_id)
            if plan:
                return plan_view(db, plan)
    elif change.kind == "message.created":
        message = db.get(Message, change.entity_id)
        if message and db.get(Participant, (message.plan_id, user_id)):
            return message_view(message)
    return None


def changes(engine: Engine, token: str, cursor: int) -> dict:
    with transaction(engine) as db:
        user_id = authenticate(db, token).user_id
        user = db.get(User, user_id)
        from outthere.product_models import SyncState

        state = db.get(SyncState, user_id)
        if state and cursor < state.low_water:
            raise AppError("invalid_cursor", "Feed history expired; restart with a snapshot", 409)
        if cursor > user.feed_seq:
            raise AppError("invalid_cursor", "Cursor is ahead of this account; restart from zero")
        rows = db.exec(
            select(Change)
            .where(Change.user_id == user_id, Change.seq > cursor)
            .order_by(Change.seq)
            .limit(100)
        ).all()
        events = []
        for row in rows:
            data = project_change(db, user_id, row)
            if data is not None:
                events.append({"seq": row.seq, "kind": row.kind, "data": data})
        return {
            "type": "changes",
            "events": events,
            "cursor": rows[-1].seq if rows else cursor,
            "has_more": len(rows) == 100,
        }
