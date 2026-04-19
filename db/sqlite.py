import sqlite3
import time
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path(__file__).resolve().parent.parent / "bot.db"
_DB: sqlite3.Connection | None = None


def db() -> sqlite3.Connection:
    global _DB
    if _DB is None:
        _DB = sqlite3.connect(DB_PATH, check_same_thread=False)
        _DB.row_factory = sqlite3.Row
    return _DB


def init_db() -> None:
    c = db()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id   INTEGER PRIMARY KEY,
            balance_uah   INTEGER NOT NULL DEFAULT 0,
            sub_active    INTEGER NOT NULL DEFAULT 0,
            sub_until_ts  REAL,
            sub_at_ts     REAL,
            registered_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS auth_codes (
            telegram_id INTEGER PRIMARY KEY,
            code        TEXT NOT NULL,
            created_at  REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS referrals (
            invitee_id  INTEGER PRIMARY KEY,
            inviter_id  INTEGER NOT NULL,
            created_at  REAL NOT NULL,
            paid_at     REAL
        );

        CREATE TABLE IF NOT EXISTS referral_stats (
            inviter_id       INTEGER PRIMARY KEY,
            registered_count INTEGER NOT NULL DEFAULT 0,
            paid_count       INTEGER NOT NULL DEFAULT 0,
            claimed_batches  INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS crypto_pending (
            invoice_id   INTEGER PRIMARY KEY,
            uah_amount   INTEGER NOT NULL,
            telegram_id  INTEGER NOT NULL,
            created_at   REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS crypto_paid (
            invoice_id   INTEGER PRIMARY KEY,
            uah_credited INTEGER NOT NULL,
            telegram_id  INTEGER NOT NULL,
            paid_at      REAL NOT NULL
        );
    """)
    c.commit()


# ─── Users ────────────────────────────────────────────────────────────────────

def get_user(tid: int) -> sqlite3.Row | None:
    return db().execute("SELECT * FROM users WHERE telegram_id=?", (tid,)).fetchone()


def ensure_user(tid: int) -> sqlite3.Row:
    u = get_user(tid)
    if u is None:
        db().execute(
            "INSERT INTO users (telegram_id, registered_at) VALUES (?, ?)",
            (tid, time.time()),
        )
        db().commit()
        u = get_user(tid)
    return u


def add_balance(tid: int, uah: int) -> int:
    ensure_user(tid)
    db().execute("UPDATE users SET balance_uah = balance_uah + ? WHERE telegram_id=?", (uah, tid))
    db().commit()
    return int(db().execute("SELECT balance_uah FROM users WHERE telegram_id=?", (tid,)).fetchone()["balance_uah"])


def deduct_balance(tid: int, uah: int) -> bool:
    ensure_user(tid)
    row = db().execute("SELECT balance_uah FROM users WHERE telegram_id=?", (tid,)).fetchone()
    if not row or int(row["balance_uah"]) < uah:
        return False
    db().execute("UPDATE users SET balance_uah = balance_uah - ? WHERE telegram_id=?", (uah, tid))
    db().commit()
    return True


def activate_subscription(tid: int, days: int | None) -> float | None:
    now = time.time()
    if days is None:
        until_ts = None
    else:
        until_ts = (datetime.fromtimestamp(now) + timedelta(days=days)).timestamp()
    db().execute(
        "UPDATE users SET sub_active=1, sub_at_ts=?, sub_until_ts=? WHERE telegram_id=?",
        (now, until_ts, tid),
    )
    db().commit()
    return until_ts


def subscription_active(tid: int) -> bool:
    row = db().execute("SELECT sub_active, sub_until_ts FROM users WHERE telegram_id=?", (tid,)).fetchone()
    if not row or not row["sub_active"]:
        return False
    until = row["sub_until_ts"]
    if until is None:
        return True
    if time.time() <= float(until):
        return True
    db().execute("UPDATE users SET sub_active=0 WHERE telegram_id=?", (tid,))
    db().commit()
    return False


def revoke_subscription(tid: int) -> None:
    db().execute(
        "UPDATE users SET sub_active=0, sub_until_ts=NULL WHERE telegram_id=?",
        (tid,),
    )
    db().execute("DELETE FROM auth_codes WHERE telegram_id=?", (tid,))
    db().commit()


# ─── Auth codes ───────────────────────────────────────────────────────────────

def auth_code_set(tid: int, code: str) -> None:
    db().execute(
        "INSERT INTO auth_codes (telegram_id, code, created_at) VALUES (?,?,?) "
        "ON CONFLICT(telegram_id) DO UPDATE SET code=excluded.code, created_at=excluded.created_at",
        (tid, code, time.time()),
    )
    db().commit()


def auth_code_get(tid: int) -> str | None:
    row = db().execute("SELECT code FROM auth_codes WHERE telegram_id=?", (tid,)).fetchone()
    return str(row["code"]) if row else None


# ─── Referrals ────────────────────────────────────────────────────────────────

def ref_register(inviter_id: int, invitee_id: int) -> None:
    if inviter_id == invitee_id:
        return
    c = db()
    c.execute(
        "INSERT OR IGNORE INTO referrals (invitee_id, inviter_id, created_at) VALUES (?,?,?)",
        (invitee_id, inviter_id, time.time()),
    )
    c.execute(
        "INSERT INTO referral_stats (inviter_id, registered_count) VALUES (?,1) "
        "ON CONFLICT(inviter_id) DO UPDATE SET registered_count=registered_count+1",
        (inviter_id,),
    )
    c.commit()


def ref_mark_paid(invitee_id: int) -> int | None:
    row = db().execute(
        "SELECT inviter_id, paid_at FROM referrals WHERE invitee_id=?", (invitee_id,)
    ).fetchone()
    if not row or row["paid_at"] is not None:
        return None
    inviter_id = int(row["inviter_id"])
    db().execute("UPDATE referrals SET paid_at=? WHERE invitee_id=?", (time.time(), invitee_id))
    db().execute(
        "INSERT INTO referral_stats (inviter_id, paid_count) VALUES (?,1) "
        "ON CONFLICT(inviter_id) DO UPDATE SET paid_count=paid_count+1",
        (inviter_id,),
    )
    db().commit()
    return inviter_id


def ref_stats(inviter_id: int) -> tuple[int, int, int]:
    row = db().execute(
        "SELECT registered_count, paid_count, claimed_batches FROM referral_stats WHERE inviter_id=?",
        (inviter_id,),
    ).fetchone()
    if not row:
        return 0, 0, 0
    return int(row["registered_count"]), int(row["paid_count"]), int(row["claimed_batches"])


def ref_claim_batch(inviter_id: int) -> bool:
    _, paid, claimed = ref_stats(inviter_id)
    if paid // 3 <= claimed:
        return False
    db().execute(
        "UPDATE referral_stats SET claimed_batches=claimed_batches+1 WHERE inviter_id=?",
        (inviter_id,),
    )
    db().commit()
    return True


# ─── Crypto invoices ──────────────────────────────────────────────────────────

def crypto_pending_store(invoice_id: int, uah: int, tid: int) -> None:
    db().execute(
        "INSERT OR REPLACE INTO crypto_pending (invoice_id, uah_amount, telegram_id, created_at) VALUES (?,?,?,?)",
        (invoice_id, uah, tid, time.time()),
    )
    db().commit()


def crypto_pending_get(invoice_id: int) -> int | None:
    row = db().execute("SELECT uah_amount FROM crypto_pending WHERE invoice_id=?", (invoice_id,)).fetchone()
    return int(row["uah_amount"]) if row else None


def crypto_pending_delete(invoice_id: int) -> None:
    db().execute("DELETE FROM crypto_pending WHERE invoice_id=?", (invoice_id,))
    db().commit()


def crypto_is_paid(invoice_id: int) -> bool:
    return db().execute("SELECT 1 FROM crypto_paid WHERE invoice_id=?", (invoice_id,)).fetchone() is not None


def crypto_mark_paid(invoice_id: int, uah: int, tid: int) -> None:
    db().execute(
        "INSERT OR IGNORE INTO crypto_paid (invoice_id, uah_credited, telegram_id, paid_at) VALUES (?,?,?,?)",
        (invoice_id, uah, tid, time.time()),
    )
    db().commit()
