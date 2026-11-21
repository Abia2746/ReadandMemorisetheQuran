"""Al-Mu'allim billing API. Run: uvicorn app.main:app --host 0.0.0.0 --port 8000
with cwd=apps/api after applying apps/api/schema.sql to PostgreSQL.

No payments are activated until the operator adds verified store offerings,
Stripe price IDs, webhook signing secrets, and OIDC authentication.
"""
from contextlib import asynccontextmanager
import os

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.routers.billing import router as billing_router
from app.routers.billing_webhooks import router as webhook_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    dsn = os.environ.get("DATABASE_URL")
    redis_url = os.environ.get("REDIS_URL")
    if not dsn or not redis_url:
        raise RuntimeError("DATABASE_URL and REDIS_URL must be configured")
    app.state.pg = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=10)
    app.state.redis = Redis.from_url(redis_url, decode_responses=True)
    try:
        yield
    finally:
        await app.state.redis.aclose()
        await app.state.pg.close()


app = FastAPI(
    title="Al-Mu'allim Billing and Entitlements",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if os.environ.get("APP_ENV") == "production" else "/docs",
)

origins = [x.strip() for x in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, allow_credentials=False,
    allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"],
)
app.include_router(billing_router)
app.include_router(webhook_router)


@app.get("/health")
async def health():
    return {"ok": True}
