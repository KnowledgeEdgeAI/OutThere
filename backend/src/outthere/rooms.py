from uuid import UUID

from sqlmodel import Session

from outthere.contracts import MessageSend
from outthere.errors import AppError
from outthere.events import emit
from outthere.models import Message, now
from outthere.plans import accessible_plan, iso, participant_ids


def message_view(message: Message) -> dict:
    return {
        "id": str(message.id),
        "plan_id": str(message.plan_id),
        "sender_id": str(message.sender_id),
        "seq": message.seq,
        "body": message.body,
        "created_at": iso(message.created_at),
    }


def send_message(db: Session, user_id: UUID, data: MessageSend, action_id: UUID) -> dict:
    plan = accessible_plan(db, user_id, data.plan_id, lock=True)
    if plan.archived or plan.ends_at + 86400 <= now():
        raise AppError("room_archived", "This plan room is read-only", 409)
    plan.message_seq += 1
    message = Message(
        plan_id=plan.id,
        sender_id=user_id,
        action_id=action_id,
        seq=plan.message_seq,
        body=data.body,
    )
    db.add(message)
    db.flush()
    emit(db, participant_ids(db, plan.id), "message.created", message.id)
    return message_view(message)
