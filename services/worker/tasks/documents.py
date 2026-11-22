from worker.celery_app import JobTask, app, task_id
from worker.tasks import run_job


@app.task(bind=True, base=JobTask, name="worker.parse_document")
def parse_document(self: JobTask, document_id: str, job_id: str) -> None:
    run_job(self, task_id(job_id), "parse", task_id(document_id))
