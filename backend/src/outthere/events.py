from uuid import UUID

from sqlalchemy import update
from sqlmodel import Session

from outthere.models import Change, User


def emit(db: Session, users: set[UUID], kind: str, entity_id: UUID):
    """Per-user counters stay locked through commit, preserving safe replay ordering."""
    for user_id in sorted(users, key=str):
        seq = db.execute(
            update(User)
            .where(User.id == user_id)
            .values(feed_seq=User.feed_seq + 1)
            .returning(User.feed_seq)
        ).scalar_one()
        db.add(Change(user_id=user_id, seq=seq, kind=kind, entity_id=entity_id))
