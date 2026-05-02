import time
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from db import get_db
from escape import escape_html
from user_manager import update_user_field
from config import CREATOR_ID

router = Router()

async def get_group_settings(chat_id: int):
    db = get_db()
    doc = await db.collection('chats').document(str(chat_id)).collection('settings').document('config').get()
    if doc.exists:
        return doc.to_dict()
    return {}

async def update_group_settings(chat_id: int, field: str, value):
    db = get_db()
    await db.collection('chats').document(str(chat_id)).collection('settings').document('config').set({field: value}, merge=True)

# 1. ПРИВЕТСТВИЕ И ПРАВИЛА
@router.message(F.text.lower().startswith("приветствие ") | F.text.lower().startswith("!приветствие "))
async def set_welcome(message: types.Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id

    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status not in ['administrator', 'creator'] and int(user_id) != int(CREATOR_ID):
            return
    except: return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return
    text = parts[1]

    await update_group_settings(chat_id, 'welcome_text', text)
    await message.answer("✅ Приветствие установлено!")

@router.message(F.new_chat_members)
async def welcome_new_member(message: types.Message):
    settings = await get_group_settings(message.chat.id)
    welcome_text = settings.get('welcome_text')

    if welcome_text:
        for user in message.new_chat_members:
            if user.is_bot: continue
            text = welcome_text.replace("{name}", escape_html(user.full_name)).replace("{username}", f"@{user.username}" if user.username else escape_html(user.full_name))
            await message.answer(f"Привет, {escape_html(user.full_name)}!\n\n{text}")

@router.message(F.text.lower().startswith("+правила "))
async def set_rules(message: types.Message, bot: Bot):
    if int(message.from_user.id) != int(CREATOR_ID):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return
    text = parts[1]

    db = get_db()
    await db.collection('bot_settings').document('global_rules').set({'text': text})
    await message.answer("✅ Глобальные правила успешно обновлены!")

@router.message(F.text.lower().in_(["правила", "!правила", "/rules"]))
async def show_rules(message: types.Message):
    db = get_db()
    doc = await db.collection('bot_settings').document('global_rules').get()
    if doc.exists:
        text = doc.to_dict().get('text', "Правила пока не установлены.")
        await message.answer(f"📜 <b>Правила:</b>\n\n{text}")
    else:
        await message.answer("Правила пока не установлены.")

# 2. ЗАМЕТКИ
@router.message(F.text.lower().startswith("заметка ") | F.text.lower().startswith("!заметка "))
async def set_note(message: types.Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status not in ['administrator', 'creator'] and int(user_id) != int(CREATOR_ID):
            return
    except: return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3: return await message.answer("Использование: заметка [имя] [текст]")

    note_name = parts[1].lower()
    note_text = parts[2]

    db = get_db()
    await db.collection('chats').document(str(chat_id)).collection('notes').document(note_name).set({'text': note_text})
    await message.answer(f"📝 Заметка <b>{escape_html(note_name)}</b> сохранена! Вызов: <code>?{escape_html(note_name)}</code>")

@router.message(F.text.startswith("?"))
async def get_note(message: types.Message):
    note_name = message.text[1:].strip().lower()
    if not note_name: return

    db = get_db()
    doc = await db.collection('chats').document(str(message.chat.id)).collection('notes').document(note_name).get()
    if doc.exists:
        text = doc.to_dict().get('text', "")
        await message.answer(text)

# 3. АВТОМОДЕРАЦИЯ (Антилинк)
@router.message(F.text.lower().in_(["антилинк вкл", "антилинк выкл"]))
async def toggle_antilink(message: types.Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status not in ['administrator', 'creator'] and int(user_id) != int(CREATOR_ID):
            return
    except: return

    is_on = "вкл" in message.text.lower()
    await update_group_settings(chat_id, 'antilink', is_on)
    await message.answer(f"🛡 Анти-ссылки {'включены' if is_on else 'выключены'}.")

@router.message(F.text & (F.text.lower().contains("http://") | F.text.lower().contains("https://") | F.text.lower().contains("t.me/")))
async def antilink_check(message: types.Message, bot: Bot):
    if not message.text: return

    settings = await get_group_settings(message.chat.id)
    if settings.get('antilink', False):
        user_id = message.from_user.id
        try:
            member = await bot.get_chat_member(message.chat.id, user_id)
            if member.status not in ['administrator', 'creator'] and int(user_id) != int(CREATOR_ID):
                await message.delete()
                await message.answer(f"⚠️ <b>{escape_html(message.from_user.full_name)}</b>, ссылки в этом чате запрещены!")
                # Выдача варна
                from admin import parse_time
                from user_manager import get_user_data
                data = await get_user_data(message.chat.id, user_id)
                warns = data.get('warns', [])
                current_time = time.time()
                warns = [w for w in warns if w > current_time]
                warns.append(current_time + 9 * 86400)
                await update_user_field(message.chat.id, user_id, 'warns', warns)
                if len(warns) >= 3:
                    await bot.ban_chat_member(message.chat.id, user_id, until_date=int(current_time) + 3*86400)
                    await update_user_field(message.chat.id, user_id, 'warns', [])
        except: pass

# 4. БИО ПРОФИЛЯ
@router.message(F.text.lower().startswith("/bio ") | F.text.lower().startswith("био "))
async def set_bio(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return

    bio_text = parts[1][:100] # Лимит 100 символов
    await update_user_field(message.chat.id, message.from_user.id, 'bio', bio_text)
    await message.answer("✅ Биография обновлена!")



# 5. АНТИВОЙС
@router.message(F.text.lower().in_(["антивойс вкл", "антивойс выкл"]))
async def toggle_antivoice(message: types.Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status not in ['administrator', 'creator'] and int(user_id) != int(CREATOR_ID):
            return
    except: return

    is_on = "вкл" in message.text.lower()
    from group_management import update_group_settings
    await update_group_settings(chat_id, 'antivoice', is_on)
    await message.answer(f"🎙 Анти-голосовые {'включены' if is_on else 'выключены'}.")

@router.message(F.voice | F.video_note)
async def antivoice_check(message: types.Message, bot: Bot):
    from group_management import get_group_settings
    settings = await get_group_settings(message.chat.id)
    if settings.get('antivoice', False):
        user_id = message.from_user.id
        try:
            member = await bot.get_chat_member(message.chat.id, user_id)
            if member.status not in ['administrator', 'creator'] and int(user_id) != int(CREATOR_ID):
                await message.delete()
                msg = await message.answer(f"⚠️ <b>{escape_html(message.from_user.full_name)}</b>, голосовые и видеосообщения в этом чате запрещены!")
                import asyncio
                await asyncio.sleep(10)
                try: await msg.delete()
                except: pass
        except: pass
