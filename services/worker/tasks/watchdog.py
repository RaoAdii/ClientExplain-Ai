import logging
from time import sleep

from sqlalchemy.exc import SQLAlchemyError
from worker.tasks import reconcile_stale_jobs


def main() -> None:
    while True:
        try:
            reconcile_stale_jobs()
        except SQLAlchemyError:
            logging.warning("Job reconciliation could not reach the database.")
        sleep(30)


if __name__ == "__main__":
    main()
