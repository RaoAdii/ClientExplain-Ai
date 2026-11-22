from worker.celery_app import JobTask, app, task_id
from worker.tasks import fail_unavailable_pipeline


@app.task(bind=True, base=JobTask, name="worker.parse_document")
def parse_document(self: JobTask, document_id: str, job_id: str) -> None:
    task_id(document_id)
    fail_unavailable_pipeline(task_id(job_id), "parse", self.request.retries)
