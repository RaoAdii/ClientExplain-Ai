from worker.celery_app import JobTask, app, task_id
from worker.tasks import fail_unavailable_pipeline


@app.task(bind=True, base=JobTask, name="worker.analyze_project")
def analyze_project(self: JobTask, job_id: str) -> None:
    fail_unavailable_pipeline(task_id(job_id), "analysis", self.request.retries)
