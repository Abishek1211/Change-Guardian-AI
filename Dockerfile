# Single container: React build served by FastAPI alongside the API.
# One origin, no CORS, one Traefik route, one thing to debug.
#
# Targets linux/arm64 (Oracle VM.Standard.A1.Flex, 4 OCPU, no GPU). Build on the
# server rather than cross-building from a dev machine.

# ---------------------------------------------------------------- frontend ---
FROM node:22-alpine AS frontend

WORKDIR /build

# Copy manifests alone first so `npm ci` is cached until dependencies change.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# vite.config.ts writes to ../backend/app/static; inside this stage that path
# is outside the build context root, so redirect it here and copy it across.
RUN npm run build -- --outDir dist --emptyOutDir


# ----------------------------------------------------------------- runtime ---
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # fastembed over onnxruntime - no torch, clean aarch64 wheels.
    EMBEDDING_BACKEND=fastembed \
    FASTEMBED_CACHE_PATH=/opt/models \
    # onnxruntime spawns a thread per core by default. This box is shared with
    # other containers; the corpus is six documents and does not need four cores.
    OMP_NUM_THREADS=2

WORKDIR /app

# Create the unprivileged user up front. Doing this last and running
# `chown -R` afterwards would rewrite every file into a new layer - which
# duplicated the 91 MB ONNX model and added ~92 MB to the image for nothing.
# Establishing ownership before the files exist costs zero extra layers.
RUN useradd --create-home --uid 10001 guardian \
    && mkdir -p /opt/models \
    && chown guardian:guardian /opt/models /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=guardian:guardian backend/app ./app
COPY --chown=guardian:guardian backend/scripts ./scripts
COPY --from=frontend --chown=guardian:guardian /build/dist ./app/static

# Drop privileges before the prebuild, so the model cache and vector file are
# written as the user that will read them at runtime.
USER guardian

# Download the ONNX model and embed the incident corpus at build time, so the
# container never reaches HuggingFace at runtime and the first request is fast.
RUN python scripts/prebuild_index.py

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

# Single worker on purpose. The pipeline is IO-bound on one Groq call and the
# box is shared - extra workers would each hold their own ONNX session for no
# throughput gain against a 30 req/min upstream quota.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
