# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/var/cache/huggingface \
    TOKENIZERS_PARALLELISM=false \
    OMP_NUM_THREADS=4 \
    MKL_NUM_THREADS=4 \
    PRAWDOWID_RUNTIME_DIR=/var/lib/prawdowid/runtime \
    PRAWDOWID_INDEX_DIR=/var/lib/prawdowid/index \
    PYTHONPATH=/app/backend

WORKDIR /app
# libgomp is required by the CPU numerical libraries. No compiler or browser in the image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 prawdowid \
    && useradd --uid 10001 --gid prawdowid --create-home prawdowid \
    && mkdir -p /var/lib/prawdowid/runtime /var/lib/prawdowid/index /var/cache/huggingface \
    && chown -R prawdowid:prawdowid /var/lib/prawdowid /var/cache/huggingface

COPY backend/requirements-container.txt /app/backend/requirements-container.txt
# The normal Linux PyPI wheel may pull CUDA packages. This service uses CPU only.
RUN python -m pip install 'torch==2.15.0' --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install -r /app/backend/requirements-container.txt \
    && python -m pip check

COPY ingest/requirements-container.txt /app/ingest/requirements-container.txt
# Keep OCR/harvester additions separate from the large ML dependency cache.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-pol \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install -r /app/ingest/requirements-container.txt \
    && python -m pip check
COPY ingest/*.py /app/ingest/

COPY backend/prawdowid /app/backend/prawdowid
COPY bots/discord_bot.py /app/bots/discord_bot.py
COPY web /app/web
COPY data/corpus /app/seed/corpus
COPY data/sources /app/seed/sources
COPY data/index /app/data/index
COPY data/watchlist.json /app/data/watchlist.json
COPY docker/start.py docker/healthcheck.py /app/docker/
# corpus and sources live on the state volume (seeded by start.py); RELEASE identifies the shipped data.
RUN ln -s /var/lib/prawdowid/corpus /app/data/corpus \
    && ln -s /var/lib/prawdowid/sources /app/data/sources \
    && mkdir -p /app/data/raw \
    && chown prawdowid:prawdowid /app/data/raw \
    && python /app/docker/start.py --write-release /app/seed/RELEASE /app/seed/corpus /app/seed/sources /app/data/index

USER prawdowid
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30m --retries=3 \
    CMD ["python", "/app/docker/healthcheck.py"]
ENTRYPOINT ["python", "/app/docker/start.py"]
# One worker: models occupy memory per worker and the prototype uses SQLite.
CMD ["python", "-m", "uvicorn", "prawdowid.api:app", "--host", "0.0.0.0", "--workers", "1"]
