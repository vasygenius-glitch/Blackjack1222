import asyncio
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from config import CREATOR_ID
from escape import escape_html
from db import get_db
import time

router = Router()

log_buffer = []

async def get_log_chat_id():
    db = get_db()
    doc = await db.collection('bot_settings').document('logchat').get()
    if doc.exists:
        return doc.to_dict().get('chat_id')
    return None

@router.message(Command("setlogchat"))
async def cmd_setlogchat(message: types.Message):
    if CREATOR_ID and int(message.from_user.id) != int(CREATOR_ID):
        return

    chat_id = message.chat.id
    db = get_db()
    await db.collection('bot_settings').document('logchat').set({'chat_id': chat_id}, merge=True)
    await message.answer("✅ Этот чат успешно назначен глобальным Лог-Чатом.")

async def log_action(text: str):
    log_buffer.append(f"[{time.strftime('%H:%M:%S')}] {text}")

async def flush_logs(bot: Bot):
    while True:
        await asyncio.sleep(60) # раз в минуту
        if not log_buffer:
            continue

        log_chat_id = await get_log_chat_id()
        if not log_chat_id:
            log_buffer.clear()
            continue

        logs_to_send = "\n\n".join(log_buffer)
        log_buffer.clear()

        # Разбиваем на чанки по 4000 символов, если нужно
        chunks = [logs_to_send[i:i+4000] for i in range(0, len(logs_to_send), 4000)]
        for chunk in chunks:
            try:
                await bot.send_message(chat_id=log_chat_id, text=f"📜 <b>Логи за минуту:</b>\n\n{chunk}")
            except Exception as e:
                print(f"Failed to send logs: {e}")
