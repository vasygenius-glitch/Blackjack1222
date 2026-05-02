import time
import asyncio
from aiogram import Router, types, Bot
from aiogram.filters import Command
from db import get_db
from escape import escape_html
from config import CREATOR_ID

router = Router()

async def get_user_stats_ref(chat_id: int, user_id: int):
    db = get_db()
    return db.collection('chats').document(str(chat_id)).collection('stats').document(str(user_id))

# В памяти будем хранить {chat_id: {user_id: {"count": X, "full_name": "Name"}}}
_stats_batch = {}
_batch_lock = asyncio.Lock()

async def increment_message_count(chat_id: int, user_id: int, full_name: str):
    async with _batch_lock:
        if chat_id not in _stats_batch:
            _stats_batch[chat_id] = {}
        if user_id not in _stats_batch[chat_id]:
            _stats_batch[chat_id][user_id] = {"count": 0, "full_name": full_name}

        _stats_batch[chat_id][user_id]["count"] += 1
        _stats_batch[chat_id][user_id]["full_name"] = full_name

async def flush_stats_task():
    """Background task to periodically flush message stats to the DB."""
    while True:
        await asyncio.sleep(30)
        async with _batch_lock:
            # Copy and clear the batch
            if not _stats_batch:
                continue
            batch_to_process = _stats_batch.copy()
            _stats_batch.clear()

        current_time = int(time.time())
        db = get_db()

        for chat_id, users in batch_to_process.items():
            for user_id, data in users.items():
                try:
                    ref = db.collection('chats').document(str(chat_id)).collection('stats').document(str(user_id))
                    doc = await ref.get()

                    if doc.exists:
                        db_data = doc.to_dict()
                        await ref.update({
                            'all_time': db_data.get('all_time', 0) + data["count"],
                            'week': db_data.get('week', 0) + data["count"],
                            'full_name': data["full_name"]
                        })
                    else:
                        await ref.set({
                            'all_time': data["count"],
                            'week': data["count"],
                            'join_date': current_time,
                            'full_name': data["full_name"]
                        })
                except Exception as e:
                    print(f"Error flushing stats for user {user_id} in chat {chat_id}: {e}")

@router.message(Command("top"))
async def cmd_top(message: types.Message):
    args = message.text.split()
    chat_id = message.chat.id

    if len(args) < 2:
        from user_manager import get_top_users
        top_users = await get_top_users(chat_id, limit=10)

        if not top_users:
            return await message.answer("🏆 Топ игроков пуст.")

        text = "🏆 <b>Топ-10 богачей чата:</b>\n\n"
        for i, user in enumerate(top_users, start=1):
            vip_icon = " 👑" if user.get('is_vip') else ""
            text += f"{i}. {escape_html(user.get('full_name', 'Unknown'))}{vip_icon} — <b>{user.get('balance', 0)}</b> сыроежек\n"

        text += "\n<i>Используйте /top week, /top all, /top old, /top young для топов активности.</i>"
        return await message.answer(text)

    mode = args[1].lower()
    chat_id = message.chat.id
    db = get_db()
    stats_ref = db.collection('chats').document(str(chat_id)).collection('stats')

    if mode == "all":
        docs = await stats_ref.order_by('all_time', direction='DESCENDING').limit(10).get()
        title = "🏆 Топ по сообщениям (за всё время)"
        key = 'all_time'
    elif mode == "week":
        docs = await stats_ref.order_by('week', direction='DESCENDING').limit(10).get()
        title = "🔥 Топ по сообщениям (за неделю)"
        key = 'week'
    elif mode == "old":
        docs = await stats_ref.order_by('join_date', direction='ASCENDING').limit(10).get()
        title = "👴 Самые старые участники чата"
        key = 'join_date'
    elif mode == "young":
        docs = await stats_ref.order_by('join_date', direction='DESCENDING').limit(10).get()
        title = "👶 Самые новые участники чата"
        key = 'join_date'
    else:
        return await message.answer("Неизвестный режим топа.")

    if not docs:
        return await message.answer("Статистика пока пуста.")

    text = f"<b>{title}:</b>\n\n"
    for i, doc in enumerate(docs, 1):
        data = doc.to_dict()
        name = escape_html(data.get('full_name', 'Unknown'))
        if mode in ["old", "young"]:
            date_str = time.strftime('%d.%m.%Y', time.localtime(data.get('join_date', 0)))
            text += f"{i}. <b>{name}</b> — с {date_str}\n"
        else:
            text += f"{i}. <b>{name}</b> — {data.get(key, 0)} сообщений\n"

    await message.answer(text)

async def weekly_reset_task(bot: Bot):
    while True:
        await asyncio.sleep(60) # Проверяем каждую минуту
        current_time = time.localtime()
        # Проверяем, является ли день воскресеньем (6) и время 23:59
        if current_time.tm_wday == 6 and current_time.tm_hour == 23 and current_time.tm_min == 59:
            from whitelist import get_whitelist
            from user_manager import update_user_balance
            db = get_db()
            whitelist = await get_whitelist()

            for chat_id in whitelist.keys():
                try:
                    stats_ref = db.collection('chats').document(str(chat_id)).collection('stats')
                    # Находим победителя недели
                    docs = await stats_ref.order_by('week', direction='DESCENDING').limit(1).get()
                    if docs:
                        winner_doc = docs[0]
                        winner_id = int(winner_doc.id)
                        winner_data = winner_doc.to_dict()
                        winner_name = winner_data.get('full_name', 'Unknown')
                        msg_count = winner_data.get('week', 0)

                        if msg_count > 0:
                            # Выдаем 1500 сыроежек
                            await update_user_balance(chat_id, winner_id, 1500)
                            try:
                                await bot.send_message(
                                    chat_id=chat_id,
                                    text=f"🎉 <b>Итоги недели!</b>\n\nСамый активный участник: <b>{escape_html(winner_name)}</b> ({msg_count} сообщений).\nОн получает премию: <b>1500</b> сыроежек! 💰"
                                )
                            except:
                                pass

                    # Обнуляем счетчики недели для всех
                    all_docs = await stats_ref.get()
                    for d in all_docs:
                        await stats_ref.document(d.id).update({'week': 0})
                except Exception as e:
                    print(f"Weekly reset error for chat {chat_id}: {e}")

            # Ждем 60 секунд, чтобы не сработало дважды
            await asyncio.sleep(60)
