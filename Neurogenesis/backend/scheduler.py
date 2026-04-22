from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from backend.database import SessionLocal
from backend.services.avatar_autonomy import run_autonomy_cycle, check_persona_drift, evolve_persona

scheduler = BackgroundScheduler()


def _autonomy_job():
    db = SessionLocal()
    try:
        run_autonomy_cycle(db)
    except Exception as e:
        print(f"[Scheduler] Autonomy job error: {e}")
    finally:
        db.close()


def _drift_check_job():
    db = SessionLocal()
    try:
        from backend import models
        avatars = db.query(models.Avatar).filter(models.Avatar.auto_post_enabled == 1).all()
        for avatar in avatars:
            try:
                check_persona_drift(avatar.id, db)
            except Exception as e:
                print(f"[Scheduler] Drift check failed for avatar {avatar.id}: {e}")
    except Exception as e:
        print(f"[Scheduler] Drift check job error: {e}")
    finally:
        db.close()


def _evolution_job():
    db = SessionLocal()
    try:
        from backend import models
        avatars = db.query(models.Avatar).filter(models.Avatar.auto_post_enabled == 1).all()
        for avatar in avatars:
            try:
                evolve_persona(avatar.id, db)
            except Exception as e:
                print(f"[Scheduler] Evolution failed for avatar {avatar.id}: {e}")
    except Exception as e:
        print(f"[Scheduler] Evolution job error: {e}")
    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(
        _autonomy_job,
        trigger=IntervalTrigger(minutes=15),
        id="avatar_autonomy",
        replace_existing=True,
    )
    scheduler.add_job(
        _drift_check_job,
        trigger=IntervalTrigger(days=7),
        id="persona_drift_check",
        replace_existing=True,
    )
    scheduler.add_job(
        _evolution_job,
        trigger=IntervalTrigger(days=30),
        id="persona_evolution",
        replace_existing=True,
    )
    scheduler.start()
    print("[Scheduler] Avatar autonomy scheduler started (15min interval)")
    print("[Scheduler] Persona drift check scheduled (weekly)")
    print("[Scheduler] Persona evolution scheduled (monthly)")


def shutdown_scheduler():
    scheduler.shutdown()
    print("[Scheduler] Avatar autonomy scheduler shutdown")
