FROM python:3.12.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir setuptools==84.0.0 \
    && pip install --no-cache-dir --no-build-isolation --no-deps . \
    && pip check \
    && groupadd --system iterflow \
    && useradd --system --gid iterflow --home-dir /app iterflow \
    && mkdir -p /app/data/uploads \
    && chown -R iterflow:iterflow /app/data
COPY alembic ./alembic
COPY alembic.ini ./
USER iterflow
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
