from datetime import datetime, timedelta, timezone

import pytest

from locator.core import ShareError, ShareStore


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.value

    def advance(self, **kwargs) -> None:
        self.value += timedelta(**kwargs)


def make_share(store: ShareStore):
    return store.create(label="Safe check-in", duration_minutes=30)


def test_invitation_is_one_time_and_tokens_are_not_interchangeable():
    store = ShareStore()
    created = make_share(store)
    accepted = store.accept(share_id=created["share_id"], accept_token=created["accept_token"], precision="approximate")
    with pytest.raises(ShareError, match="already been used"):
        store.accept(share_id=created["share_id"], accept_token=created["accept_token"], precision="exact")
    with pytest.raises(ShareError, match="Invalid upload"):
        store.upload(
            share_id=created["share_id"], upload_token=created["viewer_token"],
            latitude=1, longitude=1, accuracy_m=5, observed_at=datetime.now(timezone.utc),
        )
    assert accepted["upload_token"] != created["viewer_token"]


def test_approximate_precision_rounds_and_sets_minimum_accuracy():
    clock = Clock(); store = ShareStore(now=clock.now); created = make_share(store)
    accepted = store.accept(share_id=created["share_id"], accept_token=created["accept_token"], precision="approximate")
    point = store.upload(
        share_id=created["share_id"], upload_token=accepted["upload_token"],
        latitude=33.6844567, longitude=73.0478123, accuracy_m=8, observed_at=clock.now(),
    )
    assert point.latitude == 33.684
    assert point.longitude == 73.048
    assert point.accuracy_m == 110


def test_exact_precision_preserves_coordinates():
    clock = Clock(); store = ShareStore(now=clock.now); created = make_share(store)
    accepted = store.accept(share_id=created["share_id"], accept_token=created["accept_token"], precision="exact")
    point = store.upload(
        share_id=created["share_id"], upload_token=accepted["upload_token"],
        latitude=33.6844567, longitude=73.0478123, accuracy_m=8, observed_at=clock.now(),
    )
    assert point.latitude == 33.6844567
    assert point.longitude == 73.0478123


def test_stop_erases_location_and_upload_capability_but_keeps_status_visible():
    clock = Clock(); store = ShareStore(now=clock.now); created = make_share(store)
    accepted = store.accept(share_id=created["share_id"], accept_token=created["accept_token"], precision="exact")
    store.upload(
        share_id=created["share_id"], upload_token=accepted["upload_token"],
        latitude=1, longitude=2, accuracy_m=5, observed_at=clock.now(),
    )
    stopped = store.stop(share_id=created["share_id"], capability=accepted["upload_token"])
    assert stopped.status == "stopped"
    assert stopped.latest is None
    viewed = store.view(share_id=created["share_id"], viewer_token=created["viewer_token"])
    assert viewed.status == "stopped"
    with pytest.raises(ShareError):
        store.upload(
            share_id=created["share_id"], upload_token=accepted["upload_token"],
            latitude=1, longitude=2, accuracy_m=5, observed_at=clock.now(),
        )


def test_expiry_erases_location():
    clock = Clock(); store = ShareStore(now=clock.now); created = make_share(store)
    accepted = store.accept(share_id=created["share_id"], accept_token=created["accept_token"], precision="exact")
    store.upload(
        share_id=created["share_id"], upload_token=accepted["upload_token"],
        latitude=1, longitude=2, accuracy_m=5, observed_at=clock.now(),
    )
    clock.advance(minutes=31)
    record = store.view(share_id=created["share_id"], viewer_token=created["viewer_token"])
    assert record.status == "expired"
    assert record.latest is None


def test_rejects_stale_or_future_observations():
    clock = Clock(); store = ShareStore(now=clock.now); created = make_share(store)
    accepted = store.accept(share_id=created["share_id"], accept_token=created["accept_token"], precision="exact")
    for observed in (clock.now() - timedelta(minutes=11), clock.now() + timedelta(minutes=3)):
        with pytest.raises(ShareError):
            store.upload(
                share_id=created["share_id"], upload_token=accepted["upload_token"],
                latitude=1, longitude=2, accuracy_m=5, observed_at=observed,
            )
