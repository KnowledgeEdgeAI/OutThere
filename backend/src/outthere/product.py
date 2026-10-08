"""Transactional shared planning and consistent metadata synchronization."""

from sqlalchemy import delete
from sqlmodel import select

from outthere.errors import AppError
from outthere.events import emit
from outthere.models import (
    Change,
    Circle,
    CircleInvite,
    Job,
    Membership,
    Participant,
    Plan,
    User,
    now,
)
from outthere.people import member_ids
from outthere.plans import iso, participant_ids, plan_view
from outthere.product_models import (
    Arrival,
    PlanCircle,
    PlanInvitation,
    PlanStop,
    Snapshot,
    SyncState,
)


def missing(label="Resource"):
    raise AppError("not_found", f"{label} not found", 404)


def version(row, expected):
    if row.version != expected:
        raise AppError("version_conflict", "Refresh and review this change", 409)


def sync_state(db, user_id):
    row = db.get(SyncState, user_id)
    if row is None:
        row = SyncState(user_id=user_id)
        db.add(row)
        db.flush()
    return row


def invalidate(db, user_id, kind, entity_id):
    sync_state(db, user_id).epoch += 1
    emit(db, {user_id}, kind, entity_id)


def circle_access(db, user_id, circle_id, owner=False):
    row = db.exec(select(Circle).where(Circle.id == circle_id).with_for_update()).first()
    if row is None or db.get(Membership, (circle_id, user_id)) is None:
        missing("Circle")
    if (
        owner
        and row.owner_id != user_id
        and db.get(Membership, (circle_id, user_id)).role != "admin"
    ):
        raise AppError("forbidden", "Only the circle owner can do this", 403)
    return row


def circle_state(db, circle_id):
    return db.get(Circle, circle_id)


def circle_projection(db, row):
    state = circle_state(db, row.id)
    members = sorted(member_ids(db, row.id), key=str)
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "name": row.name,
        "kind": row.kind,
        "version": state.version,
        "sleeping": state.sleeping,
        "members": [
            {
                "user_id": str(u),
                "role": "owner" if u == row.owner_id else db.get(Membership, (row.id, u)).role,
            }
            for u in members
        ],
    }


def plan_access(db, user_id, plan_id, host=False):
    row = db.exec(select(Plan).where(Plan.id == plan_id).with_for_update()).first()
    if row is None or db.get(Participant, (plan_id, user_id)) is None:
        missing("Plan")
    if host and row.host_id != user_id:
        raise AppError("forbidden", "Only the plan host can do this", 403)
    return row


def plan_state(db, plan_id):
    return db.get(Plan, plan_id)


def editable(db, plan):
    state = plan_state(db, plan.id)
    if state.status != "active" or plan.archived or plan.ends_at + 86400 <= now():
        raise AppError("expired", "This plan no longer accepts changes", 409)
    return state


def plan_projection(db, row, viewer=None, include_cards=False):
    data = plan_view(db, row)
    state = plan_state(db, row.id)
    data.update(
        visibility=state.visibility,
        status=state.status,
        currency=state.currency,
        capacity=state.capacity,
        tags=state.tags,
    )
    data["stops"] = [
        {
            "stop_id": str(s.id),
            "order": s.position,
            "label": s.label,
            "latitude": s.latitude,
            "longitude": s.longitude,
            "place_id": s.place_id,
            "arrival_at": iso(s.arrival_at) if s.arrival_at is not None else None,
        }
        for s in db.exec(
            select(PlanStop).where(PlanStop.plan_id == row.id).order_by(PlanStop.position)
        ).all()
    ]
    data["meeting_artifact_id"] = str(row.meeting_artifact_id) if row.meeting_artifact_id else None
    if include_cards:
        from outthere.coordination import listing

        data["artifacts"] = listing(db, viewer, row.id)["items"]
    data["arrivals"] = [
        {"user_id": str(a.user_id), "state": a.state, "version": a.version}
        for a in db.exec(
            select(Arrival).where(Arrival.plan_id == row.id).order_by(Arrival.user_id)
        ).all()
    ]
    return data


def safe_plan(db, row):
    state = plan_state(db, row.id)
    return {
        "id": str(row.id),
        "title": row.title,
        "starts_at": iso(row.starts_at),
        "ends_at": iso(row.ends_at),
        "venue_timezone": row.venue_timezone,
        "visibility": state.visibility,
        "status": state.status,
        "tags": state.tags,
        "version": row.version,
    }


def reachable(db, user_id, plan):
    state = plan_state(db, plan.id)
    if state.status != "active" or plan.archived:
        return False
    if state.visibility == "public":
        return True
    invite = db.get(PlanInvitation, (plan.id, user_id))
    if invite and invite.status == "invited" and invite.expires_at > now():
        return True
    return any(
        db.get(Membership, (c, user_id))
        for c in db.exec(select(PlanCircle.circle_id).where(PlanCircle.plan_id == plan.id)).all()
    )


def audience(db, plan_id):
    users = participant_ids(db, plan_id)
    users.update(
        db.exec(select(PlanInvitation.user_id).where(PlanInvitation.plan_id == plan_id)).all()
    )
    for circle_id in db.exec(
        select(PlanCircle.circle_id).where(PlanCircle.plan_id == plan_id)
    ).all():
        users.update(member_ids(db, circle_id))
    return users


def store_stops(db, plan, stops):
    db.exec(delete(PlanStop).where(PlanStop.plan_id == plan.id))
    db.flush()
    for s in stops:
        # IDs belonging to a different plan cannot be repurposed.
        if db.get(PlanStop, s.stop_id):
            raise AppError("action_conflict", "Stop ID already exists", 409)
        db.add(
            PlanStop(
                id=s.stop_id,
                plan_id=plan.id,
                position=s.order,
                label=s.label,
                latitude=s.latitude,
                longitude=s.longitude,
                place_id=s.place_id,
                arrival_at=int(s.arrival_at.timestamp()) if s.arrival_at else None,
            )
        )


def invite_plan(db, user_id, plan, invitee):
    from outthere.safety import blocked

    if blocked(db, user_id, invitee):
        missing("Invitee")
    if db.get(User, invitee) is None:
        missing("Invitee")
    if db.get(Participant, (plan.id, invitee)):
        raise AppError("invalid_input", "Already participating")
    row = db.get(PlanInvitation, (plan.id, invitee))
    if row is None:
        row = PlanInvitation(plan_id=plan.id, user_id=invitee, expires_at=plan.starts_at)
        db.add(row)
    row.status = "invited"
    row.expires_at = plan.starts_at
    emit(db, {invitee}, "v2.plan", plan.id)
    from outthere.models import Device
    from outthere.push import enqueue

    for device in db.exec(
        select(Device).where(Device.user_id == invitee, Device.revoked_at.is_(None))
    ).all():
        enqueue(
            db, device, "plans", plan.id, f"push.plan.invite:{plan.id}:{device.id}:{plan.version}"
        )


def plan_create(db, user_id, data):
    from outthere.matching import Overlap

    if db.get(Plan, data.plan_id) or db.get(Overlap, data.plan_id):
        raise AppError("action_conflict", "Plan ID already exists", 409)
    if int(data.starts_at.timestamp()) <= now():
        raise AppError("invalid_input", "Choose a future start time")
    circles = set(data.circle_ids)
    if data.circle_id:
        circles.add(data.circle_id)
    for circle_id in sorted(circles, key=str):
        circle_access(db, user_id, circle_id)
    row = Plan(
        id=data.plan_id,
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
    db.add(row)
    db.flush()
    row.visibility, row.currency = data.visibility, data.currency
    row.capacity, row.tags = data.capacity, data.tags
    db.add(Participant(plan_id=row.id, user_id=user_id, rsvp="in"))
    for circle_id in circles:
        db.add(PlanCircle(plan_id=row.id, circle_id=circle_id))
    store_stops(db, row, data.stops)
    for invitee in data.invitee_ids:
        if invitee != user_id:
            invite_plan(db, user_id, row, invitee)
    db.add(
        Job(
            unique_key=f"plan.archive:{row.id}",
            kind="plan.archive",
            entity_id=row.id,
            run_at=row.ends_at + 86400,
        )
    )
    db.flush()
    emit(db, audience(db, row.id), "v2.plan", row.id)
    return plan_projection(db, row)


def circle_command(db, user_id, name, data):
    if name == "circle.create":
        if db.get(Circle, data.circle_id):
            raise AppError("action_conflict", "Circle ID already exists", 409)
        row = Circle(id=data.circle_id, owner_id=user_id, name=data.name, kind=data.kind)
        db.add(row)
        db.flush()
        db.add(Membership(circle_id=row.id, user_id=user_id))
    elif name in {"circle.invitation.accept", "circle.invitation.decline"}:
        row = db.get(Circle, data.circle_id)
        invite = db.get(CircleInvite, (data.circle_id, user_id))
        if row is None or invite is None or invite.expires_at <= now():
            missing("Invitation")
        if name.endswith("decline"):
            db.delete(invite)
            emit(db, {user_id}, "v2.circle_invitation", row.id)
            return {"declined": True}
        if not db.get(Membership, (row.id, user_id)):
            if len(member_ids(db, row.id)) >= 15:
                raise AppError("capacity_reached", "Circle is full", 409)
            db.add(Membership(circle_id=row.id, user_id=user_id))
            circle_state(db, row.id).version += 1
        invite.accepted_at = now()
    else:
        owner = name not in {"circle.leave"}
        row = circle_access(db, user_id, data.circle_id, owner=owner)
        state = circle_state(db, row.id)
        if name == "circle.invite":
            from outthere.safety import blocked

            if db.get(User, data.user_id) is None or blocked(db, user_id, data.user_id):
                missing("Invitee")
            if db.get(Membership, (row.id, data.user_id)):
                raise AppError("invalid_input", "Already a member")
            invite = db.get(CircleInvite, (row.id, data.user_id))
            if invite is None:
                invite = CircleInvite(circle_id=row.id, user_id=data.user_id, expires_at=0)
                db.add(invite)
            invite.expires_at, invite.accepted_at = now() + 7 * 86400, None
            emit(db, {data.user_id}, "v2.circle_invitation", row.id)
            return {"circle_id": str(row.id), "user_id": str(data.user_id)}
        if name in {"circle.leave", "circle.member.remove"}:
            target = user_id if name.endswith("leave") else data.user_id
            if target == row.owner_id:
                raise AppError("forbidden", "Transfer ownership before leaving", 403)
            member = db.get(Membership, (row.id, target))
            if member is None:
                missing("Member")
            db.delete(member)
            invite = db.get(CircleInvite, (row.id, target))
            if invite:
                db.delete(invite)
            invalidate(db, target, "v2.circle", row.id)
        else:
            version(state, data.expected_version)
            if name == "circle.update":
                row.name = data.name
            elif name in {"circle.owner.transfer", "circle.member.role"}:
                if row.owner_id != user_id:
                    raise AppError("forbidden", "Only owner can assign roles", 403)
                if not db.get(Membership, (row.id, data.user_id)):
                    missing("Member")
                if name == "circle.owner.transfer":
                    row.owner_id = data.user_id
                else:
                    if data.user_id == row.owner_id:
                        raise AppError("invalid_input", "Transfer ownership to change owner role")
                    db.get(Membership, (row.id, data.user_id)).role = data.role
            else:
                state.sleeping = name == "circle.sleep"
        state.version += 1
    db.flush()
    emit(db, member_ids(db, row.id), "v2.circle", row.id)
    return circle_projection(db, row)


def plan_command(db, user_id, name, data):
    if name == "plan.create":
        return plan_create(db, user_id, data)
    if name == "plan.join.request":
        row = db.get(Plan, data.plan_id)
        if row is None or not reachable(db, user_id, row) or row.starts_at <= now():
            missing("Plan")
        if db.get(Participant, (row.id, user_id)):
            return plan_projection(db, row)
        invitation = db.get(PlanInvitation, (row.id, user_id))
        if invitation and invitation.status == "invited":
            if len(participant_ids(db, row.id)) >= plan_state(db, row.id).capacity:
                raise AppError("capacity_reached", "Plan is full", 409)
            db.add(Participant(plan_id=row.id, user_id=user_id))
            invitation.status = "accepted"
        else:
            if invitation is None:
                invitation = PlanInvitation(
                    plan_id=row.id, user_id=user_id, expires_at=row.starts_at
                )
                db.add(invitation)
            invitation.status = "requested"
            emit(db, {row.host_id, user_id}, "v2.plan", row.id)
            return {"plan_id": str(row.id), "approval_state": "requested"}
    else:
        host = name in {
            "plan.update",
            "plan.cancel",
            "plan.invite",
            "plan.join.approve",
            "plan.join.decline",
            "plan.member.remove",
        }
        row = plan_access(db, user_id, data.plan_id, host=host)
        state = editable(db, row)
        if name == "plan.update":
            version(row, data.expected_version)
            if data.starts_at.timestamp() <= now():
                raise AppError("invalid_input", "Choose a future start time")
            # Audience changes use explicit invitation/removal commands.
            old_circles = set(
                db.exec(select(PlanCircle.circle_id).where(PlanCircle.plan_id == row.id)).all()
            )
            new_circles = set(data.circle_ids) | ({data.circle_id} if data.circle_id else set())
            if data.invitee_ids:
                raise AppError("invalid_input", "Direct audience changes need invitation commands")
            previous_audience = audience(db, row.id)
            for circle_id in sorted(new_circles, key=str):
                circle_access(db, user_id, circle_id)
            for circle_id in old_circles - new_circles:
                db.delete(db.get(PlanCircle, (row.id, circle_id)))
            for circle_id in new_circles - old_circles:
                db.add(PlanCircle(plan_id=row.id, circle_id=circle_id))
            row.circle_id = data.circle_id
            db.flush()
            for former in previous_audience - audience(db, row.id):
                invalidate(db, former, "v2.plan", row.id)
            if data.currency != state.currency:
                raise AppError("invalid_input", "Plan currency is immutable")
            if data.capacity < len(participant_ids(db, row.id)):
                raise AppError("capacity_reached", "Capacity is below current participation", 409)
            row.title, row.venue_timezone = data.title, data.venue_timezone
            row.starts_at, row.ends_at = (
                int(data.starts_at.timestamp()),
                int(data.ends_at.timestamp()),
            )
            row.place_label, row.latitude, row.longitude = (
                data.place_label,
                data.latitude,
                data.longitude,
            )
            state.visibility, state.capacity, state.tags = data.visibility, data.capacity, data.tags
            store_stops(db, row, data.stops)
            job = db.exec(select(Job).where(Job.unique_key == f"plan.archive:{row.id}")).first()
            if job:
                job.run_at, job.state = row.ends_at + 86400, "pending"
        elif name == "plan.cancel":
            version(row, data.expected_version)
            state.status = "cancelled"
            from outthere.coordination import Artifact, close

            for artifact in db.exec(
                select(Artifact).where(
                    Artifact.plan_id == row.id, Artifact.kind == "poll", Artifact.state == "active"
                )
            ).all():
                close(db, artifact, cancelled=True)
        elif name == "plan.invite":
            if row.starts_at <= now():
                raise AppError("expired", "Invitations are closed", 409)
            invite_plan(db, user_id, row, data.user_id)
            return {"plan_id": str(row.id), "user_id": str(data.user_id)}
        elif name in {"plan.join.approve", "plan.join.decline"}:
            invitation = db.get(PlanInvitation, (row.id, data.user_id))
            if not invitation or invitation.status != "requested" or invitation.expires_at <= now():
                missing("Join request")
            if name.endswith("decline"):
                invitation.status = "declined"
                invalidate(db, data.user_id, "v2.plan", row.id)
                return {"declined": True}
            if len(participant_ids(db, row.id)) >= state.capacity:
                raise AppError("capacity_reached", "Plan is full", 409)
            db.add(Participant(plan_id=row.id, user_id=data.user_id))
            invitation.status = "accepted"
        elif name in {"plan.leave", "plan.member.remove"}:
            target = user_id if name.endswith("leave") else data.user_id
            if target == row.host_id:
                raise AppError("forbidden", "Host cannot leave their plan", 403)
            member = db.get(Participant, (row.id, target))
            if member is None:
                missing("Participant")
            db.delete(member)
            arrival = db.get(Arrival, (row.id, target))
            if arrival:
                db.delete(arrival)
            invitation = db.get(PlanInvitation, (row.id, target))
            if invitation:
                invitation.status = "removed"
            from outthere.coordination import Artifact, BringClaim

            for claim in db.exec(
                select(BringClaim)
                .join(Artifact)
                .where(BringClaim.user_id == target, Artifact.plan_id == row.id)
            ).all():
                claim.user_id, claim.version = None, claim.version + 1
            from outthere.media import revoke_attendance

            revoke_attendance(db, row.id, target)
            invalidate(db, target, "v2.plan", row.id)
        elif name == "plan.rsvp":
            if row.starts_at <= now():
                raise AppError("expired", "RSVPs close at the start", 409)
            participant = db.get(Participant, (row.id, user_id))
            version(participant, data.expected_version)
            participant.rsvp, participant.version = data.rsvp, participant.version + 1
            if data.rsvp == "in":
                from outthere.media import grant_attendance

                grant_attendance(db, row.id, user_id)
        elif name == "plan.arrival.update":
            arrival = db.get(Arrival, (row.id, user_id))
            if (arrival.version if arrival else 0) != data.expected_version:
                raise AppError("version_conflict", "Refresh arrival state", 409)
            if arrival is None:
                db.add(Arrival(plan_id=row.id, user_id=user_id, state=data.state))
            else:
                arrival.state, arrival.version = data.state, arrival.version + 1
    row.version += 1
    db.flush()
    emit(db, audience(db, row.id), "v2.plan", row.id)
    if db.get(Participant, (row.id, user_id)) is None:
        return {"plan_id": str(row.id), "removed": True}
    return plan_projection(db, row)


def projected(db, user_id, kind, entity_id):
    if kind == "v2.profile":
        user = db.get(User, entity_id)
        if user_id == entity_id and user:
            from outthere.sessions import profile

            return profile(user)
    if kind in {"v2.circle", "circle.changed"}:
        row = db.get(Circle, entity_id)
        if row and db.get(Membership, (row.id, user_id)):
            return circle_projection(db, row)
    if kind in {"v2.circle_invitation", "circle.invited"}:
        invitation = db.get(CircleInvite, (entity_id, user_id))
        row = db.get(Circle, entity_id)
        if row and invitation and invitation.accepted_at is None and invitation.expires_at > now():
            return {"circle_id": str(row.id), "name": row.name, "expires_at": invitation.expires_at}
    if kind == "v2.open":
        from outthere.matching import Open, own_view

        row = db.get(Open, entity_id)
        if row and row.user_id == user_id:
            return own_view(row)
        return None
    if kind == "v2.overlap":
        from outthere.matching import Overlap, card, members
        from outthere.safety import blocked

        row = db.get(Overlap, entity_id)
        if (
            row
            and user_id in members(db, row)
            and not blocked(db, *sorted(members(db, row), key=str))
        ):
            return card(db, row, user_id)
        return None
    if kind == "v2.block":
        from outthere.safety import Block

        row = db.get(Block, (user_id, entity_id))
        if row:
            return {"user_id": str(entity_id), "created_at": row.created_at}
        return None
    if kind == "v2.ripple":
        from outthere.ripples import Ripple, audience, projection

        row = db.get(Ripple, entity_id)
        if row and user_id in audience(db, row):
            return projection(db, row, user_id)
        return None
    if kind == "v2.artifact":
        from outthere.coordination import Artifact, projection

        artifact = db.get(Artifact, entity_id)
        if (
            artifact
            and artifact.state not in {"deleted", "expired"}
            and db.get(Participant, (artifact.plan_id, user_id))
        ):
            return projection(db, artifact, user_id)
        return None
    if kind == "v2.album":
        from outthere.media import album_access, album_view

        try:
            return album_view(db, album_access(db, user_id, entity_id), user_id)
        except AppError as exc:
            if exc.code == "not_found":
                return None
            raise
    if kind == "v2.expense":
        from outthere.money import Expense, ExpenseShare, expense_view

        expense = db.get(Expense, entity_id)
        if expense:
            plan = db.get(Plan, expense.plan_id)
            if user_id in {expense.payer_id, plan.host_id} or db.get(
                ExpenseShare, (expense.id, user_id)
            ):
                return expense_view(db, expense, user_id, plan.host_id)
        return None
    if kind == "v2.settlement":
        from outthere.money import Settlement, settlement_view

        row = db.get(Settlement, entity_id)
        if row and user_id in {row.from_user_id, row.to_user_id}:
            return settlement_view(db, row)
        return None
    if kind in {"v2.plan", "plan.changed"}:
        row = db.get(Plan, entity_id)
        if row:
            if db.get(Participant, (row.id, user_id)):
                return plan_projection(db, row)
            invitation = db.get(PlanInvitation, (row.id, user_id))
            if reachable(db, user_id, row) or (invitation and invitation.status == "requested"):
                return safe_plan(db, row)
    return None


def sync(db, user, device, name, data):
    state = sync_state(db, user.id)
    if name == "sync.start":
        from outthere.sessions import profile

        items = [{"entity": "profile", "entity_id": str(user.id), "data": profile(user)}]
        circles = db.exec(
            select(Circle).join(Membership).where(Membership.user_id == user.id).order_by(Circle.id)
        ).all()
        for circle in circles:
            items.append(
                {
                    "entity": "circle",
                    "entity_id": str(circle.id),
                    "data": circle_projection(db, circle),
                }
            )
        for invitation in db.exec(
            select(CircleInvite).where(
                CircleInvite.user_id == user.id,
                CircleInvite.accepted_at.is_(None),
                CircleInvite.expires_at > now(),
            )
        ).all():
            value = projected(db, user.id, "v2.circle_invitation", invitation.circle_id)
            if value:
                items.append(
                    {
                        "entity": "circle_invitation",
                        "entity_id": str(invitation.circle_id),
                        "data": value,
                    }
                )
        # Only own plans and reachable private routes; public discovery is a separate query.
        plans = set(
            db.exec(select(Participant.plan_id).where(Participant.user_id == user.id)).all()
        )
        plans.update(
            db.exec(select(PlanInvitation.plan_id).where(PlanInvitation.user_id == user.id)).all()
        )
        plans.update(
            db.exec(
                select(PlanCircle.plan_id)
                .join(Membership, PlanCircle.circle_id == Membership.circle_id)
                .where(Membership.user_id == user.id)
            ).all()
        )
        for plan_id in sorted(plans, key=str):
            value = projected(db, user.id, "v2.plan", plan_id)
            if value:
                items.append({"entity": "plan", "entity_id": str(plan_id), "data": value})
        from outthere.matching import Open, Overlap
        from outthere.ripples import Ripple, RippleRecipient
        from outthere.safety import Block

        for block in db.exec(select(Block).where(Block.blocker_id == user.id)).all():
            items.append(
                {
                    "entity": "block",
                    "entity_id": str(block.blocked_id),
                    "data": {"user_id": str(block.blocked_id), "created_at": block.created_at},
                }
            )
        for own in db.exec(select(Open).where(Open.user_id == user.id).order_by(Open.id)).all():
            items.append(
                {
                    "entity": "open",
                    "entity_id": str(own.id),
                    "data": projected(db, user.id, "v2.open", own.id),
                }
            )
        own_ids = select(Open.id).where(Open.user_id == user.id)
        for overlap in db.exec(
            select(Overlap)
            .where(Overlap.open_a_id.in_(own_ids) | Overlap.open_b_id.in_(own_ids))
            .order_by(Overlap.id)
        ).all():
            value = projected(db, user.id, "v2.overlap", overlap.id)
            if value:
                items.append({"entity": "overlap", "entity_id": str(overlap.id), "data": value})
        recipient_ids = select(RippleRecipient.ripple_id).where(RippleRecipient.user_id == user.id)
        for ripple in db.exec(
            select(Ripple)
            .where((Ripple.sender_id == user.id) | Ripple.id.in_(recipient_ids))
            .order_by(Ripple.id)
        ).all():
            items.append(
                {
                    "entity": "ripple",
                    "entity_id": str(ripple.id),
                    "data": projected(db, user.id, "v2.ripple", ripple.id),
                }
            )
        from outthere.coordination import Artifact, projection
        from outthere.safety import blocked

        for artifact in db.exec(
            select(Artifact)
            .join(Participant, Participant.plan_id == Artifact.plan_id)
            .where(Participant.user_id == user.id, Artifact.state.notin_(["deleted", "expired"]))
            .order_by(Artifact.id)
        ).all():
            if blocked(db, user.id, artifact.creator_id):
                continue
            items.append(
                {
                    "entity": "artifact",
                    "entity_id": str(artifact.id),
                    "data": projection(db, artifact, user.id),
                }
            )
        from outthere.media import Album, AlbumGrant

        for album in db.exec(
            select(Album)
            .join(AlbumGrant)
            .where(AlbumGrant.user_id == user.id, Album.state == "active")
        ).all():
            value = projected(db, user.id, "v2.album", album.id)
            if value is None:
                continue
            items.append(
                {
                    "entity": "album",
                    "entity_id": str(album.id),
                    "data": value,
                }
            )
        from outthere.money import Expense, Settlement

        for expense in db.exec(select(Expense).order_by(Expense.id)).all():
            value = projected(db, user.id, "v2.expense", expense.id)
            if value:
                items.append({"entity": "expense", "entity_id": str(expense.id), "data": value})
        for settlement in db.exec(
            select(Settlement)
            .where((Settlement.from_user_id == user.id) | (Settlement.to_user_id == user.id))
            .order_by(Settlement.id)
        ).all():
            items.append(
                {
                    "entity": "settlement",
                    "entity_id": str(settlement.id),
                    "data": projected(db, user.id, "v2.settlement", settlement.id),
                }
            )
        db.exec(delete(Snapshot).where(Snapshot.device_id == device.id))
        snapshot = Snapshot(
            user_id=user.id,
            device_id=device.id,
            cursor=user.feed_seq,
            epoch=state.epoch,
            expires_at=now() + 600,
            items=items,
        )
        db.add(snapshot)
        db.flush()
        return snapshot_page(snapshot, 0, data.limit)
    if name == "sync.page":
        row = db.get(Snapshot, data.snapshot_id)
        if row is None or row.device_id != device.id or row.user_id != user.id:
            missing("Snapshot")
        if row.expires_at <= now() or row.epoch != state.epoch:
            raise AppError("cursor_reset_required", "Restart the metadata snapshot", 409)
        return snapshot_page(row, data.after, data.limit)
    if data.epoch != state.epoch or not state.low_water <= data.cursor <= user.feed_seq:
        raise AppError("cursor_reset_required", "Restart metadata sync", 409)
    if name == "sync.ack":
        if device.sync_epoch == state.epoch and data.cursor < device.acknowledged_cursor:
            raise AppError("invalid_input", "Acknowledged cursor cannot move backwards")
        device.acknowledged_cursor, device.sync_epoch = data.cursor, state.epoch
        return {"cursor": data.cursor, "epoch": state.epoch}
    rows = db.exec(
        select(Change)
        .where(Change.user_id == user.id, Change.seq > data.cursor)
        .order_by(Change.seq)
        .limit(100)
    ).all()
    changes = []
    for row in rows:
        # Permanent v1 chat must never enter v2 metadata snapshots/replay.
        if row.kind == "message.created":
            continue
        entity = {
            "circle.changed": "circle",
            "circle.invited": "circle_invitation",
            "plan.changed": "plan",
        }.get(row.kind, row.kind.removeprefix("v2."))
        if entity not in {
            "circle",
            "circle_invitation",
            "plan",
            "profile",
            "expense",
            "settlement",
            "album",
            "artifact",
            "ripple",
            "open",
            "overlap",
            "block",
        }:
            continue
        value = projected(db, user.id, row.kind, row.entity_id)
        changes.append(
            {
                "seq": row.seq,
                "entity": entity,
                "entity_id": str(row.entity_id),
                "operation": "upsert" if value else "remove",
                "version": value.get("version", 1) if value else None,
                "data": value,
            }
        )
    return {
        "epoch": state.epoch,
        "from_cursor": data.cursor,
        "cursor": rows[-1].seq if rows else data.cursor,
        "changes": changes,
        "has_more": len(rows) == 100,
    }


def snapshot_page(row, after, limit):
    if after > len(row.items):
        raise AppError("invalid_input", "Invalid snapshot page")
    end = min(len(row.items), after + limit)
    return {
        "snapshot_id": str(row.id),
        "cursor": row.cursor,
        "epoch": row.epoch,
        "items": row.items[after:end],
        "next_after": end if end < len(row.items) else None,
    }


def query(db, user, device, name, data):
    if name.startswith("sync."):
        return sync(db, user, device, name, data)
    if name == "circle.get":
        return circle_projection(db, circle_access(db, user.id, data.circle_id))
    if name == "plan.get":
        row = db.get(Plan, data.plan_id)
        if row and db.get(Participant, (row.id, user.id)):
            return plan_projection(db, row, user.id, include_cards=True)
        if row and reachable(db, user.id, row):
            return safe_plan(db, row)
        missing("Plan")
    if name == "circle.list":
        statement = select(Circle).join(Membership).where(Membership.user_id == user.id)
        model, render = Circle, circle_projection
    else:
        statement = select(Plan).join(Participant).where(Participant.user_id == user.id)
        model, render = Plan, plan_projection
    if data.after:
        statement = statement.where(model.id > data.after)
    rows = db.exec(statement.order_by(model.id).limit(data.limit + 1)).all()
    return {
        "items": [render(db, r) for r in rows[: data.limit]],
        "next_after": str(rows[data.limit - 1].id) if len(rows) > data.limit else None,
    }


def handle(db, user, device, name, data):
    if name == "sync.ack":
        return sync(db, user, device, name, data)
    if name.startswith("circle."):
        return circle_command(db, user.id, name, data)
    return plan_command(db, user.id, name, data)
