FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app:/app/services/api
WORKDIR /app
COPY services/api/requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r requirements.lock && useradd --create-home worker
COPY services/api/app /app/services/api/app
COPY services/worker /app/worker
USER worker
CMD ["celery", "-A", "worker.celery_app:app", "worker", "--loglevel=info", "--concurrency=1"]
