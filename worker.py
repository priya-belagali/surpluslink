"""Optional background worker: expires listings and escalates unanswered offers every minute.

The Streamlit app already runs the same housekeeping while someone has it open. Run this too
(`python worker.py` in a second terminal) so escalation continues when nobody is browsing.
"""
from apscheduler.schedulers.blocking import BlockingScheduler

from core import matching
from core.db import init_db, session_scope


def run_tick() -> None:
    with session_scope() as s:
        result = matching.tick(s)
    if any(result.values()):
        print("tick:", result)


if __name__ == "__main__":
    init_db()
    scheduler = BlockingScheduler()
    scheduler.add_job(run_tick, "interval", seconds=60, max_instances=1)
    print("Worker running. Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
