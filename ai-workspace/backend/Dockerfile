FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY app ./app

CMD ["uvicorn", "worktop.ai_workspace.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
