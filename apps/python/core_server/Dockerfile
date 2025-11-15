FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install build essentials for packages that may need compilation.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY packages/python ./packages/python
COPY apps/python/core_server ./apps/python/core_server

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -e packages/python/db_core \
    && pip install --no-cache-dir -e packages/python/permissions \
    && pip install --no-cache-dir -e packages/python/ideas_repo \
    && pip install --no-cache-dir -e packages/python/ideas_api \
    && pip install --no-cache-dir -e apps/python/core_server

EXPOSE 8000

CMD ["uvicorn", "core_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
