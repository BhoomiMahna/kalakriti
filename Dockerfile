# ── Kalakriti backend (FastAPI) — production container ───────────────────────
# Build context = repo root, so the app keeps its existing layout and every
# path (pricing_model.pkl, before_after_products, artisans_ai) resolves exactly
# as it does locally. Nothing depends on a developer machine.
FROM python:3.11-slim

# System libs required by opencv-python-headless / rembg.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Install Python deps first (better layer caching).
COPY app/backend/requirements.txt app/backend/requirements.txt
RUN pip install --no-cache-dir -r app/backend/requirements.txt

# App code + bundled assets (keep the repo layout: /srv is REPO_ROOT).
COPY app/backend            ./app/backend
COPY artisans_ai            ./artisans_ai
COPY before_after_products  ./before_after_products
COPY pricing_model.pkl      ./pricing_model.pkl

WORKDIR /srv/app/backend

# Production defaults (override any of these in the host's env panel).
ENV OTP_DEV_MODE=true \
    DEMO_MODE=true \
    IMAGE_DEMO_MODE=true \
    INSTAGRAM_DEMO_MODE=true \
    ENABLE_AI_PIPELINE=false \
    PORT=8000

EXPOSE 8000
# Hosts (Render/Railway/Fly) inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
