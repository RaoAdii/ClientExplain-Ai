from uuid import UUID

from app.core.config import settings
from celery import Celery, Task
from celery.exceptions import Reject
from celery.utils.time import get_exponential_backoff_interval

app = Celery(
    "clientexplain",
    broker=settings.redis_url,
    include=["worker.tasks.documents", "worker.tasks.analysis"],
)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=600,
    task_soft_time_limit=540,
    task_default_queue="generation",
    broker_connection_retry_on_startup=True,
)


class JobTask(Task):
    processing_retry_limit = 3
    # Persisting a terminal outcome must still be deliverable after a long DB outage.
    max_retries = None

    def retry_delivery(self, headers=None):
        delay = get_exponential_backoff_interval(
            factor=1, retries=min(self.request.retries, 6), maximum=60, full_jitter=True
        )
        try:
            raise self.retry(countdown=max(1, delay), headers=headers)
        except Reject:
            # Keep the original late-acknowledged delivery if retry publication failed.
            raise Reject("Unable to schedule the job retry.", requeue=True) from None


def task_id(value: str) -> UUID:
    if not isinstance(value, str):
        raise ValueError("Task arguments must be UUID strings.")
    return UUID(value)


@app.task(name="worker.health")
def health():
    return {"status": "ok", "generation_enabled": False}
