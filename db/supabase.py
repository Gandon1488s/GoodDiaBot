import httpx
from config import SUPABASE_URL, SUPABASE_KEY
from utils.helpers import gen_document_number, gen_tax_number

# ─── Persistent async HTTP client (reuses TCP+TLS connections) ───────────────
_async_client: httpx.AsyncClient | None = None


async def _get_async_client() -> httpx.AsyncClient:
    global _async_client
    if _async_client is None or _async_client.is_closed:
        _async_client = httpx.AsyncClient(
            timeout=15,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            http2=True,
        )
    return _async_client


def _headers(prefer: str = "") -> dict:
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


# ─── profiles ─────────────────────────────────────────────────────────────────

async def upsert_profile(telegram_id: int, auth_code: str, extra: dict | None = None) -> bool:
    payload = {"telegram_user_id": telegram_id, "auth_code": auth_code}
    if extra:
        payload.update(extra)
    try:
        c = await _get_async_client()
        chk = await c.get(
            f"{SUPABASE_URL}/rest/v1/profiles",
            headers=_headers(),
            params={"telegram_user_id": f"eq.{telegram_id}", "limit": "1"},
        )
        exists = chk.status_code == 200 and bool(chk.json())
        existing = chk.json()[0] if exists else {}

        if exists:
            update_payload = {k: v for k, v in payload.items() if k != "telegram_user_id"}
            r = await c.patch(
                f"{SUPABASE_URL}/rest/v1/profiles",
                headers=_headers("return=representation"),
                params={"telegram_user_id": f"eq.{telegram_id}"},
                json=update_payload,
            )
        else:
            insert_payload = {
                "full_name": "",
                "document_number": gen_document_number(),
                "tax_number": gen_tax_number(),
                **payload,
            }
            r = await c.post(
                f"{SUPABASE_URL}/rest/v1/profiles",
                headers=_headers("return=representation"),
                json=insert_payload,
            )

        if r.status_code not in (200, 201, 204):
            print(f"[supabase] upsert_profile error {r.status_code}: {r.text}")
            return False

        if exists:
            patch2 = {}
            if not existing.get("document_number"):
                patch2["document_number"] = gen_document_number()
            if not existing.get("tax_number"):
                patch2["tax_number"] = gen_tax_number()
            if patch2:
                await c.patch(
                    f"{SUPABASE_URL}/rest/v1/profiles",
                    headers=_headers(),
                    params={"telegram_user_id": f"eq.{telegram_id}"},
                    json=patch2,
                )
                print(f"[supabase] upsert_profile: filled missing fields {list(patch2.keys())} uid={telegram_id}")

        print(f"[supabase] upsert_profile ok ({'update' if exists else 'insert'}) uid={telegram_id}")
        return True
    except Exception as e:
        print(f"[supabase] upsert_profile exception: {e}")
        return False


async def update_profile(telegram_id: int, data: dict) -> bool:
    try:
        c = await _get_async_client()
        chk = await c.get(
            f"{SUPABASE_URL}/rest/v1/profiles",
            headers=_headers(),
            params={"telegram_user_id": f"eq.{telegram_id}", "limit": "1"},
        )
        exists = chk.status_code == 200 and bool(chk.json())

        if not exists:
            auth_code = data.get("auth_code", "")
            ins = await c.post(
                f"{SUPABASE_URL}/rest/v1/profiles",
                headers=_headers("return=representation"),
                json={"telegram_user_id": telegram_id, "auth_code": auth_code, "full_name": ""},
            )
            if ins.status_code not in (200, 201):
                print(f"[supabase] update_profile create error {ins.status_code}: {ins.text}")
                return False
            print(f"[supabase] update_profile: created missing row uid={telegram_id}")

        r = await c.patch(
            f"{SUPABASE_URL}/rest/v1/profiles",
            headers=_headers("return=representation"),
            params={"telegram_user_id": f"eq.{telegram_id}"},
            json=data,
        )
        if r.status_code not in (200, 204):
            print(f"[supabase] update_profile patch error {r.status_code}: {r.text}")
            return False
        rows = r.json() if r.text and r.text != "[]" else []
        if rows:
            print(f"[supabase] update_profile ok uid={telegram_id} fields={list(data.keys())}")
        else:
            print(f"[supabase] update_profile: status={r.status_code} but no rows returned uid={telegram_id} (may still be ok)")
        return True
    except Exception as e:
        print(f"[supabase] update_profile exception: {e}")
        return False


async def get_telegram_user(telegram_id: int) -> dict | None:
    try:
        c = await _get_async_client()
        r = await c.get(
            f"{SUPABASE_URL}/rest/v1/telegram_users",
            headers=_headers(),
            params={"telegram_user_id": f"eq.{telegram_id}", "limit": "1"},
        )
        if r.status_code != 200:
            return None
        rows = r.json()
        return rows[0] if rows else None
    except Exception as e:
        print(f"[supabase] get_telegram_user exception: {e}")
        return None


async def get_profile(telegram_id: int) -> dict | None:
    try:
        c = await _get_async_client()
        r = await c.get(
            f"{SUPABASE_URL}/rest/v1/profiles",
            headers=_headers(),
            params={"telegram_user_id": f"eq.{telegram_id}", "limit": "1"},
        )
        if r.status_code != 200:
            return None
        rows = r.json()
        return rows[0] if rows else None
    except Exception as e:
        print(f"[supabase] get_profile exception: {e}")
        return None


async def clear_auth_code(telegram_id: int) -> bool:
    try:
        c = await _get_async_client()
        r = await c.patch(
            f"{SUPABASE_URL}/rest/v1/profiles",
            headers=_headers(),
            params={"telegram_user_id": f"eq.{telegram_id}"},
            json={"auth_code": ""},
        )
        if r.status_code not in (200, 204):
            print(f"[supabase] clear_auth_code error {r.status_code}: {r.text}")
            return False
        print(f"[supabase] clear_auth_code ok uid={telegram_id}")
        return True
    except Exception as e:
        print(f"[supabase] clear_auth_code exception: {e}")
        return False


# ─── telegram_users ───────────────────────────────────────────────────────────

async def upsert_telegram_user(
    telegram_id: int,
    auth_code: str,
    sub_active: bool,
    sub_until_iso: str | None,
) -> bool:
    payload = {
        "telegram_user_id": telegram_id,
        "auth_code": auth_code,
        "subscription_active": sub_active,
        "subscription_until": sub_until_iso,
    }
    try:
        c = await _get_async_client()
        chk = await c.get(
            f"{SUPABASE_URL}/rest/v1/telegram_users",
            headers=_headers(),
            params={"telegram_user_id": f"eq.{telegram_id}", "limit": "1"},
        )
        exists = chk.status_code == 200 and bool(chk.json())

        if exists:
            r = await c.patch(
                f"{SUPABASE_URL}/rest/v1/telegram_users",
                headers=_headers("return=representation"),
                params={"telegram_user_id": f"eq.{telegram_id}"},
                json=payload,
            )
        else:
            r = await c.post(
                f"{SUPABASE_URL}/rest/v1/telegram_users",
                headers=_headers("return=representation"),
                json=payload,
            )

        if r.status_code not in (200, 201, 204):
            print(f"[supabase] upsert_telegram_user error {r.status_code}: {r.text}")
            return False
        print(f"[supabase] upsert_telegram_user ok ({'update' if exists else 'insert'}) uid={telegram_id} code={auth_code}")
        return True
    except Exception as e:
        print(f"[supabase] upsert_telegram_user exception: {e}")
        return False


# ─── Storage ──────────────────────────────────────────────────────────────────

async def upload_file(file_bytes: bytes, bucket: str, path: str, content_type: str) -> str | None:
    try:
        url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{path}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        c = await _get_async_client()
        r = await c.post(url, headers=headers, content=file_bytes, timeout=30)
        if r.status_code not in (200, 201):
            print(f"[supabase] upload_file error {r.status_code}: {r.text}")
            return None
        pub = f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}"
        print(f"[supabase] upload ok → {pub}")
        return pub
    except Exception as e:
        print(f"[supabase] upload_file exception: {e}")
        return None
