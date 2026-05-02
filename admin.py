import re
import time
from config import CREATOR_ID
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from datetime import timedelta
from escape import escape_html
from user_manager import get_user_data, update_user_field

router = Router()

def parse_time(time_str: str) -> int:
    """Парсит строку времени (напр. '30м', '2ч', '1д') в секунды."""
    if not time_str:
        return 0
    match = re.match(r"(\d+)([смчдSMHD])?", time_str.lower())
    if not match:
        return 0
    amount = int(match.group(1))
    unit = match.group(2)
    if unit in ('м', 'm'):
        return amount * 60
    elif unit in ('ч', 'h'):
        return amount * 3600
    elif unit in ('д', 'd'):
        return amount * 86400
    elif unit in ('с', 's'):
        return amount
    return amount * 60 # По умолчанию минуты


async def get_user_rank(chat_id: int, user_id: int) -> int:
    if int(user_id) == int(CREATOR_ID):
        return 999 # Создатель бота
    data = await get_user_data(chat_id, user_id)
    return data.get('admin_rank', 0)

async def check_admin_immunity(bot: Bot, chat_id: int, user_id: int, target_id: int) -> bool:
    if int(user_id) == int(CREATOR_ID):
        return False

    user_rank = await get_user_rank(chat_id, user_id)
    target_rank = await get_user_rank(chat_id, target_id)

    # ИСПРАВЛЕНИЕ: Даем иммунитет только если ранг цели больше нуля
    if target_rank > 0 and target_rank >= user_rank:
        return True 

    try:
        user_member = await bot.get_chat_member(chat_id, user_id)
        target_member = await bot.get_chat_member(chat_id, target_id)

        target_status = target_member.status
        user_status = user_member.status

        if target_status == 'creator':
            return True
        if target_status == 'administrator' and user_status != 'creator' and user_rank <= target_rank:
            return True
    except:
        pass
    return False

@router.message(F.text.lower().startswith("!повысить") | F.text.lower().startswith("повысить"))
async def cmd_promote(message: types.Message, bot: Bot):
    if not message.reply_to_message:
        return await message.answer("Ответьте на сообщение пользователя для повышения.")

    chat_id = message.chat.id
    user_id = message.from_user.id
    target = message.reply_to_message.from_user

    user_rank = await get_user_rank(chat_id, user_id)

    try:
        member = await bot.get_chat_member(chat_id, user_id)
        is_tg_admin = member.status in ['administrator', 'creator']
    except:
        is_tg_admin = False

    if not is_tg_admin and user_rank < 3 and int(user_id) != int(CREATOR_ID):
        return await message.answer("У вас нет прав для повышения (нужен ранг 3+ или права Создателя).")

    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Укажите ранг (1-5): <code>!повысить 2</code>")

    try:
        new_rank = int(args[1])
        if new_rank < 1 or new_rank > 5:
            return await message.answer("Ранг должен быть от 1 до 5.")
    except:
        return await message.answer("Ранг должен быть числом.")

    if new_rank >= user_rank and int(user_id) != int(CREATOR_ID):
        return await message.answer(f"Вы не можете выдать ранг {new_rank}, так как ваш ранг {user_rank}.")

    target_rank = await get_user_rank(chat_id, target.id)
    if target_rank >= user_rank and int(user_id) != int(CREATOR_ID):
         return await message.answer("Вы не можете повысить пользователя с равным или большим рангом.")

    await update_user_field(chat_id, target.id, 'admin_rank', new_rank)
    await message.answer(f"✅ Пользователь <b>{escape_html(target.full_name)}</b> повышен до {new_rank} ранга администратора!")

@router.message(F.text.lower().startswith("!понизить") | F.text.lower().startswith("понизить"))
async def cmd_demote(message: types.Message, bot: Bot):
    if not message.reply_to_message:
        return await message.answer("Ответьте на сообщение пользователя для понижения.")

    chat_id = message.chat.id
    user_id = message.from_user.id
    target = message.reply_to_message.from_user

    user_rank = await get_user_rank(chat_id, user_id)

    try:
        member = await bot.get_chat_member(chat_id, user_id)
        is_tg_admin = member.status in ['administrator', 'creator']
    except:
        is_tg_admin = False

    if not is_tg_admin and user_rank < 3 and int(user_id) != int(CREATOR_ID):
        return await message.answer("У вас нет прав для понижения (нужен ранг 3+ или права Создателя).")

    target_rank = await get_user_rank(chat_id, target.id)
    if target_rank >= user_rank and int(user_id) != int(CREATOR_ID):
         return await message.answer("Вы не можете понизить пользователя с равным или большим рангом.")

    if target_rank <= 1:
        await update_user_field(chat_id, target.id, 'admin_rank', 0)
        return await message.answer(f"🔻 Пользователь <b>{escape_html(target.full_name)}</b> лишен ранга администратора.")

    await update_user_field(chat_id, target.id, 'admin_rank', target_rank - 1)
    await message.answer(f"🔻 Пользователь <b>{escape_html(target.full_name)}</b> понижен до {target_rank - 1} ранга.")

@router.message(F.text.lower().startswith("!снять") | F.text.lower().startswith("снять"))
async def cmd_remove_admin(message: types.Message, bot: Bot):
    if not message.reply_to_message:
        return await message.answer("Ответьте на сообщение пользователя для снятия.")

    chat_id = message.chat.id
    user_id = message.from_user.id
    target = message.reply_to_message.from_user

    user_rank = await get_user_rank(chat_id, user_id)

    try:
        member = await bot.get_chat_member(chat_id, user_id)
        is_tg_admin = member.status in ['administrator', 'creator']
    except:
        is_tg_admin = False

    if not is_tg_admin and user_rank < 3 and int(user_id) != int(CREATOR_ID):
        return await message.answer("У вас нет прав для снятия админки (нужен ранг 3+ или права Создателя).")

    target_rank = await get_user_rank(chat_id, target.id)
    if target_rank >= user_rank and int(user_id) != int(CREATOR_ID):
         return await message.answer("Вы не можете снять пользователя с равным или большим рангом.")

    await update_user_field(chat_id, target.id, 'admin_rank', 0)
    await message.answer(f"❌ Пользователь <b>{escape_html(target.full_name)}</b> полностью лишен всех прав администратора.")


@router.message(F.text.lower().startswith("!админы") | F.text.lower().startswith("админы") | F.text.lower().startswith("кто админ"))
async def cmd_admins_list(message: types.Message):
    chat_id = message.chat.id
    from db import get_db
    db = get_db()
    users_ref = db.collection('chats').document(str(chat_id)).collection('users')

    # Ищем пользователей с admin_rank > 0
    docs = await users_ref.where('admin_rank', '>', 0).order_by('admin_rank', direction='DESCENDING').get()

    if not docs:
        return await message.answer("В этом чате пока нет назначенных администраторов бота.")

    text = "👮‍♂️ <b>Администраторы бота:</b>\n\n"
    for doc in docs:
        data = doc.to_dict()
        rank = data.get('admin_rank', 0)
        name = escape_html(data.get('full_name', 'Unknown'))

        rank_name = "Мл. Модератор"
        if rank == 2: rank_name = "Модератор"
        elif rank == 3: rank_name = "Ст. Модератор"
        elif rank == 4: rank_name = "Администратор"
        elif rank == 5: rank_name = "Ст. Администратор"

        text += f"🔹 <b>{name}</b> — {rank_name} (Ранг: {rank})\n"

    await message.answer(text)



def extract_args(text: str):
    """Извлекает время и причину из текста (с учетом SHIFT+ENTER)."""
    parts = text.split('\n', 1)
    first_line = parts[0].split()
    time_str = first_line[1] if len(first_line) > 1 else ""
    reason = parts[1].strip() if len(parts) > 1 else ""
    if len(first_line) > 2 and not reason:
        reason = " ".join(first_line[2:])
    return time_str, reason

@router.message(F.text.lower().startswith("!мут") | F.text.lower().startswith("мут"))
async def cmd_mute(message: types.Message, bot: Bot):
    if not message.reply_to_message:
        return await message.answer("Ответьте на сообщение пользователя для мута.")

    chat_id = message.chat.id
    user_id = message.from_user.id
    target = message.reply_to_message.from_user

    try:
        member = await bot.get_chat_member(chat_id, user_id)
        is_tg_admin = member.status in ['administrator', 'creator']
    except:
        is_tg_admin = False

    user_rank = await get_user_rank(chat_id, user_id)
    if not is_tg_admin and user_rank < 1 and int(user_id) != int(CREATOR_ID):
        return

    if target.is_bot:
        return await message.answer("Нельзя замутить бота.")

    if await check_admin_immunity(bot, chat_id, user_id, target.id):
        return await message.answer("У этого пользователя иммунитет!")

    time_str, reason = extract_args(message.text)
    duration_secs = parse_time(time_str) if time_str else 30 * 60 # По умолчанию 30 минут

    try:
        until_date = int(time.time()) + duration_secs
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target.id,
            permissions=types.ChatPermissions(can_send_messages=False),
            until_date=until_date
        )

        mins = duration_secs // 60
        text = f"🔇 Пользователь <b>{escape_html(target.full_name)}</b> замучен на {mins} минут.\n"
        if reason:
            text += f"Причина: <i>{escape_html(reason)}</i>"
        await message.answer(text)
    except Exception as e:
        await message.answer(f"Не удалось замутить: {e}")

@router.message(F.text.lower().startswith("!бан") | F.text.lower().startswith("бан"))
async def cmd_ban(message: types.Message, bot: Bot):
    if not message.reply_to_message:
        return await message.answer("Ответьте на сообщение пользователя для бана.")

    chat_id = message.chat.id
    user_id = message.from_user.id
    target = message.reply_to_message.from_user

    try:
        member = await bot.get_chat_member(chat_id, user_id)
        is_tg_admin = member.status in ['administrator', 'creator']
    except:
        is_tg_admin = False

    user_rank = await get_user_rank(chat_id, user_id)
    if not is_tg_admin and user_rank < 1 and int(user_id) != int(CREATOR_ID):
        return

    if target.is_bot:
        return await message.answer("Нельзя забанить бота.")

    if await check_admin_immunity(bot, chat_id, user_id, target.id):
        return await message.answer("У этого пользователя иммунитет!")

    _, reason = extract_args(message.text)

    try:
        await bot.ban_chat_member(chat_id=chat_id, user_id=target.id)
        text = f"🔨 Пользователь <b>{escape_html(target.full_name)}</b> забанен навсегда.\n"
        if reason:
            text += f"Причина: <i>{escape_html(reason)}</i>"
        await message.answer(text)
    except Exception as e:
        await message.answer(f"Не удалось забанить: {e}")

@router.message(F.text.lower().startswith("!варн") | F.text.lower().startswith("варн"))
async def cmd_warn(message: types.Message, bot: Bot):
    if not message.reply_to_message:
        return await message.answer("Ответьте на сообщение пользователя для предупреждения.")

    chat_id = message.chat.id
    user_id = message.from_user.id
    target = message.reply_to_message.from_user
    target_name = escape_html(target.full_name)

    try:
        member = await bot.get_chat_member(chat_id, user_id)
        is_tg_admin = member.status in ['administrator', 'creator']
    except:
        is_tg_admin = False

    user_rank = await get_user_rank(chat_id, user_id)
    if not is_tg_admin and user_rank < 1 and int(user_id) != int(CREATOR_ID):
        return

    if target.is_bot:
        return await message.answer("Бот не получает варны.")

    if await check_admin_immunity(bot, chat_id, user_id, target.id):
        return await message.answer("У этого пользователя иммунитет!")

    time_str, reason = extract_args(message.text)
    duration_secs = parse_time(time_str) if time_str else 9 * 86400 # 9 дней по умолчанию

    data = await get_user_data(chat_id, target.id, target_name)
    warns = data.get('warns', [])

    # Очистка старых варнов
    current_time = time.time()
    warns = [w for w in warns if w > current_time]

    warns.append(current_time + duration_secs)
    await update_user_field(chat_id, target.id, 'warns', warns)

    warn_count = len(warns)
    text = f"⚠️ Пользователь <b>{target_name}</b> получил предупреждение [{warn_count}/3].\n"
    if reason:
        text += f"Причина: <i>{escape_html(reason)}</i>\n"
    text += f"Срок: {duration_secs // 86400} дней."

    await message.answer(text)

    if warn_count >= 3:
        try:
            ban_duration = 3 * 86400 # 3 дня бана
            await bot.ban_chat_member(
                chat_id=chat_id,
                user_id=target.id,
                until_date=int(current_time) + ban_duration
            )
            await message.answer(f"⛔️ Пользователь <b>{target_name}</b> получил 3 предупреждения и был забанен на 3 дня.")
            await update_user_field(chat_id, target.id, 'warns', []) # Очищаем варны после бана
        except Exception as e:
            await message.answer(f"Не удалось забанить после 3 варнов: {e}")

@router.message(F.text.startswith("!снять варн"))
async def cmd_unwarn_admin(message: types.Message):
    if not message.reply_to_message:
        return await message.answer("Ответьте на сообщение пользователя.")

    chat_id = message.chat.id
    user_id = message.from_user.id
    target = message.reply_to_message.from_user

    from main import dp
    try:
        member = await message.bot.get_chat_member(chat_id, user_id)
        if member.status not in ['administrator', 'creator'] and int(user_id) != int(CREATOR_ID):
            return
    except:
        return

    data = await get_user_data(chat_id, target.id)
    warns = data.get('warns', [])

    if not warns:
        return await message.answer("У пользователя нет предупреждений.")

    warns.pop() # Удаляем последний
    await update_user_field(chat_id, target.id, 'warns', warns)
    await message.answer(f"✅ Одно предупреждение снято с пользователя <b>{escape_html(target.full_name)}</b>. Осталось: {len(warns)}/3.")