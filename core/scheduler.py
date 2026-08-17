"""Runs each enabled receiver on its own cron schedule from config.yaml.

Its own process, separate from the API:

    python -m core.scheduler

Both processes write to the same signals.db, so scheduled runs show up in the
dashboard on its next refresh. Config is read once at startup — restart this
process to pick up an edit to config.yaml.
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

log = logging.getLogger("scheduler")


def _run(receiver):
    log.info("%s: running", receiver.name)
    for event in run_receiver(receiver):
        if event.status == "error":
            log.error("%s: %s", receiver.name, event.error_message)
        else:
            log.info("%s: ok, %d signals", receiver.name, len(event.signals))


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    config = load_config()
    scheduler = BlockingScheduler()

    for receiver in build_receivers(config):
        schedule = config["receivers"][receiver.name]["schedule"]
        scheduler.add_job(
            _run,
            CronTrigger.from_crontab(schedule),
            args=[receiver],
            id=receiver.name,
            misfire_grace_time=MISFIRE_GRACE_SECONDS,
        )
        log.info("scheduled %s: %s", receiver.name, schedule)

    if not scheduler.get_jobs():
        log.warning("nothing enabled in config.yaml — no jobs to run")
        return

    log.info("scheduler started, ctrl-c to stop")
    scheduler.start()


if __name__ == "__main__":
    main()
