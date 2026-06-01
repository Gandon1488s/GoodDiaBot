"""Handler for managing additional documents (driver license etc.)."""
import re

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.sqlite import auth_code_get, subscription_active
from db.supabase import get_profile, update_profile, upload_file
from keyboards.menus import home
from utils.helpers import gen_license_number, gen_license_dates
from utils.image import process_avatar
from middleware.cleanup import track_message

router = Router()


class LicenseFill(StatesGroup):
    photo = State()
    categories = State()
    doi = State()


# ─── Documents menu ─────────────────────────────────────────────────────────

def docs_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚗  Водійське посвідчення", callback_data="doc_license")],
        [InlineKeyboardButton(text="🏠  Головне меню", callback_data="menu_home")],
    ])


def license_menu(is_active: bool) -> InlineKeyboardMarkup:
    rows = []
    if is_active:
        rows.append([InlineKeyboardButton(text="❌  Вимкнути", callback_data="license_off")])
        rows.append([InlineKeyboardButton(text="📷  Змінити фото", callback_data="license_edit_photo")])
        rows.append([InlineKeyboardButton(text="🏷  Змінити категорії", callback_data="license_edit_cat")])
        rows.append([InlineKeyboardButton(text="📅  Змінити дату видачі", callback_data="license_edit_doi")])
    else:
        rows.append([InlineKeyboardButton(text="✅  Увімкнути", callback_data="license_on")])
    rows.append([InlineKeyboardButton(text="📂  Документи", callback_data="menu_docs")])
    rows.append([InlineKeyboardButton(text="🏠  Головне меню", callback_data="menu_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── "Додати документи" ─────────────────────────────────────────────────────

@router.callback_query(F.data == "menu_docs")
async def menu_docs(cq: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cq.message.edit_text(
        "📂 <b>Документи</b>\n\n"
        "Тут ви можете додати або прибрати додаткові документи,\n"
        "які відображатимуться у вашому застосунку Дія.\n\n"
        "Оберіть документ:",
        parse_mode="HTML",
        reply_markup=docs_menu(),
    )
    await cq.answer()


# ─── License info ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "doc_license")
async def doc_license(cq: CallbackQuery) -> None:
    uid = cq.from_user.id

    if not subscription_active(uid):
        await cq.answer("❌ Потрібна активна підписка!", show_alert=True)
        return

    code = auth_code_get(uid)
    if not code:
        await cq.answer("❌ Спочатку отримайте код авторизації!", show_alert=True)
        return

    profile = await get_profile(uid)
    is_active = bool(profile and profile.get("license_active"))
    cats = (profile or {}).get("license_categories", "") or "—"
    num = (profile or {}).get("license_number", "") or "—"
    doi = (profile or {}).get("license_doi", "") or "—"

    status = "✅ Увімкнено" if is_active else "❌ Вимкнено"

    text = (
        "🚗 <b>Водійське посвідчення</b>\n\n"
        f"Статус: {status}\n"
    )
    if is_active:
        text += (
            f"📋 Номер: <code>{num}</code>\n"
            f"🏷 Категорії: <b>{cats}</b>\n"
            f"📅 Дата видачі: {doi}\n"
        )
    text += "\nОберіть дію:"

    await cq.message.edit_text(text, parse_mode="HTML", reply_markup=license_menu(is_active))
    await cq.answer()


# ─── Turn ON → ask photo then categories ─────────────────────────────────────

@router.callback_query(F.data == "license_on")
async def license_on(cq: CallbackQuery, state: FSMContext) -> None:
    uid = cq.from_user.id

    if not subscription_active(uid):
        await cq.answer("❌ Потрібна активна підписка!", show_alert=True)
        return

    code = auth_code_get(uid)
    if not code:
        await cq.answer("❌ Спочатку отримайте код авторизації!", show_alert=True)
        return

    await state.set_state(LicenseFill.photo)
    await state.update_data(auth_code=code)
    await cq.message.edit_text(
        "📷 <b>Фото для водійського посвідчення</b>\n\n"
        "Надішліть фото, яке буде відображатися\n"
        "на вашому водійському посвідченні.\n\n"
        "💡 Рекомендація: фото обличчя на\n"
        "однотонному фоні, як на документ.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌  Скасувати", callback_data="doc_license")],
        ]),
    )
    await cq.answer()


@router.message(LicenseFill.photo, F.photo)
async def license_fill_photo(msg: Message, state: FSMContext) -> None:
    data = await state.get_data()
    auth_code = data.get("auth_code", "")

    best = max(msg.photo, key=lambda p: p.file_size or 0)
    photo_url = ""
    try:
        tg_file = await msg.bot.get_file(best.file_id)
        buf = await msg.bot.download(tg_file)
        buf.seek(0)
        raw = buf.read()
        processed = process_avatar(raw)
        photo_url = await upload_file(
            processed, "avatars", f"{auth_code}/license_photo.jpg", "image/jpeg"
        ) or ""
    except Exception as e:
        print(f"[documents] license photo upload error: {e}")

    # If edit mode — just save photo and return to license info
    if data.get("edit_mode") == "photo":
        if photo_url:
            await update_profile(msg.from_user.id, {"auth_code": auth_code, "license_photo_url": photo_url})
        await state.clear()
        sent = await msg.answer(
            "✅ Фото водійського оновлено!" if photo_url else "❌ Не вдалося завантажити фото.",
            reply_markup=license_menu(True),
        )
        track_message(msg.chat.id, sent.message_id)
        return

    await state.update_data(license_photo_url=photo_url)
    await state.set_state(LicenseFill.categories)
    await msg.answer(
        "✅ Фото отримано!\n\n"
        "🏷 <b>Введіть категорії водійського посвідчення</b>\n\n"
        "Наприклад: <b>B</b> або <b>A1, B, C1</b>\n"
        "Якщо кілька — через кому.",
        parse_mode="HTML",
    )


@router.message(LicenseFill.photo)
async def license_fill_photo_invalid(msg: Message) -> None:
    await msg.answer(
        "❌ Надішліть саме <b>фото</b> (не файл).\n"
        "Або натисніть «Скасувати».",
        parse_mode="HTML",
    )


@router.message(LicenseFill.categories, F.text)
async def license_fill_categories(msg: Message, state: FSMContext) -> None:
    text = (msg.text or "").strip().upper()
    # Validate: letters, digits, commas, spaces
    if not re.match(r'^[A-ZА-Я0-9,\s]+$', text):
        await msg.answer(
            "❌ Невірний формат. Введіть категорії латиницею.\n"
            "Приклад: <b>B</b> або <b>A1, B, C1</b>",
            parse_mode="HTML",
        )
        return

    # Normalize: remove extra spaces, add space after commas
    categories = ", ".join(c.strip() for c in text.split(",") if c.strip())

    data = await state.get_data()
    auth_code = data.get("auth_code", "")

    # If edit mode — just update categories
    if data.get("edit_mode") == "categories":
        ok = await update_profile(msg.from_user.id, {
            "auth_code": auth_code,
            "license_categories": categories,
        })
        await state.clear()
        sent = await msg.answer(
            f"✅ Категорії оновлено: <b>{categories}</b>" if ok else "❌ Помилка збереження.",
            parse_mode="HTML",
            reply_markup=license_menu(True),
        )
        track_message(msg.chat.id, sent.message_id)
        return

    license_photo_url = data.get("license_photo_url", "")

    # Generate number and dates
    license_number = gen_license_number()
    doi, exp = gen_license_dates()

    # Save to Supabase
    update_data = {
        "auth_code": auth_code,
        "license_active": True,
        "license_number": license_number,
        "license_categories": categories,
        "license_doi": doi,
    }
    if license_photo_url:
        update_data["license_photo_url"] = license_photo_url

    ok = await update_profile(msg.from_user.id, update_data)
    await state.clear()

    if ok:
        sent = await msg.answer(
            "✅ <b>Водійське посвідчення увімкнено!</b>\n\n"
            f"📋 Номер: <code>{license_number}</code>\n"
            f"🏷 Категорії: <b>{categories}</b>\n"
            f"📅 Дата видачі: {doi}\n"
            f"🖼 Фото: {'завантажено ✅' if license_photo_url else '❌ не завантажено'}\n\n"
            "Документ з'явиться у вашому застосунку Дія\n"
            "при наступному вході за кодом авторизації.",
            parse_mode="HTML",
            reply_markup=license_menu(True),
        )
    else:
        sent = await msg.answer(
            "❌ Помилка збереження. Спробуйте ще раз.",
            reply_markup=home(),
        )
    track_message(msg.chat.id, sent.message_id)


# ─── Turn OFF ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "license_off")
async def license_off(cq: CallbackQuery) -> None:
    uid = cq.from_user.id
    code = auth_code_get(uid)
    if not code:
        await cq.answer("❌ Помилка", show_alert=True)
        return

    ok = await update_profile(uid, {"auth_code": code, "license_active": False})
    if ok:
        await cq.message.edit_text(
            "🚗 <b>Водійське посвідчення</b>\n\n"
            "Статус: ❌ Вимкнено\n\n"
            "Документ більше не відображається\n"
            "у вашому застосунку Дія.\n\n"
            "Оберіть дію:",
            parse_mode="HTML",
            reply_markup=license_menu(False),
        )
    else:
        await cq.answer("❌ Помилка збереження", show_alert=True)
    await cq.answer()


# ─── Edit photo ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "license_edit_photo")
async def license_edit_photo(cq: CallbackQuery, state: FSMContext) -> None:
    code = auth_code_get(cq.from_user.id)
    if not code:
        await cq.answer("❌ Помилка", show_alert=True)
        return

    await state.set_state(LicenseFill.photo)
    await state.update_data(auth_code=code, edit_mode="photo")
    await cq.message.edit_text(
        "📷 <b>Нове фото для водійського</b>\n\n"
        "Надішліть нове фото.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌  Скасувати", callback_data="doc_license")],
        ]),
    )
    await cq.answer()


# ─── Edit categories ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "license_edit_cat")
async def license_edit_cat(cq: CallbackQuery, state: FSMContext) -> None:
    code = auth_code_get(cq.from_user.id)
    if not code:
        await cq.answer("❌ Помилка", show_alert=True)
        return

    await state.set_state(LicenseFill.categories)
    await state.update_data(auth_code=code, edit_mode="categories")
    await cq.message.edit_text(
        "🏷 <b>Нові категорії</b>\n\n"
        "Введіть категорії водійського посвідчення.\n"
        "Наприклад: <b>B</b> або <b>A1, B, C1</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌  Скасувати", callback_data="doc_license")],
        ]),
    )
    await cq.answer()


# ─── Edit date of issue (DOI) ──────────────────────────────────────────────────

@router.callback_query(F.data == "license_edit_doi")
async def license_edit_doi(cq: CallbackQuery, state: FSMContext) -> None:
    code = auth_code_get(cq.from_user.id)
    if not code:
        await cq.answer("❌ Помилка", show_alert=True)
        return

    await state.set_state(LicenseFill.doi)
    await state.update_data(auth_code=code)
    await cq.message.edit_text(
        "📅 <b>Нова дата видачі прав</b>\n\n"
        "Введіть дату видачі у форматі <b>ДД.ММ.РРРР</b>\n"
        "Приклад: <b>28.05.2023</b>\n\n"
        "<i>Срок дії розраховується автоматично (+30 років).</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌  Скасувати", callback_data="doc_license")],
        ]),
    )
    await cq.answer()


@router.message(LicenseFill.doi, F.text)
async def license_fill_doi(msg: Message, state: FSMContext) -> None:
    text = (msg.text or "").strip()
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", text):
        await msg.answer(
            "❌ Невірний формат. Введіть дату у форматі <b>ДД.ММ.РРРР</b>",
            parse_mode="HTML",
        )
        return

    data = await state.get_data()
    auth_code = data.get("auth_code", "")

    ok = await update_profile(msg.from_user.id, {
        "auth_code": auth_code,
        "license_doi": text,
    })
    await state.clear()

    if ok:
        sent = await msg.answer(
            f"✅ Дату видачі прав оновлено: <b>{text}</b>",
            parse_mode="HTML",
            reply_markup=license_menu(True),
        )
    else:
        sent = await msg.answer(
            "❌ Помилка збереження. Спробуйте ще раз.",
            reply_markup=home(),
        )
    track_message(msg.chat.id, sent.message_id)
