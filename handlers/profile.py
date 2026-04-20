import re

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.types.web_app_info import WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.sqlite import ensure_user, auth_code_set, subscription_active
from db.supabase import update_profile, upload_file, get_profile, get_telegram_user
from keyboards.menus import home, cancel, signature_skip, sex_choice
from utils.image import process_avatar, process_signature
from utils.helpers import fmt_date_iso, gen_code, gen_unzr_from_iso
from config import SIGNATURE_WEBAPP_URL
from middleware.cleanup import track_message

router = Router()


class FillProfile(StatesGroup):
    photo     = State()
    fio       = State()
    birthday  = State()
    sex       = State()
    signature = State()


# ─── Step 1: Photo ────────────────────────────────────────────────────────────

@router.message(FillProfile.photo, F.photo)
async def fill_photo(msg: Message, state: FSMContext) -> None:
    best = max(msg.photo, key=lambda p: p.file_size or 0)
    data = await state.get_data()
    auth_code = data.get("auth_code", "")

    avatar_url = ""
    if auth_code:
        try:
            print(f"[profile] fill_photo: downloading file_id={best.file_id[:20]}...")
            tg_file = await msg.bot.get_file(best.file_id)
            buf = await msg.bot.download(tg_file)
            buf.seek(0)
            raw = buf.read()
            print(f"[profile] fill_photo: raw len={len(raw)}")
            processed = process_avatar(raw)
            print(f"[profile] fill_photo: processed len={len(processed)}")
            avatar_url = await upload_file(processed, "avatars", f"{auth_code}/avatar.jpg", "image/jpeg") or ""
            print(f"[profile] fill_photo: avatar_url={avatar_url!r}")
        except Exception as e:
            import traceback
            print(f"[profile] fill_photo error: {e}")
            traceback.print_exc()

    await state.update_data(avatar_url=avatar_url)
    await state.set_state(FillProfile.fio)
    await msg.answer(
        ("✅ Фото отримано та завантажено!" if avatar_url else "✅ Фото отримано (завантаження при збереженні)") + "\n\n"
        "✍️ <b>Крок 2 з 3 — ПІБ</b>\n\n"
        "Введіть повне ПІБ:\n"
        "Формат: <b>Прізвище Ім'я По-батькові</b>\n"
        "Приклад: <b>Іванов Іван Іванович</b>",
        parse_mode="HTML",
    )


# ─── Step 2: FIO ─────────────────────────────────────────────────────────────

@router.message(FillProfile.fio, F.text)
async def fill_fio(msg: Message, state: FSMContext) -> None:
    text = (msg.text or "").strip()
    if len(text.split()) < 2:
        await msg.answer(
            "❌ Введіть повне ПІБ через пробіл.\n"
            "Приклад: <b>Іванов Іван Іванович</b>",
            parse_mode="HTML",
        )
        return
    await state.update_data(fio=text)
    await state.set_state(FillProfile.birthday)
    await msg.answer(
        "📅 <b>Крок 3 з 3 — Дата народження</b>\n\n"
        "Формат: <b>ДД.ММ.РРРР</b>\n"
        "Приклад: <b>15.03.1995</b>",
        parse_mode="HTML",
    )


# ─── Step 3: Birthday → upload avatar ────────────────────────────────────────

@router.message(FillProfile.birthday, F.text)
async def fill_birthday(msg: Message, state: FSMContext) -> None:
    text = (msg.text or "").strip()
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", text):
        await msg.answer(
            "❌ Невірний формат. Введіть дату у форматі <b>ДД.ММ.РРРР</b>",
            parse_mode="HTML",
        )
        return

    data = await state.get_data()
    auth_code = data.get("auth_code", "")
    fio = data.get("fio", "")

    if not auth_code:
        await msg.answer("❌ Помилка: код авторизації не знайдено. Зверніться в підтримку.", reply_markup=home())
        await state.clear()
        return

    await msg.answer("⏳ Зберігаємо дані та завантажуємо фото...")

    birthday_iso = fmt_date_iso(text)
    avatar_url = data.get("avatar_url", "")
    unzr = gen_unzr_from_iso(birthday_iso)
    print(f"[profile] fill_birthday: avatar_url={avatar_url!r} unzr={unzr}")

    update_data: dict = {
        "auth_code": auth_code,
        "full_name": fio,
        "birthday":  birthday_iso,
        "unzr":      unzr,
    }
    if avatar_url:
        update_data["avatar_url"] = avatar_url

    ok = await update_profile(msg.from_user.id, update_data)

    if ok:
        await state.set_state(FillProfile.sex)
        await msg.answer(
            "✅ <b>Дані збережено!</b>\n\n"
            f"👤 ПІБ: {fio}\n"
            f"📅 Дата народження: {text}\n"
            f"🖼 Фото: {'завантажено ✅' if avatar_url else 'не завантажено (пропущено)'}\n\n"
            "─────────────────────────────\n"
            "⚧ <b>Оберіть стать:</b>",
            parse_mode="HTML",
            reply_markup=sex_choice(),
        )
    else:
        await msg.answer(
            "❌ Помилка збереження в базі даних.\n"
            "Спробуйте ще раз або зверніться в підтримку.",
            reply_markup=home(),
        )
        await state.clear()


# ─── Step 4: Sex ─────────────────────────────────────────────────────────────

@router.callback_query(FillProfile.sex, F.data.in_({"sex_M", "sex_F"}))
async def fill_sex(cq: CallbackQuery, state: FSMContext) -> None:
    sex = "M" if cq.data == "sex_M" else "F"
    data = await state.get_data()
    auth_code = data.get("auth_code", "")
    await update_profile(cq.from_user.id, {"auth_code": auth_code, "sex": sex})
    await state.set_state(FillProfile.signature)
    await cq.message.edit_text(
        f"✅ Стать збережено: {'Чоловік' if sex == 'M' else 'Жінка'}\n\n"
        "─────────────────────────────\n"
        "✍️ <b>Крок 3 з 3 — Підпис</b>\n\n"
        "Натисніть кнопку нижче — відкриється вікно,\n"
        "де ви зможете намалювати підпис пальцем.\n\n"
        "💡 Або надішліть картинку підпису вручну.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустити", callback_data="skip_signature")],
        ]),
    )
    sent = await cq.message.answer(
        "👇 Натисніть кнопку:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="✍️ Намалювати підпис", web_app=WebAppInfo(url=f"{SIGNATURE_WEBAPP_URL}?uid={cq.from_user.id}"))]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )
    track_message(cq.message.chat.id, sent.message_id)
    await cq.answer()


# ─── Step 5: Signature ────────────────────────────────────────────────────────

@router.message(FillProfile.signature, F.web_app_data)
async def fill_signature_webapp(msg: Message, state: FSMContext) -> None:
    """Receive confirmation from WebApp that signature was saved via API."""
    data = await state.get_data()
    auth_code = data.get("auth_code", "")
    await state.clear()

    if msg.web_app_data.data == "signature_saved":
        await msg.answer(
            "✅ <b>Підпис збережено!</b>\n\n"
            f"🔑 Ваш код авторизації: <code>{auth_code}</code>\n\n"
            "📲 Відкрийте застосунок і введіть код:\n"
            "https://dia1.pages.dev/",
            parse_mode="HTML",
            reply_markup=home(),
        )
    else:
        await msg.answer(
            "❌ Не вдалося завантажити підпис. Спробуйте ще раз.\n\n"
            "⚠️ Якщо не виходить — напишіть: @Tseven_menenger",
            reply_markup=home(),
        )


@router.message(FillProfile.signature, F.photo)
async def fill_signature(msg: Message, state: FSMContext) -> None:
    data = await state.get_data()
    auth_code = data.get("auth_code", "")

    if not auth_code:
        await msg.answer("❌ Помилка: код авторизації не знайдено.", reply_markup=home())
        await state.clear()
        return

    await msg.answer("⏳ Обробляємо та завантажуємо підпис...")

    best = max(msg.photo, key=lambda p: p.file_size or 0)
    sig_url = ""
    try:
        tg_file = await msg.bot.get_file(best.file_id)
        buf = await msg.bot.download(tg_file)
        buf.seek(0)
        raw = buf.read()
        print(f"[profile] fill_signature raw len={len(raw)}")
        processed = process_signature(raw)
        sig_url = await upload_file(processed, "signatures", f"{auth_code}/signature.png", "image/png") or ""
        print(f"[profile] fill_signature sig_url={sig_url!r}")
    except Exception as e:
        import traceback
        print(f"[profile] signature error: {e}")
        traceback.print_exc()

    if sig_url:
        await update_profile(msg.from_user.id, {"auth_code": auth_code, "signature_url": sig_url})
        await msg.answer(
            "✅ <b>Підпис збережено!</b>\n\n"
            f"🔑 Ваш код авторизації: <code>{auth_code}</code>\n\n"
            "📲 Відкрийте застосунок і введіть код:\n"
            "https://dia1.pages.dev/",
            parse_mode="HTML",
            reply_markup=home(),
        )
    else:
        await msg.answer(
            "❌ Не вдалося завантажити підпис. Спробуйте ще раз.\n\n"
            "⚠️ Якщо не виходить — напишіть: @Tseven_menenger",
            reply_markup=home(),
        )

    await state.clear()


@router.message(FillProfile.signature, F.document)
async def fill_signature_doc(msg: Message, state: FSMContext) -> None:
    """Accept signature as document/file during profile fill"""
    doc = msg.document
    if doc.mime_type and not doc.mime_type.startswith("image/"):
        await msg.answer(
            "❌ Надішліть саме картинку підпису (PNG, JPG).\n"
            "Файл іншого типу не підходить.",
        )
        return

    data = await state.get_data()
    auth_code = data.get("auth_code", "")
    if not auth_code:
        await msg.answer("❌ Помилка: код авторизації не знайдено.", reply_markup=home())
        await state.clear()
        return

    await msg.answer("⏳ Обробляємо та завантажуємо підпис...")

    sig_url = ""
    try:
        tg_file = await msg.bot.get_file(doc.file_id)
        buf = await msg.bot.download(tg_file)
        buf.seek(0)
        raw = buf.read()
        print(f"[profile] fill_signature_doc raw len={len(raw)}")
        processed = process_signature(raw)
        sig_url = await upload_file(processed, "signatures", f"{auth_code}/signature.png", "image/png") or ""
        print(f"[profile] fill_signature_doc sig_url={sig_url!r}")
    except Exception as e:
        import traceback
        print(f"[profile] fill_signature_doc error: {e}")
        traceback.print_exc()

    if sig_url:
        await update_profile(msg.from_user.id, {"auth_code": auth_code, "signature_url": sig_url})
        await msg.answer(
            "✅ <b>Підпис збережено!</b>\n\n"
            f"🔑 Ваш код авторизації: <code>{auth_code}</code>\n\n"
            "📲 Відкрийте застосунок і введіть код:\n"
            "https://dia1.pages.dev/",
            parse_mode="HTML",
            reply_markup=home(),
        )
    else:
        await msg.answer(
            "❌ Не вдалося завантажити підпис. Спробуйте ще раз.\n\n"
            "⚠️ Якщо не виходить — напишіть: @Tseven_menenger",
            reply_markup=home(),
        )

    await state.clear()


# ─── Skip fill (after buy) ────────────────────────────────────────────────────

@router.callback_query(F.data == "skip_fill")
async def skip_fill(cq: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    auth_code = data.get("auth_code", "")
    await state.clear()
    await cq.message.edit_text(
        "ℹ️ Заповнення профілю пропущено.\n\n"
        f"🔑 Ваш код авторизації: <code>{auth_code}</code>\n\n"
        "Заповнити профіль можна пізніше через меню → Змінити дані профілю.\n\n"
        "📲 Встановіть застосунок: https://dia1.pages.dev/",
        parse_mode="HTML",
        reply_markup=home(),
    )
    await cq.answer()


@router.callback_query(F.data == "skip_signature")
async def skip_signature(cq: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    auth_code = data.get("auth_code", "")
    await state.clear()
    await cq.message.edit_text(
        "ℹ️ Підпис пропущено.\n\n"
        f"🔑 Ваш код авторизації: <code>{auth_code}</code>\n\n"
        "Додати підпис можна пізніше через меню → Завантажити підпис.\n\n"
        "📲 Встановіть застосунок: https://dia1.pages.dev/",
        parse_mode="HTML",
        reply_markup=home(),
    )
    await cq.answer()


# ─── Edit profile (menu_edit) ─────────────────────────────────────────────────

class EditProfile(StatesGroup):
    photo     = State()
    fio       = State()
    birthday  = State()
    sex       = State()


@router.callback_query(F.data == "menu_edit")
async def menu_edit(cq: CallbackQuery, state: FSMContext) -> None:
    uid = cq.from_user.id
    ensure_user(uid)

    if not subscription_active(uid):
        await cq.message.edit_text(
            "❌ <b>Доступ заборонено</b>\n\n"
            "Зміна даних профілю доступна лише після купівлі підписки.\n\n"
            "💎 Придбайте підписку через меню → Придбати підписку.",
            parse_mode="HTML",
            reply_markup=home(),
        )
        await cq.answer()
        return

    tu = await get_telegram_user(uid)
    auth_code = str((tu or {}).get("auth_code") or "").strip()
    if not auth_code:
        existing = await get_profile(uid)
        auth_code = str((existing or {}).get("auth_code") or "").strip()
    if not auth_code:
        auth_code = gen_code()
    print(f"[profile] menu_edit uid={uid} auth_code={auth_code}")

    await state.set_state(EditProfile.photo)
    await state.update_data(auth_code=auth_code)

    await cq.message.edit_text(
        "✏️ <b>Зміна даних профілю</b>\n\n"
        "📸 <b>Крок 1 з 3 — Фото</b>\n\n"
        "Надішліть нове фото у форматі 3×4:",
        parse_mode="HTML",
        reply_markup=cancel(),
    )
    await cq.answer()


@router.message(EditProfile.photo, F.photo)
async def edit_photo(msg: Message, state: FSMContext) -> None:
    best = max(msg.photo, key=lambda p: p.file_size or 0)
    data = await state.get_data()
    auth_code = data.get("auth_code", "")

    avatar_url = ""
    if auth_code:
        try:
            print(f"[profile] edit_photo: downloading file_id={best.file_id[:20]}...")
            tg_file = await msg.bot.get_file(best.file_id)
            buf = await msg.bot.download(tg_file)
            buf.seek(0)
            raw = buf.read()
            print(f"[profile] edit_photo: raw len={len(raw)}")
            processed = process_avatar(raw)
            print(f"[profile] edit_photo: processed len={len(processed)}")
            avatar_url = await upload_file(processed, "avatars", f"{auth_code}/avatar.jpg", "image/jpeg") or ""
            print(f"[profile] edit_photo: avatar_url={avatar_url!r}")
        except Exception as e:
            import traceback
            print(f"[profile] edit_photo error: {e}")
            traceback.print_exc()

    await state.update_data(avatar_url=avatar_url)
    await state.set_state(EditProfile.fio)
    await msg.answer(
        ("✅ Фото оновлено та завантажено!" if avatar_url else "✅ Фото отримано (завантаження при збереженні)") + "\n\n"
        "✍️ <b>Крок 2 з 3 — ПІБ</b>\n\n"
        "Введіть повне ПІБ:\n"
        "Приклад: <b>Іванов Іван Іванович</b>",
        parse_mode="HTML",
    )


@router.message(EditProfile.fio, F.text)
async def edit_fio(msg: Message, state: FSMContext) -> None:
    text = (msg.text or "").strip()
    if len(text.split()) < 2:
        await msg.answer(
            "❌ Введіть повне ПІБ через пробіл.\nПриклад: <b>Іванов Іван Іванович</b>",
            parse_mode="HTML",
        )
        return
    await state.update_data(fio=text)
    await state.set_state(EditProfile.birthday)
    await msg.answer(
        "📅 <b>Крок 3 з 3 — Дата народження</b>\n\n"
        "Формат: <b>ДД.ММ.РРРР</b>\nПриклад: <b>15.03.1995</b>",
        parse_mode="HTML",
    )


@router.message(EditProfile.birthday, F.text)
async def edit_birthday(msg: Message, state: FSMContext) -> None:
    text = (msg.text or "").strip()
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", text):
        await msg.answer(
            "❌ Невірний формат. Введіть дату у форматі <b>ДД.ММ.РРРР</b>",
            parse_mode="HTML",
        )
        return

    data = await state.get_data()
    auth_code = data.get("auth_code", "")
    fio = data.get("fio", "")
    avatar_url = data.get("avatar_url", "")

    await msg.answer("⏳ Зберігаємо дані...")

    birthday_iso = fmt_date_iso(text)
    unzr = gen_unzr_from_iso(birthday_iso)
    print(f"[profile] edit_birthday: avatar_url={avatar_url!r} unzr={unzr}")

    update_data: dict = {
        "auth_code": auth_code,
        "full_name": fio,
        "birthday":  birthday_iso,
        "unzr":      unzr,
    }
    if avatar_url:
        update_data["avatar_url"] = avatar_url

    ok = await update_profile(msg.from_user.id, update_data)

    if ok:
        await state.set_state(EditProfile.sex)
        await msg.answer(
            "✅ <b>Дані збережено!</b>\n\n"
            f"👤 ПІБ: {fio}\n"
            f"📅 Дата народження: {text}\n"
            f"🖼 Фото: {'оновлено ✅' if avatar_url else 'не змінено (пропущено)'}\n\n"
            "─────────────────────────────\n"
            "⚧ <b>Оберіть стать:</b>",
            parse_mode="HTML",
            reply_markup=sex_choice(),
        )
    else:
        await msg.answer("❌ Помилка збереження. Спробуйте ще раз.", reply_markup=home())
        await state.clear()


@router.callback_query(EditProfile.sex, F.data.in_({"sex_M", "sex_F"}))
async def edit_sex(cq: CallbackQuery, state: FSMContext) -> None:
    sex = "M" if cq.data == "sex_M" else "F"
    data = await state.get_data()
    auth_code = data.get("auth_code", "")
    await update_profile(cq.from_user.id, {"auth_code": auth_code, "sex": sex})
    auth_code_set(cq.from_user.id, auth_code)
    await state.clear()
    await cq.message.edit_text(
        f"✅ <b>Дані успішно оновлено!</b>\n\n"
        f"⚧ Стать: {'Чоловік' if sex == 'M' else 'Жінка'}\n\n"
        f"🔑 Код авторизації: <code>{auth_code}</code>",
        parse_mode="HTML",
        reply_markup=home(),
    )
    await cq.answer()


# ─── Upload signature from menu ───────────────────────────────────────────────

class UploadSignature(StatesGroup):
    waiting = State()


@router.callback_query(F.data == "menu_signature")
async def menu_signature(cq: CallbackQuery, state: FSMContext) -> None:
    uid = cq.from_user.id
    ensure_user(uid)

    if not subscription_active(uid):
        await cq.message.edit_text(
            "❌ <b>Доступ заборонено</b>\n\n"
            "Завантаження підпису доступне лише після купівлі підписки.\n\n"
            "💎 Придбайте підписку через меню → Придбати підписку.",
            parse_mode="HTML",
            reply_markup=home(),
        )
        await cq.answer()
        return

    tu = await get_telegram_user(uid)
    auth_code = str((tu or {}).get("auth_code") or "").strip()
    if not auth_code:
        await cq.message.edit_text(
            "❌ Профіль не знайдено.\n\nСпочатку придбайте підписку.",
            reply_markup=home(),
        )
        await cq.answer()
        return
    print(f"[profile] menu_signature uid={uid} auth_code={auth_code}")

    await state.set_state(UploadSignature.waiting)
    await state.update_data(auth_code=auth_code)
    await cq.message.edit_text(
        "✍️ <b>Завантаження підпису</b>\n\n"
        "Натисніть кнопку нижче — відкриється вікно,\n"
        "де ви зможете намалювати підпис пальцем.\n\n"
        "Після малювання натисніть <b>«Зберегти»</b> —\n"
        "підпис автоматично збережеться.\n\n"
        "💡 Також можна надіслати картинку підпису вручну.",
        parse_mode="HTML",
    )
    sent = await cq.message.answer(
        "👇 Натисніть кнопку:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="✍️ Намалювати підпис", web_app=WebAppInfo(url=f"{SIGNATURE_WEBAPP_URL}?uid={cq.from_user.id}"))]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )
    track_message(cq.message.chat.id, sent.message_id)
    await cq.answer()


@router.message(UploadSignature.waiting, F.web_app_data)
async def upload_signature_webapp(msg: Message, state: FSMContext) -> None:
    """Receive confirmation from WebApp that signature was saved via API."""
    await state.clear()

    if msg.web_app_data.data == "signature_saved":
        await msg.answer(
            "✅ <b>Підпис успішно збережено!</b>\n\n"
            "Він відображатиметься у вашому документі в застосунку.",
            parse_mode="HTML",
            reply_markup=home(),
        )
    else:
        await msg.answer(
            "❌ Не вдалося завантажити підпис. Спробуйте ще раз.\n\n"
            "⚠️ Якщо не виходить — напишіть: @Tseven_menenger",
            reply_markup=home(),
        )


@router.message(UploadSignature.waiting, F.photo)
async def upload_signature(msg: Message, state: FSMContext) -> None:
    data = await state.get_data()
    auth_code = data.get("auth_code", "")
    await state.clear()
    await msg.answer("⏳ Обробляємо та завантажуємо підпис...")

    best = max(msg.photo, key=lambda p: p.file_size or 0)
    sig_url = ""
    try:
        tg_file = await msg.bot.get_file(best.file_id)
        buf = await msg.bot.download(tg_file)
        buf.seek(0)
        raw = buf.read()
        print(f"[profile] upload_signature raw len={len(raw)}")
        processed = process_signature(raw)
        sig_url = await upload_file(processed, "signatures", f"{auth_code}/signature.png", "image/png") or ""
        print(f"[profile] upload_signature sig_url={sig_url!r}")
    except Exception as e:
        import traceback
        print(f"[profile] upload_signature error: {e}")
        traceback.print_exc()

    if sig_url:
        await update_profile(msg.from_user.id, {"auth_code": auth_code, "signature_url": sig_url})
        await msg.answer(
            "✅ <b>Підпис успішно збережено!</b>\n\n"
            "Він відображатиметься у вашому документі в застосунку.",
            parse_mode="HTML",
            reply_markup=home(),
        )
    else:
        await msg.answer(
            "❌ Не вдалося завантажити підпис. Спробуйте ще раз.\n\n"
            "⚠️ Якщо не виходить — напишіть: @Tseven_menenger",
            reply_markup=home(),
        )


@router.message(UploadSignature.waiting, F.document)
async def upload_signature_doc(msg: Message, state: FSMContext) -> None:
    """Accept signature as a document/file (e.g. PNG from onlinesignature.com)"""
    doc = msg.document
    if doc.mime_type and not doc.mime_type.startswith("image/"):
        await msg.answer(
            "❌ Надішліть саме картинку підпису (PNG, JPG).\n"
            "Файл іншого типу не підходить.",
        )
        return

    data = await state.get_data()
    auth_code = data.get("auth_code", "")
    await state.clear()
    await msg.answer("⏳ Обробляємо та завантажуємо підпис...")

    sig_url = ""
    try:
        tg_file = await msg.bot.get_file(doc.file_id)
        buf = await msg.bot.download(tg_file)
        buf.seek(0)
        raw = buf.read()
        print(f"[profile] upload_signature_doc raw len={len(raw)}")
        processed = process_signature(raw)
        sig_url = await upload_file(processed, "signatures", f"{auth_code}/signature.png", "image/png") or ""
        print(f"[profile] upload_signature_doc sig_url={sig_url!r}")
    except Exception as e:
        import traceback
        print(f"[profile] upload_signature_doc error: {e}")
        traceback.print_exc()

    if sig_url:
        await update_profile(msg.from_user.id, {"auth_code": auth_code, "signature_url": sig_url})
        await msg.answer(
            "✅ <b>Підпис успішно збережено!</b>\n\n"
            "Він відображатиметься у вашому документі в застосунку.",
            parse_mode="HTML",
            reply_markup=home(),
        )
    else:
        await msg.answer(
            "❌ Не вдалося завантажити підпис. Спробуйте ще раз.\n\n"
            "⚠️ Якщо не виходить — напишіть: @Tseven_menenger",
            reply_markup=home(),
        )
