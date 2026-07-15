from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import compare_digest
import secrets
from threading import RLock
from typing import Callable, Literal

Precision = Literal["approximate", "exact"]
Status = Literal["awaiting_acceptance", "sharing", "stopped", "expired"]


class ShareError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(slots=True)
class LocationPoint:
    latitude: float
    longitude: float
    accuracy_m: float | None
    observed_at: datetime
    received_at: datetime
    precision: Precision


@dataclass(slots=True)
class ShareRecord:
    share_id: str
    label: str
    created_at: datetime
    expires_at: datetime
    status: Status
    accept_hash: str | None
    upload_hash: str | None
    viewer_hash: str | None
    precision: Precision | None = None
    accepted_at: datetime | None = None
    stopped_at: datetime | None = None
    latest: LocationPoint | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _matches(token: str, expected_hash: str | None) -> bool:
    return bool(expected_hash) and compare_digest(_hash_token(token), expected_hash)


class ShareStore:
    """In-memory, latest-point-only location sharing store.

    The process intentionally retains no location history and erases the latest
    point when a share is stopped or expires. A restart also clears everything.
    """

    def __init__(self, now: Callable[[], datetime] = _utc_now) -> None:
        self._records: dict[str, ShareRecord] = {}
        self._now = now
        self._lock = RLock()

    def create(self, *, label: str, duration_minutes: int) -> dict[str, str]:
        label = label.strip()
        if not 1 <= len(label) <= 80:
            raise ShareError("Label must contain 1 to 80 characters.", 422)
        if not 5 <= duration_minutes <= 120:
            raise ShareError("Duration must be between 5 and 120 minutes.", 422)

        now = self._now()
        share_id = secrets.token_urlsafe(12)
        accept_token = _new_token()
        viewer_token = _new_token()
        record = ShareRecord(
            share_id=share_id,
            label=label,
            created_at=now,
            expires_at=now + timedelta(minutes=duration_minutes),
            status="awaiting_acceptance",
            accept_hash=_hash_token(accept_token),
            upload_hash=None,
            viewer_hash=_hash_token(viewer_token),
        )
        with self._lock:
            self._records[share_id] = record
        return {
            "share_id": share_id,
            "accept_token": accept_token,
            "viewer_token": viewer_token,
            "expires_at": record.expires_at.isoformat(),
        }

    def accept(self, *, share_id: str, accept_token: str, precision: Precision) -> dict[str, str]:
        if precision not in ("approximate", "exact"):
            raise ShareError("Invalid precision.", 422)
        with self._lock:
            record = self._get_active(share_id)
            if record.status != "awaiting_acceptance":
                raise ShareError("This invitation has already been used.", 409)
            if not _matches(accept_token, record.accept_hash):
                raise ShareError("Invalid invitation capability.", 403)
            upload_token = _new_token()
            record.accept_hash = None
            record.upload_hash = _hash_token(upload_token)
            record.precision = precision
            record.accepted_at = self._now()
            record.status = "sharing"
            return {
                "upload_token": upload_token,
                "expires_at": record.expires_at.isoformat(),
                "precision": precision,
            }

    def upload(
        self,
        *,
        share_id: str,
        upload_token: str,
        latitude: float,
        longitude: float,
        accuracy_m: float | None,
        observed_at: datetime,
    ) -> LocationPoint:
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ShareError("Coordinates are outside valid ranges.", 422)
        if accuracy_m is not None and not 0 <= accuracy_m <= 100_000:
            raise ShareError("Accuracy is outside the accepted range.", 422)
        if observed_at.tzinfo is None:
            raise ShareError("observed_at must include a timezone.", 422)

        with self._lock:
            record = self._get_active(share_id)
            if record.status != "sharing" or not _matches(upload_token, record.upload_hash):
                raise ShareError("Invalid upload capability.", 403)
            now = self._now()
            observed_at = observed_at.astimezone(timezone.utc)
            if observed_at > now + timedelta(minutes=2):
                raise ShareError("Location timestamp is too far in the future.", 422)
            if observed_at < now - timedelta(minutes=10):
                raise ShareError("Location timestamp is too old.", 422)

            precision: Precision = record.precision or "approximate"
            if precision == "approximate":
                latitude = round(latitude, 3)
                longitude = round(longitude, 3)
                accuracy_m = max(accuracy_m or 0, 110.0)

            point = LocationPoint(
                latitude=float(latitude),
                longitude=float(longitude),
                accuracy_m=float(accuracy_m) if accuracy_m is not None else None,
                observed_at=observed_at,
                received_at=now,
                precision=precision,
            )
            record.latest = point
            return point

    def view(self, *, share_id: str, viewer_token: str) -> ShareRecord:
        with self._lock:
            record = self._get(share_id)
            self._expire_if_needed(record)
            if not _matches(viewer_token, record.viewer_hash):
                raise ShareError("Invalid viewer capability.", 403)
            return record

    def stop(self, *, share_id: str, capability: str) -> ShareRecord:
        with self._lock:
            record = self._get(share_id)
            self._expire_if_needed(record)
            if not (_matches(capability, record.upload_hash) or _matches(capability, record.viewer_hash)):
                raise ShareError("Invalid stop capability.", 403)
            if record.status not in ("stopped", "expired"):
                record.status = "stopped"
                record.stopped_at = self._now()
            self._wipe(record, keep_viewer=True)
            return record

    def cleanup(self) -> int:
        expired = 0
        with self._lock:
            for record in self._records.values():
                before = record.status
                self._expire_if_needed(record)
                if before != "expired" and record.status == "expired":
                    expired += 1
        return expired

    def _get(self, share_id: str) -> ShareRecord:
        record = self._records.get(share_id)
        if not record:
            raise ShareError("Share not found.", 404)
        return record

    def _get_active(self, share_id: str) -> ShareRecord:
        record = self._get(share_id)
        self._expire_if_needed(record)
        if record.status == "expired":
            raise ShareError("Share has expired.", 410)
        if record.status == "stopped":
            raise ShareError("Share has been stopped.", 410)
        return record

    def _expire_if_needed(self, record: ShareRecord) -> None:
        if record.status not in ("stopped", "expired") and self._now() >= record.expires_at:
            record.status = "expired"
            self._wipe(record, keep_viewer=True)

    @staticmethod
    def _wipe(record: ShareRecord, *, keep_viewer: bool) -> None:
        record.accept_hash = None
        record.upload_hash = None
        if not keep_viewer:
            record.viewer_hash = None
        record.latest = None
