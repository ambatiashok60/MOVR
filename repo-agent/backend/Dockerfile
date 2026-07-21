# RepoAgent backend image.
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# git is used by the read-only git tools and per-run repo clones.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
# boto3 is installed here so the image can use the Bedrock provider in prod.
RUN pip install -r requirements.txt boto3

COPY app ./app

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8080
# DB defaults to a writable path; override REPO_AGENT_DATABASE_PATH in prod.
ENV REPO_AGENT_DATABASE_PATH=/tmp/repo_agent.db \
    REPO_AGENT_LLM_PROVIDER=fake

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/health').status==200 else 1)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
