# Kalakriti — AI-Powered Artisan Product Digitization & Multi-Channel Selling

A mobile-first web application that turns an artisan's **photo + voice** into a
professional, marketplace-ready listing and publishes it to multiple channels —
automatically.

> **"I just showed the app my product. It did everything else."**

This repository contains the full application (backend + frontend) built around
the project's provided AI models:

| Capability | Provided model | How it's integrated |
|---|---|---|
| Speech-to-text, translation, extraction, description, validation | `SIH_2026/artisan_ai/` (Whisper/Bhashini/Sarvam, IndicTrans2, Gemini) | `backend/services/ai_service.py` |
| Price recommendation | `pricing_model.pkl` (scikit-learn) | `backend/services/pricing_service.py` |
| Image enhancement | FLUX.2 + NAFNet + MIRNet + rembg (GPU, see `README (1) (1).md`) | `backend/services/image_service.py` |

Every model sits behind a clean interface with a **graceful fallback**, so the
whole app runs end-to-end on a laptop with no GPU and no API keys — then the
real models drop in via configuration, without rewriting the app.

---

## Architecture

```
Mobile Web App (React + Vite + Tailwind)          app/frontend
        │  REST + polling
        ▼
FastAPI backend                                   app/backend
        ├── auth (OTP + JWT)
        ├── Product = canonical source of truth   (SQLite / SQLAlchemy)
        ├── AI orchestration (async jobs)         services/job_service.py
        │     ├── image_service   → enhancement
        │     ├── ai_service      → artisan_ai pipeline
        │     └── pricing_service → pricing_model.pkl
        └── Marketplace adapters                  marketplace/
              ├── Amazon SP-API (LWA + Listings)
              └── ONDC (SNP, Ed25519 signing)
```

The **canonical Product** is decoupled from every marketplace; each channel's
publishing state lives in its own `ProductChannel` row. Adding a marketplace =
adding one adapter in `marketplace/registry.py` — the product pipeline never
changes. A failure on one channel never blocks another.

---

## Quick start

### 1. Backend

```bash
cd app/backend
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
copy .env.example .env                                # then edit as needed
uvicorn main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Health / integration status: http://localhost:8000/api/admin/health

By default (`ENABLE_AI_PIPELINE=false`, no marketplace creds) the app runs with
the built-in fallback generator + local image enhancement, and marketplace
channels report **"needs attention"** with a clear reason — nothing crashes.

### 2. Frontend

```bash
cd app/frontend
npm install
npm run dev            # http://localhost:5173  (proxies /api to :8000)
```

Open http://localhost:5173 on a phone-sized viewport. `OTP_DEV_MODE=true`
returns the OTP in the response and pre-fills it, so you can log in without an
SMS gateway.

---

## Enabling the real models

### AI language pipeline (`artisan_ai`)
```
ENABLE_AI_PIPELINE=true
GOOGLE_API_KEY=<your Gemini key>
```
Also install the heavier deps: `pip install -r ../../SIH_2026/requirements.txt`.
The service imports `artisan_ai.ArtisanProductPipeline` and runs the real
Whisper/IndicTrans2/Gemini flow on the uploaded audio.

### Image enhancement (GPU FLUX pipeline)
Host the provided enhancer as an HTTP service that accepts an image and returns
the enhanced bytes, then set:
```
IMAGE_ENHANCER_URL=http://<gpu-host>:9000/enhance
```
Otherwise a local Pillow cleanup (auto-contrast, sharpen, white square canvas)
is used — a truthful enhancement that never fabricates the product.

### Amazon SP-API
```
AMAZON_ENABLED=true
AMAZON_LWA_CLIENT_ID=...        AMAZON_LWA_CLIENT_SECRET=...
AMAZON_REFRESH_TOKEN=...        AMAZON_SELLER_ID=...
AMAZON_MARKETPLACE_ID=A21TJRUUN4KGV      # amazon.in
AMAZON_REGION=eu   AMAZON_SANDBOX=true
```
The adapter mints an LWA access token (`refresh_token` grant) and `PUT`s to the
Listings Items API (`/listings/2021-08-01/items/{sellerId}/{sku}`). Flip
`AMAZON_SANDBOX=false` for production. Seller registration / identity
verification that Amazon requires directly is guided in-app, not bypassed.

### ONDC
```
ONDC_ENABLED=true
ONDC_SUBSCRIBER_ID=...   ONDC_UNIQUE_KEY_ID=...   ONDC_SIGNING_PRIVATE_KEY=<base64 ed25519>
```
The adapter maps the product to an ONDC catalog item and builds the signed
`Authorization` header (BLAKE-512 digest + Ed25519). Install PyNaCl for signing:
`pip install pynacl`.

---

## The automated pipeline (spec §19)

`POST /api/products` (multipart: photos, optional audio, guided pricing inputs)
creates a DRAFT product and enqueues one async job. The frontend polls
`GET /api/products/{id}/job` and shows live progress:

```
Enhancing your photos       ✓
Understanding your story     ✓
Creating your description    ✓
Finding the right price      ✓
Preparing your listing       ✓
```

Then the artisan reviews, adjusts the price, approves, and publishes — one tap
sends the canonical product to every connected marketplace.

---

## Key endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/request-otp` · `/verify-otp` | Phone login |
| GET/PATCH | `/api/artisans/me` | Profile (register once) |
| GET | `/api/pricing/metadata` · POST `/api/pricing/suggest` | Guided pricing |
| POST | `/api/products` | Create + start AI pipeline |
| GET | `/api/products` · `/api/products/{id}` · `/api/products/{id}/job` | Read / poll |
| PATCH | `/api/products/{id}/price` · POST `/approve` | Review |
| POST | `/api/products/{id}/publish` · `/channels/{c}/retry` | Multi-channel publish |
| GET | `/api/admin/health` · `/api/admin/stats` | Ops |

---

## Security notes
- Marketplace credentials, JWT secret, and LLM keys are read only from env/`.env`
  and never exposed to the frontend.
- OTPs are stored as keyed HMAC hashes with expiry + attempt limits.
- Prohibited/irreversible seller actions (Amazon identity verification, payments)
  are guided to the artisan, never performed automatically.
