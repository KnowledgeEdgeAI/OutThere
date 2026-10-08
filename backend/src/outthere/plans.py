from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import Session, select

from outthere.contracts import RSVP, PlanCreate
from outthere.errors import AppError
from outthere.events import emit
from outthere.models import Circle, Job, Membership, Participant, Plan, now
from outthere.people import member_ids


def participant_ids(db: Session, plan_id: UUID) -> set[UUID]:
    return set(db.exec(select(Participant.user_id).where(Participant.plan_id == plan_id)).all())


def accessible_plan(db: Session, user_id: UUID, plan_id: UUID, *, lock=False) -> Plan:
    query = select(Plan).where(Plan.id == plan_id)
    if lock:
        query = query.with_for_update()
    plan = db.exec(query).first()
    if plan is None or db.get(Participant, (plan_id, user_id)) is None:
        raise AppError("not_found", "Plan not found", 404)
    return plan


def iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, UTC).isoformat()


def plan_view(db: Session, plan: Plan) -> dict:
    people = db.exec(select(Participant).where(Participant.plan_id == plan.id)).all()
    return {
        "id": str(plan.id),
        "host_id": str(plan.host_id),
        "circle_id": str(plan.circle_id) if plan.circle_id else None,
        "title": plan.title,
        "starts_at": iso(plan.starts_at),
        "ends_at": iso(plan.ends_at),
        "venue_timezone": plan.venue_timezone,
        "place_label": plan.place_label,
        "latitude": plan.latitude,
        "longitude": plan.longitude,
        "version": plan.version,
        "archived": plan.archived,
        "participants": [
            {"user_id": str(p.user_id), "rsvp": p.rsvp, "version": p.version}
            for p in sorted(people, key=lambda p: str(p.user_id))
        ],
    }


def create_plan(db: Session, user_id: UUID, data: PlanCreate, action_id: UUID) -> dict:
    if data.starts_at.timestamp() <= now():
        raise AppError("invalid_time", "Choose a future start time")
    users = {user_id}
    if data.circle_id:
        # Lock the circle so a concurrent join is wholly before or after this audience snapshot.
        circle = db.exec(
            select(Circle).where(Circle.id == data.circle_id).with_for_update()
        ).first()
        if circle is None or db.get(Membership, (circle.id, user_id)) is None:
            raise AppError("not_found", "Circle not found", 404)
        users = member_ids(db, circle.id)
    plan = Plan(
        host_id=user_id,
        circle_id=data.circle_id,
        title=data.title,
        starts_at=int(data.starts_at.timestamp()),
        ends_at=int(data.ends_at.timestamp()),
        venue_timezone=data.venue_timezone,
        place_label=data.place_label,
        latitude=data.latitude,
        longitude=data.longitude,
    )
    db.add(plan)
    db.flush()
    for person in users:
        db.add(
            Participant(
                plan_id=plan.id, user_id=person, rsvp="in" if person == user_id else "maybe"
            )
        )
    db.add(
        Job(
            unique_key=f"plan.archive:{plan.id}",
            kind="plan.archive",
            entity_id=plan.id,
            run_at=plan.ends_at + 86400,
        )
    )
    db.flush()
    emit(db, users, "plan.changed", plan.id)
    return plan_view(db, plan)


def set_rsvp(db: Session, user_id: UUID, data: RSVP, action_id: UUID) -> dict:
    plan = accessible_plan(db, user_id, data.plan_id, lock=True)
    if plan.archived or plan.starts_at <= now():
        raise AppError("plan_locked", "RSVPs are locked after the plan starts", 409)
    person = db.get(Participant, (plan.id, user_id))
    if person.version != data.version:
        raise AppError("version_conflict", "Fetch the plan and review your RSVP", 409)
    person.rsvp = data.rsvp
    person.version += 1
    db.flush()
    emit(db, participant_ids(db, plan.id), "plan.changed", plan.id)
    return plan_view(db, plan)
