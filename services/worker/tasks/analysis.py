from worker.celery_app import JobTask, app, task_id
from worker.tasks import run_job


@app.task(bind=True, base=JobTask, name="worker.analyze_project")
def analyze_project(self: JobTask, job_id: str) -> None:
    run_job(self, task_id(job_id), "analysis")
