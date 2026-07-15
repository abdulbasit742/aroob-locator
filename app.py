from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict
from datetime import datetime
import os
from pathlib import Path
import time
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from locator import ShareError, ShareStore

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
store = ShareStore()
app = FastAPI(
    title="Aroob Locator",
    description="Consent-first, short-lived location sharing.",
    version="2.0.0",
)
app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")

allowed_origins = [value.strip() for value in os.getenv("ALLOWED_ORIGINS", "").split(",") if value.strip()]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )


class FixedWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def check(self, client: str, bucket: str, limit: int, window_seconds: int = 60) -> None:
        now = time.monotonic()
        events = self._events[(client, bucket)]
        while events and now - events[0] >= window_seconds:
            events.popleft()
        if len(events) >= limit:
            raise HTTPException(status_code=429, detail="Too many requests. Try again shortly.", headers={"Retry-After": str(window_seconds)})
        events.append(now)


limiter = FixedWindowLimiter()


def rate_limit(bucket: str, limit: int):
    def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        limiter.check(client, bucket, limit)
    return dependency


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer capability required.")
    token = authorization[7:].strip()
    if len(token) < 32 or len(token) > 256:
        raise HTTPException(status_code=401, detail="Invalid bearer capability.")
    return token


class CreateShareIn(BaseModel):
    label: str = Field(default="Location share", min_length=1, max_length=80)
    duration_minutes: int = Field(default=30, ge=5, le=120)


class CreateShareOut(BaseModel):
    share_id: str
    share_url: str
    viewer_url: str
    expires_at: datetime
    retention: str = "latest point only; erased on stop or expiry"


class AcceptShareIn(BaseModel):
    accept_token: str = Field(min_length=32, max_length=256)
    precision: Literal["approximate", "exact"] = "approximate"


class AcceptShareOut(BaseModel):
    upload_token: str
    expires_at: datetime
    precision: Literal["approximate", "exact"]
    upload_interval_seconds: int = 30


class LocationIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0, le=100_000)
    observed_at: datetime


class LocationOut(BaseModel):
    latitude: float
    longitude: float
    accuracy_m: float | None
    observed_at: datetime
    received_at: datetime
    precision: Literal["approximate", "exact"]


class ShareViewOut(BaseModel):
    share_id: str
    label: str
    status: Literal["awaiting_acceptance", "sharing", "stopped", "expired"]
    expires_at: datetime
    precision: Literal["approximate", "exact"] | None
    location: LocationOut | None


@app.exception_handler(ShareError)
async def share_error_handler(_: Request, exc: ShareError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.middleware("http")
async def security_headers(request: Request, call_next):
    store.cleanup()
    response: Response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'; "
        "img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'"
    )
    if request.url.scheme == "https" or os.getenv("FORCE_HTTPS") == "1":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/web/share.html", include_in_schema=False)
def share_page() -> FileResponse:
    return FileResponse(WEB_DIR / "share.html")


@app.get("/web/viewer.html", include_in_schema=False)
def viewer_page() -> FileResponse:
    return FileResponse(WEB_DIR / "viewer.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "storage": "ephemeral-memory", "history": "disabled"}


@app.post("/api/shares", response_model=CreateShareOut, dependencies=[Depends(rate_limit("create", 10))])
def create_share(data: CreateShareIn, request: Request) -> CreateShareOut:
    created = store.create(label=data.label, duration_minutes=data.duration_minutes)
    base = str(request.base_url).rstrip("/")
    return CreateShareOut(
        share_id=created["share_id"],
        share_url=f"{base}/web/share.html#share={created['share_id']}&accept={created['accept_token']}",
        viewer_url=f"{base}/web/viewer.html#share={created['share_id']}&view={created['viewer_token']}",
        expires_at=datetime.fromisoformat(created["expires_at"]),
    )


@app.post("/api/shares/{share_id}/accept", response_model=AcceptShareOut, dependencies=[Depends(rate_limit("accept", 20))])
def accept_share(share_id: str, data: AcceptShareIn) -> AcceptShareOut:
    accepted = store.accept(share_id=share_id, accept_token=data.accept_token, precision=data.precision)
    return AcceptShareOut(
        upload_token=accepted["upload_token"],
        expires_at=datetime.fromisoformat(accepted["expires_at"]),
        precision=accepted["precision"],
    )


@app.post("/api/shares/{share_id}/locations", response_model=LocationOut, dependencies=[Depends(rate_limit("upload", 120))])
def upload_location(share_id: str, data: LocationIn, token: str = Depends(bearer_token)) -> LocationOut:
    point = store.upload(
        share_id=share_id,
        upload_token=token,
        latitude=data.latitude,
        longitude=data.longitude,
        accuracy_m=data.accuracy_m,
        observed_at=data.observed_at,
    )
    return LocationOut(**asdict(point))


@app.get("/api/shares/{share_id}/location", response_model=ShareViewOut, dependencies=[Depends(rate_limit("view", 120))])
def view_location(share_id: str, token: str = Depends(bearer_token)) -> ShareViewOut:
    record = store.view(share_id=share_id, viewer_token=token)
    location = LocationOut(**asdict(record.latest)) if record.latest else None
    return ShareViewOut(
        share_id=record.share_id,
        label=record.label,
        status=record.status,
        expires_at=record.expires_at,
        precision=record.precision,
        location=location,
    )


@app.post("/api/shares/{share_id}/stop", response_model=ShareViewOut, dependencies=[Depends(rate_limit("stop", 30))])
def stop_share(share_id: str, token: str = Depends(bearer_token)) -> ShareViewOut:
    record = store.stop(share_id=share_id, capability=token)
    return ShareViewOut(
        share_id=record.share_id,
        label=record.label,
        status=record.status,
        expires_at=record.expires_at,
        precision=record.precision,
        location=None,
    )
