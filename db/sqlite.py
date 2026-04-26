"""Bot data storage — backed by Supabase (persistent across deploys).

Drop-in replacement for the old SQLite module. All public function
signatures stay the same so callers don't need changes.
"""
import time
import httpx
from datetime import datetime, timedelta
from config import SUPABASE_URL, SUPABASE_KEY

_BASE = f"{SUPABASE_URL}/rest/v1"


def _h(prefer: str = "") -> dict:
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def _sync_get(path: str, params: dict | None = None) -> list[dict]:
    with httpx.Client(timeout=10) as c:
        r = c.get(f"{_BASE}/{path}", headers=_h(), params=params or {})
        return r.json() if r.status_code == 200 and r.text else []


def _sync_post(path: str, data: dict, prefer: str = "return=representation") -> list[dict]:
    with httpx.Client(timeout=10) as c:
        r = c.post(f"{_BASE}/{path}", headers=_h(prefer), json=data)
        if r.status_code in (200, 201):
            return r.json() if r.text else []
        print(f"[db] POST {path} error {r.status_code}: {r.text}")
        return []


def _sync_patch(path: str, params: dict, data: dict) -> bool:
    with httpx.Client(timeout=10) as c:
        r = c.patch(f"{_BASE}/{path}", headers=_h("return=representation"), params=params, json=data)
        if r.status_code in (200, 204):
            return True
        print(f"[db] PATCH {path} error {r.status_code}: {r.text}")
        return False


def _sync_delete(path: str, params: dict) -> bool:
    with httpx.Client(timeout=10) as c:
        r = c.delete(f"{_BASE}/{path}", headers=_h(), params=params)
        return r.status_code in (200, 204)


def _sync_upsert(path: str, data: dict) -> bool:
    with httpx.Client(timeout=10) as c:
        r = c.post(
            f"{_BASE}/{path}",
            headers={**_h("return=representation"), "Prefer": "return=representation,resolution=merge-duplicates"},
            json=data,
        )
        if r.status_code in (200, 201):
            return True
        print(f"[db] UPSERT {path} error {r.status_code}: {r.text}")
        return False


def init_db() -> None:
    """No-op: tables are created via Supabase SQL Editor."""
    pass


# ─── Users ────────────────────────────────────────────────────────────────────

def get_user(tid: int) -> dict | None:
    rows = _sync_get("bot_users", {"telegram_id": f"eq.{tid}", "limit": "1"})
    return rows[0] if rows else None


def ensure_user(tid: int) -> dict:
    u = get_user(tid)
    if u is None:
        _sync_post("bot_users", {"telegram_id": tid, "registered_at": time.time()})
        u = get_user(tid)
    return u


def add_balance(tid: int, uah: int) -> int:
    ensure_user(tid)
    u = get_user(tid)
    new_balance = int(u.get("balance_uah", 0)) + uah
    _sync_patch("bot_users", {"telegram_id": f"eq.{tid}"}, {"balance_uah": new_balance})
    return new_balance


def deduct_balance(tid: int, uah: int) -> bool:
    ensure_user(tid)
    u = get_user(tid)
    cur = int(u.get("balance_uah", 0))
    if cur < uah:
        return False
    _sync_patch("bot_users", {"telegram_id": f"eq.{tid}"}, {"balance_uah": cur - uah})
    return True


def activate_subscription(tid: int, days: int | None) -> float | None:
    now = time.time()
    if days is None:
        until_ts = None
    else:
        until_ts = (datetime.fromtimestamp(now) + timedelta(days=days)).timestamp()
    _sync_patch("bot_users", {"telegram_id": f"eq.{tid}"}, {
        "sub_active": True,
        "sub_at_ts": now,
        "sub_until_ts": until_ts,
    })
    return until_ts


def subscription_active(tid: int) -> bool:
    u = get_user(tid)
    if not u or not u.get("sub_active"):
        return False
    until = u.get("sub_until_ts")
    if until is None:
        return True
    if time.time() <= float(until):
        return True
    _sync_patch("bot_users", {"telegram_id": f"eq.{tid}"}, {"sub_active": False})
    return False


def activate_subscription_minutes(tid: int, minutes: int) -> float:
    now = time.time()
    until_ts = now + minutes * 60
    _sync_patch("bot_users", {"telegram_id": f"eq.{tid}"}, {
        "sub_active": True,
        "sub_at_ts": now,
        "sub_until_ts": until_ts,
    })
    return until_ts


def get_expired_subscriptions() -> list[dict]:
    now = time.time()
    rows = _sync_get("bot_users", {
        "sub_active": "eq.true",
        "sub_until_ts": f"not.is.null",
    })
    return [r for r in rows if r.get("sub_until_ts") is not None and float(r["sub_until_ts"]) < now]


def revoke_subscription(tid: int) -> None:
    _sync_patch("bot_users", {"telegram_id": f"eq.{tid}"}, {"sub_active": False, "sub_until_ts": None})
    _sync_delete("auth_codes", {"telegram_id": f"eq.{tid}"})


# ─── Auth codes ───────────────────────────────────────────────────────────────

def auth_code_set(tid: int, code: str) -> None:
    _sync_upsert("auth_codes", {"telegram_id": tid, "code": code, "created_at": time.time()})


def auth_code_get(tid: int) -> str | None:
    rows = _sync_get("auth_codes", {"telegram_id": f"eq.{tid}", "limit": "1"})
    return str(rows[0]["code"]) if rows else None


# ─── Referrals ────────────────────────────────────────────────────────────────

def ref_register(inviter_id: int, invitee_id: int) -> None:
    if inviter_id == invitee_id:
        return
    # Insert referral (ignore if exists)
    rows = _sync_get("referrals", {"invitee_id": f"eq.{invitee_id}", "limit": "1"})
    if not rows:
        _sync_post("referrals", {"invitee_id": invitee_id, "inviter_id": inviter_id, "created_at": time.time()})
    # Upsert stats
    stats_rows = _sync_get("referral_stats", {"inviter_id": f"eq.{inviter_id}", "limit": "1"})
    if stats_rows:
        cur = int(stats_rows[0].get("registered_count", 0))
        _sync_patch("referral_stats", {"inviter_id": f"eq.{inviter_id}"}, {"registered_count": cur + 1})
    else:
        _sync_post("referral_stats", {"inviter_id": inviter_id, "registered_count": 1, "paid_count": 0, "claimed_batches": 0})


def ref_mark_paid(invitee_id: int) -> int | None:
    rows = _sync_get("referrals", {"invitee_id": f"eq.{invitee_id}", "limit": "1"})
    if not rows or rows[0].get("paid_at") is not None:
        return None
    inviter_id = int(rows[0]["inviter_id"])
    _sync_patch("referrals", {"invitee_id": f"eq.{invitee_id}"}, {"paid_at": time.time()})
    stats_rows = _sync_get("referral_stats", {"inviter_id": f"eq.{inviter_id}", "limit": "1"})
    if stats_rows:
        cur = int(stats_rows[0].get("paid_count", 0))
        _sync_patch("referral_stats", {"inviter_id": f"eq.{inviter_id}"}, {"paid_count": cur + 1})
    else:
        _sync_post("referral_stats", {"inviter_id": inviter_id, "registered_count": 0, "paid_count": 1, "claimed_batches": 0})
    return inviter_id


def ref_stats(inviter_id: int) -> tuple[int, int, int]:
    rows = _sync_get("referral_stats", {"inviter_id": f"eq.{inviter_id}", "limit": "1"})
    if not rows:
        return 0, 0, 0
    r = rows[0]
    return int(r.get("registered_count", 0)), int(r.get("paid_count", 0)), int(r.get("claimed_batches", 0))


def ref_claim_batch(inviter_id: int) -> bool:
    _, paid, claimed = ref_stats(inviter_id)
    if paid // 3 <= claimed:
        return False
    _sync_patch("referral_stats", {"inviter_id": f"eq.{inviter_id}"}, {"claimed_batches": claimed + 1})
    return True


# ─── Crypto invoices ──────────────────────────────────────────────────────────

def crypto_pending_store(invoice_id: int, uah: int, tid: int) -> None:
    _sync_upsert("crypto_pending", {"invoice_id": invoice_id, "uah_amount": uah, "telegram_id": tid, "created_at": time.time()})


def crypto_pending_get(invoice_id: int) -> int | None:
    rows = _sync_get("crypto_pending", {"invoice_id": f"eq.{invoice_id}", "limit": "1"})
    return int(rows[0]["uah_amount"]) if rows else None


def crypto_pending_delete(invoice_id: int) -> None:
    _sync_delete("crypto_pending", {"invoice_id": f"eq.{invoice_id}"})


def crypto_is_paid(invoice_id: int) -> bool:
    rows = _sync_get("crypto_paid", {"invoice_id": f"eq.{invoice_id}", "limit": "1"})
    return bool(rows)


def crypto_mark_paid(invoice_id: int, uah: int, tid: int) -> None:
    _sync_upsert("crypto_paid", {"invoice_id": invoice_id, "uah_credited": uah, "telegram_id": tid, "paid_at": time.time()})
