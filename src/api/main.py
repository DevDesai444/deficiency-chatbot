from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import health, results, upload
from api.ws import router as ws_router
from config import get_settings

app = FastAPI(title="defpredict", version="0.1.0")

s = get_settings()
allowed_origins = [o.strip() for o in s.frontend_url.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(upload.router)
app.include_router(results.router)
app.include_router(ws_router)
