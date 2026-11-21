"""Offline billing security checks; no real Stripe, RevenueCat, or database keys."""
from datetime import datetime, timezone
from uuid import UUID
from unittest.mock import patch
import hashlib
import hmac

import pytest

from app.services.billing import FEATURES, User, local_day_for_user, require_entitlement
from app.routers.billing_webhooks import _signature_rc, _stripe_sub_period, _transfer_participants


def test_quran_is_free_on_every_tier():
    for tier, flags in FEATURES.items():
        assert {"mushaf", "translations", "qari_audio",
                "basic_follow_along", "calendar_export"}.issubset(flags)


def test_entitlement_decorator_rejects_unknown_feature():
    with pytest.raises(ValueError):
        require_entitlement("ads")


def test_quota_date_uses_timezone_not_server_utc():
    user = User(UUID("00000000-0000-0000-0000-000000000001"), "Asia/Kuala_Lumpur")
    utc = datetime(2026, 11, 21, 18, 30, tzinfo=timezone.utc)
    assert local_day_for_user(user, utc).isoformat() == "2026-11-22"


def test_revenuecat_signature_roundtrip_and_tampering(monkeypatch):
    monkeypatch.setenv("REVENUECAT_WEBHOOK_SIGNING_SECRET", "test_not_for_production")
    raw = b'{"event":{"id":"evt_test"}}'
    moment = 1795284000
    digest = hmac.new(
        b"test_not_for_production", str(moment).encode() + b"." + raw,
        hashlib.sha256,
    ).hexdigest()
    header = f"t={moment},v1={digest}"
    with patch("app.routers.billing_webhooks.time.time", return_value=moment):
        assert _signature_rc(raw, header)
        assert not _signature_rc(raw + b"x", header)
        assert not _signature_rc(raw, "t=1,v1=" + digest)


def test_stripe_current_period_on_subscription_item():
    sub = {
        "items": {"data": [{
            "current_period_start": 1795284000,
            "current_period_end": 1797876000,
        }]}
    }
    start, end = _stripe_sub_period(sub)
    assert start is not None and end is not None and end > start


def test_revenuecat_transfer_has_no_app_user_id_and_tracks_both_accounts():
    event = {
        "type": "TRANSFER",
        "transferred_from": ["former-user"],
        "transferred_to": ["new-user"],
    }
    assert _transfer_participants(event) == {"former-user", "new-user"}
    assert _transfer_participants({"type": "TRANSFER"}) == set()
