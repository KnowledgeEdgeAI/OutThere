import logging
import time
from uuid import uuid4

from sqlalchemy import Engine, delete, or_, text
from sqlmodel import select

from outthere import coordination, delivery, media, push, ripples
from outthere.db import make_engine, transaction
from outthere.events import emit
from outthere.models import ActionReceipt, AuthOperation, Change, Job, Plan, now
from outthere.plans import participant_ids
from outthere.product_models import Snapshot, SyncState
from outthere.settings import Settings

logger = logging.getLogger(__name__)


def run_once(engine: Engine, settings: Settings | None = None) -> bool:
    with transaction(engine, write=True) as db:
        if db.bind.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(73482109)"))
        ripples.cleanup(db)
        coordination.cleanup(db)
        delivery.cleanup(db)
        media.cleanup(db, settings or Settings())
        for state in db.exec(select(SyncState).with_for_update()).all():
            old = db.exec(
                select(Change)
                .where(Change.user_id == state.user_id, Change.created_at < now() - 30 * 86400)
                .order_by(Change.seq)
            ).all()
            # Prune only a contiguous prefix; a newer row cannot be skipped.
            for row in old:
                newer_before = db.exec(
                    select(Change).where(
                        Change.user_id == state.user_id,
                        Change.seq < row.seq,
                        Change.created_at >= now() - 30 * 86400,
                    )
                ).first()
                if newer_before:
                    break
                state.low_water = max(state.low_water, row.seq)
                db.delete(row)
        db.exec(delete(Snapshot).where(Snapshot.expires_at <= now()))
        db.exec(delete(AuthOperation).where(AuthOperation.expires_at <= now()))
        db.exec(delete(ActionReceipt).where(ActionReceipt.expires_at <= now()))
        job = db.exec(
            select(Job)
            .where(
                Job.run_at <= now(),
                or_(Job.state == "pending", (Job.state == "running") & (Job.lease_until < now())),
            )
            .order_by(Job.run_at, Job.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        ).first()
        if job is None:
            return False
        job.state = "running"
        job.attempts += 1
        job.lease_token = uuid4()
        job.lease_until = now() + 60
        job_id, lease = job.id, job.lease_token
    try:
        with transaction(engine, write=True) as db:
            if engine.dialect.name == "postgresql":
                db.execute(text("SELECT pg_advisory_xact_lock(73482109)"))
            job = db.exec(select(Job).where(Job.id == job_id).with_for_update()).one()
            if job.lease_token != lease:
                return True
            if job.kind == "artifact.notify":
                coordination.notify(db, job)
                job.state, job.lease_until = "done", 0
                return True
            if job.kind == "push.notify":
                push.execute(db, settings or Settings(), job)
                job.state, job.lease_until = "done", 0
                return True
            if job.kind != "plan.archive":
                raise ValueError("Unsupported job kind")
            plan = db.exec(select(Plan).where(Plan.id == job.entity_id).with_for_update()).first()
            if plan and plan.ends_at + 86400 > now():
                job.run_at = plan.ends_at + 86400
                job.state = "pending"
                return True
            if plan and not plan.archived:
                plan.archived = True
                plan.version += 1
                emit(db, participant_ids(db, plan.id), "plan.changed", plan.id)
            # State, feed, and completion commit together. Safe to rerun after a crash.
            job.state = "done"
            job.lease_until = 0
    except Exception:
        logger.exception("Background job failed: %s", job_id)
        with transaction(engine, write=True) as db:
            job = db.exec(select(Job).where(Job.id == job_id).with_for_update()).one()
            if job.lease_token == lease:
                job.state = "failed" if job.attempts >= 5 else "pending"
                job.run_at = now() + min(300, 2**job.attempts)
                job.lease_until = 0
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    engine = make_engine(settings.database_url)
    try:
        while True:
            if not run_once(engine, settings):
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
