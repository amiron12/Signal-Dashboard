"""Runs each enabled receiver on its own cron schedule from config.yaml.

Its own process, separate from the API:

    python -m core.scheduler

Both processes write to the same signals.db, so scheduled runs show up in the
dashboard on its next refresh. config.yaml is re-read every minute, so editing
a schedule or an `enabled` flag takes effect on the next runs without
restarting this process.
"""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import load_config
from .runner import build_receivers, run_receiver

# A laptop asleep at 9am would otherwise skip the run entirely; this lets a
# job that missed its slot still run up to an hour late. Drop it if you'd
# rather a missed window just stay missed.
MISFIRE_GRACE_SECONDS = 3600

# How often to re-read config.yaml. An edit takes effect within this long.
RELOAD_SECONDS = 60

# Job id of the reload job itself, so syncing doesn't treat it as a receiver.
RELOAD_JOB_ID = "_reload_config"

log = logging.getLogger("scheduler")


def _run(receiver):
    log.info("%s: running", receiver.name)
    for event in run_receiver(receiver):
        if event.status == "error":
            log.error("%s: %s", receiver.name, event.error_message)
        else:
            log.info("%s: ok, %d signals", receiver.name, len(event.signals))


def _sync_jobs(scheduler, applied: dict):
    """Make the scheduled jobs match config.yaml as it is on disk right now.

    Runs at startup and every RELOAD_SECONDS after that. `applied` holds the
    config block each job was built from, so a receiver is only rebuilt when
    its block actually changed — an untouched receiver keeps the run it
    already had pending instead of having it pushed back every minute.
    """
    try:
        config = load_config()
        # Build first: a typo'd cron string should raise here, before we've
        # touched any live job.
        wanted = {
            receiver: CronTrigger.from_crontab(
                config["receivers"][receiver.name]["schedule"]
            )
            for receiver in build_receivers(config)
        }
    except Exception as error:
        # A half-saved file or a bad value shouldn't kill the scheduler —
        # keep the schedule we already have and try again on the next reload.
        log.error("could not read config.yaml, keeping current schedule: %s", error)
        return

    names = {receiver.name for receiver in wanted}
    for job in scheduler.get_jobs():
        if job.id != RELOAD_JOB_ID and job.id not in names:
            scheduler.remove_job(job.id)
            applied.pop(job.id, None)
            log.info("unscheduled %s", job.id)

    for receiver, trigger in wanted.items():
        settings = config["receivers"][receiver.name]
        if applied.get(receiver.name) == settings:
            continue
        scheduler.add_job(
            _run,
            trigger,
            args=[receiver],
            id=receiver.name,
            misfire_grace_time=MISFIRE_GRACE_SECONDS,
            replace_existing=True,
        )
        applied[receiver.name] = settings
        log.info("scheduled %s: %s", receiver.name, settings["schedule"])


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    scheduler = BlockingScheduler()
    applied = {}
    _sync_jobs(scheduler, applied)

    if not scheduler.get_jobs():
        log.warning("nothing enabled in config.yaml — no jobs to run yet")

    scheduler.add_job(
        _sync_jobs,
        "interval",
        seconds=RELOAD_SECONDS,
        args=[scheduler, applied],
        id=RELOAD_JOB_ID,
    )

    log.info("scheduler started, ctrl-c to stop")
    scheduler.start()


if __name__ == "__main__":
    main()
