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

        # --- Ежедневное пополнение капитала банков и начисление % по вкладам ---
        if current_time.tm_hour == 0 and current_time.tm_min == 0:
            db = get_db()
            from whitelist import get_whitelist
            from user_manager import update_user_field
            whitelist = await get_whitelist()
            for chat_id in whitelist.keys():
                try:
                    # 1. Загружаем все банки в чате
                    banks_ref = db.collection('chats').document(str(chat_id)).collection('banks')
                    bank_docs = await banks_ref.get()
                    banks_data = {doc.id: doc.to_dict() for doc in bank_docs}

                    # 2. Начисляем % всем вкладчикам
                    users_ref = db.collection('chats').document(str(chat_id)).collection('users')
                    user_docs = await users_ref.get()
                    for user_doc in user_docs:
                        u_data = user_doc.to_dict()
                        deposit = u_data.get('bank_deposit', 0)
                        bank_id_str = str(u_data.get('bank_name', ''))

                        if deposit > 0 and bank_id_str in banks_data:
                            base_rate = banks_data[bank_id_str].get('deposit_rate', 3.0)

                            # Лояльность (бонус за дни)
                            deposit_start_time = u_data.get('deposit_start_time', current_time.tm_sec)
                            # Приближенная калькуляция дней
                            days_held = (time.time() - deposit_start_time) // 86400 if 'deposit_start_time' in u_data else 0
                            loyalty_bonus = min(5.0, days_held * 0.5) # Максимум +5%

                            final_rate = base_rate + loyalty_bonus
                            profit = int(deposit * (final_rate / 100))

                            if profit > 0:
                                # Проверяем, есть ли у банка деньги выплатить %
                                if banks_data[bank_id_str].get('capital', 0) >= profit:
                                    banks_data[bank_id_str]['capital'] -= profit
                                    await update_user_field(chat_id, int(user_doc.id), 'bank_deposit', deposit + profit)

                                    # Оффшорная комиссия (если счет скрытый)
                                    if u_data.get('is_offshore', False):
                                        fee = int(deposit * 0.005) # 0.5% за обслуживание оффшора
                                        new_dep = deposit + profit - fee
                                        await update_user_field(chat_id, int(user_doc.id), 'bank_deposit', max(0, new_dep))

                    # 3. Обновляем капитал банков (вычитаем выплаченные %, добавляем гос. субсидию 50М, налог на сверхприбыль, банкротство)
                    for b_id, b_data in banks_data.items():
                        current_cap = b_data.get('capital', 0)

                        # Банкротство
                        if current_cap < 0:
                            # Возвращаем вкладчикам 50% из фонда ЦБ, если банк обанкротился
                            for user_doc in user_docs:
                                u_data = user_doc.to_dict()
                                if str(u_data.get('bank_name', '')) == b_id:
                                    deposit = u_data.get('bank_deposit', 0)
                                    if deposit > 0:
                                        refund = int(deposit * 0.5)
                                        await update_user_field(chat_id, int(user_doc.id), 'bank_deposit', 0)
                                        await update_user_balance(chat_id, int(user_doc.id), refund)
                                        await update_user_field(chat_id, int(user_doc.id), 'bank_name', None)
                                        try:
                                            await bot.send_message(chat_id, f"🏛 Банк <b>{b_data.get('name')}</b> обанкротился! ЦБ компенсировал 50% вашего вклада ({refund} сыр.) на наличный счет.")
                                        except: pass

                            await banks_ref.document(b_id).delete()
                            await update_user_field(chat_id, int(b_id), 'is_banker', False)
                            try:
                                await bot.send_message(chat_id, f"💥 <b>ДЕФОЛТ!</b> Банк <b>{b_data.get('name')}</b> признан банкротом и закрыт. Банкир отстранен.")
                            except: pass
                            continue

                        new_capital = current_cap + 50000000

                        # Налог на роскошь (сверхприбыль > 1 млрд)
                        if new_capital > 1000000000:
                            luxury_tax = int((new_capital - 1000000000) * 0.05) # 5% с суммы превышающей 1 млрд
                            new_capital -= luxury_tax

                        await banks_ref.document(b_id).update({'capital': new_capital})

                except Exception as e:
                    print(f"Ошибка ежедневных банковских операций в чате {chat_id}: {e}")

            await asyncio.sleep(60) # Чтобы не сработало дважды
            continue

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
