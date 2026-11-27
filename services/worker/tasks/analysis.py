from app.core.config import settings
from app.integrations.openai_provider import get_analysis_provider, get_embedding_provider
from app.services.analysis import AnalysisProviders
from worker.celery_app import JobTask, app, task_id
from worker.pipelines.analysis import run_analysis_job
from worker.tasks import run_job


def _analysis_pipeline(task, job_id, document_id):
    providers = AnalysisProviders(
        None if settings.ai_provider == "groq" else get_embedding_provider(settings),
        get_analysis_provider(settings),
        task.request.id,
    )
    run_analysis_job(job_id, providers)


@app.task(bind=True, base=JobTask, name="worker.analyze_project")
def analyze_project(self: JobTask, job_id: str) -> None:
    run_job(self, task_id(job_id), "analysis", pipeline=_analysis_pipeline)
