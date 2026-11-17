import os

from celery import Celery

app = Celery("clientexplain", broker=os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"))
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    worker_prefetch_multiplier=1,
    task_time_limit=600,
    task_soft_time_limit=540,
    task_default_queue="generation",
    broker_connection_retry_on_startup=True,
)


@app.task(name="worker.health")
def health():
    return {"status": "ok", "generation_enabled": False}
