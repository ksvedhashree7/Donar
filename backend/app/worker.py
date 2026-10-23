import logging
import time
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.core.database import SessionFactory, engine
from app.models import BloodOutreachBatch, BloodRequest
from app.services.blood_outreach import _as_utc, advance_outreach

logger = logging.getLogger("uthiram.outreach_worker")
POLL_INTERVAL_SECONDS = 1
BATCH_LIMIT = 50


def advance_due_outreach(factory: sessionmaker = SessionFactory) -> int:
    now = datetime.now(timezone.utc)
    with factory() as db:
        request_ids = db.scalars(
            select(BloodRequest.id)
            .join(BloodOutreachBatch, BloodOutreachBatch.request_id == BloodRequest.id)
            .where(
                BloodRequest.outreach_active.is_(True),
                BloodRequest.current_stage == BloodOutreachBatch.stage,
                BloodOutreachBatch.status == "ACTIVE",
                (
                    (BloodOutreachBatch.expires_at <= now)
                    | (BloodRequest.required_by <= now)
                ),
            )
            .distinct()
            .order_by(BloodRequest.id)
            .limit(BATCH_LIMIT)
        ).all()

    processed = 0
    for request_id in request_ids:
        try:
            with factory.begin() as db:
                request = db.scalar(
                    select(BloodRequest)
                    .where(BloodRequest.id == request_id)
                    .with_for_update(skip_locked=True)
                )
                if request is None or not request.outreach_active:
                    continue
                batch = db.scalar(
                    select(BloodOutreachBatch)
                    .where(
                        BloodOutreachBatch.request_id == request_id,
                        BloodOutreachBatch.stage == request.current_stage,
                        BloodOutreachBatch.status == "ACTIVE",
                    )
                    .order_by(BloodOutreachBatch.started_at.desc())
                    .limit(1)
                    .with_for_update()
                )
                if batch is None or (
                    _as_utc(batch.expires_at) > now and _as_utc(request.required_by) > now
                ):
                    continue
                advance_outreach(db, request, actor=None)
                processed += 1
        except HTTPException as error:
            if error.status_code != 409:
                raise
            logger.info("Skipped a stale outreach transition for request_id=%s", request_id)
        except SQLAlchemyError:
            logger.exception("Failed to advance outreach for request_id=%s", request_id)
    return processed


def run_worker() -> None:
    if engine.dialect.name != "postgresql":
        raise RuntimeError("The outreach worker requires PostgreSQL row-level locking")
    logger.info("Starting the PostgreSQL-backed outreach worker")
    while True:
        advance_due_outreach()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_worker()
