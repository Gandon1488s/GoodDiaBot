import random
import secrets
from datetime import datetime


def gen_code() -> str:
    """12-symbol unique auth code."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(12))


def gen_rnocpp() -> str:
    return str(random.randint(1000000000, 9999999999))


def gen_unzr(dob_ddmmyyyy: str) -> str:
    try:
        parts = dob_ddmmyyyy.strip().split(".")
        d, m, y = parts[0].zfill(2), parts[1].zfill(2), parts[2].zfill(4)
        suffix = str(random.randint(10000, 99999))
        return f"{d}{m}{y}-{suffix}"
    except Exception:
        return f"01012000-{random.randint(10000, 99999)}"


def gen_document_number() -> str:
    """9 digits, first digit always 0."""
    return "0" + "".join(str(random.randint(0, 9)) for _ in range(8))


def gen_tax_number() -> str:
    """10 digits, first digit 3."""
    return "3" + "".join(str(random.randint(0, 9)) for _ in range(9))


def gen_unzr_from_iso(birthday_iso: str) -> str:
    """YYYY-MM-DD → DDMMYYYY-12345"""
    try:
        y, m, d = birthday_iso.strip().split("-")
        suffix = str(random.randint(10000, 99999))
        return f"{d}{m}{y}-{suffix}"
    except Exception:
        return f"01012000-{random.randint(10000, 99999)}"


def fmt_date_iso(dob: str) -> str:
    """DD.MM.YYYY → YYYY-MM-DD"""
    try:
        parts = dob.strip().split(".")
        if len(parts) == 3:
            d, m, y = parts
            return f"{y.zfill(4)}-{m.zfill(2)}-{d.zfill(2)}"
    except Exception:
        pass
    return dob


def fmt_dt(ts: float | None) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(float(ts)).strftime("%d.%m.%Y %H:%M")


def fmt_date(ts: float | None) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(float(ts)).strftime("%d.%m.%Y")


def uah_from_stars(stars: int) -> int:
    from config import UAH_PER_50_STARS, STARS_PER_PACK
    return int(stars) * UAH_PER_50_STARS // STARS_PER_PACK


def usdt_from_uah(uah: int) -> str:
    from decimal import Decimal, ROUND_UP
    from config import UAH_PER_1_USDT
    amt = (Decimal(uah) / Decimal(UAH_PER_1_USDT)).quantize(Decimal("0.01"), rounding=ROUND_UP)
    return format(amt, "f")
